"""
How this works / why it is safe:
This module exposes endpoints for reviewing and resolving flagged anomalies.
Auditors have strictly read-only visibility into the flag queue.
Only administrators may record decisions. Decisions are committed to the append-only
review_decisions table with the admin's identity, timestamp, and mandatory written justification.
Neither AI nor flags can ever reverse, debit, or credit an account directly.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.engine import get_db
from app.db.models import ReviewDecision, ReviewFlag, User
from app.deps import require_role
from app.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/review", tags=["Review & Surveillance"])


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["approve", "dismiss", "escalate"]
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory reason for decision")


@router.get("/flags")
def list_flags(
    status: str = "open",
    current_user: User = Depends(require_role("admin", "auditor")),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List surveillance flags (Admin & Auditor read-only)."""
    flags = (
        db.query(ReviewFlag)
        .filter(ReviewFlag.status == status)
        .order_by(ReviewFlag.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": f.id,
            "rule_id": f.rule_id,
            "journal_id": str(f.journal_id) if f.journal_id else None,
            "account_id": str(f.account_id) if f.account_id else None,
            "severity": f.severity,
            "status": f.status,
            "evidence": f.evidence,
            "narrative": f.narrative,
            "created_at": f.created_at.isoformat(),
        }
        for f in flags
    ]


@router.post("/flags/{flag_id}/decision")
def record_decision(
    flag_id: int,
    req: DecisionRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record an immutable human decision on a flagged item (Admin only)."""
    flag = db.query(ReviewFlag).filter(ReviewFlag.id == flag_id).first()
    if not flag:
        raise NotFoundError("Review flag not found.")

    decision_record = ReviewDecision(
        flag_id=flag.id,
        decision=req.decision,
        reason=req.reason,
        decided_by=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(decision_record)

    flag.status = "reviewed" if req.decision == "approve" else "dismissed"
    db.commit()

    return {
        "status": "decision_recorded",
        "flag_id": flag.id,
        "decision": req.decision,
        "decided_by": str(current_user.id),
    }
