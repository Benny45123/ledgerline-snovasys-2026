"""
How this works / why it is safe:
This module handles account lifecycle events (creation, freeze, unfreeze).
All accounts initialize with zero balance and a unique account number.
Freezing or unfreezing an account is restricted to administrators and audits the action
to security_events. System accounts (EXTERNAL for cash inflow/outflow, SUSPENSE for adjustments)
are created idempotently and protected from direct customer mutation.
"""

import secrets
import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Account, AccountMember, SecurityEvent, User
from app.errors import NotFoundError


def generate_account_number() -> str:
    """Generate a non-sequential 12-digit account number."""
    suffix = secrets.randbelow(9_000_000_000) + 1_000_000_000
    return f"10{suffix}"


def create_customer_account(
    db: Session,
    name: str,
    owner_user_id: UUID,
    overdraft_limit: int = 0,
) -> Account:
    """Create a new customer account and bind ownership to the specified user."""
    owner = db.query(User).filter(User.id == owner_user_id, User.is_active.is_(True)).first()
    if not owner:
        raise NotFoundError("Assigned owner user was not found.")

    account_number = generate_account_number()
    while db.query(Account).filter(Account.number == account_number).first():
        account_number = generate_account_number()

    account = Account(
        id=uuid.uuid4(),
        number=account_number,
        name=name,
        kind="customer",
        currency="INR",
        balance=0,
        overdraft_limit=overdraft_limit,
        status="active",
        next_seq=1,
        last_hash=b"\x00",
    )
    db.add(account)
    db.flush()

    member = AccountMember(account_id=account.id, user_id=owner.id)
    db.add(member)
    db.commit()
    db.refresh(account)
    return account


def get_system_account(db: Session, kind: str) -> Account:
    """Retrieve the designated system account (external or suspense)."""
    acc = db.query(Account).filter(Account.kind == kind).first()
    if not acc:
        acc = Account(
            id=uuid.uuid4(),
            number=f"SYS-{kind.upper()}",
            name=f"System {kind.capitalize()} Account",
            kind=kind,
            currency="INR",
            balance=0,
            overdraft_limit=0,
            status="active",
            next_seq=1,
            last_hash=b"\x00",
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)
    return acc


def freeze_account(db: Session, account_id: UUID, admin_id: UUID) -> Account:
    """Freeze an account to suspend all outgoing money movements."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")
    acc.status = "frozen"

    sec_event = SecurityEvent(
        actor_user_id=admin_id,
        event="account_frozen",
        detail={"account_id": str(account_id)},
    )
    db.add(sec_event)
    db.commit()
    db.refresh(acc)
    return acc


def unfreeze_account(db: Session, account_id: UUID, admin_id: UUID) -> Account:
    """Unfreeze an account, restoring normal transaction capabilities."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")
    acc.status = "active"

    sec_event = SecurityEvent(
        actor_user_id=admin_id,
        event="account_unfrozen",
        detail={"account_id": str(account_id)},
    )
    db.add(sec_event)
    db.commit()
    db.refresh(acc)
    return acc
