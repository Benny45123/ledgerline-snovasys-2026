# Project Status

## Done
- [x] Initial codebase and problem statement review (`AGENTS.md`, `Problem_Statement.md`, `Instructions.md`, `02_FRONTEND.md`).
- [x] Responsive Next.js landing page built matching the design inspiration in `frontend/LedgerLine — money you can prove.html`:
  - 3D interactive phone card with dynamic mouse tilt (`perspective: 1400px`).
  - Interactive scroll storytelling steps (`01 — BOOKS BALANCE`, `02 — EXACTLY ONCE`, `03 — PROVABLE`) driving sticky mockup screens.
  - Provable statement ledger table displaying Dr/Cr, duplicate retry, and refusal rows.
  - Three distinct role cards (`ADMIN`, `ACCOUNT HOLDER`, `AUDITOR`) with animated visualizers.
  - Scrolling matrix log banner in callout section.
  - Dark/Light mode theme switcher with pre-hydration anti-flicker script and `localStorage` persistence.
  - Responsive across mobile (390px/480px), tablet (768px/900px), laptop (1024px), and desktop (1200px+).
- [x] Created `CHANGELOG.md`, `PROMPTS.md`, `.ai/PROMPTS.md`, and `.ai/PROMPRS.md`.

- [x] Backend setup and ledger schema implementation (PostgreSQL/Supabase + FastAPI + SQLAlchemy 2.x + Alembic):
  - Strict Pydantic v2 schemas (`strict=True`, `extra="forbid"`, integer paise only).
  - SQLAlchemy models matching `ARCHITECTURE.md` (Users, Sessions, Accounts, AccountMembers, Journals, LedgerEntries, RefusedAttempts, IdempotencyKeys, IdempotencyReplays, SecurityEvents, ReviewFlags, ReviewDecisions).
  - PostgreSQL migration scripts (`0001_initial_schema.py`, `0002_triggers_and_roles.py`) with append-only triggers (`forbid_mutation`), deferred zero-sum trigger (`journal_sums_to_zero`), and balance cache parity trigger.
  - Sole ledger writer `app/ledger/service.py::post_movement()` enforcing the 6-phase atomic transaction protocol: deterministic sorted row locks (`ORDER BY id`), post-lock authorization, floor validation, append-only refusal commits, and SHA-256 hash chaining.
  - Argon2id password hashing and 256-bit opaque bearer sessions with progressive delay throttling (no hard lockout).
  - Audit verification engine (`/audit/verify`) validating hash chains, balance cache equality, zero-sum journals, and global conservation.
  - Review surveillance engine with deterministic risk heuristics and strict architectural isolation from ledger writes.
  - Contractual test suite verifying invariants, concurrency races, idempotency replays, deadlock immunity, and append-only constraints.
- [x] Complete backend security audit and code review documented in [`docs/BACKEND_AUDIT_REPORT.md`](file:///workspace/docs/BACKEND_AUDIT_REPORT.md):
  - Catalogued 9 concrete vulnerabilities and bugs across auth, ledger, accounts, review, and PostgreSQL triggers.
  - Documented broken test suite interfaces and directory paths.
  - Provided prioritized remediation roadmap with code-level defensive patches.
  - Scoped application stylesheet `frontend/app/app/app.css` under `.app-root` with zero global pollution or keyframe collisions.
  - Interactive authentication screen with optional demo role selector gated by `NEXT_PUBLIC_DEMO_MODE`, progressive throttle safety, and ambient video player (`app-hero.mp4` / `app-poster.jpg`) with `prefers-reduced-motion` safety detection.
  - Responsive application shell with sticky top navbar (`.nv`), role chip, theme toggle, and mobile bottom bar (`.bb` $\le 900$px).
  - Dashboard view with 4 live server-computed KPIs (Balance, Credits received, Debits sent, Refused attempts), Net Movement bar chart with hover tooltips, and account card with deposit/withdraw/transfer quick actions.
  - Keyset statement table with cursor-based pagination ("Load more"), real `has_more` and `next_after` indicators, Dr/Cr styling (`.pos`, `.neg`), sequence numbers, timestamps, and refusal records (`Refused · insufficient_funds`).
  - Move Money modal with 2-step review, fee ₹0.00, client-generated `Idempotency-Key` UUID, non-optimistic posting state, payload locking after unknown outcome failures, and duplicate replay verification retry.
  - Audit explorer with live `/audit/verify` verification trigger mapping discrepancy reports to a 4-point health matrix, real SHA-256 block hashes from the ledger, and an isolated tampering simulation demo overlay.
  - Admin operations view with live account freeze/unfreeze switches, SUSPENSE adjustments, and AI review queue.
  - Floating toast notifications rendering standardized RFC error envelopes `{code, message, request_id}`.
  - Type-safe HTTP client `frontend/lib/api.ts` and exact integer paise currency utilities `frontend/lib/money.ts`.
  - Restored landing page (`/`) to match `frontend/LedgerLine — money you can prove.html` identically.

- [x] Backend Security, Integrity, and Audit Remediation (`docs/backend_security_and_integrity_fix_plan.md`):
  - Fixed VULN-01 through VULN-09 and GAPs 01–07 from `docs/BACKEND_AUDIT_REPORT.md`.
  - Implemented Phase 3 caller authorization in `post_movement()` for admin adjustments/reversals and customer transfers (`AccountMember`).
  - Removed `.with_for_update()` contention on IdempotencyKey replays; mapped 55P03/57014 timeouts to domain `LockTimeoutError` (503 Retry-After).
  - Enforced transfer destination validation (blocking customer-to-system transfers) and self-transfer prevention.
  - Connected surveillance pipeline (`evaluate_transaction_for_flags`) to post-commit hooks for all money movements.
  - Resolved trigger violation on review decision updates by deriving review flag status dynamically from append-only `review_decisions`.
  - Guarded HTTP `Content-Length` header parsing and enforced 16 KB body size limit.
  - Optimized `/audit/verify` with bulk queries, cutting latency from ~36s to ~7.4s.
- [x] Concurrency & Invariant Verification:
  - 20-thread race test (`test_no_overdraft_race.py`) verified: ₹100 account, 20 concurrent ₹30 withdrawals -> exactly 3 succeed, 17 cleanly refused, final balance ₹10.
  - 20-thread deadlock test (`test_deadlock_opposite_transfers.py`) verified: concurrent A<->B transfers without deadlock.
  - 20-thread concurrent idempotency test (`test_idempotency_concurrent.py`) verified: 1 original journal + 19 exact replays.
  - Hypothesis property-based testing (`test_property_conservation.py`) verified: zero-sum conservation ($I_1$) and floor ($I_2$) hold across arbitrary pseudo-random operation sequences.
- [x] Automated Mutation Testing (`scripts/mutation_check.sh`):
  - 5/5 mutations killed (row lock, balance floor check, idempotency claim, append-only triggers, membership authorization).
  - Cross-platform Python replacement helper (`mutate_service`) verified live on macOS (`apple@Apples-MBP`).
  - Generated contractual evidence report [`docs/MUTATION_REPORT.md`](file:///workspace/docs/MUTATION_REPORT.md).
- [x] Threat Model Verification (`THREATS.md`):
  - Updated all 46 threat rows to `CLOSED` referencing passing tests.
- [x] Dynamic 12-Day Net Movement Chart (`frontend/app/app/page.tsx`):
  - Live ledger aggregation across 12 calendar days with dynamic scaling, rupee tooltips, and `.neg-net` tinting.
- [x] Atomic Account Switching & Keyset Statement Pagination:
  - Eliminated stale closure in `refreshStatements()` and fixed `UndefinedTable` SQL query alias error in `get_account_statement()` (`backend/app/ledger/queries.py`).
- [x] Submission Write-Up & Evaluation Form Answers (`docs/WRITEUP.md`):
  - 750-word comprehensive write-up and exact answers to the 6 hackathon submission questions.
- [x] Dynamic Multi-Factor Fraud Risk Scoring & Copilot Presentation Scoping:
  - Replaced static `score = 5` with a dynamic multi-factor engine in `backend/app/review/analytics.py` evaluating administrative governance/freeze (+45), recent 48h and lifetime refusals (+12 to +40), active compliance surveillance flags (+20 to +35), balance drain ratio (>75%/95% of inflows drained) (+10 to +20), rapid succession transactions (<180s apart) (+12), velocity bursts, and outlier outflows (+15 to +18).
  - Scoped Global Ledger Reconciliation card in `backend/app/review/copilot.py` and `frontend/app/app/page.tsx` strictly to explicit reconciliation queries (`intent === "reconciliation"`) or the global auditor view (`!currentAccount`), eliminating global card spam when inspecting customer accounts.
  - Scoped the full circular SVG risk gauge card to `intent === "anomaly"` or elevated risk (`risk_score >= 35`), keeping normal query responses clean with the top compact insight pill.
  - Added unit test `test_dynamic_risk_scoring_and_reconciliation_scoping` in `backend/tests/unit/test_copilot.py` (8/8 tests passing).
- [x] Interactive Copilot Deep-Linking & Clickable Proofs (`backend/app/review/copilot.py`, `backend/app/review/analytics.py`, `frontend/app/app/page.tsx`, `frontend/app/app/app.css`):
  - Natural language intent routing for previous transactions, history, transfers, statement, and action queries.
  - Backend search & metrics enriched with sequence numbers `#<seq>` and `account_id`.
  - Refined Copilot UI to match `frontend/LedgerLine — app.html` prototype identically:
    - Removed repetitive 4-button proof-nav-bar and tool tag chips from assistant messages.
    - Rendered clean `.ac` search card with standard `.sr` rows (no clunky "Clickable Proofs" header or "Jump ↗" badges).
    - Ample vertical padding and height (`min-height: 52px; padding: 13px 16px; gap: 14px;`) with clean typography.
    - Clicking any transaction item in the card or `#<seq>` in chat navigates directly to that transaction in Statement with account switching, filter clearing, scrolling, and animated emerald pulse highlight.

- [x] BalanceVault Execution Plan (organizer addendum):
  - [x] Documentation alignment: `docs/Problem_Statement.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `THREATS.md`, `docs/UNFINISHED.md`, `README.md`, `docs/WRITEUP.md`.
  - [x] Execution plan artifact generated (`balancevault_execution_plan.md`) and accepted by human operator.
  - [x] Account management & user onboarding backend endpoints (`POST /auth/register`, `GET /admin/users`, `POST /admin/users`, `POST /admin/users/{user_id}/status`).
  - [x] Frontend user onboarding flow (registration tab on auth screen with instant primary customer account) and Admin User Management Directory panel with status toggle and live refresh.
  - [x] Redis distributed sliding-window rate limiting (`backend/app/rate_limit.py`) with thread-safe in-memory fallback, attached to `/auth/login`, `/auth/register`, and money movements (`deposit`, `withdraw`, `transfer`).
  - [x] Dedicated first-admin bootstrap script (`scripts/bootstrap_admin.py`) with zero-admin guard and role permission isolation.
  - [x] Enriched deployment health and readiness checks (`/health`, `/ready` verifying both PostgreSQL and Redis connectivity).
- [x] Admin Operations UI Refinement:
  - Removed cluttered User Directory table and bulk account list from the Admin Operations view per operator instructions.
  - Restored clean, fintech-grade layout matching `frontend/LedgerLine — app.html`: side-by-side Accounts & Adjustment cards, followed by the focused AI Review Queue ("Suggestions only. A person decides, and the decision is recorded. No flags waiting for review.").
- [x] Institutional Account Request & Admin Approval Flow (`POST /auth/register`, `GET /accounts/requests/mine`, `POST /accounts/requests`, `POST /review/flags/{flag_id}/decision`):
  - New users register without unvetted vault creation. A pending `AccountRequest` is recorded and an `account_request` flag is queued in the Admin Review Queue.
  - Zero-account state: newly registered users see clean default zeros across all KPIs (`₹0.00` balance, `+₹0.00` credits, `−₹0.00` debits, `0` refusals) and an interactive 3-step Fintech Onboarding Status Stepper card (`🟡 APPLICATION UNDER REVIEW`).
  - Admin Review Queue: reviews the onboarding flag with zero UI bloat ("Suggestions only. A person decides, and the decision is recorded. No flags waiting for review.").
  - Approval / Dismissal: approving automatically provisions the double-entry customer vault via `create_customer_account` in an atomic transaction, activates the vault with `₹0.00` ready for transfers and statements, records an append-only `ReviewDecision`, and logs audit trail `SecurityEvent`.
  - Automated integration test `backend/tests/integration/test_account_onboarding_approval.py` passes completely (2/2 tests green).

- None (all planned deliverables completed).

## Blocked
- None.

## Next Steps
1. End-to-end integration and smoke run against target cloud deployment (Neon PostgreSQL + Redis).
2. Final code freeze ahead of submission deadline.


