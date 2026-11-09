"""
How this works / why it is safe:
This module performs strictly read-only analytical queries against confirmed
ledger entries, account balances, and refusal records.
It powers the AI Financial Intelligence and Copilot layers:
- Computing financial metrics, cash flow moving averages, and spending velocity.
- Multi-factor fraud risk scoring (0-100) based on transfer velocity, amount anomalies, and refusal clustering.
- Constrained natural-language search across transaction histories.
Crucially, this module never mutates balances, never writes ledger rows, and never
imports app.ledger.service, upholding architectural layering and Invariant I8.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Account, Journal, LedgerEntry, RefusedAttempt, ReviewFlag


def format_paise(paise: int | float | Any) -> str:
    """Format integer paise to Indian Rupee representation (e.g. ₹1,234.50)."""
    p_int = int(paise or 0)
    abs_val = abs(p_int)
    rupees = abs_val // 100
    rem = abs_val % 100
    formatted_rupees = f"{rupees:,}"
    sign = "-" if p_int < 0 else ""
    return f"{sign}₹{formatted_rupees}.{rem:02d}"


def get_account_metrics(db: Session, account_id: UUID) -> dict[str, Any]:
    """Calculate core financial analytics for an authorized customer account."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return {}

    entries = (
        db.query(LedgerEntry, Journal)
        .join(Journal, LedgerEntry.journal_id == Journal.id)
        .filter(LedgerEntry.account_id == account_id)
        .order_by(LedgerEntry.account_seq.desc())
        .limit(100)
        .all()
    )

    total_credits = 0
    total_debits = 0
    largest_credit = 0
    largest_debit = 0
    now = datetime.now(UTC)
    last_7d_cutoff = now - timedelta(days=7)
    last_7d_credits = 0
    last_7d_debits = 0
    recent_transactions: list[dict[str, Any]] = []

    for entry, journal in entries:
        amt = entry.amount
        if amt > 0:
            total_credits += amt
            if amt > largest_credit:
                largest_credit = amt
            if entry.created_at >= last_7d_cutoff:
                last_7d_credits += amt
        elif amt < 0:
            pos_amt = abs(amt)
            total_debits += pos_amt
            if pos_amt > largest_debit:
                largest_debit = pos_amt
            if entry.created_at >= last_7d_cutoff:
                last_7d_debits += pos_amt

        if len(recent_transactions) < 10:
            recent_transactions.append({
                "seq": entry.account_seq,
                "kind": journal.kind,
                "amount": entry.amount,
                "amount_formatted": format_paise(entry.amount),
                "balance_after": entry.balance_after,
                "balance_after_formatted": format_paise(entry.balance_after),
                "created_at": entry.created_at.isoformat(),
                "memo": journal.memo or "",
            })

    # Count refused attempts
    refusal_count = (
        db.query(func.count(RefusedAttempt.id))
        .filter(RefusedAttempt.account_id == account_id)
        .scalar()
        or 0
    )

    tx_count = len(entries)
    avg_tx_size = (total_credits + total_debits) // max(1, tx_count)

    return {
        "account_id": str(account.id),
        "number": account.number,
        "name": account.name,
        "currency": account.currency,
        "current_balance": account.balance,
        "current_balance_formatted": format_paise(account.balance),
        "overdraft_limit": account.overdraft_limit,
        "overdraft_limit_formatted": format_paise(account.overdraft_limit),
        "status": account.status,
        "total_credits": total_credits,
        "total_credits_formatted": format_paise(total_credits),
        "total_debits": total_debits,
        "total_debits_formatted": format_paise(total_debits),
        "net_cash_flow": total_credits - total_debits,
        "net_cash_flow_formatted": format_paise(total_credits - total_debits),
        "last_7d_credits": last_7d_credits,
        "last_7d_credits_formatted": format_paise(last_7d_credits),
        "last_7d_debits": last_7d_debits,
        "last_7d_debits_formatted": format_paise(last_7d_debits),
        "largest_credit_formatted": format_paise(largest_credit),
        "largest_debit_formatted": format_paise(largest_debit),
        "average_transaction_formatted": format_paise(avg_tx_size),
        "transaction_count": tx_count,
        "refusal_count": refusal_count,
        "recent_transactions": recent_transactions,
    }


def compute_fraud_risk_score(db: Session, account_id: UUID) -> tuple[int, str, list[str]]:
    """
    Evaluate multi-factor fraud and anomalous behavior score (0 to 100).

    Dynamically evaluates risk across:
    1. Account Governance: Administrative freeze or closure.
    2. Refusal Patterns: Recent (past 48h) and lifetime refusal velocity.
    3. Active Compliance Surveillance: Open review flags pending auditor review.
    4. Balance Drain & Overdraft: High fund depletion (>75% or >95% of inflows) or active overdraft.
    5. Velocity & Rapid Succession: Spikes in ledger activity and rapid back-to-back postings (<180s).
    6. Outlier Outflows: Single transfer >= 70% of total inflows or 3x historical debit average.
    7. Baseline Calibration: Differentiates dormant/pristine vs active vs high-risk accounts.
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return 0, "LOW", ["Account record not found."]

    reasons: list[str] = []
    now = datetime.now(UTC)

    # 1. Fetch entries and compute volume
    entries = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.account_id == account_id)
        .order_by(LedgerEntry.account_seq.desc())
        .limit(50)
        .all()
    )
    tx_count = len(entries)

    # 2. Refusal history (recent 48h and lifetime)
    total_refusals = (
        db.query(func.count(RefusedAttempt.id))
        .filter(RefusedAttempt.account_id == account_id)
        .scalar()
        or 0
    )
    recent_refusals = (
        db.query(func.count(RefusedAttempt.id))
        .filter(
            RefusedAttempt.account_id == account_id,
            RefusedAttempt.created_at >= now - timedelta(hours=48),
        )
        .scalar()
        or 0
    )

    # 3. Dynamic Baseline Score based on transaction maturity
    if tx_count == 0 and total_refusals == 0:
        score = 2
        baseline_note = "Pristine account state with zero transaction history."
    elif tx_count <= 2:
        score = 6
        baseline_note = "Account behavior aligns with normal operational baseline."
    else:
        score = min(12, 6 + min(tx_count, 6))
        baseline_note = "Account behavior aligns with normal operational baseline."

    # Factor 1: Account Governance / Status
    if account.status == "frozen":
        score += 45
        reasons.append("Account is administratively FROZEN due to risk or compliance hold.")
    elif account.status == "closed":
        score += 25
        reasons.append("Account is CLOSED; subsequent activity is restricted.")

    # Factor 2: Refusal History
    if recent_refusals >= 5:
        score += 40
        reasons.append(f"High refusal frequency: {recent_refusals} transaction attempts refused in past 48 hours.")
    elif recent_refusals >= 2:
        score += 25
        reasons.append(f"Repeated refusals: {recent_refusals} transaction attempts refused in past 48 hours.")
    elif recent_refusals == 1:
        score += 12
        reasons.append("Recent transaction refusal recorded within past 48 hours.")
    elif total_refusals >= 3:
        score += 15
        reasons.append(f"Historical refusal record: {total_refusals} lifetime refused attempts on file.")
    elif total_refusals > 0:
        score += 8
        reasons.append(f"Historical refusal record: {total_refusals} previous refused attempt on file.")

    # Factor 3: Open surveillance review flags
    open_flags = (
        db.query(ReviewFlag)
        .filter(ReviewFlag.account_id == account_id, ReviewFlag.status == "open")
        .all()
    )
    if open_flags:
        flag_points = min(35, len(open_flags) * 20)
        score += flag_points
        reasons.append(f"Active surveillance flags: {len(open_flags)} open risk flag(s) pending compliance review.")

    # Factor 4: Balance Drain & Overdraft
    total_credits = sum(e.amount for e in entries if e.amount > 0)
    total_debits = sum(abs(e.amount) for e in entries if e.amount < 0)

    if account.balance < 0:
        score += 25
        reasons.append(f"Negative balance: Account currently operating in overdraft ({format_paise(account.balance)}).")
    elif total_credits > 0:
        drain_ratio = total_debits / total_credits
        if drain_ratio >= 0.95 and total_credits >= 100_00:
            score += 20
            reasons.append(f"High fund depletion: {int(drain_ratio * 100)}% of cumulative inflows have been withdrawn ({format_paise(total_debits)} of {format_paise(total_credits)}).")
        elif drain_ratio >= 0.75 and total_credits >= 100_00:
            score += 10
            reasons.append(f"Elevated fund utilization: {int(drain_ratio * 100)}% of cumulative inflows have been transferred out.")

    # Factor 5: Velocity & Rapid Succession in last 2 hours
    cutoff_2h = now - timedelta(hours=2)
    recent_entries_2h = [e for e in entries if e.created_at >= cutoff_2h]

    if len(recent_entries_2h) >= 6:
        score += 30
        reasons.append(f"Abnormal burst velocity: {len(recent_entries_2h)} money movements executed within 2 hours.")
    elif len(recent_entries_2h) >= 3:
        score += 15
        reasons.append(f"Elevated velocity: {len(recent_entries_2h)} transactions posted in past 2 hours.")

    if len(recent_entries_2h) >= 2:
        for i in range(len(recent_entries_2h) - 1):
            t1 = recent_entries_2h[i].created_at
            t2 = recent_entries_2h[i + 1].created_at
            delta_secs = abs((t1 - t2).total_seconds())
            if delta_secs <= 180 and (recent_entries_2h[i].amount < 0 or recent_entries_2h[i + 1].amount < 0):
                score += 12
                reasons.append(f"Rapid succession transfers: consecutive postings occurred {int(delta_secs)}s apart.")
                break

    # Factor 6: Outlier Debits
    debit_entries = [e for e in entries if e.amount < 0]
    if debit_entries:
        largest_debit = max(abs(e.amount) for e in debit_entries)
        if total_credits > 0 and largest_debit >= int(total_credits * 0.70) and total_credits >= 100_00:
            pct = int((largest_debit / total_credits) * 100)
            score += 15
            reasons.append(f"Substantial single outflow: Single transfer of {format_paise(largest_debit)} accounts for {pct}% of total deposits.")
        elif len(debit_entries) >= 3:
            latest_debit = abs(debit_entries[0].amount)
            prior_debits = [abs(e.amount) for e in debit_entries[1:]]
            avg_prior = sum(prior_debits) // len(prior_debits)
            if avg_prior > 0 and latest_debit >= avg_prior * 3:
                score += 18
                reasons.append(f"Outlier outflow: Latest debit ({format_paise(latest_debit)}) exceeds 3x typical average debit ({format_paise(avg_prior)}).")

    # Score clamping and level categorization
    score = max(0, min(100, score))
    if score >= 75:
        level = "CRITICAL" if score >= 90 else "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    if not reasons:
        reasons.append(baseline_note)

    return score, level, reasons


def forecast_cash_flow(db: Session, account_id: UUID, days: int = 30) -> dict[str, Any]:
    """Forecast 30-day cash flow and runway using historical velocity."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return {}

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)

    entries = (
        db.query(LedgerEntry.amount, LedgerEntry.created_at)
        .filter(LedgerEntry.account_id == account_id, LedgerEntry.created_at >= cutoff)
        .all()
    )

    total_in = sum(e[0] for e in entries if e[0] > 0)
    total_out = sum(abs(e[0]) for e in entries if e[0] < 0)
    net_30d = total_in - total_out
    daily_net_velocity = net_30d // max(1, 30)

    curr_bal = account.balance
    projected_30d = curr_bal + net_30d

    # Outlier threshold matching app.html mo = max(abs(e.a))
    all_amounts = [abs(e[0]) for e in entries]
    mo = max(all_amounts) if all_amounts else abs(daily_net_velocity * 10)
    lo = projected_30d - (mo * 2)
    hi = projected_30d + (mo // 2) if mo > 0 else projected_30d + 500000

    if hi <= lo:
        hi = projected_30d + 1000000
        lo = projected_30d - 1000000

    range_span = max(1, hi - lo)
    range_pct = int(max(0.0, min(100.0, ((projected_30d - lo) / range_span) * 100.0)))

    runway_days = None
    if daily_net_velocity < 0:
        available_liquidity = curr_bal + account.overdraft_limit
        runway_days = max(0, available_liquidity) // abs(daily_net_velocity)

    vel_sign = "+" if daily_net_velocity >= 0 else "-"
    vel_status = "surplus" if daily_net_velocity >= 0 else "net burn"
    vel_label = f"{vel_sign}{format_paise(abs(daily_net_velocity))}/day ({vel_status})"

    return {
        "current_balance_paise": curr_bal,
        "current_balance_formatted": format_paise(curr_bal),
        "daily_net_velocity_paise": daily_net_velocity,
        "daily_net_velocity_formatted": format_paise(daily_net_velocity),
        "projected_balance_30d_paise": projected_30d,
        "projected_balance_30d_formatted": format_paise(projected_30d),
        "pessimistic_scenario_paise": lo,
        "pessimistic_scenario_formatted": format_paise(lo),
        "optimistic_scenario_paise": hi,
        "optimistic_scenario_formatted": format_paise(hi),
        "range_percentage": range_pct,
        "burn_status": "surplus" if daily_net_velocity >= 0 else "deficit",
        "runway_days": runway_days,
        "velocity_label": vel_label,
    }


def search_ledger_transactions(db: Session, account_id: UUID, query_text: str) -> list[dict[str, Any]]:
    """Parse natural language query parameters and search account entries."""
    q_lower = query_text.lower()

    # Extract potential numerical amount threshold (e.g., 'above 5000', '> 1000', '10000')
    amt_matches = re.findall(r"(?:above|greater than|>|over|₹|\b)(\d+(?:,\d+)*(?:\.\d+)?)\b", q_lower)
    amt_threshold = None
    if amt_matches:
        try:
            raw_str = amt_matches[0].replace(",", "")
            amt_threshold = int(float(raw_str) * 100)  # convert to paise
        except ValueError:
            pass

    # Direction filter
    is_credit = any(w in q_lower for w in ("credit", "received", "inflow", "deposit"))
    is_debit = any(w in q_lower for w in ("debit", "spent", "outflow", "withdrawal", "sent"))
    is_largest = any(w in q_lower for w in ("largest", "highest", "biggest", "max", "top"))
    is_refusal = any(w in q_lower for w in ("failed", "refused", "rejected", "blocked"))

    if is_refusal:
        refusals = (
            db.query(RefusedAttempt)
            .filter(RefusedAttempt.account_id == account_id)
            .order_by(RefusedAttempt.account_seq.desc())
            .limit(10)
            .all()
        )
        return [
            {
                "type": "refusal",
                "is_refusal": True,
                "seq": r.account_seq,
                "kind": "Withdrawal",
                "amount": r.amount,
                "amount_formatted": format_paise(r.amount),
                "reason": r.reason_code,
                "balance_after": None,
                "balance_after_formatted": "",
                "memo": "",
                "created_at": r.created_at.isoformat(),
            }
            for r in refusals
        ]

    query = (
        db.query(LedgerEntry, Journal)
        .join(Journal, LedgerEntry.journal_id == Journal.id)
        .filter(LedgerEntry.account_id == account_id)
    )

    if is_credit and not is_debit:
        query = query.filter(LedgerEntry.amount > 0)
    elif is_debit and not is_credit:
        query = query.filter(LedgerEntry.amount < 0)

    if amt_threshold:
        query = query.filter(func.abs(LedgerEntry.amount) >= amt_threshold)

    if is_largest:
        query = query.order_by(func.abs(LedgerEntry.amount).desc())
    else:
        query = query.order_by(LedgerEntry.account_seq.desc())

    matches = query.limit(10).all()

    return [
        {
            "type": "posting",
            "is_refusal": False,
            "seq": e.account_seq,
            "kind": j.kind.capitalize(),
            "amount": e.amount,
            "amount_formatted": format_paise(e.amount),
            "balance_after": e.balance_after,
            "balance_after_formatted": format_paise(e.balance_after),
            "created_at": e.created_at.isoformat(),
            "memo": j.memo or "",
        }
        for e, j in matches
    ]


def get_global_audit_reconciliation(db: Session) -> dict[str, Any]:
    """Calculate system-wide double-entry reconciliation and conservation status."""
    total_balance = db.query(func.sum(Account.balance)).scalar() or 0
    total_accounts = db.query(func.count(Account.id)).scalar() or 0
    total_journals = db.query(func.count(Journal.id)).scalar() or 0
    total_entries = db.query(func.count(LedgerEntry.id)).scalar() or 0
    total_refusals = db.query(func.count(RefusedAttempt.id)).scalar() or 0
    open_flags = db.query(func.count(ReviewFlag.id)).filter(ReviewFlag.status == "open").scalar() or 0

    ext_acc = db.query(Account).filter(Account.kind == "external").first()
    susp_acc = db.query(Account).filter(Account.kind == "suspense").first()

    customer_balance_sum = (
        db.query(func.sum(Account.balance)).filter(Account.kind == "customer").scalar() or 0
    )

    is_balanced = total_balance == 0
    ext_balance = ext_acc.balance if ext_acc else 0
    susp_balance = susp_acc.balance if susp_acc else 0

    return {
        "is_balanced": is_balanced,
        "conservation_invariant": "HELD" if is_balanced else "VIOLATED",
        "global_balance_sum": total_balance,
        "global_balance_formatted": format_paise(total_balance),
        "total_customer_funds_formatted": format_paise(customer_balance_sum),
        "external_balance_formatted": format_paise(ext_balance),
        "suspense_balance_formatted": format_paise(susp_balance),
        "total_accounts": total_accounts,
        "total_journals": total_journals,
        "total_ledger_entries": total_entries,
        "total_refused_attempts": total_refusals,
        "open_surveillance_flags": open_flags,
    }
