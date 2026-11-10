"""
How this works / why it is safe:
This module verifies the institutional Account Request & Admin Approval workflow.
When a user signs up:
1. They are registered with credentials, but have 0 active ledger accounts.
2. An AccountRequest row is created in 'pending' status, and an 'account_request'
   flag is queued in the Review Queue.
3. Only an administrator can review the request and approve or dismiss it.
4. Upon approval, create_customer_account provisions a zero-balance double-entry
   vault bound to the user, and an audit trail is recorded.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.sessions import create_session


def test_account_onboarding_request_and_admin_approval_flow(client: TestClient, db: Session, test_users):
    """Prove the end-to-end onboarding: register -> pending request -> admin approval -> vault provisioned."""
    admin = test_users["admin"]
    admin_token, _ = create_session(db, admin)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. New user registers
    unique_email = f"onboarding_{uuid.uuid4().hex[:8]}@ledgerline.io"
    reg_resp = client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": "SecurePassword123!",
            "account_name": "Treasury Reserve Vault",
        },
    )
    assert reg_resp.status_code == 201, reg_resp.text
    reg_data = reg_resp.json()
    new_user_token = reg_data["token"]
    user_headers = {"Authorization": f"Bearer {new_user_token}"}
    assert reg_data["account"] is None

    # 2. User checks accounts -> should be 0 accounts
    accs_resp = client.get("/accounts", headers=user_headers)
    assert accs_resp.status_code == 200
    assert len(accs_resp.json()["accounts"]) == 0

    # 3. User checks their pending requests -> 1 pending request
    my_reqs_resp = client.get("/accounts/requests/mine", headers=user_headers)
    assert my_reqs_resp.status_code == 200
    my_reqs = my_reqs_resp.json()["requests"]
    assert len(my_reqs) == 1
    assert my_reqs[0]["account_name"] == "Treasury Reserve Vault"
    assert my_reqs[0]["status"] == "pending"
    assert my_reqs[0]["account_id"] is None

    # 4. Admin inspects Review Queue
    flags_resp = client.get("/review/flags?status=open", headers=admin_headers)
    assert flags_resp.status_code == 200
    flags = flags_resp.json()
    onboarding_flag = next(
        (f for f in flags if f["rule_id"] == "account_request" and unique_email in f["narrative"]), None
    )
    assert onboarding_flag is not None, "Onboarding flag should appear in Admin Review Queue"

    # 5. Admin approves the onboarding request with a mandatory explanation
    decision_resp = client.post(
        f"/review/flags/{onboarding_flag['id']}/decision",
        headers=admin_headers,
        json={
            "decision": "approved",
            "reason": "KYC verified and business profile approved for institutional vault access.",
        },
    )
    assert decision_resp.status_code == 200, decision_resp.text
    assert decision_resp.json()["decision"] == "approve"

    # 6. User re-checks accounts -> vault is now active!
    accs_after = client.get("/accounts", headers=user_headers)
    assert accs_after.status_code == 200
    user_accounts = accs_after.json()["accounts"]
    assert len(user_accounts) == 1
    vault = user_accounts[0]
    assert vault["name"] == "Treasury Reserve Vault"
    assert vault["balance"] == 0
    assert vault["status"] == "active"
    assert vault["currency"] == "INR"

    # 7. Request record is now updated to approved
    my_reqs_after = client.get("/accounts/requests/mine", headers=user_headers).json()["requests"]
    assert my_reqs_after[0]["status"] == "approved"
    assert my_reqs_after[0]["account_id"] == vault["id"]


def test_account_onboarding_request_admin_dismiss_flow(client: TestClient, db: Session, test_users):
    """Prove that an admin can dismiss/reject an onboarding request, preventing vault creation."""
    admin = test_users["admin"]
    admin_token, _ = create_session(db, admin)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    unique_email = f"rejected_{uuid.uuid4().hex[:8]}@ledgerline.io"
    reg_resp = client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": "SecurePassword123!",
            "account_name": "Suspicious Shell Vault",
        },
    )
    assert reg_resp.status_code == 201
    user_token = reg_resp.json()["token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Find flag in review queue
    flags = client.get("/review/flags?status=open", headers=admin_headers).json()
    onboarding_flag = next(
        (f for f in flags if f["rule_id"] == "account_request" and unique_email in f["narrative"]), None
    )
    assert onboarding_flag is not None

    # Admin dismisses the request
    client.post(
        f"/review/flags/{onboarding_flag['id']}/decision",
        headers=admin_headers,
        json={
            "decision": "dismissed",
            "reason": "Entity failed compliance documentation requirements.",
        },
    )

    # User still has 0 accounts
    accs_resp = client.get("/accounts", headers=user_headers)
    assert len(accs_resp.json()["accounts"]) == 0

    # User request reflects rejection reason
    my_reqs = client.get("/accounts/requests/mine", headers=user_headers).json()["requests"]
    assert my_reqs[0]["status"] == "rejected"
    assert "Entity failed compliance" in my_reqs[0]["rejection_reason"]
