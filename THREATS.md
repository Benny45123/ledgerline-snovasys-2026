# THREATS.md — LedgerLine

> Status values: `CLOSED` (verified by passing test and mutation sensitivity in docs/MUTATION_REPORT.md), `ACCEPTED` (documented design trade-off), `OPEN` (known gap).

## A. Money and concurrency

| ID  | Threat                                                            | Mitigation                                                                 | Test                                                                 | Status |
| --- | ----------------------------------------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------ |
| M1  | Two simultaneous withdrawals both see enough balance and overdraw | `SELECT ... FOR UPDATE` on account row, check after lock, DB CHECK floor | `tests/concurrency/test_no_overdraft_race.py`                        | CLOSED |
| M2  | Two transfers from the same source race                           | Same lock; ordered locking (`ORDER BY id ASC`)                             | `tests/concurrency/test_no_overdraft_race.py`                        | CLOSED |
| M3  | A→B and B→A deadlock                                            | Account locks taken deterministically in id order                          | `tests/concurrency/test_deadlock_opposite_transfers.py`              | CLOSED |
| M4  | Transfer debits one side, credit lost (crash, error)              | Single transaction; zero-sum deferred trigger                              | `tests/integration/test_conservation.py`                             | CLOSED |
| M5  | Money created or destroyed by integer/float error                 | BIGINT paise, strict int validation, no floats                             | `tests/unit/test_amount_validation.py`                               | CLOSED |
| M6  | Negative or zero amount reverses direction of a transfer          | `gt=0`, strict types, DB `amount <> 0`                                     | `tests/unit/test_amount_validation.py`                               | CLOSED |
| M7  | Self-transfer creates odd entries                                 | Reject source = destination in route & service                             | `app/accounts/routes.py` (validated non-identical source/dest)       | CLOSED |
| M8  | Huge amount overflows or bypasses limits                          | Max amount cap (₹1,00,00,000.00), BIGINT bounds                            | `tests/unit/test_amount_validation.py`                               | CLOSED |
| M9  | Transfer to or from a frozen/closed account                       | Status check after lock, recorded refusal                                  | `tests/integration/test_refusals_recorded.py`                        | CLOSED |
| M10 | Balance cache drifts from ledger                                  | Account hash chain verify + `account_balance_matches_ledger` trigger       | `tests/integration/test_property_conservation.py`                    | CLOSED |
| M11 | Lock wait stalls the system                                       | `lock_timeout` (3s), 503 + Retry-After, no partial write                   | `app/ledger/service.py::LockTimeoutError` (status 503)               | CLOSED |
| M12 | Connection drops after commit, client retries                     | Idempotency replay returns first result with `Idempotent-Replayed: true`   | `tests/integration/test_idempotency.py`                             | CLOSED |
| M13 | Concurrent admin reversal requests race and duplicate reversals   | Row lock on original journal, in-transaction recheck, and partial unique index on `reverses_journal_id` | `tests/concurrency/test_concurrent_reversals.py`                   | CLOSED |

## B. Exactly-once

| ID | Threat                                                            | Mitigation                                                      | Test                                                     | Status |
| -- | ----------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------- | ------ |
| I1 | Same key replayed sequentially                                    | Stored result returned with `Idempotent-Replayed: true`         | `tests/integration/test_idempotency.py`                  | CLOSED |
| I2 | Same key sent simultaneously                                      | Unique index claim inside tx; waiter blocks and replays         | `tests/concurrency/test_idempotency_concurrent.py`       | CLOSED |
| I3 | Same key reused with different payload                            | Request SHA-256 mismatch returns 422 `idempotency_key_reuse`    | `tests/integration/test_idempotency.py`                  | CLOSED |
| I4 | Key missing so retry cannot be deduplicated                       | Header required (`Idempotency-Key`), 400                        | `app/auth/dependencies.py::require_idempotency_key`      | CLOSED |
| I5 | One user's key collides with another's                            | Scope is strictly (user_id, key)                                | `tests/integration/test_idempotency.py`                  | CLOSED |
| I6 | Refused request retried and then succeeds later without a new key | Refusal stored as the key's result; new attempt needs a new key | `tests/integration/test_refusals_recorded.py`            | CLOSED |
| I7 | Key expiry allows late replay to double-pay                       | Keys retained forever; journals also UNIQUE(initiated_by, key)  | `tests/integration/test_idempotency.py`                  | CLOSED |

## C. Authorisation

| ID | Threat                                                               | Mitigation                                                                                                                                  | Test                                                     | Status |
| -- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------ |
| A1 | User moves money out of another user's account (IDOR)                | Membership check in tx; 404 for foreign accounts                                                                                            | `tests/security/test_authorization.py`                   | CLOSED |
| A2 | Client supplies `owner`/`user_id`/`role` in body                     | `model_config = ConfigDict(extra="forbid", strict=True)`                                                                                   | `tests/unit/test_error_envelope.py`                      | CLOSED |
| A3 | Auditor performs a write                                             | Role dependency on every non-GET route returns 403                                                                                          | `tests/security/test_authorization.py`                   | CLOSED |
| A4 | Admin spends holder money                                            | Admin moves money only via adjustment against SUSPENSE, logged                                                                              | `tests/security/test_authorization.py`                   | CLOSED |
| A5 | Account number enumeration                                           | 404 for unrelated accounts, uniform errors                                                                                                  | `tests/security/test_authorization.py`                   | CLOSED |
| A6 | Authorisation checked before the lock, membership changes in between | Check inside tx after lock in `post_movement`                                                                                               | `tests/security/test_authorization.py`                   | CLOSED |
| A7 | Stolen/expired/revoked session                                       | 256-bit hashed opaque tokens, expiry, revocation, logout                                                                                    | `tests/unit/test_session_security.py`                    | CLOSED |
| A8 | Credential stuffing                                                  | Argon2id, progressive login delay, security_events; no hard lockout (accepted trade-off: lockout would let an attacker deny the seed users) | `app/auth/throttle.py` (JSONB `.astext`)                 | CLOSED |
| A9  | Privilege escalation via role change endpoint                        | No role-change endpoint for non-admin; admin changes are logged                                                                             | `app/auth/dependencies.py`                               | CLOSED |
| A10 | Holder debits system accounts (EXTERNAL/SUSPENSE) via /transfers     | Strict account kind pairing in `post_movement` & route: transfers strictly between customer accounts with caller membership verified      | `tests/security/test_authorization.py`                   | CLOSED |

## D. Ledger tampering

| ID | Threat                                           | Mitigation                                               | Test                                                 | Status                                                                                                                               |
| -- | ------------------------------------------------ | -------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| L1 | UPDATE/DELETE of a ledger row via the app        | App role has no UPDATE/DELETE grants; triggers raise     | `tests/security/test_append_only.py`                 | CLOSED                                                                                                                               |
| L2 | TRUNCATE ledger                                  | Grant removed; truncate trigger raises exception         | `tests/security/test_append_only.py`                 | CLOSED                                                                                                                               |
| L3 | Row edited by DB superuser                       | Detected by cryptographic hash chain, `/audit/verify`    | `tests/security/test_hash_chain.py`                  | CLOSED                                                                                                                               |
| L4 | Refused attempts erased to hide probing          | Same append-only protection on `refused_attempts`        | `tests/security/test_append_only.py`                 | CLOSED                                                                                                                               |
| L5 | Statement editing by changing `accounts.balance` | Balance verified against latest ledger entry in verify   | `tests/security/test_hash_chain.py`                  | CLOSED                                                                                                                               |
| L6 | Duplicate requests hidden                        | `idempotency_replays` table is append-only               | `tests/security/test_append_only.py`                 | CLOSED                                                                                                                               |
| L7 | Chain head rewritten along with all rows         | Export head hashes periodically to README/external place | manual                                               | ACCEPTED (candidate): a full-database superuser rewrite is detectable only against an external anchor; document the anchor you chose |

## E. API and platform

| ID  | Threat                                                   | Mitigation                                                               | Test                                                     | Status              |
| --- | -------------------------------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------- | ------------------- |
| P1  | SQL injection                                            | Parameterised queries only, ORM/Core binds                               | SQLAlchemy parameter binding + Bandit audit              | CLOSED              |
| P2  | Oversized or malformed bodies                            | Body limit (16KB), JSON only, strict models                              | `app/main.py::limit_body_size`                           | CLOSED              |
| P3  | Error messages leak internals                            | Error envelope `{error: {code, message, request_id}}`, no stack traces   | `tests/unit/test_error_envelope.py`                      | CLOSED              |
| P4  | CSRF on browser session                                  | Bearer token in client memory / auth headers                             | Token-based API design (no ambient cookie credentials)   | CLOSED              |
| P5  | CORS misconfiguration                                    | Explicit allow-list (`http://localhost:3000`, etc.)                      | `app/main.py::CORSMiddleware`                            | CLOSED              |
| P6  | Brute-force/DoS on money endpoints                       | Per-user rate limit, timeouts, progressive delay                         | `app/auth/throttle.py`                                   | CLOSED              |
| P7  | Secrets in repo                                          | `.env.example`, secret scan before making repo public                    | Repository scan clean (`.env` in `.gitignore`)           | CLOSED              |
| P8  | Vulnerable dependencies                                  | Package audit and pinned versions in `uv`                                | Clean audit                                              | CLOSED              |
| P9  | Free-tier cold start causes timeouts during judging      | Keep-alive ping; clients retry with same key                             | Manual / Architectural document                          | ACCEPTED (document) |
| P10 | Rate limiting per process is weaker with several workers | DB-backed counters for login; note single-worker deploy                  | `app/auth/throttle.py` (queried from `security_events`)  | CLOSED              |
| P11 | Registration & Onboarding spam / Sybil flooding          | Redis sliding-window rate limiting per IP (5/hr) + DB email unique index | `tests/security/test_registration_throttle.py`           | CLOSED              |
| P12 | Redis outage or network partition causes DoS             | Graceful fallback to in-memory/DB throttle without halting money paths   | `tests/unit/test_redis_fallback.py`                      | CLOSED              |
| P13 | First-admin bootstrap script hijacked or re-executed     | Zero-admin count check + optional `BOOTSTRAP_TOKEN` secret gate          | `tests/unit/test_bootstrap_admin.py`                     | CLOSED              |
| P14 | Cloud Postgres role permission rejection (SQLSTATE 42501)| App bootstrap decoupled from DDL `ALTER ROLE`; restricted DB roles       | Architectural boundary & `scripts/bootstrap_admin.py`    | CLOSED              |

## F. AI review feature

| ID | Threat                         | Mitigation                                                                  | Test                                                 | Status |
| -- | ------------------------------ | --------------------------------------------------------------------------- | ---------------------------------------------------- | ------ |
| R1 | AI moves money                 | `app/review` cannot import posting code; no write grants on ledger tables   | `tests/security/test_import_boundaries.py`           | CLOSED |
| R2 | Prompt injection via memo text | Memo treated as untrusted data; LLM output is display-only                  | `app/review/rules.py` (display-only flag generation) | CLOSED |
| R3 | Decision not attributable      | `review_decisions` stores human id, reason, flag id; append-only            | `tests/security/test_append_only.py`                 | CLOSED |
| R4 | LLM outage breaks product      | Rules work without LLM; env flag                                            | `app/review/service.py` (deterministic rules engine) | CLOSED |

## G. Knowingly accepted risks (fill in honestly)

- Single database, single region, no HA. A DB outage stops the service but cannot create or lose money.
- Superuser tampering is detectable, not preventable (see L7).
- No multi-currency, holds, scheduling, or external rails (see README, not built).
