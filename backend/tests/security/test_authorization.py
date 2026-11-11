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


def test_holder_cannot_transfer_from_system_account(db: Session, test_users):
    """Prove that post_movement rejects attempts by a holder to transfer from external or suspense accounts."""
    holder1 = test_users["holder1"]
    ext_acc = get_system_account(db, "external")
    suspense_acc = get_system_account(db, "suspense")
    h1_account = create_customer_account(
        db, f"System Transfer Guard {uuid.uuid4().hex[:4]}", holder1.id, overdraft_limit=0
    )

    # Attempt transfer from EXTERNAL
    with pytest.raises(NotFoundError):
        post_movement(
            db=db,
            user_id=holder1.id,
            idempotency_key=f"ext-transfer-{uuid.uuid4()}",
            request_id=f"req-ext-{uuid.uuid4().hex[:8]}",
            kind="transfer",
            source_account_id=ext_acc.id,
            destination_account_id=h1_account.id,
            amount=5000,
            raw_payload={"amount": 5000},
        )

    # Attempt transfer from SUSPENSE
    with pytest.raises(NotFoundError):
        post_movement(
            db=db,
            user_id=holder1.id,
            idempotency_key=f"susp-transfer-{uuid.uuid4()}",
            request_id=f"req-susp-{uuid.uuid4().hex[:8]}",
            kind="transfer",
            source_account_id=suspense_acc.id,
            destination_account_id=h1_account.id,
            amount=5000,
            raw_payload={"amount": 5000},
        )


def test_transfer_route_rejects_unowned_or_system_source_account(client: TestClient, db: Session, test_users):
    """Prove that /transfers endpoint rejects requests when from_account_id is a system or unowned account."""
    holder1 = test_users["holder1"]
    holder2 = test_users["holder2"]
    ext_acc = get_system_account(db, "external")
    h1_account = create_customer_account(db, f"H1 Dest {uuid.uuid4().hex[:4]}", holder1.id, overdraft_limit=0)
    h2_account = create_customer_account(db, f"H2 Target {uuid.uuid4().hex[:4]}", holder2.id, overdraft_limit=0)

    h1_token, _ = create_session(db, holder1)
    headers = {
        "Authorization": f"Bearer {h1_token}",
        "Idempotency-Key": f"sys-transfer-route-{uuid.uuid4()}",
    }

    # Attempt transfer from external system account
    resp_ext = client.post(
        "/transfers",
        json={
            "from_account_id": str(ext_acc.id),
            "to_account_number": h1_account.number,
            "amount": 1000,
        },
        headers=headers,
    )
    assert resp_ext.status_code == 404
    assert resp_ext.json()["error"]["code"] == "not_found"

    # Attempt transfer from holder2's account without membership
    resp_unowned = client.post(
        "/transfers",
        json={
            "from_account_id": str(h2_account.id),
            "to_account_number": h1_account.number,
            "amount": 1000,
        },
        headers={
            "Authorization": f"Bearer {h1_token}",
            "Idempotency-Key": f"unowned-transfer-route-{uuid.uuid4()}",
        },
    )
    assert resp_unowned.status_code == 404
    assert resp_unowned.json()["error"]["code"] == "not_found"


def test_admin_domain_isolation_test_vs_internal(client: TestClient, db: Session):
    """Prove that .test and .internal environments are strictly isolated for admin inspection."""
    from app.auth.passwords import hash_password
    from app.db.models import User

    pwd_hash = hash_password("IsoPassword123!")
    test_tag = uuid.uuid4().hex[:6]

    # 1. Provision isolated users
    admin_test = User(id=uuid.uuid4(), email=f"adm_{test_tag}@ledgerline.test", password_hash=pwd_hash, role="admin", is_active=True)
    admin_internal = User(id=uuid.uuid4(), email=f"adm_{test_tag}@ledgerline.internal", password_hash=pwd_hash, role="admin", is_active=True)
    holder_test = User(id=uuid.uuid4(), email=f"h_{test_tag}@ledgerline.test", password_hash=pwd_hash, role="holder", is_active=True)
    holder_internal = User(id=uuid.uuid4(), email=f"h_{test_tag}@ledgerline.internal", password_hash=pwd_hash, role="holder", is_active=True)

    db.add_all([admin_test, admin_internal, holder_test, holder_internal])
    db.commit()

    # 2. Provision isolated accounts
    acc_test = create_customer_account(db, f"Vault Test ({test_tag}) (test)", holder_test.id, overdraft_limit=0)
    acc_internal = create_customer_account(db, f"Vault Internal ({test_tag}) (internal)", holder_internal.id, overdraft_limit=0)

    # 3. Test Admin (.test) session
    adm_test_token, _ = create_session(db, admin_test)
    headers_test = {"Authorization": f"Bearer {adm_test_token}"}

    # Verify list_accounts only contains .test account
    resp_list_test = client.get("/accounts", headers=headers_test)
    assert resp_list_test.status_code == 200
    listed_ids_test = [a["id"] for a in resp_list_test.json()["accounts"]]
    assert str(acc_test.id) in listed_ids_test
    assert str(acc_internal.id) not in listed_ids_test

    # Direct access: .test account succeeds, .internal account returns 404
    assert client.get(f"/accounts/{acc_test.id}", headers=headers_test).status_code == 200
    assert client.get(f"/accounts/{acc_internal.id}", headers=headers_test).status_code == 404

    # 4. Test Admin (.internal) session
    adm_int_token, _ = create_session(db, admin_internal)
    headers_int = {"Authorization": f"Bearer {adm_int_token}"}

    # Verify list_accounts only contains .internal account
    resp_list_int = client.get("/accounts", headers=headers_int)
    assert resp_list_int.status_code == 200
    listed_ids_int = [a["id"] for a in resp_list_int.json()["accounts"]]
    assert str(acc_internal.id) in listed_ids_int
    assert str(acc_test.id) not in listed_ids_int

    # Direct access: .internal account succeeds, .test account returns 404
    assert client.get(f"/accounts/{acc_internal.id}", headers=headers_int).status_code == 200
    assert client.get(f"/accounts/{acc_test.id}", headers=headers_int).status_code == 404
