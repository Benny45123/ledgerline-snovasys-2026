
# AGENTS.md — LedgerLine (master rules for every AI agent in this repo)

> Read this file fully before every task. If a task conflicts with it, stop and tell the human.

## Read order (mandatory, before any task)

1. `docs/agent/00_READ_FIRST.md` (precedence, session start/end protocol, kickoff)
2. This file, then `docs/ARCHITECTURE.md`
3. `docs/agent/AGENT_POSTGRES_DIRECTIVE.md` (database: PostgreSQL only, never SQLite)
4. By task: `01_BACKEND.md`, `02_FRONTEND.md`, `03_SECURITY.md`, `04_TESTING.md`, `05_DEPLOYMENT.md`, `06_DOCS_AND_SUBMISSION.md`, `07_AI_FEATURE_AND_HONESTY.md`, `08_WORKFLOW_AND_COORDINATION.md`, `BUILD_PLAN.md` (all in `docs/agent/`)
5. Status files: `.ai/STATUS.md`, `.ai/HANDOFF.md`

Never hide AI use: the README and PROMPTS.md disclose the tools and the real mistakes. Never invent PROMPTS entries, claims, or results.

## 0. Context

- Challenge: Snovasys Fresher Hiring Challenge 2026, "LedgerLine, money movement with a ledger you can prove".
- Deadline: Thursday 12 November 2026, 6:00 PM IST. Freeze code by Thursday 12:00.
- Marks: 35 integrity and security, 15 threat thinking, 15 functionality, 15 AI usage (PROMPTS.md), 10 engineering quality, 10 docs/deploy/demo.
- One rupee created, lost, or moved by the wrong person costs most of the 35. A small system that is always right beats a large one that leaks.
- The owner is a student who must explain every line live in an interview and change it on the spot. Therefore:
  - Prefer boring, explicit, readable code over clever code.
  - After finishing any module, add a 5 to 10 line "How this works / why it is safe" docstring at the top of the file.
  - Never add a dependency or pattern you cannot explain in two sentences.

## 1. Invariants (the system's laws)

| ID | Invariant                                                                                                                                                                                                          |
| -- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| I1 | Conservation. Every journal's entries sum to exactly 0. Sum of ALL account balances (including the external/world account) is always 0. Sum of customer balances = total deposits minus total withdrawals.         |
| I2 | Floor. `balance >= -overdraft_limit` (default limit 0). Enforced in server code AND by a DB CHECK constraint.                                                                                                    |
| I3 | Exactly once. A money-moving request with the same (user, idempotency key) moves money at most once and always returns the first result.                                                                           |
| I4 | Append-only. Ledger rows, refused attempts, replay log, security events and AI decisions can never be updated or deleted, by the app role or by accident. Tampering by a superuser is detectable via a hash chain. |
| I5 | Every attempt is recorded: each posting AND each refusal, with running balance and initiator.                                                                                                                      |
| I6 | Authorisation is decided by the server on every request from DB state, never from client-supplied fields.                                                                                                          |
| I7 | `accounts.balance` always equals the `balance_after` of that account's latest ledger entry (it is a cache, and it is verified).                                                                                |
| I8 | AI never moves money. A human authorises. Suggestion and human decision are both stored.                                                                                                                           |

## 2. Stack (decided, do not change without asking)

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x (sync, psycopg3), Alembic, Pydantic v2, argon2-cffi, structlog. Package manager: `uv`.
- DB: PostgreSQL 16 (Neon or Supabase for deploy; docker compose locally). READ COMMITTED + explicit row locks + DB constraints.
- Frontend: Next.js (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, Framer Motion, three.js via `@react-three/fiber` + `@react-three/drei`.
- Tests: pytest, pytest-timeout, hypothesis, httpx, real PostgreSQL (never SQLite, never mocks for money paths).
- Quality gates: ruff, mypy --strict (on `app/ledger`), bandit, pip-audit, eslint, `tsc --noEmit`.
- Deploy: backend on Render (or Fly), DB on Neon, frontend on Vercel. Deploy a skeleton on DAY 1.

## 3. Money rules

- Money is an integer number of paise (`BIGINT` in DB, `int` in Python). Never `float`. Never `Decimal` in money paths. No rounding exists anywhere.
- Single currency: INR. Reject any other currency code.
- Pydantic models for money requests: `model_config = ConfigDict(extra="forbid", strict=True)`, `amount: int = Field(gt=0, le=MAX_AMOUNT)`. Reject booleans, strings, floats, negative, zero, and amounts above the cap.
- The UI converts rupees to paise at the form boundary and back for display only.

## 4. The only way money moves

All money movement goes through ONE function: `app/ledger/service.py::post_movement()`. No other module may write to `journals`, `ledger_entries`, `refused_attempts`, or `accounts.balance`. A test greps the codebase and fails if any other module does.

`post_movement()` runs in one DB transaction and follows ARCHITECTURE.md section 4 exactly:

1. Claim the idempotency key (insert; on conflict wait, then replay the stored result).
2. Lock the involved account rows `SELECT ... FOR UPDATE ORDER BY id` (deterministic order prevents deadlocks).
3. Authorise against membership read inside the transaction after the lock.
4. Validate status, currency, floor.
5. On refusal: write a `refused_attempts` row, store the refusal as the key's result, COMMIT (do not roll back; the refusal is a record).
6. On success: write the journal, the entries (with `account_seq`, `balance_after`, hashes), update balances, store the result, COMMIT.
7. Unexpected exception: roll back everything including the key claim, return 500 (client may safely retry).

Set `lock_timeout` (3s) and `statement_timeout` (10s) per transaction. Map lock timeouts to 503 with `Retry-After`, never to a partial success.

## 5. Idempotency rules

- `Idempotency-Key` header is REQUIRED on deposit, withdraw, transfer, adjustment, reversal. Missing means 400. Length 16 to 128, charset `[A-Za-z0-9_-]`.
- Scope: (user_id, key). Store a SHA-256 of the canonical request body. Same key + different body means 422 `idempotency_key_reuse`.
- Replay returns the identical status code and body plus header `Idempotent-Replayed: true`, and appends a row to `idempotency_replays` (append-only) so duplicates are visible in the data.
- A retry that arrives while the first is in flight blocks on the unique index until the first commits, then replays. It never runs twice.
- Keys are kept forever in the MVP, and `journals(initiated_by, idempotency_key)` is also UNIQUE. Document this retention choice in THREATS.md.

## 6. Ledger integrity rules

- Double-entry: every journal has 2 or more entries with signed amounts summing to 0 (deferred constraint trigger checks at COMMIT).
- Deposits and withdrawals post against a system `EXTERNAL` account so the zero-sum law holds globally.
- Append-only enforcement, all of these, layered:
  1. Runtime DB role `ledgerline_app` has no UPDATE, DELETE, or TRUNCATE on ledger tables (GRANT only INSERT, SELECT). Migrations run as a different owner role.
  2. `BEFORE UPDATE OR DELETE` and `BEFORE TRUNCATE` triggers raise an exception.
  3. Per-account hash chain, `entry_hash = sha256(prev_hash || canonical_fields)`, computed by a DB trigger so application code cannot forge it.
  4. `GET /audit/verify` recomputes the chain and reconciles balances; a test tampers a row as superuser and proves verify detects it.
- Corrections are made by new reversal journals referencing the original, never by edits.

## 7. AuthN and AuthZ

- Roles: `admin`, `holder`, `auditor`. Matrix lives in ARCHITECTURE.md section 6 and is mirrored in the API docs and in tests.
- Passwords: Argon2id. Sessions: opaque random token (256 bit), stored hashed server-side, expiry and revocation supported. Rate-limit login with progressive delay per (IP, email). Do NOT hard-lock accounts (judges share seed accounts).
- Every endpoint declares its allowed roles via a dependency; account-scoped endpoints additionally check membership in `account_members`. Deny by default. 404 (not 403) for accounts the caller has no relationship to, so account ids cannot be enumerated.
- Never trust `user_id`, `role`, `owner`, or `from_account` ownership claims from the body. Reject unknown fields.
- Auditor is strictly read-only. A test asserts every non-GET route returns 403 for the auditor.
- Admin cannot spend holders' money. Admin actions on balances are only `adjustment` journals against the SUSPENSE account with a mandatory reason, and they appear in the ledger with the admin as initiator.

## 8. API hardening checklist

- Strict CORS allow-list, security headers (HSTS, nosniff, frame deny, CSP on the frontend), request body size limit, JSON-only on write endpoints.
- No stack traces to clients; structured error envelope `{error: {code, message, request_id}}`.
- Every request gets a `request_id`; it is stored on journals and refusals.
- No secrets in git. `.env.example` only. Rotate the seed passwords for deploy and put the demo ones in the README.
- Validate all path and query params (UUID parsing, pagination limits).
- Statements: keyset pagination, max page size 200.

## 9. AI feature rules (optional, build last)

- Purpose: flag unusual transfers and write a reconciliation summary. Deterministic rules first (amount vs account history, velocity, new beneficiary, round-trip, many small transfers). An LLM may only write the narrative explanation on top of those flags.
- AI code lives in `app/review/` and must not import `app.ledger.service` (a test enforces this) and has no DB grants on ledger tables beyond SELECT.
- Tables `review_flags` and `review_decisions` are append-only. A decision records the human who made it, the decision, the reason, and the suggestion it responds to.
- Treat `memo` and any user text as untrusted input to the LLM (prompt injection). Never put instructions from data into prompts unescaped; the LLM output is display text only and cannot trigger any action.
- The product must work fully with the LLM disabled (env flag).

## 10. Testing rules

Tests are evidence for the judges, so they must be able to FAIL.

- Real concurrency: use `threading` with a `Barrier` (or `asyncio.gather` with a start gate) so N requests hit the server at the same instant. Run each race test with 20 or more parallel callers, repeated several times.
- Required test files (names are contractual): `test_conservation.py`, `test_no_overdraft_race.py`, `test_idempotency.py`, `test_authorization.py`, `test_append_only.py`, `test_hash_chain.py`, `test_deadlock_opposite_transfers.py`, `test_refusals_recorded.py`, `test_property_conservation.py` (Hypothesis random op sequences).
- Race assertions must be exact: with balance 100 and 20 parallel withdrawals of 30, EXACTLY 3 succeed, 17 are clean refusals, ZERO responses are 5xx, final balance is exactly 10, and the ledger has exactly 3 withdrawal journals and 17 refused attempts.
- `scripts/mutation_check.sh` removes, one at a time: the `FOR UPDATE`, the balance check, the idempotency unique constraint, the append-only triggers, the membership check. After each removal the test suite MUST fail. If any mutation survives, a test is missing: write it. Print a table of results; commit it to `docs/MUTATION_REPORT.md`.
- Never "fix" a red test by weakening the assertion. Find the root cause.
- Add `locust` or `k6` script in `scripts/load/` for the demo and for final soak: 60 seconds of mixed traffic, then run `/audit/verify` and assert zero discrepancies.

## 11. Frontend rules

- Server is the authority. The UI never computes whether a transfer is allowed; it renders server errors beautifully.
- Generate an `Idempotency-Key` per user intent (`crypto.randomUUID()` when the form opens, reused for retries of the same submit, regenerated only after success or an edit). Disable the button while in flight.
- Design direction: dark, precise, fintech-grade. One accent colour, tabular numerals for amounts, strong typographic hierarchy, skeleton loaders, optimistic UI is FORBIDDEN for money (show confirmed state only).
- three.js is used with purpose: a `LedgerChain3D` component that renders the hash chain as linked blocks on the landing page and the Audit page; verify success pulses green, a detected tamper turns the block red. It must be lazy-loaded (`next/dynamic`, `ssr:false`), respect `prefers-reduced-motion`, and fall back to a static SVG on low-power devices.
- Accessibility: keyboard navigable, visible focus, AA contrast, labelled inputs, `aria-live` on transfer results.
- Screens: Login, Dashboard (accounts), Account detail + Statement (filters, refused attempts styled distinctly), Move Money (deposit, withdraw, transfer), Admin (users, accounts, freeze, adjustments, flags), Auditor (read-only ledger explorer, verify, replay log), AI review queue.

## 12. Process rules

- Commit small and often with conventional messages (`feat(ledger): ...`, `test(race): ...`, `fix(idempotency): ...`). Never rewrite or squash history. Never back-date.
- After each logical unit: run tests and linters, then commit. Do not batch a day's work into one commit.
- Plan before coding. For any money, auth, or schema change, first write a short plan, wait for the human's go-ahead, then implement test-first.
- When the human says something you produced was wrong (a bug, a race, a bad approach), append a candidate entry to `.ai/candidates.md` with the date, the prompt summary, what you produced, what was wrong, and the fixing commit hash. The human turns these into PROMPTS.md entries in their own words. NEVER invent PROMPTS.md entries or claim a bug that did not happen.
- Never claim "done" or "works" without running the code and showing the command output. README, docs and demo may only describe features that exist and pass tests.
- If something is unfinished, say so in `docs/UNFINISHED.md`. Honest gaps score; false claims disqualify.
- Individual assessment: do not use code from other candidates or public copies of this exact challenge.

## 13. Definition of done (per feature)

Code written, types and lint clean, tests including the hostile case written FIRST and passing, mutation check still catches removal of the protection, API doc updated (who may call it, what it does to money), THREATS.md row updated, committed.

## 14. Never do

- Never use floats for money, or read-then-write a balance without the row lock.
- Never do the balance check in the frontend or in a separate transaction from the debit.
- Never catch-and-swallow a database error on a money path.
- Never add an UPDATE or DELETE on ledger tables, or a "cleanup" script that does.
- Never disable a test, loosen a constraint, or grant extra DB privileges to make something pass.
- Never let AI-generated text trigger a write.
