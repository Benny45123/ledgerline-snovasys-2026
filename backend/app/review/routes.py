"""
How this works / why it is safe:
This module exposes endpoints for reviewing and resolving flagged anomalies.
Auditors have strictly read-only visibility into the flag queue.
Only administrators may record decisions. Decisions are committed to the append-only
review_decisions table with the admin's identity, timestamp, and mandatory written justification.
Neither AI nor flags can ever reverse, debit, or credit an account directly.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.accounts.service import create_customer_account
from app.db.engine import get_db
from app.db.models import Account, AccountMember, AccountRequest, ReviewDecision, ReviewFlag, SecurityEvent, User
from app.deps import get_current_user, require_role
from app.errors import NotFoundError
from app.review.analytics import compute_fraud_risk_score, forecast_cash_flow, get_account_metrics
from app.review.copilot import query_copilot
from app.review.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/review", tags=["Review & Surveillance"])


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["approve", "approved", "dismiss", "dismissed", "escalate"]
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory reason for decision")


@router.get("/flags")
def list_flags(
    status: str = "open",
    current_user: User = Depends(require_role("admin", "auditor")),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List surveillance flags with dynamically derived status (Admin & Auditor read-only)."""
    # Subquery to identify the latest decision per flag
    latest_decisions = db.query(
        ReviewDecision.flag_id,
        ReviewDecision.decision,
        func.row_number()
        .over(partition_by=ReviewDecision.flag_id, order_by=ReviewDecision.created_at.desc())
        .label("rn"),
    ).subquery()

    rows = (
        db.query(
            ReviewFlag,
            latest_decisions.c.decision,
        )
        .outerjoin(
            latest_decisions,
            (ReviewFlag.id == latest_decisions.c.flag_id) & (latest_decisions.c.rn == 1),
        )
        .order_by(ReviewFlag.created_at.desc())
        .limit(200)
        .all()
    )

    res: list[dict[str, Any]] = []
    target_status = status.lower()

    for f, dec in rows:
        if dec == "approve":
            eff_status = "reviewed"
        elif dec == "dismiss":
            eff_status = "dismissed"
        elif dec == "escalate":
            eff_status = "escalated"
        else:
            eff_status = "open"

        # Filter by effective status unless 'all' is requested
        if target_status not in ("all", ""):
            match_status = "open" if target_status in ("open", "pending") else target_status
            if match_status == "approved":
                match_status = "reviewed"
            if eff_status != match_status:
                continue

        res.append(
            {
                "id": f.id,
                "rule_id": f.rule_id,
                "journal_id": str(f.journal_id) if f.journal_id else None,
                "account_id": str(f.account_id) if f.account_id else None,
                "severity": f.severity,
                "status": eff_status,
                "evidence": f.evidence,
                "narrative": f.narrative,
                "created_at": f.created_at.isoformat(),
            }
        )

    return res[:100]


@router.post("/flags/{flag_id}/decision")
def record_decision(
    flag_id: int,
    req: DecisionRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record an immutable human decision on a flagged item (Admin only)."""
    flag = db.query(ReviewFlag).filter(ReviewFlag.id == flag_id).first()
    if not flag:
        raise NotFoundError("Review flag not found.")

    canonical_decision = (
        "approve"
        if req.decision in ("approve", "approved")
        else ("dismiss" if req.decision in ("dismiss", "dismissed") else "escalate")
    )

    # If this review flag corresponds to a new account request, process the onboarding decision
    if flag.rule_id == "account_request" and flag.evidence:
        req_id_str = flag.evidence.get("request_id")
        if req_id_str:
            try:
                parsed_req_id = UUID(req_id_str)
                acc_req = db.query(AccountRequest).filter(AccountRequest.id == parsed_req_id).first()
                if acc_req and acc_req.status == "pending":
                    if canonical_decision == "approve":
                        new_acc = create_customer_account(
                            db=db,
                            name=acc_req.account_name,
                            owner_user_id=acc_req.user_id,
                            overdraft_limit=0,
                        )
                        acc_req.status = "approved"
                        acc_req.account_id = new_acc.id
                        acc_req.reviewed_by = current_user.id
                        acc_req.reviewed_at = func.now()
                        db.add(
                            SecurityEvent(
                                actor_user_id=current_user.id,
                                event="account_request_approved",
                                detail={
                                    "request_id": str(acc_req.id),
                                    "account_id": str(new_acc.id),
                                    "account_number": new_acc.number,
                                    "reason": req.reason,
                                },
                            )
                        )
                    elif canonical_decision == "dismiss":
                        acc_req.status = "rejected"
                        acc_req.rejection_reason = req.reason
                        acc_req.reviewed_by = current_user.id
                        acc_req.reviewed_at = func.now()
                        db.add(
                            SecurityEvent(
                                actor_user_id=current_user.id,
                                event="account_request_rejected",
                                detail={
                                    "request_id": str(acc_req.id),
                                    "reason": req.reason,
                                },
                            )
                        )
            except Exception:
                pass

    decision_record = ReviewDecision(
        flag_id=flag.id,
        decision=canonical_decision,
        reason=req.reason,
        decided_by=current_user.id,
        created_at=datetime.now(UTC),
    )
    db.add(decision_record)
    # ReviewFlag is append-only; we do NOT mutate flag.status
    db.commit()

    return {
        "status": "decision_recorded",
        "flag_id": flag.id,
        "decision": canonical_decision,
        "decided_by": str(current_user.id),
    }


@router.post("/chat", response_model=ChatResponse)
def copilot_chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Conversational AI Financial Intelligence & Copilot.
    Authorized across holder, admin, and auditor roles with strict IDOR protections.
    Under Invariant I8, this endpoint is strictly read-only and never mutates ledger state.
    """
    return query_copilot(
        db=db,
        user=current_user,
        message=req.message,
        context_account_id=req.account_id,
        history=req.history,
    )


@router.get("/accounts/{account_id}/insights")
def get_account_insights(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Retrieve read-only financial intelligence metrics, fraud risk score,
    and cash flow forecast for an account. Enforces IDOR boundary on account membership.
    """
    if current_user.role == "holder":
        membership = (
            db.query(AccountMember)
            .filter(AccountMember.account_id == account_id, AccountMember.user_id == current_user.id)
            .first()
        )
        if not membership:
            raise NotFoundError("Account not found.")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise NotFoundError("Account not found.")

    metrics = get_account_metrics(db, account_id)
    score, level, reasons = compute_fraud_risk_score(db, account_id)
    forecast = forecast_cash_flow(db, account_id)

    return {
        "account_id": str(account_id),
        "metrics": metrics,
        "risk": {
            "score": score,
            "level": level,
            "reasons": reasons,
        },
        "forecast": forecast,
    }
