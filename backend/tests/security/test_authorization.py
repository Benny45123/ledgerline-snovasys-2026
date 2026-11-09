"""
How this works / why it is safe:
This module tests Invariant I6 (Server-Authoritative Authorization & Least Privilege).
It proves that:
1. Holder 2 cannot inspect or withdraw from Holder 1's account (returns 404, preventing enumeration).
2. Auditors cannot perform write operations (returns 403 Forbidden).
3. Unauthenticated requests are rejected with 401 Unauthorized.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.accounts.service import create_customer_account, get_system_account
from app.auth.sessions import create_session
from app.errors import NotFoundError
from app.ledger.service import post_movement


def test_idor_foreign_account_returns_404(client: TestClient, db: Session, test_users):
    """Prove that attempting to access another user's account returns 404 Not Found."""
    holder1 = test_users["holder1"]
    holder2 = test_users["holder2"]

    # Holder 1 owns this account
    h1_account = create_customer_account(db, "Holder 1 Secret Acc", holder1.id, overdraft_limit=0)

    # Log in as Holder 2
    h2_token, _ = create_session(db, holder2)
    headers = {"Authorization": f"Bearer {h2_token}"}

    # Holder 2 attempts GET on Holder 1's account
    resp = client.get(f"/accounts/{h1_account.id}", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

    # Holder 2 attempts to fetch statement on Holder 1's account
    resp_stmt = client.get(f"/accounts/{h1_account.id}/statement", headers=headers)
    assert resp_stmt.status_code == 404

    # Holder 2 attempts to withdraw from Holder 1's account
    resp_wd = client.post(
        f"/accounts/{h1_account.id}/withdraw",
        headers={**headers, "Idempotency-Key": "idor-attack-key-12345678"},
        json={"amount": 1000},
    )
    assert resp_wd.status_code == 404


def test_auditor_cannot_execute_writes(client: TestClient, db: Session, test_users):
    """Prove that the auditor role is strictly read-only and denied on write routes."""
    auditor = test_users["auditor"]
    auditor_token, _ = create_session(db, auditor)
    headers = {
        "Authorization": f"Bearer {auditor_token}",
        "Idempotency-Key": "auditor-attempt-key-12345",
    }

    # Attempt to transfer as auditor
    resp = client.post(
        "/transfers",
        headers=headers,
        json={
            "from_account_id": "00000000-0000-0000-0000-000000000000",
            "to_account_number": "100000000000",
            "amount": 1000,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_unauthenticated_request_rejected(client: TestClient):
    """Prove that requests without bearer tokens are rejected with 401."""
    resp = client.get("/accounts")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_post_movement_enforces_membership(db: Session, test_users):
    """Prove that post_movement in-transaction authorization rejects callers without membership."""
    holder1 = test_users["holder1"]
    holder2 = test_users["holder2"]
    ext_acc = get_system_account(db, "external")
    h1_account = create_customer_account(db, f"Member Guard {uuid.uuid4().hex[:4]}", holder1.id, overdraft_limit=0)

    # holder2 attempts to withdraw from holder1's account directly inside the transaction
    with pytest.raises(NotFoundError):
        post_movement(
            db=db,
            user_id=holder2.id,
            idempotency_key=f"direct-auth-{uuid.uuid4()}",
            request_id=f"req-auth-{uuid.uuid4().hex[:8]}",
            kind="withdrawal",
            source_account_id=h1_account.id,
            destination_account_id=ext_acc.id,
            amount=1000,
            raw_payload={"amount": 1000},
        )
