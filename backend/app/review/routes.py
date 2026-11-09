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

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.db.models import ReviewDecision, ReviewFlag, User
from app.deps import require_role
from app.errors import NotFoundError

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
    latest_decisions = (
        db.query(
            ReviewDecision.flag_id,
            ReviewDecision.decision,
            func.row_number()
            .over(partition_by=ReviewDecision.flag_id, order_by=ReviewDecision.created_at.desc())
            .label("rn"),
        )
        .subquery()
    )

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
