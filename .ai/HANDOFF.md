# Agent Handoff Notes

### Latest: 2026-11-10 21:30 IST — Institutional Account Request & Admin Approval Workflow
- **Refinement Delivered**:
  - Implemented the end-to-end "Account Request -> Admin Approval" onboarding pipeline across backend and frontend:
    - `POST /auth/register`: Users register without unvetted bank accounts. An `AccountRequest` row (`status="pending"`) and an `account_request` review flag (`severity="medium"`, `status="open"`) are recorded, returning `account=None`.
    - `GET /accounts/requests/mine`: Returns the authenticated user's pending and historical vault requests.
    - `POST /accounts/requests`: Allows authenticated users with zero accounts to submit a request for an institutional vault.
    - `POST /review/flags/{flag_id}/decision`: Enhanced admin decision handler to atomically approve or dismiss account requests. Upon admin approval, `create_customer_account` provisions a zero-balance double-entry customer vault bound to the user in PostgreSQL, updates `AccountRequest` status to `approved`, appends a `ReviewDecision`, and emits audit `SecurityEvent` log.
    - Zero-account dashboard state: Newly registered users with 0 active accounts see default zeros (`₹0.00` balance, `+₹0.00` inflow, `−₹0.00` outflow, `0` refusals) and an institutional 3-step Fintech Onboarding Status Stepper card (`🟡 APPLICATION UNDER REVIEW`).
    - Statement tab: Renders clean default zero state (`Account: Pending Activation · 0 entries recorded`).
    - Admin Review Queue: Retained the authentic, unbloated layout ("Suggestions only. A person decides, and the decision is recorded. No flags waiting for review.") with Approve / Dismiss controls that refresh active accounts upon decision.
  - Automated integration test `backend/tests/integration/test_account_onboarding_approval.py` verified and passing (2/2 tests green).
- **Files Touched**:
  - `backend/app/db/models.py`, `backend/migrations/versions/0004_account_requests.py`: Added `AccountRequest` table and constraints.
  - `backend/app/auth/routes.py`, `backend/app/accounts/routes.py`, `backend/app/review/routes.py`: Onboarding request & decision logic.
  - `backend/app/accounts/schemas.py`, `backend/app/auth/schemas.py`: Schemas for requests and registration.
  - `backend/tests/integration/test_account_onboarding_approval.py`: Full end-to-end integration tests.
  - `frontend/lib/api.ts`, `frontend/app/app/page.tsx`: Frontend zero-state KPIs, stepper card, and request management.
  - `docs/API.md`, `.ai/STATUS.md`, `.ai/HANDOFF.md`: Updated API contracts and progress tracking.

### Previous: 2026-11-10 21:05 IST — Clean Admin Operations Layout Aligned with Reference Prototype
- **Refinement Delivered**:
  - Removed the cluttered `User Directory & Role Access (RBAC)` table from the Admin Operations tab. In test/demo environments, accounts with 100+ race test accounts had dumped huge unformatted walls of account numbers, breaking the UI layout.
  - Restored the exact, clean 2-column layout from `frontend/LedgerLine — app.html` line 182:
    - Side-by-side cards in `.g2`: `Accounts` (with live freeze/unfreeze switches) and `Adjustment` (posting against SYS-SUSPENSE with mandatory reason).
    - Directly below: focused `Review queue` card ("Suggestions only. A person decides, and the decision is recorded. No flags waiting for review.").
  - Pruned unused `adminUsers` state, hooks, and event handlers from `frontend/app/app/page.tsx` and removed unused `AdminUser` import.
- **Files Touched**:
  - `frontend/app/app/page.tsx`: Removed user directory form and table; restored clean operations layout.
  - `.ai/STATUS.md`, `.ai/HANDOFF.md`: Updated progress tracking.

### Previous: 2026-11-10 20:45 IST — Streamlined Fintech Auth Sliding Transition
- **Refinement Delivered**:
  - Removed redundant top segmented pill bar (`Sign in | Create account`); switching is now driven exclusively by clean, natural bottom switch prompts ("Don't have an account? Create account" and "Already have an account? Sign in"), matching standard single-page auth UX (Stripe, Linear).
  - Removed cluttered bottom footer note (`opaque bearer session · idempotent writes v1.0`), restoring clean vertical centering.
  - Retained the smooth horizontal sliding carousel (`.auth-viewport` & `.auth-track`) with 350ms institutional-grade cubic-bezier (`cubic-bezier(0.25, 1, 0.5, 1)`) so clicking the switch links glides seamlessly between Sign In and Create Account without vertical jumps.
  - Isolated demo presets into a clean `.auth-demo-box` inside the Sign In panel with clear captioning.
  - Preserved shared input states (`authEmail`, `authPassword`) across the transition.
- **Files Touched**:
  - `frontend/app/app/page.tsx`: Removed `.auth-mode-seg` and footer note; streamlined sliding track controls.
  - `frontend/app/app/app.css`: Pruned unused `.auth-mode-seg` rules.

### Previous: 2026-11-10 20:30 IST — BalanceVault Full Implementation & Hardening
- **Completed Deliverables**:
  - **User Registration & Atomic Account Provisioning**: Added `POST /auth/register` in `backend/app/auth/routes.py` with Argon2id password hashing, atomic customer account creation via `create_customer_account`, `user_registered` security event logging, and instant session issuance.
  - **Admin User Management & RBAC**: Implemented `GET /admin/users`, `POST /admin/users`, and `POST /admin/users/{user_id}/status` in `backend/app/accounts/routes.py` with self-deactivation protection and immediate session revocation upon deactivation.
  - **Distributed Redis Rate Limiting with Fallback**: Implemented sliding-window algorithm using Redis sorted sets with thread-safe in-memory fallback in `backend/app/rate_limit.py`. Attached route dependencies to `/auth/login`, `/auth/register`, and money movements (`deposit`, `withdraw`, `transfer`).
  - **First-Admin Bootstrap Script**: Created `scripts/bootstrap_admin.py` with zero-admin guard, Argon2id encryption, CLI and env configuration, and Neon/Supabase cloud PostgreSQL compatibility.
  - **Enriched Health & Readiness Probes**: Updated `/ready` in `backend/app/main.py` to verify both PostgreSQL and Redis connectivity.
  - **Frontend UI & Onboarding Integration**: Added `Sign in` | `Create account` mode toggle on the Auth screen with self-service registration and auto-login, and added a dedicated "User Directory & Role Access (RBAC)" card in the Admin tab with live status toggling, account balances, and user provisioning.
  - **Branding Alignment**: Aligned public UI branding to `BalanceVault (formerly LedgerLine)` while keeping database role identifiers (`ledgerline_app`, `ledgerline_owner`) strictly intact.
- **Files Touched**:
  - `backend/app/auth/routes.py`, `backend/app/accounts/routes.py`, `backend/app/accounts/schemas.py`, `backend/app/rate_limit.py`, `backend/app/main.py`.
  - `scripts/bootstrap_admin.py`.
  - `frontend/lib/api.ts`, `frontend/app/app/page.tsx`, `frontend/app/page.tsx`, `frontend/app/layout.tsx`.
  - `README.md`, `docs/WRITEUP.md`, `.ai/STATUS.md`, `.ai/HANDOFF.md`.

### Previous: 2026-11-10 19:55 IST — Copilot UI Refinements Aligned with LedgerLine Prototype
- **Refinement Delivered**:
  - Removed repetitive 4-button `.proof-nav-bar` (`📊 Dashboard`, `📑 Statement`, `🛡️ Audit Verify`, `⚡ Move Money`) and tool tag chips (`forecast · read-only`) from assistant messages.
  - Removed "Clickable Proofs" header and "Jump ↗" text badges that cluttered the search results card.
  - Re-aligned `.ac` and `.sr` with the exact prototype in `frontend/LedgerLine — app.html`:
    - Standard `<a href="#statement" class="sr">` items inside `<div class="ac">`.
    - Generous vertical height (`min-height: 52px; padding: 13px 16px; gap: 14px;`) with clean typography.
    - Left side: bold entry title (`#2 · Transfer`) with subtle inline chip for refusals (`Refused · insufficient_funds`) and secondary memo/balance (`Balance after ₹600.00`).
    - Right side: cleanly aligned mono amount with sign and color coding (`+₹1,000.00` in emerald, `−₹400.00` in red).
    - Smooth click handler navigating to statement item with account selection, filter reset, smooth scroll, and glowing emerald pulse.
  - Replaced duplicate bulleted search text in `copilot.py` with concise prototype response: `Found **X matching entries**, newest first.`
- **Files Touched**:
  - `frontend/app/app/page.tsx`: Cleaned up Copilot card rendering to match `frontend/LedgerLine — app.html`.
  - `frontend/app/app/app.css`: Updated `.sr` styling for optimal height and typography; pruned unused proof classes.
  - `backend/app/review/copilot.py`: Made search reply text concise without duplicate markdown bullet rows.
  - `backend/tests/unit/test_copilot.py`: Added unit test `test_copilot_search_response_concise_format`.

### Previous: 2026-11-10 19:15 IST — BalanceVault Requirements Alignment & Documentation Overhaul
- **Context & Organizer Clarifications**:
  - Organizers officially confirmed: *BalanceVault is the renamed LedgerLine*. All core financial invariants ($I_1$ to $I_8$, double-entry, append-only, concurrency locks, idempotency) remain strictly applicable.
  - Added mandatory items: Account management & user onboarding, RBAC, Redis rate limiting, First-admin bootstrap script, Database roles & deployment health checks.
  - Directive: *Extend existing LedgerLine implementation, do not start from scratch.*
- **Files Touched**:
  - `docs/Problem_Statement.md`: Appended official addendum and clarifications from the organizers.
  - `docs/ARCHITECTURE.md`: Added Section 9 documenting User Onboarding, Redis Rate Limiting architecture, First-Admin Bootstrap (Neon SQLSTATE 42501 analysis), and Health/Readiness probes.
  - `docs/API.md`: Documented `POST /auth/register`, `GET /admin/users`, `POST /admin/users`, `POST /admin/users/{id}/status`, `GET /health`, `GET /ready`, and rate limiting headers.
  - `THREATS.md`: Added threat vectors P11 to P14 (registration spam, Redis outage fallback, bootstrap hijacking, cloud PostgreSQL role permission errors).
  - `docs/UNFINISHED.md`: Updated known scope and aligned in-progress items with portal submission checklist.
  - `.ai/STATUS.md`: Updated active tasks and detailed execution plan.
- **Next Actions**:
  - Implement `POST /auth/register` and admin user directory endpoints in FastAPI backend.
  - Create Redis rate-limiting provider with resilient fallback.
  - Create dedicated `scripts/bootstrap_admin.py` handling restricted DB role environments.
  - Update frontend with registration modal/tab and admin user management panel.

### Previous: 2026-11-09 13:00 IST — Statement Keyset Pagination, Account Sync, & Net Movement Chart
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

