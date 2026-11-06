# THREATS.md — LedgerLine

> SEED FILE. Every row starts as `TO VERIFY`. Change a status to `CLOSED` only after the named test exists, passes, and fails when the protection is removed (see docs/MUTATION_REPORT.md). Never mark something closed that is not. Replace the `Test` cells with real test names. Add threats you discover.

Status values: `TO VERIFY`, `CLOSED`, `ACCEPTED` (with reason), `OPEN` (known, explained).

## A. Money and concurrency

| ID  | Threat                                                            | Mitigation                                                                 | Test                                      | Status    |
| --- | ----------------------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------- | --------- |
| M1  | Two simultaneous withdrawals both see enough balance and overdraw | `SELECT ... FOR UPDATE` on account row, check after lock, DB CHECK floor | test_no_overdraft_race                    | TO VERIFY |
| M2  | Two transfers from the same source race                           | Same lock; ordered locking                                                 | test_no_overdraft_race (transfer variant) | TO VERIFY |
| M3  | A→B and B→A deadlock                                            | Locks taken in id order                                                    | test_deadlock_opposite_transfers          | TO VERIFY |
| M4  | Transfer debits one side, credit lost (crash, error)              | Single transaction; zero-sum deferred trigger                              | test_conservation, fault-injection test   | TO VERIFY |
| M5  | Money created or destroyed by integer/float error                 | BIGINT paise, strict int validation, no floats                             | test_amount_validation                    | TO VERIFY |
| M6  | Negative or zero amount reverses direction of a transfer          | `gt=0`, strict types, DB `amount <> 0`                                 | test_amount_validation                    | TO VERIFY |
| M7  | Self-transfer creates odd entries                                 | Reject source = destination                                                | test_validation                           | TO VERIFY |
| M8  | Huge amount overflows or bypasses limits                          | Max amount cap, BIGINT bounds                                              | test_amount_validation                    | TO VERIFY |
| M9  | Transfer to or from a frozen/closed account                       | Status check after lock, recorded refusal                                  | test_frozen_account                       | TO VERIFY |
| M10 | Balance cache drifts from ledger                                  | Deferred trigger + `/audit/verify`                                       | test_balance_cache_matches_ledger         | TO VERIFY |
| M11 | Lock wait stalls the system                                       | `lock_timeout`, 503 + Retry-After, no partial write                      | test_lock_timeout                         | TO VERIFY |
| M12 | Connection drops after commit, client retries                     | Idempotency replay returns first result                                    | test_idempotency                          | TO VERIFY |

## B. Exactly-once

| ID | Threat                                                            | Mitigation                                                      | Test                        | Status    |
| -- | ----------------------------------------------------------------- | --------------------------------------------------------------- | --------------------------- | --------- |
| I1 | Same key replayed sequentially                                    | Stored result returned                                          | test_idempotency            | TO VERIFY |
| I2 | Same key sent simultaneously                                      | Unique index claim inside tx; waiter replays                    | test_idempotency_concurrent | TO VERIFY |
| I3 | Same key reused with different payload                            | Request hash mismatch returns 422                               | test_idempotency_key_reuse  | TO VERIFY |
| I4 | Key missing so retry cannot be deduplicated                       | Header required, 400                                            | test_missing_key            | TO VERIFY |
| I5 | One user's key collides with another's                            | Scope is (user, key)                                            | test_key_scope              | TO VERIFY |
| I6 | Refused request retried and then succeeds later without a new key | Refusal stored as the key's result; new attempt needs a new key | test_refusal_replay         | TO VERIFY |
| I7 | Key expiry allows late replay to double-pay                       | Keys retained forever; journals also UNIQUE(initiated_by, key)  | test_late_replay            | TO VERIFY |

## C. Authorisation

| ID | Threat                                                               | Mitigation                                                                                                                                  | Test                   | Status    |
| -- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | --------- |
| A1 | User moves money out of another user's account (IDOR)                | Membership check in tx; 404 for foreign accounts                                                                                            | test_authorization     | TO VERIFY |
| A2 | Client supplies `owner`/`user_id`/`role` in body               | `extra="forbid"`, identity only from session                                                                                              | test_mass_assignment   | TO VERIFY |
| A3 | Auditor performs a write                                             | Role dependency on every non-GET                                                                                                            | test_auditor_read_only | TO VERIFY |
| A4 | Admin spends holder money                                            | Admin moves money only via adjustment against SUSPENSE, logged                                                                              | test_admin_limits      | TO VERIFY |
| A5 | Account number enumeration                                           | 404 for unrelated accounts, uniform errors                                                                                                  | test_enumeration       | TO VERIFY |
| A6 | Authorisation checked before the lock, membership changes in between | Check inside tx after lock                                                                                                                  | test_membership_race   | TO VERIFY |
| A7 | Stolen/expired/revoked session                                       | Hashed opaque tokens, expiry, revocation, logout                                                                                            | test_sessions          | TO VERIFY |
| A8 | Credential stuffing                                                  | Argon2id, progressive login delay, security_events; no hard lockout (accepted trade-off: lockout would let an attacker deny the seed users) | test_login_throttle    | TO VERIFY |
| A9 | Privilege escalation via role change endpoint                        | No role-change endpoint for non-admin; admin changes are logged                                                                             | test_role_changes      | TO VERIFY |

## D. Ledger tampering

| ID | Threat                                             | Mitigation                                               | Test                              | Status                                                                                                                               |
| -- | -------------------------------------------------- | -------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| L1 | UPDATE/DELETE of a ledger row via the app          | No grants; triggers raise                                | test_append_only                  | TO VERIFY                                                                                                                            |
| L2 | TRUNCATE ledger                                    | Grant removed; truncate trigger                          | test_append_only                  | TO VERIFY                                                                                                                            |
| L3 | Row edited by DB superuser                         | Detected by hash chain, `/audit/verify`                | test_hash_chain                   | TO VERIFY                                                                                                                            |
| L4 | Refused attempts erased to hide probing            | Same append-only protection                              | test_append_only                  | TO VERIFY                                                                                                                            |
| L5 | Statement editing by changing `accounts.balance` | Deferred trigger ties balance to ledger                  | test_balance_cache_matches_ledger | TO VERIFY                                                                                                                            |
| L6 | Duplicate requests hidden                          | `idempotency_replays` append-only                      | test_replay_log                   | TO VERIFY                                                                                                                            |
| L7 | Chain head rewritten along with all rows           | Export head hashes periodically to README/external place | manual                            | ACCEPTED (candidate): a full-database superuser rewrite is detectable only against an external anchor; document the anchor you chose |

## E. API and platform

| ID  | Threat                                                   | Mitigation                                                               | Test              | Status              |
| --- | -------------------------------------------------------- | ------------------------------------------------------------------------ | ----------------- | ------------------- |
| P1  | SQL injection                                            | Parameterised queries only, ORM/Core binds                               | bandit + test     | TO VERIFY           |
| P2  | Oversized or malformed bodies                            | Body limit, JSON only, strict models                                     | test_input_limits | TO VERIFY           |
| P3  | Error messages leak internals                            | Error envelope, no traces                                                | test_error_shape  | TO VERIFY           |
| P4  | CSRF on browser session                                  | Bearer token in memory or SameSite cookie + CSRF token (document choice) | test_csrf         | TO VERIFY           |
| P5  | CORS misconfiguration                                    | Explicit allow-list                                                      | test_cors         | TO VERIFY           |
| P6  | Brute-force/DoS on money endpoints                       | Per-user rate limit, timeouts                                            | test_rate_limit   | TO VERIFY           |
| P7  | Secrets in repo                                          | `.env.example`, secret scan before making repo public                  | gitleaks          | TO VERIFY           |
| P8  | Vulnerable dependencies                                  | `pip-audit`, `npm audit` in `make check`                           | CI output         | TO VERIFY           |
| P9  | Free-tier cold start causes timeouts during judging      | Keep-alive ping; clients retry with same key                             | manual            | ACCEPTED (document) |
| P10 | Rate limiting per process is weaker with several workers | DB-backed counters for login; note single-worker deploy                  | manual            | TO VERIFY           |

## F. AI review feature

| ID | Threat                         | Mitigation                                                                  | Test                  | Status    |
| -- | ------------------------------ | --------------------------------------------------------------------------- | --------------------- | --------- |
| R1 | AI moves money                 | `app/review` cannot import posting code; no write grants on ledger tables | test_ai_cannot_post   | TO VERIFY |
| R2 | Prompt injection via memo text | Memo treated as untrusted data; LLM output is display-only                  | test_prompt_injection | TO VERIFY |
| R3 | Decision not attributable      | `review_decisions` stores human id, reason, flag id; append-only          | test_review_audit     | TO VERIFY |
| R4 | LLM outage breaks product      | Rules work without LLM; env flag                                            | test_llm_disabled     | TO VERIFY |

## G. Knowingly accepted risks (fill in honestly)

- Single database, single region, no HA. A DB outage stops the service but cannot create or lose money.
- Superuser tampering is detectable, not preventable (see L7).
- No multi-currency, holds, scheduling, or external rails (see README, not built).
- Add your own as you discover them. An honest "this is still open under this condition" scores; a false "closed" does not.
