# Agent Handoff Notes

### Latest: 2026-11-09 13:00 IST — Statement Keyset Pagination, Account Sync, & Net Movement Chart
- **Files Touched**:
  - `backend/app/ledger/queries.py`: Fixed `psycopg.errors.UndefinedTable: missing FROM-clause entry for table "e"` by using `seq_filter_entries` (`e.account_seq`) for entries and `seq_filter_refusals` (`r.account_seq`) for refusals in the keyset-paginated `UNION ALL` query.
  - `frontend/app/app/page.tsx`: Fixed stale closure in `refreshStatements()` to ensure atomic UI updates across balance, statement, recent activity, and KPI cards when switching accounts; added real ledger transaction aggregation for 12-day net movement chart; added explicit source account display with live balance in Move Money modal.
  - `frontend/app/app/app.css`: Added styles for negative net daily movement bars (`.neg-net`).
  - `scripts/mutation_check.sh`: Ported mutation testing harness using Python multi-line replacement helper `mutate_service` for macOS BSD sed compatibility.
  - `docs/WRITEUP.md`: Created comprehensive 750-word system write-up and exact answers to the 6 submission questions.
  - `.ai/candidates.md`: Logged Candidates 16–19 (BSD sed syntax, SQL alias leak, stale closure in account switching, static mock chart).

### Previous: 2026-11-09 11:30 IST — Backend Security & Integrity Remediation & Verification
- **Artifacts Created**:
  - `docs/backend_security_and_integrity_fix_plan.md`: Comprehensive remediation plan addressing VULN-01 to VULN-09, TEST-01, and GAPs 01–07.
  - `scripts/mutation_check.sh`: Automated mutation check harness.
  - `docs/MUTATION_REPORT.md`: Mutation check results proving 5/5 core mutations killed.
- **Files Touched**:
  - `backend/app/ledger/service.py`: Added in-transaction caller authorization for adjustments and reversals (admin-only) and customer transfers (`AccountMember`), removed redundant `.with_for_update()` on IdempotencyKey replay query to eliminate contention, mapped lock/statement timeouts (`55P03`, `57014`) to domain `LockTimeoutError` (503 Retry-After).
  - `backend/app/accounts/routes.py`: Blocked transfers to system accounts (`EXTERNAL`, `SUSPENSE`), prevented self-transfers, restricted deposits to holders, wired `evaluate_transaction_for_flags` to all post-commit money movements, added admin reversal route `POST /admin/journals/{id}/reverse`.
  - `backend/app/review/routes.py`: Derived review flag status dynamically from `review_decisions` table to comply with append-only database trigger `trg_review_flags_append_only_rows`.
  - `backend/app/auth/throttle.py`: Switched JSONB email lookup from `.as_string()` to `.astext`.
  - `backend/app/main.py`: Guarded `Content-Length` header against malformed/negative values and enforced 16 KB body size limit.
  - `backend/app/audit/verify.py`: Bulk-loaded entries and refusals by account, eliminating N+1 queries over network; cast global and customer sums to `int`.
  - `backend/app/errors.py`: Implemented `standardized_error_envelope(code, message, request_id)` helper.
  - `frontend/lib/api.ts`: Added `reverseJournal`, keyset statement ordering, and review decision normalization.
  - `backend/tests/integration/test_property_conservation.py`: Added Hypothesis property test proving Invariants I1/I2 across random operation sequences.
  - `backend/tests/security/test_authorization.py`: Added `test_post_movement_enforces_membership`.
  - `THREATS.md`: Updated all threat vectors to CLOSED with verified passing test references.
- **Verification Evidence**:
  - `test_no_overdraft_race.py`: 20 concurrent threads against ₹100 account; exactly 3 succeed, 17 cleanly refused, final balance ₹10.
  - `test_deadlock_opposite_transfers.py`: 20 concurrent opposite transfers without deadlock.
  - `test_idempotency_concurrent.py`: 20 concurrent replays return original journal.
  - `test_property_conservation.py`: Hypothesis property-based testing passes with zero discrepancies.
  - `scripts/mutation_check.sh`: 5/5 mutations killed (row lock, balance floor check, idempotency claim, append-only triggers, membership authorization).
  - Live cryptographic ledger audit `/audit/verify`: Zero discrepancies.

### Previous: 2026-11-07 16:00 IST — Backend Security & Bug Audit Report
- **Files Touched**:
  - `docs/BACKEND_AUDIT_REPORT.md`: Comprehensive audit report covering 9 backend vulnerabilities/bugs across auth, accounts, ledger, review, migrations, and test suites.
- **Key Findings Documented**:
  - VULN-01 (Critical): Downward admin balance adjustment blocked by customer `AccountMember` check in `post_movement()`.
  - VULN-02 (Critical): Review decision endpoint fails with HTTP 500 because mutating `review_flags.status` violates `trg_review_flags_append_only_rows` trigger.
  - VULN-03 (High): Transfer endpoint allows transferring customer money directly to `SYS-EXTERNAL` or `SYS-SUSPENSE`.
  - VULN-04 (High): Login throttler crashes with `AttributeError` due to `.as_string()` on SQLAlchemy JSONB expression.
  - VULN-05 to 09 (Medium/Low): Flag escalation status bug, disconnected surveillance pipeline, admin direct deposit role leak, unhandled malformed `Content-Length`, and statement keyset sort order.
  - TEST-01: Broken test interfaces and directory path bug in `test_import_boundaries.py`.

### Previous: 2026-11-07 15:38 IST — UI Polish & Cleanup

### Previous: 2026-11-07 14:45 IST — Pydantic v2 Strict UUID Deserialization Fix
- **Files Touched**:
  - `backend/app/ledger/schemas.py`: Added `field_validator(..., mode="before")` on `TransferRequest.from_account_id` and `AdjustmentRequest.account_id` to parse RFC JSON UUID strings into `UUID` instances before validation, preventing Pydantic v2 `strict=True` 422 `is_instance_of` rejections.
  - `backend/app/accounts/schemas.py`: Added `field_validator(..., mode="before")` on `CreateAccountRequest.owner_user_id`.
  - `backend/tests/unit/test_amount_validation.py`: Added tests asserting valid UUID strings are parsed into `UUID` objects, invalid UUID strings are rejected with 422, and amounts remain strictly validated as integer paise (rejecting floats, strings, booleans).
  - `.ai/candidates.md`: Logged defect candidate entry per `07_AI_FEATURE_AND_HONESTY.md`.

### Previous: 2026-11-07 14:15 IST — Review Findings Remediation (10 Issues Fixed)
- **Files Touched**:
  - `frontend/app/app/page.tsx`:
    1. Gated demo role selector and pre-filled credentials behind `NEXT_PUBLIC_DEMO_MODE === "true"`. Form inputs default to empty string.
    2. Locked movement payload in `"review"` step after unknown outcome errors (5xx/network/timeout) with "Retry same request" to prevent key-reuse/tampering bugs.
    3. Fixed admin adjustments so adjusting an account does not switch or corrupt the active account statement context.
    4. Replaced hard-coded "Replays blocked: 1" with server-computed "Debits sent" KPI; implemented keyset cursor pagination with "Load more" action.
    5. Gated session token dropping strictly on 401 unauthenticated errors (preventing logout on transient 5xx or network errors).
    6. Removed `autoPlay` from `<video id="lv">` and respected `prefers-reduced-motion` in `handleVideoEnded`.
    7. Removed permanent client-side login lockout (`loginFails >= 4`), delegating rate-limiting to server progressive delay.
    8. Reset all session-scoped state on logout and clamped `currentTab` to `allowedTabs`.
    9. Mapped `/audit/verify` discrepancy reports to the 4-point health matrix, rendered real SHA-256 hashes from statement entries, and isolated the tampering simulation demo overlay.
  - `frontend/lib/api.ts`: Added `prev_hash` & `entry_hash` to `StatementItem`, `has_more` & `next_after` to `StatementResponse`, and mapped `Discrepancy[]` in `AuditVerification`.
  - `backend/app/ledger/schemas.py`: Added `prev_hash` & `entry_hash` to `StatementItem`; added `has_more: bool` & `next_after: Optional[int]` to `StatementResponse`.
  - `backend/app/ledger/queries.py`: Extracted `prev_hash` and `entry_hash` in SQL query and returned keyset pagination metadata (`has_more`, `next_after`).
  - `backend/app/audit/verify.py`: Added `is_valid: bool = True` field to `AuditVerifyReport` and assigned `is_valid=verified`.
  - `frontend/.env.example`: Created with documentation for `NEXT_PUBLIC_DEMO_MODE=false`.
  - `CHANGELOG.md`, `PROMPTS.md`, `.ai/STATUS.md`, `.ai/PROMPTS.md`: Corrected claims (removed `app-scr`, updated auth video description, accurately stated 4 server KPIs, pagination, and audit mapping).
  - `.ai/candidates.md`: Documented all 10 defect candidates per `07_AI_FEATURE_AND_HONESTY.md`.

### Previous: 2026-11-06 17:05 IST — Backend Core Delivery
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

