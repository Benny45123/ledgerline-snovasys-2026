# ARCHITECTURE.md — LedgerLine integrity and concurrency model

Place this at `docs/ARCHITECTURE.md` in the repo. Agents implement it; the human must be able to defend every choice in the interview.

## 1. Key decisions and the defence for each

| Decision        | Choice                                                                        | Why (interview answer)                                                                                                                                                                                                  |
| --------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ledger model    | Double-entry: journals + signed entries, plus a system EXTERNAL account       | Conservation becomes a checkable equation: every journal sums to 0, so globally sum(balances)=0. A lost credit is structurally impossible, not just tested.                                                             |
| Atomicity       | One Postgres transaction per movement                                         | Debit, credit, balance update, journal, key result all commit or none do.                                                                                                                                               |
| Isolation       | READ COMMITTED + `SELECT ... FOR UPDATE` on accounts in id order + DB CHECK | Explicit locks are easy to point at in code. Ordered locking prevents A→B / B→A deadlock. The CHECK is a backstop if code is ever wrong. SERIALIZABLE would also work but needs retry loops and is harder to explain. |
| Balance         | Cached `accounts.balance`, verified against ledger                          | O(1) reads, and a deferred trigger plus `/audit/verify` prove cache = ledger.                                                                                                                                         |
| Idempotency     | `(user_id, key)` unique row claimed inside the money transaction            | A concurrent duplicate blocks on the unique index, then replays the stored response. No "in flight" state to get stuck.                                                                                                 |
| Refusals        | Committed rows, not rollbacks                                                 | The statement must show refused attempts, so a refusal is a successful write of a refusal record.                                                                                                                       |
| Tamper-proofing | Revoked privileges + triggers + DB-computed hash chain + verify endpoint      | Layers: prevent (grants, triggers), detect (hash chain). Honest limit: a DB superuser can rewrite everything and the chain; head-hash snapshots exported to the README or an external place raise the bar.              |

## 2. Schema (implement as Alembic migrations; adjust names, keep the constraints)

```sql
-- Roles (run as owner/superuser in migration 0001)
CREATE ROLE ledgerline_app LOGIN PASSWORD '...';          -- runtime
-- ledgerline_owner runs migrations. App role gets only what is listed in GRANTs below.

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE NOT NULL,
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('admin','holder','auditor')),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  token_hash bytea PRIMARY KEY,                           -- sha256 of opaque token
  user_id uuid NOT NULL REFERENCES users(id),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz
);

CREATE TABLE accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  number text UNIQUE NOT NULL,
  name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('customer','external','suspense')),
  currency char(3) NOT NULL CHECK (currency = 'INR'),
  balance bigint NOT NULL DEFAULT 0,
  overdraft_limit bigint NOT NULL DEFAULT 0 CHECK (overdraft_limit >= 0),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','frozen','closed')),
  next_seq bigint NOT NULL DEFAULT 1,                     -- per-account sequence, used under the row lock
  last_hash bytea NOT NULL DEFAULT '\x00',
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT balance_floor CHECK (kind <> 'customer' OR balance >= -overdraft_limit)
);

CREATE TABLE account_members (                            -- who may move money out of an account
  account_id uuid REFERENCES accounts(id),
  user_id uuid REFERENCES users(id),
  PRIMARY KEY (account_id, user_id)
);

CREATE TABLE journals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL CHECK (kind IN ('deposit','withdrawal','transfer','adjustment','reversal')),
  initiated_by uuid NOT NULL REFERENCES users(id),
  idempotency_key text NOT NULL,
  request_id text NOT NULL,
  memo text,
  reverses_journal_id uuid REFERENCES journals(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (initiated_by, idempotency_key)
);

CREATE TABLE ledger_entries (
  id bigserial PRIMARY KEY,
  journal_id uuid NOT NULL REFERENCES journals(id),
  account_id uuid NOT NULL REFERENCES accounts(id),
  account_seq bigint NOT NULL,
  amount bigint NOT NULL CHECK (amount <> 0),             -- + credit, - debit
  balance_after bigint NOT NULL,
  prev_hash bytea NOT NULL,
  entry_hash bytea NOT NULL,                              -- set by BEFORE INSERT trigger
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (account_id, account_seq)
);

CREATE TABLE refused_attempts (
  id bigserial PRIMARY KEY,
  account_id uuid NOT NULL REFERENCES accounts(id),       -- the account the attempt was against
  account_seq bigint NOT NULL,
  kind text NOT NULL,
  counterparty_account_id uuid,
  amount bigint NOT NULL,
  reason_code text NOT NULL,                              -- insufficient_funds, frozen, over_limit...
  balance_at_attempt bigint NOT NULL,
  initiated_by uuid NOT NULL REFERENCES users(id),
  idempotency_key text NOT NULL,
  request_id text NOT NULL,
  prev_hash bytea NOT NULL,
  entry_hash bytea NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (account_id, account_seq)
);

CREATE TABLE idempotency_keys (
  user_id uuid NOT NULL REFERENCES users(id),
  key text NOT NULL,
  request_hash bytea NOT NULL,
  response_status int,
  response_body jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, key)
);

CREATE TABLE idempotency_replays (                        -- proof of duplicates
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL, key text NOT NULL,
  same_payload boolean NOT NULL,
  request_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE security_events (                            -- authz denials, login failures, admin actions
  id bigserial PRIMARY KEY, actor_user_id uuid, event text NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}', request_id text, ip inet,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review_flags (...);      -- AI/rule suggestions, append-only
CREATE TABLE review_decisions (...);  -- human decision, who, why, FK to flag; append-only
```

### Required database-level protections (migration 0002)

```sql
-- 1. Append-only on every ledger/audit table
CREATE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME; END $$ LANGUAGE plpgsql;
-- BEFORE UPDATE OR DELETE ... FOR EACH ROW  and  BEFORE TRUNCATE ... FOR EACH STATEMENT
-- on: journals, ledger_entries, refused_attempts, idempotency_replays, security_events,
--     review_flags, review_decisions

-- 2. Privileges
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ledgerline_app;
GRANT SELECT, INSERT ON journals, ledger_entries, refused_attempts, idempotency_replays,
      security_events, review_flags, review_decisions TO ledgerline_app;
GRANT SELECT, INSERT, UPDATE ON accounts, idempotency_keys, sessions TO ledgerline_app;  -- accounts: see trigger 4
GRANT SELECT, INSERT, UPDATE ON users TO ledgerline_app; GRANT SELECT, INSERT ON account_members TO ledgerline_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ledgerline_app;

-- 3. Zero-sum per journal, checked at COMMIT
CREATE CONSTRAINT TRIGGER journal_sums_to_zero AFTER INSERT ON ledger_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_journal_zero_sum();

-- 4. Balance cache must equal the ledger at COMMIT (accounts.balance = latest balance_after);
--    also blocks UPDATE of accounts.balance/next_seq/last_hash unless a matching entry or refusal exists.
-- 5. BEFORE INSERT on ledger_entries/refused_attempts: set prev_hash from accounts.last_hash and
--    entry_hash = sha256(prev_hash || canonical text of account_id|seq|journal|amount|balance_after|created_at);
--    update accounts.last_hash in the same statement.
-- 6. Non-superuser-owner check: if the host cannot create a second role, document that honestly in
--    THREATS.md (triggers + hash chain remain; grant separation is the missing layer).
```

## 3. The invariant, stated and proven

- Each journal: `SUM(amount) = 0` (trigger 3).
- Whole system: `SELECT SUM(balance) FROM accounts` is 0 at every committed state.
- Customer money: `SUM(balance) WHERE kind='customer'` = `SUM(deposits) - SUM(withdrawals)` plus adjustments (adjustments move against SUSPENSE, so they are included in the system sum but should be reported separately).
- `GET /audit/verify` returns: per-account chain OK, balance cache = ledger, journal sums = 0, global sum = 0, customer total = deposits - withdrawals (+/- adjustments), and the list of any discrepancies.

## 4. `post_movement()` algorithm (exact steps)

```
BEGIN;                                           -- READ COMMITTED
SET LOCAL lock_timeout = '3s'; SET LOCAL statement_timeout = '10s';

-- 1. Claim the key
INSERT INTO idempotency_keys(user_id,key,request_hash) VALUES (:u,:k,:h)
  ON CONFLICT (user_id,key) DO NOTHING;
if 0 rows inserted:                              -- (this INSERT waits if the first request is still in flight)
    SELECT request_hash, response_status, response_body FROM idempotency_keys WHERE ...;
    INSERT INTO idempotency_replays(...);        -- record the duplicate
    COMMIT; if hash differs -> 422 idempotency_key_reuse else return stored response (Idempotent-Replayed: true)

-- 2. Lock (sorted by id, one statement)
SELECT id, balance, overdraft_limit, status, kind, next_seq, last_hash
FROM accounts WHERE id = ANY(:ids) ORDER BY id FOR UPDATE;
if any missing -> 404 (store as the key's result, COMMIT)

-- 3. Authorise (inside the tx, after the lock)
withdraw / transfer-out: caller in account_members of source, or ... nobody else (admin is NOT a member by default)
deposit: caller is member of target (design choice; document it)
adjustment/reversal: caller is admin; reason required
failure -> INSERT security_events; store 403/404 as key result; COMMIT

-- 4. Validate: both accounts active (not frozen/closed), currency, source != destination, amount in range
-- 5. Floor: new_balance = balance - amount; if new_balance < -overdraft_limit -> REFUSE
--    REFUSE = INSERT refused_attempts (takes next_seq), UPDATE accounts SET next_seq/last_hash, store 409 result, COMMIT.
-- 6. Post: INSERT journal; INSERT entries (debit, credit) with account_seq = next_seq++, balance_after;
--          UPDATE accounts SET balance, next_seq, last_hash; store 200 result; COMMIT (deferred triggers verify).
-- Any unexpected exception: ROLLBACK (the key claim vanishes too) and return 500; the client can retry safely.
```

## 5. Failure modes covered by this design

| Scenario                            | What happens                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Two withdrawals race on one balance | Second blocks on `FOR UPDATE`, re-reads the committed balance, gets a recorded refusal                      |
| Same key twice, sequentially        | Second returns stored result, replay logged                                                                   |
| Same key twice, simultaneously      | Second blocks on the unique index, then replays                                                               |
| Same key, different amount          | 422, nothing moves                                                                                            |
| A→B and B→A at once               | Locks taken in id order, no deadlock                                                                          |
| Crash mid-transaction               | Everything rolls back, nothing partial, key not consumed                                                      |
| Code bug removes the lock           | CHECK constraint still stops negative balance (test must fail anyway: 5xx appears and refusal record missing) |
| Someone UPDATEs a ledger row        | Grant denies, trigger raises; superuser edit is caught by hash chain verify                                   |

## 6. Roles and permissions

| Capability                                        | admin                                   | holder                       | auditor                  |
| ------------------------------------------------- | --------------------------------------- | ---------------------------- | ------------------------ |
| Create users / accounts, assign owners            | yes                                     | no                           | no                       |
| Freeze / unfreeze account                         | yes                                     | no                           | no                       |
| View balance and statement                        | all accounts                            | own accounts only            | all accounts (read-only) |
| Deposit                                           | no (unless owner)                       | own accounts                 | no                       |
| Withdraw                                          | no (unless owner)                       | own accounts                 | no                       |
| Transfer from                                     | no (unless owner)                       | own accounts only            | no                       |
| Transfer to                                       | n/a                                     | any active account by number | no                       |
| Adjustment / reversal                             | yes, reason mandatory, against SUSPENSE | no                           | no                       |
| View ledger explorer, replay log, security events | yes                                     | own account only             | yes                      |
| Run `/audit/verify`                             | yes                                     | no                           | yes                      |
| Review AI flags and decide                        | yes                                     | no                           | view only                |

## 7. API surface (agents must produce `docs/API.md` from this, stating caller roles and money effect)

| Method + path                                             | Roles                          | Money effect                        |
| --------------------------------------------------------- | ------------------------------ | ----------------------------------- |
| POST /auth/login, POST /auth/logout, GET /auth/me         | public / any                   | none                                |
| POST /accounts                                            | admin                          | none (creates zero-balance account) |
| GET /accounts, GET /accounts/{id}                         | holder (own), admin, auditor   | none                                |
| GET /accounts/{id}/statement                              | holder (own), admin, auditor   | none                                |
| POST /accounts/{id}/deposit                               | holder (own)                   | + account, - EXTERNAL               |
| POST /accounts/{id}/withdraw                              | holder (own)                   | - account, + EXTERNAL               |
| POST /transfers                                           | holder (source own)            | - source, + destination             |
| POST /admin/adjustments                                   | admin                          | against SUSPENSE                    |
| POST /admin/journals/{id}/reverse                         | admin                          | new reversing journal               |
| POST /admin/accounts/{id}/freeze, /unfreeze               | admin                          | none                                |
| GET /audit/verify, /audit/replays, /audit/security-events | admin, auditor                 | none                                |
| GET /review/flags, POST /review/flags/{id}/decision       | admin (decide), auditor (read) | none (decision only logged)         |

## 8. Scope: build / stretch / deliberately not built

- Build (core): all ten requirements, reversal journals, freeze, hash-chain verify, replay log, security events, rule-based flags with human decision.
- Stretch: LLM narrative on flags, maker-checker (second admin approves large adjustments), daily limit per account.
- Deliberately not built (write these in the README with reasons): multi-currency, scheduled/batch transfers, holds/authorisations, external bank rails, real KYC. Each adds an invariant to defend; the brief prefers a small always-correct system.

---

## 9. BalanceVault Enhancements (November 2026 Addendum)

Following official organizer guidance from Snovasys, the system extends LedgerLine into BalanceVault, incorporating the following production-grade operational components while preserving all core financial invariants ($I_1$ to $I_8$).

### 9.1 Account Management & User Onboarding
- **Self-Service Registration (`POST /auth/register`)**:
  - Open to unauthenticated prospective account holders.
  - Generates an active `User` record with role `holder` and Argon2id password hash.
  - Automatically provisions an initial customer `Account` (e.g., "Primary Savings") with currency `INR`, `balance = 0`, and `overdraft_limit = 0`.
  - Links the user and account in `account_members` in an atomic transaction.
  - Records an append-only `user_registered` event in `security_events`.
  - Rate-limited per IP and email via Redis.
- **Admin User Onboarding & Management (`/admin/users`)**:
  - `GET /admin/users`: Lists registered users, roles, active statuses, and account memberships.
  - `POST /admin/users`: Enables administrators to onboard users with designated roles (`holder`, `auditor`, `admin`).
  - `POST /admin/users/{id}/status`: Allows administrators to suspend or reactivate user logins without deleting historical audit records.

### 9.2 Redis Distributed Rate Limiting Architecture
- **Purpose**: Protect authentication (`/auth/login`, `/auth/register`), account onboarding, and money movement endpoints against credential stuffing, brute force, and volumetric denial of service.
- **Algorithm**: Redis sliding-window counter or token bucket using high-speed atomic scripts / pipelines (`INCR`, `EXPIRE`, or sorted set `ZREMRANGEBYSCORE` + `ZCARD`).
- **Keyspace Hierarchy**:
  - `rl:auth:ip:{client_ip}` (Window: 15 min, Limit: 15 attempts)
  - `rl:auth:email:{normalized_email}` (Window: 15 min, Limit: 15 attempts)
  - `rl:onboard:ip:{client_ip}` (Window: 1 hour, Limit: 5 registrations)
  - `rl:movement:user:{user_id}` (Window: 1 min, Limit: 60 movements)
- **High-Availability & Graceful Fallback**:
  - In environments without Redis or during transient Redis disconnections, the limiter fails gracefully to local in-process / database throttling (`check_login_throttle`).
  - Money movement integrity is never compromised by cache failure.
- **RFC Standard Headers**:
  - Emits `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
  - On limit exhaustion, returns HTTP 429 `rate_limited` with standard error envelope and `Retry-After` header.

### 9.3 First-Admin Bootstrap & PostgreSQL Role Security Model
- **Cloud PostgreSQL (Neon) Privilege Isolation Analysis**:
  - On managed PostgreSQL platforms (such as Neon), database connections operate under restricted project-owner roles lacking global superuser privileges.
  - Naive attempts to run `ALTER ROLE ... WITH PASSWORD` or mutate administrative roles across users trigger SQLSTATE `42501` (`insufficient_privilege`).
  - AI tools often misdiagnose this as a missing grant and recommend granting dangerous superuser rights or executing invalid DDL.
- **Secure Bootstrap Architecture**:
  - Application-level first administrator bootstrapping is decoupled from database role administration.
  - A dedicated bootstrap utility (`scripts/bootstrap_admin.py` and CLI `python -m app.auth.bootstrap`) is provided.
  - **Zero-Admin Invariant Check**: The bootstrap process queries the database:
    $$\text{COUNT}(id) \text{ FROM users WHERE role = 'admin' AND is_active = true}$$
    If an active administrator already exists, execution aborts with error `admin_already_exists`.
  - **Bootstrap Secret Guard**: If configured, `BOOTSTRAP_TOKEN` environment variable must match the invocation argument, preventing unauthorized execution even if no admin exists.
  - **Database Role Enforcement**:
    - `ledgerline_app`: Restricted runtime role used by the FastAPI web service (no DDL, no DELETE/UPDATE on ledger tables).
    - `ledgerline_owner` / bootstrap operator: Migration and bootstrap role with privileges to manage tables and execute security definer functions without granting broad superuser access.

### 9.4 Deployment Health & Readiness Probes
- **`/health` (Process Liveness)**:
  - Lightweight, unauthenticated GET probe returning `{"status": "ok"}`.
  - Verifies that the ASGI event loop and HTTP server are responsive.
- **`/ready` (Dependency Readiness)**:
  - Unauthenticated GET probe validating backing dependencies.
  - Executes `SELECT 1` against PostgreSQL via the active connection pool.
  - Pings Redis (if configured) via `redis.ping()`.
  - Returns `200 OK` with `{"status": "ready", "database": "connected", "redis": "connected"}`.
  - Returns `503 Service Unavailable` with `{"status": "unavailable", "database": "disconnected"}` if any core backing dependency fails.

