# Changelog

All notable changes to the LedgerLine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-11-06 17:35 IST

### Added

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


