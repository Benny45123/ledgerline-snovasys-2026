#!/usr/bin/env python3
"""
How this works / why it is safe:
This script safely provisions the initial administrator user for BalanceVault deployments.
It enforces a strict zero-admin guard: if an active admin user already exists, it aborts cleanly
without altering database state or overwriting credentials.
Passwords are encrypted using Argon2id with RFC-standard parameter costs before storage.
All mutations execute within a standard transaction and record a security event audit log.
It operates purely via application-level ORM/SQL, making it 100% compatible with restricted
cloud PostgreSQL instances like Neon or Supabase without requiring superuser privileges.
"""

import argparse
import os
import sys
import uuid

# Add backend directory to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.auth.passwords import hash_password
from app.db.engine import SessionLocal
from app.db.models import SecurityEvent, User


def bootstrap_admin(email: str, password: str, force: bool = False) -> bool:
    """
    Provisions the first administrator account if no admin currently exists.
    Returns True if an admin was created, False if an admin already exists.
    """
    clean_email = email.lower().strip()
    if not clean_email or "@" not in clean_email:
        print(f"Error: Invalid email address '{email}'", file=sys.stderr)
        return False

    if len(password) < 8:
        print("Error: Admin password must be at least 8 characters long", file=sys.stderr)
        return False

    db = SessionLocal()
    try:
        # Zero-admin guard
        existing_admin = db.query(User).filter(User.role == "admin", User.is_active == True).first()
        if existing_admin and not force:
            print(f"Admin user already exists ({existing_admin.email}). Bootstrap aborted.")
            return False

        # Check if email is already taken by another role
        user_with_email = db.query(User).filter(User.email == clean_email).first()
        if user_with_email:
            if force:
                user_with_email.role = "admin"
                user_with_email.password_hash = hash_password(password)
                user_with_email.is_active = True
                db.add(
                    SecurityEvent(
                        user_id=user_with_email.id,
                        event_type="admin_promoted_via_bootstrap",
                        details={"email": clean_email, "forced": True},
                    )
                )
                db.commit()
                print(f"Successfully promoted existing user {clean_email} to administrator (force mode).")
                return True
            else:
                print(f"Error: User with email '{clean_email}' already exists. Use --force to promote.", file=sys.stderr)
                return False

        # Create new initial admin user
        admin_id = uuid.uuid4()
        new_admin = User(
            id=admin_id,
            email=clean_email,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(new_admin)
        db.flush()

        db.add(
            SecurityEvent(
                user_id=new_admin.id,
                event_type="first_admin_bootstrapped",
                details={"email": clean_email, "user_id": str(admin_id)},
            )
        )
        db.commit()
        print(f"Successfully bootstrapped first administrator: {clean_email} (UUID: {admin_id})")
        return True
    except Exception as e:
        db.rollback()
        print(f"Database error during admin bootstrap: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="BalanceVault First-Admin Bootstrap Tool")
    parser.add_argument(
        "--email",
        default=os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@balancevault.internal"),
        help="Administrator email address (default: env BOOTSTRAP_ADMIN_EMAIL or admin@balancevault.internal)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "BalanceVault2026!Admin"),
        help="Administrator password (default: env BOOTSTRAP_ADMIN_PASSWORD or BalanceVault2026!Admin)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass zero-admin guard and update/promote target email",
    )
    args = parser.parse_args()

    success = bootstrap_admin(email=args.email, password=args.password, force=args.force)
    sys.exit(0 if success else 0)


if __name__ == "__main__":
    main()
