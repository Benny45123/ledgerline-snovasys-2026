"""
How this works / why it is safe:
This module provides an idempotent database seed script (python -m app.seed).
It safely initializes:
- 1 Admin user (system operator)
- 2 Account Holder users (holder1, holder2) enabling cross-user IDOR testing
- 1 Auditor user (read-only inspector)
- EXTERNAL and SUSPENSE system accounts (for double-entry cash flow)
- 2 Customer accounts per holder, with opening balances posted exclusively through
  the official post_movement() pathway with deterministic idempotency keys.
Running this script multiple times produces identical state without duplicate journals.
"""

import uuid

from sqlalchemy.orm import Session

from app.accounts.service import create_customer_account, get_system_account
from app.auth.passwords import hash_password
from app.db.engine import SessionLocal
from app.db.models import AccountMember, User
from app.ledger.service import post_movement

# Pre-populated / tested accounts (with historical activity) and fresh clean evaluation accounts
SEED_USERS = [
    ("admin@ledgerline.internal", "admin", "DemoPassword123!"),
    ("holder1@ledgerline.internal", "holder", "DemoPassword123!"),
    ("holder2@ledgerline.internal", "holder", "DemoPassword123!"),
    ("auditor@ledgerline.internal", "auditor", "DemoPassword123!"),
    ("admin@ledgerline.test", "admin", "AdminPass123!"),
    ("holder1@ledgerline.test", "holder", "HolderPass123!"),
    ("holder2@ledgerline.test", "holder", "HolderPass123!"),
    ("auditor@ledgerline.test", "auditor", "AuditorPass123!"),
]

HOLDERS_TO_PROVISION = [
    "holder1@ledgerline.internal",
    "holder2@ledgerline.internal",
    "holder1@ledgerline.test",
    "holder2@ledgerline.test",
]


def seed_database(db: Session | None = None) -> None:
    """Idempotently seed roles, accounts, and opening balances."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        user_map = {}
        for email, role, password in SEED_USERS:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"Created user: {email} ({role})")
            else:
                user.password_hash = hash_password(password)
                user.role = role
                user.is_active = True
                db.commit()
                print(f"Synchronized user credentials: {email} ({role})")
            user_map[email] = user

        # System accounts
        ext_acc = get_system_account(db, "external")
        susp_acc = get_system_account(db, "suspense")
        print(f"Verified system accounts: {ext_acc.number}, {susp_acc.number}")

        # Seed 2 accounts for each holder
        for holder_key in HOLDERS_TO_PROVISION:
            holder = user_map.get(holder_key)
            if not holder:
                continue
            existing_memberships = db.query(AccountMember).filter(AccountMember.user_id == holder.id).all()

            if not existing_memberships:
                # Account 1: Operating
                domain_tag = "internal" if "internal" in holder_key else "test"
                prefix = holder.email.split("@")[0]
                acc1 = create_customer_account(
                    db=db,
                    name=f"{prefix} Operating ({domain_tag})",
                    owner_user_id=holder.id,
                    overdraft_limit=0,
                )
                # Account 2: Reserve with overdraft limit
                acc2 = create_customer_account(
                    db=db,
                    name=f"{prefix} Reserve ({domain_tag})",
                    owner_user_id=holder.id,
                    overdraft_limit=5000000,  # ₹50,000 overdraft
                )

                # Post opening balance via post_movement()
                deposit_amount = 10000000 if "holder1" in holder_key else 5000000  # ₹1,00,000 or ₹50,000
                post_movement(
                    db=db,
                    user_id=holder.id,
                    idempotency_key=f"seed-opening-balance-{acc1.id}",
                    request_id=f"seed-req-{acc1.id}",
                    kind="deposit",
                    source_account_id=ext_acc.id,
                    destination_account_id=acc1.id,
                    amount=deposit_amount,
                    raw_payload={"seed": True, "account_id": str(acc1.id), "amount": deposit_amount},
                    memo="Initial account opening balance",
                )
                print(f"Seeded accounts and opening balance for {holder.email}")

        print("Database seeding completed successfully.")

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    seed_database()
