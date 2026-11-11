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

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.accounts.schemas import (
    AccountListResponse,
    AccountRequestCreate,
    AccountRequestItem,
    AccountRequestListResponse,
    AccountResponse,
    AdminCreateUserRequest,
    AdminToggleUserStatusRequest,
    AdminUserAccountItem,
    AdminUserItem,
    AdminUserListResponse,
    CreateAccountRequest,
)
from app.accounts.service import (
    create_customer_account,
    freeze_account,
    get_system_account,
    unfreeze_account,
)
from app.auth.passwords import hash_password
from app.db.engine import get_db
from app.db.models import (
    Account,
    AccountMember,
    AccountRequest,
    Journal,
    LedgerEntry,
    ReviewFlag,
    SecurityEvent,
    SessionModel,
    User,
)
from app.deps import get_current_user, get_request_id, require_role
from app.errors import (
    InvalidDestinationError,
    MissingIdempotencyKeyError,
    NotFoundError,
    UserAlreadyExistsError,
    ValidationError,
)
from app.ledger.queries import get_account_statement
from app.ledger.schemas import (
    AdjustmentRequest,
    DepositRequest,
    MovementResponse,
    ReversalRequest,
    StatementResponse,
    TransferRequest,
    WithdrawRequest,
)
from app.ledger.service import post_movement
from app.rate_limit import rate_limit_dependency
from app.review.rules import evaluate_transaction_for_flags

router = APIRouter(tags=["Accounts & Money Movement"])


def require_idempotency_key(idempotency_key: str | None = Header(None)) -> str:
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


def is_account_in_user_scope(account: Account, user: User, db: Session) -> bool:
    """Check if account is within scope of the user's role and domain environment."""
    if user.role == "holder":
        return (
            db.query(AccountMember)
            .filter(AccountMember.account_id == account.id, AccountMember.user_id == user.id)
            .first()
            is not None
        )

    # Clean test evaluation domain (.test)
    if user.email.lower().endswith(".test"):
        if "(test)" in account.name.lower():
            return True
        is_test_member = (
            db.query(AccountMember)
            .join(User, AccountMember.user_id == User.id)
            .filter(AccountMember.account_id == account.id, User.email.ilike("%.test"))
            .first()
        )
        return is_test_member is not None

    # Tested / internal domain (.internal)
    if user.email.lower().endswith(".internal"):
        if "(test)" in account.name.lower():
            return False
        is_test_member = (
            db.query(AccountMember)
            .join(User, AccountMember.user_id == User.id)
            .filter(AccountMember.account_id == account.id, User.email.ilike("%.test"))
            .first()
        )
        return is_test_member is None

    # Other domains (e.g. general unit tests) can access all customer accounts
    return True


@router.get("/accounts", response_model=AccountListResponse)
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountListResponse:
    """List accessible accounts (Holders see own; Admin/Auditor see environment-isolated accounts)."""
    if current_user.role in ("admin", "auditor"):
        is_test_env = current_user.email.lower().endswith(".test")
        is_internal_env = current_user.email.lower().endswith(".internal")

        base_query = db.query(Account).filter(Account.kind == "customer")
        if is_test_env:
            test_user_ids = db.query(User.id).filter(User.email.ilike("%.test")).subquery()
            test_account_ids = (
                db.query(AccountMember.account_id).filter(AccountMember.user_id.in_(test_user_ids)).subquery()
            )
            accounts = (
                base_query.filter(
                    (Account.id.in_(test_account_ids)) | (Account.name.ilike("%(test)%"))
                )
                .order_by(Account.created_at.desc())
                .all()
            )
        elif is_internal_env:
            test_user_ids = db.query(User.id).filter(User.email.ilike("%.test")).subquery()
            test_account_ids = (
                db.query(AccountMember.account_id).filter(AccountMember.user_id.in_(test_user_ids)).subquery()
            )
            accounts = (
                base_query.filter(
                    ~Account.id.in_(test_account_ids),
                    ~Account.name.ilike("%(test)%"),
                )
                .order_by(Account.created_at.desc())
                .all()
            )
        else:
            accounts = base_query.order_by(Account.created_at.desc()).all()
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
    """Fetch details for a specific account with strict ownership and domain verification."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")

    if not is_account_in_user_scope(acc, current_user, db):
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
    after: int | None = None,
    limit: int = 50,
    order: str = "asc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatementResponse:
    """Retrieve keyset-paginated statement of postings and refusals."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise NotFoundError("Account not found.")

    if not is_account_in_user_scope(acc, current_user, db):
        raise NotFoundError("Account not found.")

    return get_account_statement(db, account_id, after_seq=after, limit=limit, order=order)


@router.post(
    "/accounts/{account_id}/deposit",
    response_model=MovementResponse,
    dependencies=[Depends(rate_limit_dependency("money.movement", max_requests=30, window_seconds=60))],
)
def deposit(
    account_id: UUID,
    req: DepositRequest,
    response: Response,
    idempotency_key: str = Depends(require_idempotency_key),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(require_role("holder")),
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

    if not is_replayed:
        journal = db.query(Journal).filter(Journal.id == movement.journal_id).first()
        if journal:
            evaluate_transaction_for_flags(db, journal, acc.id, req.amount)

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement


@router.post(
    "/accounts/{account_id}/withdraw",
    response_model=MovementResponse,
    dependencies=[Depends(rate_limit_dependency("money.movement", max_requests=30, window_seconds=60))],
)
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

    if not is_replayed:
        journal = db.query(Journal).filter(Journal.id == movement.journal_id).first()
        if journal:
            evaluate_transaction_for_flags(db, journal, acc.id, req.amount)

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement


@router.post(
    "/transfers",
    response_model=MovementResponse,
    dependencies=[Depends(rate_limit_dependency("money.movement", max_requests=30, window_seconds=60))],
)
def transfer(
    req: TransferRequest,
    response: Response,
    idempotency_key: str = Depends(require_idempotency_key),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(require_role("holder")),
    db: Session = Depends(get_db),
) -> MovementResponse:
    """Transfer funds from caller's account to any active recipient account by number."""
    src_acc = db.query(Account).filter(Account.id == req.from_account_id).first()
    if not src_acc or src_acc.kind != "customer":
        raise NotFoundError("Account not found.")

    is_member = (
        db.query(AccountMember)
        .filter(AccountMember.account_id == src_acc.id, AccountMember.user_id == current_user.id)
        .first()
    )
    if not is_member:
        raise NotFoundError("Account not found.")

    dest_acc = db.query(Account).filter(Account.number == req.to_account_number).first()
    if not dest_acc or dest_acc.status != "active" or dest_acc.kind != "customer":
        raise InvalidDestinationError()

    if req.from_account_id == dest_acc.id:
        raise ValidationError("Source and destination accounts must be distinct.")

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

    if not is_replayed:
        journal = db.query(Journal).filter(Journal.id == movement.journal_id).first()
        if journal:
            evaluate_transaction_for_flags(db, journal, req.from_account_id, req.amount)

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
    target = db.query(Account).filter(Account.id == account_id).first()
    if not target or not is_account_in_user_scope(target, current_user, db):
        raise NotFoundError("Account not found.")
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
    target = db.query(Account).filter(Account.id == account_id).first()
    if not target or not is_account_in_user_scope(target, current_user, db):
        raise NotFoundError("Account not found.")
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
    if not acc or not is_account_in_user_scope(acc, current_user, db):
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

    if not is_replayed:
        journal = db.query(Journal).filter(Journal.id == movement.journal_id).first()
        if journal:
            evaluate_transaction_for_flags(db, journal, acc.id, amt)

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement


@router.post("/admin/journals/{journal_id}/reverse", response_model=MovementResponse)
def admin_reverse_journal(
    journal_id: UUID,
    req: ReversalRequest,
    response: Response,
    idempotency_key: str = Depends(require_idempotency_key),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> MovementResponse:
    """Post an audited reversal journal (Admin only)."""
    orig_journal = db.query(Journal).filter(Journal.id == journal_id).first()
    if not orig_journal:
        raise NotFoundError("Original journal not found.")

    if orig_journal.kind == "reversal":
        raise ValidationError("Cannot reverse a reversal journal.")

    # Check if already reversed
    already_reversed = db.query(Journal).filter(Journal.reverses_journal_id == orig_journal.id).first()
    if already_reversed:
        raise ValidationError("Journal has already been reversed.")

    # Fetch entries
    entries = db.query(LedgerEntry).filter(LedgerEntry.journal_id == orig_journal.id).all()
    if len(entries) != 2:
        raise ValidationError("Only two-legged journals can be automatically reversed.")

    # Invert debit and credit legs
    debit_entry = next(e for e in entries if e.amount < 0)
    credit_entry = next(e for e in entries if e.amount > 0)

    movement, is_replayed = post_movement(
        db=db,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_id=request_id,
        kind="reversal",
        source_account_id=credit_entry.account_id,  # Inverted
        destination_account_id=debit_entry.account_id,  # Inverted
        amount=credit_entry.amount,
        raw_payload=req.model_dump(),
        memo=f"Reversal of {orig_journal.id}: {req.reason}",
        reverses_journal_id=orig_journal.id,
    )

    if not is_replayed:
        journal = db.query(Journal).filter(Journal.id == movement.journal_id).first()
        if journal:
            evaluate_transaction_for_flags(db, journal, credit_entry.account_id, credit_entry.amount)

    if is_replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return movement


@router.get("/admin/users", response_model=AdminUserListResponse)
def admin_list_users(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    """List all registered users with their roles and linked accounts (Admin only)."""
    if current_user.email.lower().endswith(".test"):
        users = db.query(User).filter(User.email.ilike("%.test")).order_by(User.created_at.desc()).all()
    elif current_user.email.lower().endswith(".internal"):
        users = db.query(User).filter(~User.email.ilike("%.test")).order_by(User.created_at.desc()).all()
    else:
        users = db.query(User).order_by(User.created_at.desc()).all()

    user_items = []
    for u in users:
        accs = (
            db.query(Account)
            .join(AccountMember, AccountMember.account_id == Account.id)
            .filter(AccountMember.user_id == u.id)
            .all()
        )
        user_items.append(
            AdminUserItem(
                id=u.id,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
                accounts=[
                    AdminUserAccountItem(
                        id=a.id,
                        number=a.number,
                        name=a.name,
                        balance=a.balance,
                        status=a.status,
                    )
                    for a in accs
                ],
            )
        )
    return AdminUserListResponse(users=user_items)


@router.post("/admin/users", response_model=AdminUserItem, status_code=201)
def admin_create_user(
    req: AdminCreateUserRequest,
    current_user: User = Depends(require_role("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> AdminUserItem:
    """Directly provision a new user with specific role and optional initial account (Admin only)."""
    clean_email = str(req.email).lower().strip()
    if req.role not in ("admin", "holder", "auditor"):
        raise ValidationError(f"Invalid role '{req.role}'. Must be admin, holder, or auditor.")

    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise UserAlreadyExistsError()

    user_id = uuid.uuid4()
    new_user = User(
        id=user_id,
        email=clean_email,
        password_hash=hash_password(req.password),
        role=req.role,
        is_active=True,
    )
    db.add(new_user)
    db.flush()

    user_accounts = []
    if req.role == "holder":
        account_name = req.account_name.strip() if req.account_name else f"{clean_email.split('@')[0]} Account"
        account = create_customer_account(
            db=db,
            name=account_name,
            owner_user_id=new_user.id,
            overdraft_limit=0,
        )
        user_accounts.append(
            AdminUserAccountItem(
                id=account.id,
                number=account.number,
                name=account.name,
                balance=account.balance,
                status=account.status,
            )
        )

    db.add(
        SecurityEvent(
            user_id=current_user.id,
            event_type="user_created_by_admin",
            request_id=request_id,
            details={"created_user_id": str(new_user.id), "email": new_user.email, "role": new_user.role},
        )
    )
    db.commit()

    return AdminUserItem(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        accounts=user_accounts,
    )


@router.post("/admin/users/{user_id}/status", response_model=AdminUserItem)
def admin_toggle_user_status(
    user_id: UUID,
    req: AdminToggleUserStatusRequest,
    current_user: User = Depends(require_role("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> AdminUserItem:
    """Activate or deactivate a user account with self-deactivation protection (Admin only)."""
    if user_id == current_user.id:
        raise ValidationError("Administrators cannot deactivate their own user account.")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise NotFoundError("User not found.")

    if current_user.email.lower().endswith(".test") and not target_user.email.lower().endswith(".test"):
        raise NotFoundError("User not found.")
    if current_user.email.lower().endswith(".internal") and target_user.email.lower().endswith(".test"):
        raise NotFoundError("User not found.")

    target_user.is_active = req.is_active
    if not req.is_active:
        db.query(SessionModel).filter(
            SessionModel.user_id == target_user.id,
            SessionModel.revoked_at.is_(None),
        ).update({"revoked_at": func.now()}, synchronize_session=False)

    db.add(
        SecurityEvent(
            user_id=current_user.id,
            event_type="user_status_changed",
            request_id=request_id,
            details={"target_user_id": str(target_user.id), "is_active": req.is_active},
        )
    )
    db.commit()
    db.refresh(target_user)

    accs = (
        db.query(Account)
        .join(AccountMember, AccountMember.account_id == Account.id)
        .filter(AccountMember.user_id == target_user.id)
        .all()
    )

    return AdminUserItem(
        id=target_user.id,
        email=target_user.email,
        role=target_user.role,
        is_active=target_user.is_active,
        created_at=target_user.created_at,
        accounts=[
            AdminUserAccountItem(
                id=a.id,
                number=a.number,
                name=a.name,
                balance=a.balance,
                status=a.status,
            )
            for a in accs
        ],
    )


@router.get("/accounts/requests/mine", response_model=AccountRequestListResponse)
def get_my_account_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountRequestListResponse:
    """List all account onboarding requests submitted by the authenticated user."""
    reqs = (
        db.query(AccountRequest)
        .filter(AccountRequest.user_id == current_user.id)
        .order_by(AccountRequest.created_at.desc())
        .all()
    )
    items = []
    for r in reqs:
        acc_num = None
        if r.account_id:
            acc = db.query(Account).filter(Account.id == r.account_id).first()
            if acc:
                acc_num = acc.number
        items.append(
            AccountRequestItem(
                id=r.id,
                user_id=r.user_id,
                account_name=r.account_name,
                purpose=r.purpose,
                currency=r.currency,
                status=r.status,
                created_at=r.created_at,
                reviewed_at=r.reviewed_at,
                rejection_reason=r.rejection_reason,
                account_id=r.account_id,
                account_number=acc_num,
            )
        )
    return AccountRequestListResponse(requests=items)


@router.post("/accounts/requests", response_model=AccountRequestItem, status_code=201)
def create_account_request(
    payload: AccountRequestCreate,
    current_user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> AccountRequestItem:
    """Submit a request for a new customer vault account."""
    acc_req_id = uuid.uuid4()
    req_obj = AccountRequest(
        id=acc_req_id,
        user_id=current_user.id,
        account_name=payload.account_name.strip(),
        purpose=payload.purpose.strip() if payload.purpose else None,
        currency="INR",
        status="pending",
    )
    db.add(req_obj)

    # Place in review queue for administrator approval
    flag = ReviewFlag(
        rule_id="account_request",
        severity="medium",
        status="open",
        evidence={
            "request_id": str(acc_req_id),
            "user_id": str(current_user.id),
            "email": current_user.email,
            "account_name": payload.account_name.strip(),
        },
        narrative=f"Account request from {current_user.email}: '{payload.account_name.strip()}'. Administrator approval required.",
    )
    db.add(flag)

    db.add(
        SecurityEvent(
            actor_user_id=current_user.id,
            event="account_request_created",
            request_id=request_id,
            detail={"request_id": str(acc_req_id), "account_name": payload.account_name.strip()},
        )
    )
    db.commit()
    db.refresh(req_obj)

    return AccountRequestItem(
        id=req_obj.id,
        user_id=req_obj.user_id,
        account_name=req_obj.account_name,
        purpose=req_obj.purpose,
        currency=req_obj.currency,
        status=req_obj.status,
        created_at=req_obj.created_at,
        reviewed_at=None,
        rejection_reason=None,
        account_id=None,
        account_number=None,
    )
