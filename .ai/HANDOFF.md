# Agent Handoff Notes

### Latest: 2026-11-06 17:05 IST — Backend Core Delivery
- **Files Touched**:
  - `backend/app/config.py`: Environment configuration with fail-fast production guards.
  - `backend/app/logging.py`: Structlog configuration with sensitive parameter redaction.
  - `backend/app/errors.py`: Domain `AppError` taxonomy and standardized error envelopes.
  - `backend/app/db/`: Models (`models.py`), DeclarativeBase (`base.py`), Engine & session management (`engine.py`).
  - `backend/app/auth/`: Argon2id password hashing (`passwords.py`), opaque bearer sessions (`sessions.py`), progressive throttle (`throttle.py`), routes and schemas.
  - `backend/app/ledger/`: Sole money movement transaction pipeline `post_movement()` (`service.py`), SHA-256 hash chaining (`hashing.py`), keyset statement queries (`queries.py`), strict schemas (`schemas.py`), domain exceptions (`errors.py`).
  - `backend/app/accounts/`: Account lifecycle, system accounts (`EXTERNAL`, `SUSPENSE`), admin freeze/unfreeze (`service.py`, `schemas.py`, `routes.py`).
  - `backend/app/audit/`: 4-point cryptographic audit engine and verify route (`verify.py`, `routes.py`).
  - `backend/app/review/`: Surveillance heuristics and narrative engine (`rules.py`, `narrative.py`, `routes.py`).
  - `backend/app/seed/__main__.py`: Idempotent database seeder.
  - `backend/app/main.py`: FastAPI app factory, CORS, body limits, route mounting.
  - `backend/migrations/`: Alembic env, initial tables, and PostgreSQL trigger scripts (`0001_initial_schema.py`, `0002_triggers_and_roles.py`).
  - `backend/tests/`: Contractual test suites (`test_conservation.py`, `test_no_overdraft_race.py`, `test_idempotency.py`, `test_authorization.py`, `test_deadlock_opposite_transfers.py`, `test_append_only.py`, `test_hash_chain.py`, `test_import_boundaries.py`).
  - `CHANGELOG.md`, `PROMPTS.md`, `.ai/PROMPTS.md`, `.ai/STATUS.md`.

- **Architectural & Security Highlights**:
  - **Deterministic Sorted Row Locking**: Account row IDs are sorted ascending before issuing `SELECT ... FOR UPDATE`, guaranteeing immune behavior to deadlocks during concurrent opposite transfers (Alice -> Bob vs Bob -> Alice).
  - **6-Phase Atomic Movement Protocol**: All transfers, deposits, withdrawals, and adjustments pass exclusively through `app/ledger/service.py::post_movement()`.
  - **PostgreSQL Defense-in-Depth**: `forbid_mutation()` trigger prevents UPDATE, DELETE, and TRUNCATE on ledger tables; deferred `journal_sums_to_zero` trigger guarantees zero-sum conservation at COMMIT; balance cache trigger guarantees `balance == balance_after`.
  - **Opaque Bearer Sessions**: 256-bit random tokens, stored as SHA-256 hashes in DB, with progressive delay on failed logins to prevent credential stuffing without locking out shared judge accounts.
  - **Uniform 404 on Unauthorized Accounts**: Account-scoped routes return uniform 404 rather than 403 to prevent enumeration of valid account numbers.

### Previous: 2026-11-06 15:35 IST — Landing Page Delivery
- Built strictly using existing Next.js / Tailwind setup without extra package installations.
- Smooth interactive 3D phone in hero with pointer movement tilt and subtle fallback drift.
- Sticky storytelling section synchronizes the 3 steps with the phone screen via `IntersectionObserver`.
- Accessible theme toggling between dark and light modes with immediate localStorage persistence.
- Fully responsive across mobile (390px, 480px), tablet (768px, 900px), laptop (1024px), and desktop (1200px+).

