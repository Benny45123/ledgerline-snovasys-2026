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

## In Progress
- [ ] Final smoke check of live deployment and incognito demo credentials.

## Blocked
- None.

## Next Steps
- Final deployment verification (backend on Render/Fly, frontend on Vercel).
- Prepare 5-minute video walkthrough following `.ai/WALKTHROUGH.md` and `docs/WRITEUP.md`.
- Tick "I am done. Submit this for evaluation" before Thursday deadline.


