"""
How this works / why it is safe:
This module exposes auditor and administrator inspection endpoints.
It provides read-only transparency into ledger verification (/audit/verify),
recorded duplicate requests (/audit/replays), and system authentication/IDOR events (/audit/security-events).
Only users with 'admin' or 'auditor' roles can access these routes.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit.verify import AuditVerifyReport, verify_ledger_integrity
from app.db.engine import get_db
from app.db.models import IdempotencyReplay, SecurityEvent, User
from app.deps import require_role

router = APIRouter(prefix="/audit", tags=["Audit & Verification"])


@router.get("/verify", response_model=AuditVerifyReport)
def run_verify(
    current_user: User = Depends(require_role("admin", "auditor")),
    db: Session = Depends(get_db),
) -> AuditVerifyReport:
    """Run full cryptographic hash chain and accounting equation verification."""
    return verify_ledger_integrity(db)


@router.get("/replays")
def list_replays(
    limit: int = 50,
    current_user: User = Depends(require_role("admin", "auditor")),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve recorded idempotent replay logs (proof of deduplication)."""
    replays = (
        db.query(IdempotencyReplay)
        .order_by(IdempotencyReplay.created_at.desc())
        .limit(min(max(1, limit), 200))
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": str(r.user_id),
            "key": r.key,
            "same_payload": r.same_payload,
            "request_id": r.request_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in replays
    ]


@router.get("/security-events")
def list_security_events(
    limit: int = 50,
    current_user: User = Depends(require_role("admin", "auditor")),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve logged security events (IDOR, failed logins, admin freezes)."""
    events = (
        db.query(SecurityEvent)
        .order_by(SecurityEvent.created_at.desc())
        .limit(min(max(1, limit), 200))
        .all()
    )
    return [
        {
            "id": e.id,
            "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
            "event": e.event,
            "detail": e.detail,
            "request_id": e.request_id,
            "ip": e.ip,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
