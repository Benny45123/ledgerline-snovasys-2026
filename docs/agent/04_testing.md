
# 04_TESTING — tests that can fail, mutation checks, load and attack scripts

Audience: AI agents. The judges will remove one lock or one check and run our tests. If the tests still pass, they were not testing anything. Every test here must be able to fail.

## 1. Tooling

- `pytest`, `pytest-timeout` (default 60 s, race tests 30 s), `hypothesis`, `httpx` (TestClient against the real app for API tests, real HTTP server for concurrency tests), `schemathesis` (OpenAPI fuzzing), `locust` or `k6` (load), `playwright` (frontend e2e).
- Real PostgreSQL only (see Postgres directive section 6). Database state strategy: fresh DB per session from migrations; per-test unique users/accounts; dedicated fresh DB for global-invariant tests.
- `make check` runs: ruff, mypy, bandit, pip-audit, pytest (unit + integration + concurrency), frontend lint/types/unit. `make test-race` repeats race tests 10 times. `make mutate` runs the mutation script.

## 2. Test helper contract

`tests/helpers/concurrency.py`:

- `fire_concurrent(n, fn, *, start_barrier=True)` runs `fn(i)` in `n` threads, all released at the same instant through a `threading.Barrier`, returns results list in order and any exceptions. Use a thread pool bigger than `n` and an HTTP client per thread.
- `new_user(role)`, `new_account(owner, balance=...)` (opening balance via the real deposit path), `auth_headers(user)`, `idem_key()` helpers.
- `ledger_snapshot(account_id)` returns entries, refusals, balance, and chain status read through the owner connection for assertions.
  Never sleep to "wait for the race". Synchronise with barriers and assert exact outcomes.

## 3. Required tests and exact assertions

| File                                     | Scenario                                                                                                                               | Exact assertions                                                                                                                                                 |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_conservation.py`                 | Mixed deposits, withdrawals, transfers (sequential), on a fresh DB                                                                     | Every journal sums to 0; global balance sum is 0; customer total equals deposits minus withdrawals; `/audit/verify` clean                                      |
| `test_property_conservation.py`        | Hypothesis stateful machine: ops = deposit, withdraw, transfer, replay-same-key, refused attempt                                       | After EVERY step: invariants I1, I2, I7 hold; replays never change balances; refused attempts recorded                                                           |
| `test_no_overdraft_race.py`            | Balance 100, 20 parallel withdrawals of 30 (also transfer variant, mixed withdraw+transfer, 50 parallel)                               | EXACTLY 3 successes, 17 refusals (409), ZERO 5xx, final balance exactly 10, exactly 3 withdrawal journals and 17 refused attempts in the ledger. Repeat 10 times |
| `test_deadlock_opposite_transfers.py`  | 40 parallel transfers alternating A to B and B to A, 20 iterations                                                                     | No deadlock errors, no 5xx, conservation holds, total of A+B unchanged                                                                                           |
| `test_idempotency.py`                  | Same key replayed sequentially                                                                                                         | Second response identical (status, body) plus `Idempotent-Replayed: true`; exactly one journal; one replay row                                                 |
| `test_idempotency_concurrent.py`       | 50 parallel requests with one key                                                                                                      | Exactly one journal; all responses identical; replay rows = 49                                                                                                   |
| `test_idempotency_key_reuse.py`        | Same key, different amount/destination                                                                                                 | 422 `idempotency_key_reuse`; nothing moved by the second call                                                                                                  |
| `test_idempotency_scope.py`            | Two users send the same key string                                                                                                     | Both succeed independently                                                                                                                                       |
| `test_refusals_recorded.py`            | Insufficient funds, frozen account                                                                                                     | 409; refusal row with running balance and initiator; appears in statement in correct sequence; replay returns same 409                                           |
| `test_authorization.py`                | holder2 against holder1's accounts on every account-scoped route; auditor on every non-GET route; holder on admin routes; no/bad token | Correct 401/403/404; no side effects; security events recorded; zero ledger rows created                                                                         |
| `test_mass_assignment.py`              | Extra fields in bodies                                                                                                                 | Rejected 422; nothing persisted                                                                                                                                  |
| `test_amount_validation.py`            | 0, negative, float, string, bool, null, huge, missing                                                                                  | 422; nothing persisted                                                                                                                                           |
| `test_append_only.py`                  | As runtime role: UPDATE/DELETE/TRUNCATE on every ledger/audit table                                                                    | All rejected (privilege or trigger error); as owner (test DB): trigger still rejects                                                                             |
| `test_hash_chain.py`                   | Tamper with a row via owner connection (trigger disabled in test DB), then call verify                                                 | Verify reports the exact account and sequence of the first break; intact DB reports clean                                                                        |
| `test_balance_cache_matches_ledger.py` | Direct balance UPDATE via owner                                                                                                        | Commit fails (deferred trigger) or verify flags it                                                                                                               |
| `test_db_constraints.py`               | Bypass the service via owner connection: negative balance, unbalanced journal, duplicate seq                                           | CHECK / constraint trigger / unique rejects each. These prove the DB backstops independent of Python                                                             |
| `test_lock_timeout.py`                 | Hold a row lock in another connection                                                                                                  | 503 + Retry-After; no partial effects                                                                                                                            |
| `test_crash_rollback.py`               | Inject failure after debit insert                                                                                                      | Nothing persisted; same key can be reused successfully afterwards                                                                                                |
| `test_error_shape.py`                  | Force 500, 404, 422                                                                                                                    | Envelope shape, request id, no internals                                                                                                                         |
| `test_sessions.py`                     | Expiry, logout, revoked token                                                                                                          | 401 afterwards                                                                                                                                                   |
| `test_login_throttle.py`               | Repeated bad logins                                                                                                                    | Progressive delay/429; valid login still works for the seed user                                                                                                 |
| `test_routes_declare_roles.py`         | Iterate all routes                                                                                                                     | Every route has a declared role or an explicit public marker                                                                                                     |
| `test_import_boundaries.py`            | Static import check                                                                                                                    | Only `ledger.service` writes ledger tables; `review` never imports it                                                                                        |
| `test_ai_cannot_post.py`               | Review module under a role without write grants                                                                                        | Any posting attempt fails                                                                                                                                        |
| `test_review_audit.py`                 | Human decision on a flag                                                                                                               | Decision row has human id, reason, flag id; cannot be modified                                                                                                   |

## 4. Mutation check (`scripts/mutation_check.sh`)

Purpose: prove each protection is actually tested. Procedure:

1. Copy the repo to a temp dir (never mutate the working tree). Create a fresh test database and run migrations.
2. For each mutation below: apply it (code patch via a small Python patcher with exact-match asserts, or SQL as owner for DB-level mutations), run the named tests with `-x`, record whether they FAILED (good: mutation killed) or PASSED (bad: mutation survived), then revert.
3. Print a table and write `docs/MUTATION_REPORT.md`. Exit non-zero if any mutation survives.

| ID                                                                               | Mutation                                                         | Must be killed by                                        |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------- |
| MU1                                                                              | Remove `FOR UPDATE` from the account lock query                | `test_no_overdraft_race`, `test_refusals_recorded`   |
| MU2                                                                              | Remove the post-lock balance check in Python                     | `test_no_overdraft_race`                               |
| MU3                                                                              | Remove `ORDER BY id` from the lock query                       | `test_deadlock_opposite_transfers` (run 50 iterations) |
| MU4                                                                              | Drop the idempotency primary key / unique constraint             | `test_idempotency_concurrent`                          |
| MU5                                                                              | Skip the request-hash comparison                                 | `test_idempotency_key_reuse`                           |
| MU6                                                                              | Remove the membership check                                      | `test_authorization`                                   |
| MU7                                                                              | Remove the auditor role guard on a write route                   | `test_authorization`, `test_routes_declare_roles`    |
| MU8                                                                              | Drop append-only triggers                                        | `test_append_only`                                     |
| MU9                                                                              | Re-grant UPDATE/DELETE to the runtime role                       | `test_append_only`                                     |
| MU10                                                                             | Drop the zero-sum constraint trigger                             | `test_db_constraints`, `test_conservation`           |
| MU11                                                                             | Drop the balance_floor CHECK                                     | `test_db_constraints`                                  |
| MU12                                                                             | Drop the hash-chain trigger                                      | `test_hash_chain`                                      |
| MU13                                                                             | Record refusals only by rolling back (do not insert refusal row) | `test_refusals_recorded`                               |
| MU14                                                                             | Check authorisation before taking the lock                       | `test_membership_race` (add this test if missing)      |
| Every surviving mutation means a missing or weak test: write it, re-run, commit. |                                                                  |                                                          |

## 5. Load and soak (`scripts/load/`)

- Locust/k6 scenario: 20 virtual users, mixed deposits, withdrawals, transfers, statements, 60 seconds, deliberately including replays and over-limit withdrawals.
- After the run: call `/audit/verify` and assert zero discrepancies, global sum zero, no 5xx other than 503 under saturation, p95 latency reported in the README (honestly).

## 6. Attack scripts (`scripts/attack/`)

- `attack.py --base-url URL --yes-this-is-mine`: refuses to run unless the flag is present and the URL is localhost or matches the allow-listed own deployment from env. Implements the hostile checklist in 03_SECURITY section 3 end to end, prints PASS/FAIL per scenario with exact counts, and exits non-zero on any FAIL.
- It must create its own users/accounts (via admin credentials from env) so it can run repeatedly against the deployed system.
- Run it against localhost on every milestone and against production on Wednesday and Thursday morning.

## 7. API fuzzing

- `schemathesis run <openapi url> --checks all --auth <token>` against local. Fix every 5xx. Record the command in the README.

## 8. Frontend tests

- Vitest: `money.ts` (parsing/formatting edge cases), `idempotency.ts` (key lifecycle).
- Playwright: each role's login and navigation, successful transfer, refused transfer rendering, double-click submits exactly one journal (verify through the API), session expiry redirect, auditor has no action buttons, three.js fallback renders with reduced motion.

## 9. Rules

- Never weaken an assertion, add `skip`, or raise a timeout to make a test pass.
- A new bug fix needs a regression test that fails before the fix.
- Flaky concurrency tests are bugs in the code or the test. Fix the root cause. Do not retry-until-green.
- Test names state the behaviour. Each test file starts with a comment: what threat it covers (THREATS.md ID) and what would break if the protection were removed.
