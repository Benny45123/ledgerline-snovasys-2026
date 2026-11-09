# LedgerLine Database Schema Reference

> Engine: PostgreSQL 16
> Isolation Level: READ COMMITTED with explicit `FOR UPDATE` row locking
> Currency: Indian Rupee (INR) — integer paise stored in `BIGINT`

---

## 1. Tables Overview

```
users (id, email, password_hash, role, is_active, created_at)
  └── sessions (token_hash, user_id, expires_at, created_at)
  └── security_events (id, actor_user_id, event, detail, request_id, created_at)

accounts (id, account_number, name, kind, currency, balance, overdraft_limit, status, created_at)
  └── account_members (account_id, user_id, role, created_at)

journals (id, kind, initiated_by, idempotency_key, request_id, memo, created_at)
  └── ledger_entries (id, journal_id, account_id, account_seq, amount, balance_after, prev_hash, entry_hash, created_at)

refused_attempts (id, account_id, account_seq, amount, balance_at_attempt, reason_code, initiated_by, request_id, prev_hash, entry_hash, created_at)

idempotency_keys (user_id, key, request_hash, response_status, response_body, created_at)
  └── idempotency_replays (id, user_id, key, same_payload, request_id, created_at)

review_flags (id, journal_id, account_id, flag_code, severity, score, reason, created_at)
  └── review_decisions (id, flag_id, decided_by, decision, reason, created_at)
```

---

## 2. Table Specifications

### `users`
- `id`: UUID (Primary Key, default `gen_random_uuid()`).
- `email`: VARCHAR(255) (UNIQUE, NOT NULL).
- `password_hash`: VARCHAR(255) (Argon2id, NOT NULL).
- `role`: VARCHAR(32) (CHECK `role IN ('admin', 'holder', 'auditor')`).
- `is_active`: BOOLEAN (default `true`).
- `created_at`: TIMESTAMPTZ (default `now()`).

### `accounts`
- `id`: UUID (Primary Key).
- `account_number`: VARCHAR(32) (UNIQUE, NOT NULL, format `100000000000+`).
- `name`: VARCHAR(255) (NOT NULL).
- `kind`: VARCHAR(32) (CHECK `kind IN ('customer', 'external', 'suspense')`).
- `currency`: VARCHAR(3) (CHECK `currency = 'INR'`).
- `balance`: BIGINT (NOT NULL, default `0`).
- `overdraft_limit`: BIGINT (NOT NULL, default `0`, CHECK `overdraft_limit >= 0`).
- `status`: VARCHAR(32) (CHECK `status IN ('active', 'frozen', 'closed')`).
- **Constraint**: `CHECK (balance >= -overdraft_limit)` (enforces balance floor at disk level).

### `journals`
- `id`: UUID (Primary Key).
- `kind`: VARCHAR(32) (CHECK `kind IN ('deposit', 'withdrawal', 'transfer', 'adjustment', 'reversal')`).
- `initiated_by`: UUID (FOREIGN KEY `users.id`).
- `idempotency_key`: VARCHAR(128) (NOT NULL).
- `request_id`: VARCHAR(128) (NOT NULL).
- `memo`: TEXT (Optional).
- `created_at`: TIMESTAMPTZ (NOT NULL, default `now()`).
- **Constraint**: `UNIQUE (initiated_by, idempotency_key)` (prevents double posting).

### `ledger_entries` (Double-Entry Postings)
- `id`: UUID (Primary Key).
- `journal_id`: UUID (FOREIGN KEY `journals.id`, NOT NULL).
- `account_id`: UUID (FOREIGN KEY `accounts.id`, NOT NULL).
- `account_seq`: BIGINT (NOT NULL, strictly monotonically increasing per account).
- `amount`: BIGINT (Signed integer paise, CHECK `amount <> 0`).
- `balance_after`: BIGINT (NOT NULL, cached snapshot after this posting).
- `prev_hash`: BYTEA (NOT NULL, SHA-256 digest of previous record or `\x00` for genesis).
- `entry_hash`: BYTEA (NOT NULL, SHA-256 digest of current row fields).
- `created_at`: TIMESTAMPTZ (NOT NULL, default `now()`).
- **Constraint**: `UNIQUE (account_id, account_seq)` (strict sequence ordering).

### `refused_attempts`
- `id`: UUID (Primary Key).
- `account_id`: UUID (FOREIGN KEY `accounts.id`, NOT NULL).
- `account_seq`: BIGINT (NOT NULL, consumes sequence slot in account's hash chain).
- `amount`: BIGINT (NOT NULL, attempted amount).
- `balance_at_attempt`: BIGINT (NOT NULL, balance snapshot when refusal occurred).
- `reason_code`: VARCHAR(64) (`insufficient_funds`, `account_frozen`, `account_closed`).
- `initiated_by`: UUID (FOREIGN KEY `users.id`, NOT NULL).
- `request_id`: VARCHAR(128) (NOT NULL).
- `prev_hash`: BYTEA (NOT NULL).
- `entry_hash`: BYTEA (NOT NULL).
- `created_at`: TIMESTAMPTZ (NOT NULL, default `now()`).

### `idempotency_keys`
- `user_id`: UUID (FOREIGN KEY `users.id`).
- `key`: VARCHAR(128).
- `request_hash`: BYTEA (SHA-256 of canonical request payload).
- `response_status`: INT (HTTP response status code, NULL while in flight).
- `response_body`: JSONB (Canonical JSON response).
- `created_at`: TIMESTAMPTZ (NOT NULL).
- **Primary Key**: `(user_id, key)`.

---

## 3. PostgreSQL Triggers & Invariant Enforcement

### 1. Immutability Trigger (`forbid_mutation`)
```sql
CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Table % is strictly append-only. UPDATE, DELETE, and TRUNCATE are prohibited.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
```
Attached `BEFORE UPDATE OR DELETE OR TRUNCATE` on:
- `journals`
- `ledger_entries`
- `refused_attempts`
- `idempotency_replays`
- `security_events`
- `review_flags`
- `review_decisions`

### 2. Double-Entry Zero-Sum Deferred Trigger (`journal_sums_to_zero`)
```sql
CREATE CONSTRAINT TRIGGER journal_sums_to_zero
AFTER INSERT ON ledger_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION verify_journal_zero_sum();
```
At transaction `COMMIT`, asserts that $\sum \text{amount} = 0$ for all entries belonging to the journal. Any unilateral debit or credit is automatically aborted.

### 3. Balance Cache Parity Trigger (`account_balance_matches_ledger`)
```sql
CREATE CONSTRAINT TRIGGER account_balance_matches_ledger
AFTER INSERT ON ledger_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION verify_balance_cache_parity();
```
Guarantees that `accounts.balance` strictly equals `ledger_entries.balance_after` of that account's highest sequence number.
