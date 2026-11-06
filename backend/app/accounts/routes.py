"""
How this works / why it is safe:
This module exposes account, statement, and money movement HTTP endpoints.
Every write route strictly mandates the Idempotency-Key header.
All money mutations delegate solely to post_movement() in the ledger service.
Access control is enforced on every request: holders can only read or touch
accounts they own in account_members (foreign accounts return uniform 404s).
Auditors are strictly restricted to read-only GET routes. Admins can freeze/unfreeze
and make adjustments against the designated SUSPENSE account.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session
from app.accounts.schemas import (
    AccountListResponse,
    AccountResponse,
    CreateAccountRequest,
)
from app.accounts.service import (
    create_customer_account,
    freeze_account,
    get_system_account,
    unfreeze_account,
)
from app.db.engine import get_db
from app.db.models import Account, AccountMember, Journal, User
from app.deps import get_current_user, get_request_id, require_role
from app.errors import (
    ForbiddenError,
    InvalidDestinationError,
    MissingIdempotencyKeyError,
    NotFoundError,
    ValidationError,
)
from app.ledger.queries import get_account_statement
from app.ledger.schemas import (
    AdjustmentRequest,
    DepositRequest,
    MovementResponse,
    StatementResponse,
    TransferRequest,
    WithdrawRequest,
)
from app.ledger.service import post_movement

router = APIRouter(tags=["Accounts & Money Movement"])


def require_idempotency_key(idempotency_key: Optional[str] = Header(None)) -> str:
    """Validate presence and format of required Idempotency-Key header."""
    if not idempotency_key:
        raise MissingIdempotencyKeyError()
    key = idempotency_key.strip()
    if not (16 <= len(key) <= 128):
        raise ValidationError("Idempotency-Key header length must be between 16 and 128 characters.")
    return key


@router.post("/accounts", response_model=AccountResponse)
def create_account(
    req: CreateAccountRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Create a new customer account (Admin only)."""
    acc = create_customer_account(db, req.name, req.owner_user_id, req.overdraft_limit)
    return AccountResponse(
        id=acc.id,
        number=acc.number,
        name=acc.name,
        kind=acc.kind,
        currency=acc.currency,
        balance=acc.balance,
        overdraft_limit=acc.overdraft_limit,
        status=acc.status,
        created_at=acc.created_at,
    )


@router.get("/accounts", response_model=AccountListResponse)
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountListResponse:
    """List accessible accounts (Holders see own; Admin/Auditor see all)."""
    if current_user.role in ("admin", "auditor"):
        accounts = db.query(Account).filter(Account.kind == "customer").order_by(Account.created_at.desc()).all()
    else:
        accounts = (
            db.query(Account)
            .join(AccountMember, AccountMember.account_id == Account.id)
            .filter(AccountMember.user_id == current_user.id)
            .order_by(Account.created_at.desc())
            .all()
        )

    res = [
        AccountResponse(
            id=acc.id,
            number=acc.number,
            name=acc.name,
            kind=acc.kind,
            currency=acc.currency,
            balance=acc.balance,
            overdraft_limit=acc.overdraft_limit,
            status=acc.status,
            created_at=acc.created_at,
        )
        for acc in accounts
    ]
    return AccountListResponse(accounts=res)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Fetch details for a specific account with strict ownership verification."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")

    if current_user.role == "holder":
        is_member = (
            db.query(AccountMember)
            .filter(AccountMember.account_id == acc.id, AccountMember.user_id == current_user.id)
            .first()
        )
        if not is_member:
            raise NotFoundError("Account not found.")

    return AccountResponse(
        id=acc.id,
        number=acc.number,
        name=acc.name,
        kind=acc.kind,
        currency=acc.currency,
        balance=acc.balance,
        overdraft_limit=acc.overdraft_limit,
        status=acc.status,
        created_at=acc.created_at,
    )


@router.get("/accounts/{account_id}/statement", response_model=StatementResponse)
def get_statement(
    account_id: UUID,
    after: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatementResponse:
    """Retrieve keyset-paginated statement of postings and refusals."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")

    if current_user.role == "holder":
        is_member = (
            db.query(AccountMember)
            .filter(AccountMember.account_id == acc.id, AccountMember.user_id == current_user.id)
            .first()
        )
        if not is_member:
            raise NotFoundError("Account not found.")

    return get_account_statement(db, account_id, after_seq=after, limit=limit)


@router.post("/accounts/{account_id}/deposit", response_model=MovementResponse)
def deposit(
    account_id: UUID,
    req: DepositRequest,
    response: Response,
    idempotency_key: str = Depends(require_idempotency_key),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(require_role("holder", "admin")),
    db: Session = Depends(get_db),
) -> MovementResponse:
    """Deposit external funds into an account."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")

    if current_user.role == "holder":
        is_member = (
            db.query(AccountMember)
            .filter(AccountMember.account_id == acc.id, AccountMember.user_id == current_user.id)
            .first()
        )
        if not is_member:
            raise NotFoundError("Account not found.")

    external_acc = get_system_account(db, "external")
    movement, is_replayed = post_movement(
        db=db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_id=request_id,
        kind="deposit",
        source_account_id=external_acc.id,
        destination_account_id=acc.id,
        amount=req.amount,
        raw_payload=req.model_dump(),
        memo=req.memo,
    )

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement


@router.post("/accounts/{account_id}/withdraw", response_model=MovementResponse)
def withdraw(
    account_id: UUID,
    req: WithdrawRequest,
    response: Response,
    idempotency_key: str = Depends(require_idempotency_key),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(require_role("holder")),
    db: Session = Depends(get_db),
) -> MovementResponse:
    """Withdraw funds from caller's account to external cash."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")

    is_member = (
        db.query(AccountMember)
        .filter(AccountMember.account_id == acc.id, AccountMember.user_id == current_user.id)
        .first()
    )
    if not is_member:
        raise NotFoundError("Account not found.")

    external_acc = get_system_account(db, "external")
    movement, is_replayed = post_movement(
        db=db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_id=request_id,
        kind="withdrawal",
        source_account_id=acc.id,
        destination_account_id=external_acc.id,
        amount=req.amount,
        raw_payload=req.model_dump(),
        memo=req.memo,
    )

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement


@router.post("/transfers", response_model=MovementResponse)
def transfer(
    req: TransferRequest,
    response: Response,
    idempotency_key: str = Depends(require_idempotency_key),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(require_role("holder")),
    db: Session = Depends(get_db),
) -> MovementResponse:
    """Transfer funds from caller's account to any active recipient account by number."""
    dest_acc = db.query(Account).filter(Account.number == req.to_account_number).first()
    if not dest_acc or dest_acc.status != "active":
        raise InvalidDestinationError()

    movement, is_replayed = post_movement(
        db=db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_id=request_id,
        kind="transfer",
        source_account_id=req.from_account_id,
        destination_account_id=dest_acc.id,
        amount=req.amount,
        raw_payload=req.model_dump(),
        memo=req.memo,
    )

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement


@router.post("/admin/accounts/{account_id}/freeze", response_model=AccountResponse)
def admin_freeze(
    account_id: UUID,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Freeze an account (Admin only)."""
    acc = freeze_account(db, account_id, current_user.id)
    return AccountResponse(
        id=acc.id,
        number=acc.number,
        name=acc.name,
        kind=acc.kind,
        currency=acc.currency,
        balance=acc.balance,
        overdraft_limit=acc.overdraft_limit,
        status=acc.status,
        created_at=acc.created_at,
    )


@router.post("/admin/accounts/{account_id}/unfreeze", response_model=AccountResponse)
def admin_unfreeze(
    account_id: UUID,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Unfreeze an account (Admin only)."""
    acc = unfreeze_account(db, account_id, current_user.id)
    return AccountResponse(
        id=acc.id,
        number=acc.number,
        name=acc.name,
        kind=acc.kind,
        currency=acc.currency,
        balance=acc.balance,
        overdraft_limit=acc.overdraft_limit,
        status=acc.status,
        created_at=acc.created_at,
    )


@router.post("/admin/adjustments", response_model=MovementResponse)
def admin_adjustment(
    req: AdjustmentRequest,
    response: Response,
    idempotency_key: str = Depends(require_idempotency_key),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> MovementResponse:
    """Post an audited balance adjustment against the SUSPENSE account (Admin only)."""
    acc = db.query(Account).filter(Account.id == req.account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")

    suspense_acc = get_system_account(db, "suspense")

    if req.amount > 0:
        src = suspense_acc.id
        dest = acc.id
        amt = req.amount
    else:
        src = acc.id
        dest = suspense_acc.id
        amt = abs(req.amount)

    movement, is_replayed = post_movement(
        db=db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_id=request_id,
        kind="adjustment",
        source_account_id=src,
        destination_account_id=dest,
        amount=amt,
        raw_payload=req.model_dump(),
        memo=req.reason,
    )

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement
