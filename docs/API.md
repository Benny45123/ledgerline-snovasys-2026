# LedgerLine API Reference

> Contractual documentation per `Problem_Statement.md` ("API documentation, saying for each endpoint who is allowed to call it and what it does to the money") and `AGENTS.md` Section 13.
> All money values are strictly integer paise (1 INR = 100 paise).
> Standard Error Envelope: `{"error": {"code": "...", "message": "...", "request_id": "..."}}`

---

## 1. Authentication & Sessions

### `POST /auth/login`
- **Allowed Callers**: Anyone (Unauthenticated).
- **Effect on Money**: None.
- **Idempotency**: Not required.
- **Rate Limiting**: Progressive delay per (IP, email) backed by `security_events`. No hard lockouts.
- **Request Body**:
  ```json
  {
    "email": "holder1@ledgerline.test",
    "password": "HolderPass123!"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "token": "a1b2c3d4...",
    "user": {
      "id": "e4f8a32b-...",
      "email": "holder1@ledgerline.test",
      "role": "holder"
    }
  }
  ```

### `POST /auth/register`
- **Allowed Callers**: Anyone (Unauthenticated).
- **Effect on Money**: None (Provisions user with role `holder` and creates primary account with initial balance `0`).
- **Idempotency**: Handled via unique email constraints and atomic transaction.
- **Rate Limiting**: Enforced via Redis sliding window (5 registrations/hour per IP).
- **Request Body**:
  ```json
  {
    "email": "newuser@example.com",
    "password": "SecurePassword123!",
    "account_name": "Primary Operating"
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "token": "7f8e9d...",
    "user": {
      "id": "c1a2b3c4-...",
      "email": "newuser@example.com",
      "role": "holder",
      "is_active": true
    },
    "account": {
      "id": "f5e4d3c2-...",
      "number": "ACC-984210",
      "name": "Primary Operating",
      "currency": "INR",
      "balance": 0
    }
  }
  ```

### `GET /auth/me`
- **Allowed Callers**: Authenticated (`holder`, `admin`, `auditor`).
- **Effect on Money**: None.
- **Header**: `Authorization: Bearer <token>`
- **Response (200 OK)**:
  ```json
  {
    "id": "e4f8a32b-...",
    "email": "holder1@ledgerline.test",
    "role": "holder",
    "is_active": true,
    "created_at": "2026-11-06T12:00:00Z"
  }
  ```

### `POST /auth/logout`
- **Allowed Callers**: Authenticated (`holder`, `admin`, `auditor`).
- **Effect on Money**: None.
- **Header**: `Authorization: Bearer <token>`
- **Response (200 OK)**: `{"message": "Logged out successfully"}`

---

## 2. Accounts & Statements

### `GET /accounts`
- **Allowed Callers**: Authenticated (`holder`, `admin`, `auditor`).
- **Allowed Scope**:
  - `holder`: Returns only accounts the caller is an active member of in `account_members`.
  - `admin`, `auditor`: Returns all accounts.
- **Effect on Money**: None (Read-only).
- **Response (200 OK)**: Array of account objects (`id`, `name`, `kind`, `currency`, `balance`, `overdraft_limit`, `status`).

### `POST /accounts`
- **Allowed Callers**: `admin` only.
- **Effect on Money**: None (Creates account with initial balance `0`).
- **Request Body**:
  ```json
  {
    "name": "Acme Payroll Account",
    "owner_user_id": "e4f8a32b-...",
    "overdraft_limit": 0
  }
  ```
- **Response (201 Created)**: Account object.

### `GET /accounts/{account_id}`
- **Allowed Callers**: `admin`, `auditor`, or `holder` if member of `account_id`.
- **Security Rule**: Returns `404 Not Found` (never 403) for non-member holders to eliminate account enumeration.
- **Effect on Money**: None (Read-only).
- **Response (200 OK)**: Account object.

### `GET /accounts/{account_id}/statement`
- **Allowed Callers**: `admin`, `auditor`, or `holder` if member of `account_id`.
- **Security Rule**: Returns `404 Not Found` for non-member holders.
- **Effect on Money**: None (Read-only).
- **Pagination**: Keyset pagination with cursor `after` (sequence number) and `limit` (max 200).
- **Response (200 OK)**:
  ```json
  {
    "account_id": "...",
    "items": [
      {
        "type": "posting",
        "account_seq": 1,
        "journal_id": "...",
        "amount": 5000,
        "balance_after": 5000,
        "prev_hash": "00...",
        "entry_hash": "e3b0c44...",
        "created_at": "2026-11-09T05:00:00Z"
      },
      {
        "type": "refusal",
        "account_seq": 2,
        "amount": 10000,
        "balance_at_attempt": 5000,
        "reason_code": "insufficient_funds",
        "prev_hash": "e3b0c44...",
        "entry_hash": "a4f8c12...",
        "created_at": "2026-11-09T05:01:00Z"
      }
    ],
    "has_more": false,
    "next_after": null
  }
  ```

### `GET /accounts/requests/mine`
- **Allowed Callers**: Authenticated (`holder`, `admin`, `auditor`).
- **Effect on Money**: None (Read-only).
- **Response (200 OK)**:
  ```json
  {
    "requests": [
      {
        "id": "...",
        "user_id": "...",
        "account_name": "Treasury Reserve Vault",
        "currency": "INR",
        "status": "pending",
        "account_id": null,
        "rejection_reason": null,
        "created_at": "2026-11-10T12:00:00Z",
        "decided_at": null
      }
    ]
  }
  ```

### `POST /accounts/requests`
- **Allowed Callers**: Authenticated `holder` with 0 active accounts.
- **Effect on Money**: None.
- **Request Body**:
  ```json
  {
    "account_name": "Operating Checking"
  }
  ```
- **Response (201 Created)**: AccountRequestItem object.


---

## 3. Money Movement Pipeline (`post_movement`)

All four money movement endpoints below invoke `app/ledger/service.py::post_movement()` and execute inside an atomic PostgreSQL transaction.

### `POST /accounts/{account_id}/deposit`
- **Allowed Callers**: `holder` (must be member of `{account_id}`).
- **Required Header**: `Idempotency-Key` (16–128 chars `[A-Za-z0-9_-]`).
- **Effect on Money**:
  - Debits system account `SYS-EXTERNAL` by `amount`.
  - Credits customer account `{account_id}` by `amount`.
  - Net global balance change: `0`. Customer total increases by `amount`; External decreases by `amount`.
- **Request Body**:
  ```json
  {
    "amount": 50000,
    "memo": "Initial bank wire"
  }
  ```
- **Response (200 OK / 201 Created)**:
  Header: `Idempotent-Replayed: true` (if duplicate).
  ```json
  {
    "journal_id": "...",
    "kind": "deposit",
    "amount": 50000,
    "status": "posted",
    "entry": {
      "account_id": "...",
      "account_seq": 1,
      "amount": 50000,
      "balance_after": 50000
    },
    "created_at": "2026-11-09T05:00:00Z"
  }
  ```

### `POST /accounts/{account_id}/withdraw`
- **Allowed Callers**: `holder` (must be member of `{account_id}`).
- **Required Header**: `Idempotency-Key`.
- **Effect on Money**:
  - Debits customer account `{account_id}` by `amount`.
  - Credits system account `SYS-EXTERNAL` by `amount`.
  - Enforces `balance >= -overdraft_limit`. If balance is insufficient, writes to `refused_attempts` and returns HTTP 409 `insufficient_funds`.
  - Net global balance change: `0`.
- **Request Body**:
  ```json
  {
    "amount": 20000,
    "memo": "ATM Cash Out"
  }
  ```

### `POST /transfers`
- **Allowed Callers**: `holder` (must be member of `from_account_id`).
- **Required Header**: `Idempotency-Key`.
- **Security Invariant**: Target account must be `kind == "customer"` (transfers directly to `EXTERNAL` or `SUSPENSE` are rejected with 422). Self-transfers (`from_account_id == to_account_id`) are rejected with 422.
- **Effect on Money**:
  - Debits `from_account_id` by `amount`.
  - Credits `to_account_id` by `amount`.
  - Net balance change: exactly `0` paise.
- **Request Body**:
  ```json
  {
    "from_account_id": "e4f8a32b-...",
    "to_account_number": "100000000002",
    "amount": 15000,
    "memo": "Vendor settlement"
  }
  ```

### `POST /admin/adjustments`
- **Allowed Callers**: `admin` only.
- **Required Header**: `Idempotency-Key`.
- **Effect on Money**:
  - Offsets target account against system account `SYS-SUSPENSE`.
  - If `amount > 0`: credits target account, debits `SYS-SUSPENSE`.
  - If `amount < 0`: debits target account, credits `SYS-SUSPENSE`.
  - Net balance change: `0` (double-entry zero-sum).
  - Recorded in the ledger with the admin user as `initiated_by`.
- **Request Body**:
  ```json
  {
    "account_id": "e4f8a32b-...",
    "amount": -500,
    "reason": "Reconciled ledger discrepancy fee"
  }
  ```

### `POST /admin/journals/{journal_id}/reverse`
- **Allowed Callers**: `admin` only.
- **Required Header**: `Idempotency-Key`.
- **Effect on Money**:
  - Posts an exact inverted reversal journal referencing the original `journal_id`.
  - Every account originally credited is debited; every account originally debited is credited.
  - The original journal remains untouched and append-only.
- **Request Body**:
  ```json
  {
    "reason": "Customer duplicate transfer refund"
  }
  ```

---

## 4. Cryptographic Audit & Verification

### `GET /audit/verify`
- **Allowed Callers**: `admin`, `auditor`.
- **Effect on Money**: None (Cryptographic audit engine).
- **What It Computes**:
  1. Re-computes SHA-256 hash chains from genesis to head for every account.
  2. Asserts `accounts.balance == balance_after` of each account's latest ledger entry.
  3. Asserts double-entry zero-sum $\sum \text{amount} = 0$ for every journal.
  4. Asserts global conservation $\sum \text{all balances} == 0$.
- **Response (200 OK)**:
  ```json
  {
    "verified": true,
    "is_valid": true,
    "total_accounts_checked": 53,
    "total_entries_verified": 235,
    "total_journals_verified": 118,
    "global_balance_sum": 0,
    "customer_balance_sum": 1500000,
    "discrepancies": []
  }
  ```

---

## 5. Surveillance & Review

### `GET /review/flags`
- **Allowed Callers**: `admin`, `auditor`.
- **Effect on Money**: None.
- **Response (200 OK)**: List of review flags with dynamically derived statuses (`pending`, `escalated`, `dismissed`).

### `POST /review/flags/{flag_id}/decide`
- **Allowed Callers**: `admin` only.
- **Effect on Money**: None (Appends immutable decision record to `review_decisions`).
- **Request Body**:
  ```json
  {
    "decision": "dismissed",
    "reason": "Verified legitimate invoice payment with counterparty"
  }
  ```

---

## 6. Admin User Management & Onboarding

### `GET /admin/users`
- **Allowed Callers**: `admin` only.
- **Effect on Money**: None (Read-only user directory).
- **Response (200 OK)**:
  ```json
  [
    {
      "id": "e4f8a32b-...",
      "email": "holder1@ledgerline.internal",
      "role": "holder",
      "is_active": true,
      "created_at": "2026-11-06T12:00:00Z",
      "accounts": [
        {
          "id": "a1b2c3d4-...",
          "number": "ACC-100001",
          "name": "holder1 Operating",
          "balance": 10000000,
          "status": "active"
        }
      ]
    }
  ]
  ```

### `POST /admin/users`
- **Allowed Callers**: `admin` only.
- **Effect on Money**: None (Provisions user with designated role).
- **Request Body**:
  ```json
  {
    "email": "auditor2@ledgerline.internal",
    "password": "TemporaryPassword123!",
    "role": "auditor"
  }
  ```
- **Response (201 Created)**: User details object.

### `POST /admin/users/{user_id}/status`
- **Allowed Callers**: `admin` only.
- **Effect on Money**: None (Activates or suspends user authentication).
- **Request Body**:
  ```json
  {
    "is_active": false
  }
  ```
- **Response (200 OK)**: Updated user details.

---

## 7. Operational Health & Readiness Probes

### `GET /health`
- **Allowed Callers**: Anyone (Unauthenticated).
- **Effect on Money**: None (Process liveness probe).
- **Response (200 OK)**:
  ```json
  {
    "status": "ok"
  }
  ```

### `GET /ready`
- **Allowed Callers**: Anyone (Unauthenticated).
- **Effect on Money**: None (Dependency readiness probe: PostgreSQL + Redis).
- **Response (200 OK)**:
  ```json
  {
    "status": "ready",
    "database": "connected",
    "redis": "connected"
  }
  ```
- **Response (503 Service Unavailable)**:
  ```json
  {
    "status": "unavailable",
    "database": "disconnected"
  }
  ```

---

## 8. Rate Limiting Headers & Error Contract

All public and transactional routes return standard rate-limiting metadata headers:
- `X-RateLimit-Limit`: Maximum permitted requests in current window.
- `X-RateLimit-Remaining`: Remaining request quota.
- `X-RateLimit-Reset`: Unix timestamp when quota resets.

When rate limits are exceeded, the API returns:
- **HTTP Status**: `429 Too Many Requests`
- **Header**: `Retry-After: <seconds>`
- **Body Envelope**:
  ```json
  {
    "error": {
      "code": "rate_limited",
      "message": "Too many requests. Please retry in 30 seconds.",
      "request_id": "req-98f2b1a4"
    }
  }
  ```

