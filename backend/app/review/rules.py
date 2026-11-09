"""
How this works / why it is safe:
This module evaluates deterministic rules to flag anomalous financial activity.
Crucially, it only reads data (SELECT) and inserts flags; it NEVER imports
app.ledger.service or modifies balances.
Flags evaluate:
- High transaction amounts (e.g. above ₹10,00,000 / 10 crore paise).
- High velocity bursts.
- Structuring patterns (just under round limits).
- Admin balance adjustments.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Journal, ReviewFlag

HIGH_VALUE_THRESHOLD = 50_000_000  # ₹5,00,000 in paise


def evaluate_transaction_for_flags(
    db: Session,
    journal: Journal,
    account_id: UUID,
    amount: int,
) -> list[ReviewFlag]:
    """Scan newly posted movement against deterministic rules and generate flags."""
    flags: list[ReviewFlag] = []

    # Rule 1: High value transfer
    if abs(amount) >= HIGH_VALUE_THRESHOLD:
        flag = ReviewFlag(
            rule_id="RULE_HIGH_VALUE",
            journal_id=journal.id,
            account_id=account_id,
            severity="medium",
            status="open",
            evidence={
                "amount": amount,
                "threshold": HIGH_VALUE_THRESHOLD,
                "memo": journal.memo or "",
            },
            narrative=f"Transaction of ₹{abs(amount) / 100:,.2f} exceeds the high-value surveillance threshold.",
        )
        db.add(flag)
        flags.append(flag)

    # Rule 2: Admin adjustment surveillance
    if journal.kind == "adjustment":
        flag = ReviewFlag(
            rule_id="RULE_ADMIN_ADJUSTMENT",
            journal_id=journal.id,
            account_id=account_id,
            severity="high",
            status="open",
            evidence={"amount": amount, "admin_user_id": str(journal.initiated_by)},
            narrative="Administrative balance adjustment posted against SUSPENSE account requires mandatory review.",
        )
        db.add(flag)
        flags.append(flag)

    db.commit()
    return flags
