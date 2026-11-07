# Changelog

All notable changes to the LedgerLine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-11-07 16:00 IST

### Added

#### [2026-11-07 16:00 IST] Backend Security & Vulnerability Audit Report (`docs/BACKEND_AUDIT_REPORT.md`)
- Delivered comprehensive defensive security audit analyzing ledger invariants, double-entry triggers, concurrency isolation, and RBAC enforcement.
- Cataloged 9 concrete vulnerabilities and architectural discrepancies (VULN-01 to VULN-09) covering downward adjustment authorization, append-only trigger conflicts in review decisions, system account transfer boundaries, and JSONB throttle query syntax.
- Documented broken test suite contracts and import paths (TEST-01) with prioritized code remediations.

#### [2026-11-07 15:38 IST] Multi-Account Switching & Context Selection (`frontend/app/app/page.tsx`)
- Added multi-account switcher dropdown menus to both Overview and Statement headers, enabling holders to seamlessly toggle between multiple owned accounts.

#### [2026-11-07 11:35 IST] Auth Page Video Player & Binary Extraction (`frontend/public/`, `frontend/app/app/`)
- Extracted and decoded embedded base64 video payloads from `frontend/LedgerLine — app.html`:
  - `frontend/public/app-hero.mp4` (1.6 MB H.264 MP4 ambient video).
  - `frontend/public/app-poster.jpg` (79 KB JPEG high-resolution poster).
- Integrated `<video id="lv">` into `/app` authentication panel with automatic muted playback, `prefers-reduced-motion` safety detection, and seamless opacity fading on loop boundaries (`onTimeUpdate` fade-out and `onEnded` replay).

#### [2026-11-07 11:15 IST] Full Interactive Application Interface & Backend Connection (`frontend/app/app/`)
- Built complete Next.js application interface at `/app` faithfully matching `frontend/LedgerLine — app.html`.
- **Auth & Session Hydration**: Implemented sign-in screen with optional demo role switcher gated behind `NEXT_PUBLIC_DEMO_MODE`, login throttling via progressive server delay, and ambient video hero panel (`app-hero.mp4` / `app-poster.jpg`) with reduced-motion support.
- **Dashboard Screen**: Implemented 4 live server-computed KPIs (Balance, Credits received, Debits sent, Refused attempts), Net Movement interactive bar chart with hover tooltips, account card with Deposit/Withdraw/Transfer action triggers, and recent activity table.
- **Statement Screen**: Keyset-paginated ledger entries and committed refusal rows (`Refused · insufficient_funds`) with cursor-based "Load more" pagination, real `has_more` and `next_after` indicators, Dr/Cr styling (`.pos`, `.neg`), sequence numbers, timestamps, and balance-after cache parity.
- **Audit Explorer Screen**: Implemented live `/audit/verify` verification trigger mapping discrepancy reports to a 4-point health matrix (hash chain, balance cache parity, zero-sum journals, global conservation), real SHA-256 block hashes from the ledger, and an interactive tampering simulation demo overlay turning blocks red (`.blk.bad`).
- **Admin Operations Screen**: Implemented account management with live Active/Frozen toggle switches (`/admin/accounts/{id}/freeze`), administrative adjustment form against `SYS-SUSPENSE` with mandatory reason, and AI surveillance flag review queue.
- **Move Money Modal**: Multi-tab dialog (Transfer, Deposit, Withdraw), 2-step review with fee ₹0.00 and Idempotency Key, non-optimistic posting spinner, and result receipt with duplicate replay retry.
- **RFC Error Toasts**: Implemented floating notifications displaying server error envelopes `{code, message, request_id}`.
- **API Client & Money Utilities**: Created `frontend/lib/api.ts` (typed HTTP client with Bearer tokens and idempotency injection) and `frontend/lib/money.ts` (strict integer paise conversion and Indian Rupee formatting).
- **Navigation Links & Redirects**: Updated "Open app" and "Launch app" on the landing page to route to `/app`; created instant client-side route redirects for `/login`, `/dashboard`, `/statement`, `/audit`, and `/admin`.

### Fixed

#### [2026-11-07 15:38 IST] UI Polish & Alignment Refinements (`frontend/app/app/`)
- Removed developer debug cursor text (`has_more: ... · next_after: ... · verified against latest ledger entry`) from statement table footer; replaced with clean centered "Load more entries" button when additional records exist.
- Removed technical jargon footer (`httpOnly session · idempotent writesv1.0`) from the authentication lock screen.
- Fixed `₹` currency symbol vertical alignment in `.app-root .pre` using `top: 50%; transform: translateY(-50%); line-height: 1; padding-left: 38px`, eliminating input placeholder offset.

#### [2026-11-07 14:45 IST] Pydantic v2 Strict Mode UUID String Deserialization (`backend/app/`)
- Added `@field_validator(..., mode="before")` pre-validation hooks on `TransferRequest.from_account_id` and `AdjustmentRequest.account_id` in `backend/app/ledger/schemas.py`.
- Added `@field_validator(..., mode="before")` on `CreateAccountRequest.owner_user_id` in `backend/app/accounts/schemas.py`.
- Resolved HTTP 422 `is_instance_of` validation failures when receiving valid RFC UUID strings in JSON request bodies while preserving `strict=True` and `extra="forbid"`.

#### [2026-11-07 14:15 IST] Code Review Remediation — 10 Findings Fixed (`frontend/app/app/`, `backend/app/`)
- Gated demo role selector and pre-filled credentials behind `NEXT_PUBLIC_DEMO_MODE === "true"`, defaulting form fields to empty strings.
- Retained modal step at `"review"` with payload fields read-only and provided a "Retry same request" action using the identical key and payload on unknown outcome errors.
- Prevented active account context switching on arbitrary admin adjustments.
- Replaced hard-coded "Replays blocked: 1" with live server-computed Debits sent KPI; implemented cursor-based "Load more" statement pagination (`has_more`, `next_after`).
- Gated session token clearance strictly on HTTP 401 unauthenticated responses, preventing logout on transient 5xx or network errors.
- Removed `autoPlay` from `<video id="lv">` and enforced `prefers-reduced-motion` safety detection in `handleVideoEnded`.
- Removed client-side login lockout (`loginFails >= 4`), delegating rate-limiting strictly to backend progressive delay.
- Reset all session-scoped state (`currentTab`, `reviewFlags`, `auditResult`, `moveResult`) on logout and clamped `currentTab` to `allowedTabs`.
- Mapped `/audit/verify` discrepancy categories directly to the 4-point health matrix, displayed real SHA-256 block hashes from statement entries, and isolated the tampering simulation demo overlay.
- Corrected documentation claims across `CHANGELOG.md`, `PROMPTS.md`, `.ai/STATUS.md`, and `.ai/PROMPTS.md`.

#### [2026-11-07 11:35 IST] Auth Page Visual & Typography Fidelity
- Added missing CSS rules for `.app-root .ar video`, `.app-root .ar video.fo`, and the dual-gradient radial vignette overlay `.app-root .ar::after`.
- Fixed typography colors across headings (`.app-root h1, h2, h3` to `var(--fg)`), subtitle (`.af .sub` to `var(--mut)`), and `.logo` (`color: var(--fg)`).
- Ensured right video panel heading (`.aq h2`) displays in crisp white (`#ffffff`) with Instrument Serif italic styling.

#### [2026-11-07 11:15 IST] Landing Page Keyframe Restoration & CSS Isolation
- Restored `frontend/app/globals.css` to match `frontend/LedgerLine — money you can prove.html` identically.
- Resolved `@keyframes up` namespace collision where app styles inadvertently broke the landing page hero text reveal (`.ln > span`).
- Scoped all app styles into `frontend/app/app/app.css` under `.app-root` with prefixed keyframes (`app-up`, `app-grow`, `app-rot`, `app-fi`), guaranteeing zero style leakage to the landing page.

#### [2026-11-06 17:35 IST] Test Suite Stratification (`backend/tests/`)
- **Unit Tests (`backend/tests/unit/`)**:
  - `test_amount_validation.py`: Enforces positive integer paise validation, strict type checks rejecting floats, strings, booleans, negatives, zeros, amounts over `MAX_AMOUNT_PAISE`, and extra payload fields (`extra="forbid"`).
  - `test_hashing_unit.py`: Verifies deterministic canonical JSON hashing (order-independent key sorting) and SHA-256 chain linking computation.
  - `test_error_shape.py`: Verifies RFC/contractual error envelope structure `{"error": {"code", "message", "request_id"}}` and domain exceptions.
  - `test_sessions.py`: Verifies 256-bit cryptographically secure session token generation, SHA-256 storage hashing, and expiration checks.
- **Integration Tests (`backend/tests/integration/`)**:
  - `test_refusals_recorded.py`: Verifies Invariant I5 (every attempt is recorded) ensuring over-limit withdrawal attempts persist an immutable row in `refused_attempts` and commit rejection to the idempotency key without 500 rollbacks.
  - `test_db_constraints.py`: Verifies database-level defense-in-depth independently of Python (balance floor `CHECK (balance >= -overdraft_limit)`, append-only triggers rejecting journal deletions).
- **Concurrency Tests (`backend/tests/concurrency/`)**:
  - `test_idempotency_concurrent.py`: Verifies Invariant I3 (exactly once) under high contention, running 20 parallel threads with identical idempotency keys to prove exactly 1 journal commits and 19 identical replays are logged.

#### [2026-11-06 17:00 IST] Backend Architecture & Money Movement Engine (`backend/app/`)
- Initialized complete FastAPI, SQLAlchemy 2.x, psycopg3, and Pydantic v2 backend service.
- Implemented the single movement gateway `post_movement()` in `app/ledger/service.py` adhering to all 8 system invariants.
- Implemented deterministic lock acquisition (`SELECT ... FOR UPDATE ORDER BY id`) preventing deadlocks and double-spend races.
- Implemented transactional idempotency key claims and replay deduplication with `idempotency_replays` logging.
- Implemented cryptographic per-account hash chains (`prev_hash`, `entry_hash`) and full audit verification engine (`/audit/verify`).
- Implemented Argon2id password hashing, hashed 256-bit opaque sessions, and progressive login throttling.
- Created Alembic database migrations:
  - `0001_initial_schema.py`: Tables for users, sessions, accounts, account_members, journals, ledger_entries, refused_attempts, idempotency_keys, idempotency_replays, security_events, review_flags, review_decisions.
  - `0002_triggers_and_roles.py`: Append-only trigger functions, zero-sum constraint triggers, and balance cache equality triggers.
- Created automated test suite with real concurrency testing (`test_no_overdraft_race.py`, `test_deadlock_opposite_transfers.py`, `test_conservation.py`, `test_idempotency.py`, `test_authorization.py`, `test_append_only.py`, `test_hash_chain.py`, `test_import_boundaries.py`).
- Created idempotent seed module (`python -m app.seed`).

#### [2026-11-06 15:30 IST] Fintech Landing Page UI & Tokens (`frontend/`)
- Implemented responsive landing page matching the high-craft design from `frontend/LedgerLine — money you can prove.html`.
- Responsive design across mobile (390px/480px), tablet/laptop (768px/900px/1024px), and desktop (1200px+).
- Sticky glassmorphic navigation with scroll detection and scroll progress bar indicator.
- Interactive 3D phone mockup in the hero section with dynamic mouse/pointer tilt effect (`perspective: 1400px`) and floating retry toast.
- Interactive storytelling section (`#how`) with 3 synchronized steps (`01 — BOOKS BALANCE`, `02 — EXACTLY ONCE`, `03 — PROVABLE`) linked via `IntersectionObserver` to the sticky phone preview.
- Interactive statement ledger table with distinct styling for credits (`.pos`), debits (`.neg`), duplicate requests (`.chip.b`), and refused withdrawals.
- Three distinct role capability cards (`ADMIN`, `ACCOUNT HOLDER`, `AUDITOR`) featuring bespoke CSS/SVG animations (account limit bar, money transfer flow dot, and hash-chain verification with tamper rejection).
- Animated matrix log streamer in the callout banner (`.band`).
- Dark and Light theme toggle with `localStorage` persistence and immediate pre-hydration theme application to prevent flicker.
- Full support for `prefers-reduced-motion` accessibility standards.
- Added fintech design tokens (`--bg`, `--bg2`, `--fg`, `--mut`, `--line`, `--tint`, `--acc`, `--bad`, `--badt`, `--phone`, `--band`).
- Google typography configuration for `Inter`, `Inter Tight`, `Instrument Serif`, and `JetBrains Mono`.
- Safe area insets for mobile viewports (`viewport-fit=cover`).

### Removed

#### [2026-11-06 17:25 IST] Scaffolding & Dead Code Cleanup
- Removed unused `backend/app/api` directory to align strictly with the domain-driven routes layout defined in `docs/agent/01_backend.md`.
- Removed empty legacy directories (`backend/docs`, `backend/tests/concurrency`, `backend/tests/integration`, `backend/tests/security`, `backend/tests/unit`) and replaced them with structured, tested suites.
- Removed default boilerplate `backend/main.py` from `uv init` in favor of `backend/app/main.py`.


