"""
How this works / why it is safe:
This module provides Pytest fixtures for integration and concurrency testing.
It initializes database tables, provides clean session contexts, and sets up
a TestClient against the FastAPI application. Real PostgreSQL is used;
mocking money paths or SQLite substitutions is strictly prohibited.
"""

import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.accounts.service import get_system_account
from app.auth.passwords import hash_password
from app.db.base import Base
from app.db.engine import SessionLocal, engine
from app.db.models import User
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure database schema is established for the test session."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    """Provide a clean transactional database session per test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """Provide a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def test_users(db: Session):
    """Fixture providing authenticated test users for each role."""
    pwd_hash = hash_password("TestPassword123!")
    users = {}

    for email, role in [
        ("test_admin@ledgerline.test", "admin"),
        ("test_holder1@ledgerline.test", "holder"),
        ("test_holder2@ledgerline.test", "holder"),
        ("test_auditor@ledgerline.test", "auditor"),
    ]:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=pwd_hash,
                role=role,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        users[role if role != "holder" else email.split("@")[0].replace("test_", "")] = user

    # Ensure system accounts exist
    get_system_account(db, "external")
    get_system_account(db, "suspense")

    return users
