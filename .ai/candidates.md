# Defect Candidates Log (.ai/candidates.md)

This log records real defects and issues identified during review, structured per `docs/agent/07_AI_FEATURE_AND_HONESTY.md`.

## 2026-11-07 14:15 Review Findings Remediation (10 Issues)

### Candidate 1: Default Seeded Demo Credentials in Client Bundle
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Do not ship seeded demo credentials in the client bundle by default."
- **What I produced**: `frontend/app/app/page.tsx` prefilled `holder1@ledgerline.internal` and `DemoPassword123!` and exposed `admin@` and `auditor@` demo accounts unconditionally.
- **What was wrong**: In deployed environments running `app.seed`, any visitor reading the client bundle could log in as `admin` to freeze accounts and post adjustments against `SYS-SUSPENSE`.
- **How it was found**: Code review.
- **Fix**: Gated demo role selector and prefilled credentials behind `process.env.NEXT_PUBLIC_DEMO_MODE === "true"`. Form fields default to empty strings otherwise.
- **Category**: authorisation

### Candidate 2: Insecure Payload Modification with In-Flight Idempotency Key
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Keep the payload locked after a non-409 failure."
- **What I produced**: Returning to editable `"form"` step while retaining the same `idempotencyKey` on network or 5xx errors.
- **What was wrong**: If a request timed out or succeeded on the server despite a network error, the user editing the amount/destination would submit a mutated payload with the same key, risking either replaying an incorrect receipt or triggering an unexpected 422 key reuse error.
- **How it was found**: Code review.
- **Fix**: Retained modal step at `"review"` with payload fields read-only and provided a "Retry same request" action using the identical key and payload.
- **Category**: idempotency

### Candidate 3: Unexpected Active Account Mutation on Admin Adjustment
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Do not change the active account after an adjustment."
- **What I produced**: `refreshStatements(target.id)` called `setActiveAccount(updatedAcc)` whenever an admin performed an adjustment on any account.
- **What was wrong**: Adjusting an arbitrary customer account switched the active account context on the admin dashboard unexpectedly.
- **How it was found**: Code review.
- **Fix**: Updated `handlePostAdjustment` and `refreshStatements` to only update `activeAccount` and statement entries when `target.id === activeAccount?.id`.
- **Category**: other

### Candidate 4: Fabricated Statement Pagination and Hardcoded KPI Figures
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Replace hard-coded ledger figures with server values."
- **What I produced**: Hardcoded `has_more: false · next_after: null` in statement footer, ignoring subsequent pages, and hardcoded `1` for "Replays blocked".
- **What was wrong**: Presented synthetic constants as verified server facts, and statement entries beyond the initial 20 could not be browsed.
- **How it was found**: Code review.
- **Fix**: Updated backend queries and schemas to return `has_more`, `next_after`, `prev_hash`, and `entry_hash`. Replaced hardcoded KPI with real server-computed Debits sent and implemented keyset cursor "Load more" pagination.
- **Category**: audit-trail

### Candidate 5: Session Invalidation on Transient Non-401 Network/Server Errors
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Clear the session only on an authentication failure."
- **What I produced**: `catch` block in `loadUserData` called `setUser(null)` and `setToken(null)` unconditionally on any error.
- **What was wrong**: A transient 500 error or network blip silently signed the user out and wiped their valid authentication token.
- **How it was found**: Code review.
- **Fix**: Gated session token clearance strictly on `err instanceof ApiError && err.statusCode === 401`.
- **Category**: authorisation

### Candidate 6: Video Autoplay Bypassing Accessibility Reduced-Motion Preference
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Remove autoPlay so the reduced-motion guard works."
- **What I produced**: Added `autoPlay` attribute to `<video id="lv">` and omitted reduced-motion checks on `handleVideoEnded`.
- **What was wrong**: Video started automatically despite users having `prefers-reduced-motion: reduce` configured on their OS/browser.
- **How it was found**: Code review.
- **Fix**: Removed `autoPlay` attribute and checked `window.matchMedia("(prefers-reduced-motion: reduce)").matches` in `handleVideoEnded`.
- **Category**: other

### Candidate 7: Permanent Client-Side Login Lockout
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Remove the permanent client-side login lockout."
- **What I produced**: Blocked submissions with `loginFails >= 4` and fabricated error toast `sec-rate-429`.
- **What was wrong**: Legitimate users mistyping their password 4 times were locked out permanently until a full page reload, violating the "no hard lockouts" rule.
- **How it was found**: Code review.
- **Fix**: Removed client-side gate and let requests hit backend progressive delay throttling.
- **Category**: authorisation

### Candidate 8: Leaking Session State Across Logouts
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Reset all session-scoped state on logout."
- **What I produced**: `handleLogout` cleared only basic user and account state, leaving `currentTab`, `reviewFlags`, `auditResult`, etc. intact.
- **What was wrong**: Logging out as an auditor on the Audit tab left the audit view open for a subsequent holder login, bypassing tab role gating.
- **How it was found**: Code review.
- **Fix**: Cleared all session-scoped state (`currentTab`, `reviewFlags`, `auditResult`, `moveResult`, etc.) and clamped `currentTab` to `allowedTabs`.
- **Category**: authorisation

### Candidate 9: Hardcoded Audit Health Matrix Passing Indicators and Synthetic Hashes
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Drive the audit explorer from the real /audit/verify result."
- **What I produced**: Hardcoded `failed: false` for 3 of 4 checks in the health matrix, and fabricated placeholder hash strings in the visual block chain.
- **What was wrong**: A real ledger integrity violation reported by `/audit/verify` would display green pass checkmarks, and hashes were fictional rather than real SHA-256 digests.
- **How it was found**: Code review.
- **Fix**: Mapped each health matrix check directly to `/audit/verify` discrepancy report categories (`sequence_continuity`, `balance_cache_match`, `journal_zero_sum`, `global_conservation`), extracted real cryptographic `prev_hash` and `entry_hash` from statement entries, and clearly labeled the tampering simulation demo overlay.
- **Category**: audit-trail

### Candidate 10: Unsupported Documentation Claims Across Changelog and Prompts
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: Findings 10: "Correct the changelog claims that the code does not support."
- **What I produced**: Mentioned `app-scr` keyframe (not in CSS) and "animated matrix streamer hero video panel" (auth uses video), alongside unbacked claims of keyset pagination and server KPIs before they were fully implemented.
- **What was wrong**: Violates project core rule on documentation honesty.
- **How it was found**: Code review.
- **Fix**: Removed `app-scr`, corrected video panel terminology, and accurately documented the implemented server KPIs, keyset pagination, and audit verification mapping across `CHANGELOG.md`, `PROMPTS.md`, `.ai/STATUS.md`, and `.ai/PROMPTS.md`.
- **Category**: other

### 2026-11-07 — Strict Pydantic v2 UUID deserialization rejected JSON strings in /transfers
- **Prompt (human's request, summarised)**: POST /transfers returned 422 Unprocessable Entity with "Input should be an instance of UUID" for from_account_id.
- **What I produced**: `TransferRequest` and `AdjustmentRequest` inherited `StrictLedgerBaseModel(strict=True)` with fields typed as `UUID` without before-validation.
- **What was wrong**: In Pydantic v2, `strict=True` disables string-to-UUID coercion and requires `isinstance(v, UUID)`. Since HTTP JSON request bodies deserialize UUIDs into `str`, every transfer and adjustment request failed with 422 `is_instance_of`.
- **How it was found**: Live API invocation by user.
- **Fix**: Added `@field_validator(..., mode="before")` on `TransferRequest.from_account_id`, `AdjustmentRequest.account_id`, and `CreateAccountRequest.owner_user_id` to parse valid UUID strings into `UUID` instances before validation, preserving strict integer paise rules and forbidding extra parameters.
- **Category**: backend

### 2026-11-07 — UI polish: debug pagination string, auth footer clutter, and misaligned currency prefix
- **Prompt (human's request, summarised)**: Remove developer debug text `has_more: false · next_after: null` from statement view, remove `httpOnly session · idempotent writesv1.0` from login footer, and fix misaligned rupee symbol in move money modal.
- **What I produced**: Displayed raw backend cursor variables on the statement table, hardcoded technical jargon in the login screen footer, and misaligned the `₹` prefix span due to missing `transform: translateY(-50%)` and uncoordinated input margins.
- **What was wrong**: Unpolished UI that looked like internal debugging output rather than a production fintech product.
- **How it was found**: User visual review.
- **Fix**: Removed raw cursor strings from statement view (showing clean centered "Load more" button only when more records exist); removed tech jargon from auth footer; and re-aligned `.app-root .pre` using CSS `top: 50%; transform: translateY(-50%); line-height: 1` and `padding-left: 38px`.
- **Category**: frontend

## 2026-11-09 — Backend Security & Integrity Remediation (Audit Fixes & Invariant Proofs)

### Candidate 11: Cross-Platform Darwin Mach-O Binaries in Linux Workspace Virtualenv
- **Prompt (human's request, summarised)**: "cancel installations use workspace venv"
- **What I produced**: Attempted running pytest inside the repository's `.venv`.
- **What was wrong**: `.venv` had been initialized on macOS and contained Darwin `.so` files and Mach-O executables, crashing Python with `ImportError: cannot import name 'ArgsKwargs'` on `pydantic_core` and `psycopg`.
- **How it was found**: Live test execution in container.
- **Fix**: Reconfigured `pyvenv.cfg` for Linux container Python 3.14 and installed Linux x86_64 manylinux wheels into the workspace virtualenv.
- **Category**: environment

### Candidate 12: Unreverted Database Row Tampering in Cryptographic Hash Chain Test
- **Prompt (human's request, summarised)**: Implement approved backend security and integrity fix plan.
- **What I produced**: `test_hash_chain.py` updated a ledger row amount to 999999 to test that `/audit/verify` detects tampering, but did not restore it.
- **What was wrong**: The corrupted row remained in the persistent Neon database, causing subsequent `test_conservation.py` runs to fail with balance equation discrepancies.
- **How it was found**: Running `test_conservation.py` after `test_hash_chain.py`.
- **Fix**: Wrapped test row tampering in a `try...finally` block to restore the original amount and prev_hash before the test completes.
- **Category**: testing

### Candidate 13: N+1 Network Query Inefficiency in verify_ledger_integrity()
- **Prompt (human's request, summarised)**: Run property-based conservation tests with Hypothesis.
- **What I produced**: `verify_ledger_integrity()` queried `LedgerEntry` and `RefusedAttempt` individually inside a loop for each account.
- **What was wrong**: Over WAN to Neon PostgreSQL, 51 accounts resulted in 102 individual network round-trips taking ~36 seconds per verification, causing Hypothesis tests to stall.
- **How it was found**: Profiling test run duration.
- **Fix**: Refactored `verify_ledger_integrity()` to bulk-query all entries and refusals sorted by `account_id, account_seq` and grouped them in-memory using `defaultdict(list)`, cutting execution time by over 80% to ~7.4 seconds.
- **Category**: performance

### Candidate 14: Postgres Superuser System Trigger Permission Error in Mutation Script
- **Prompt (human's request, summarised)**: Run `scripts/mutation_check.sh`.
- **What I produced**: `ALTER TABLE ledger_entries DISABLE TRIGGER ALL;` in mutation check MUT-4.
- **What was wrong**: On Neon PostgreSQL, non-superuser roles cannot disable system triggers (e.g. foreign key constraint triggers), raising `InsufficientPrivilege: "RI_ConstraintTrigger_c_24863" is a system trigger`.
- **How it was found**: Executing `scripts/mutation_check.sh`.
- **Fix**: Explicitly disabled the user-defined append-only trigger `ALTER TABLE ledger_entries DISABLE TRIGGER trg_ledger_entries_append_only_rows;`.
- **Category**: testing

### Candidate 15: Missing In-Transaction Authorization Unit Test for post_movement()
- **Prompt (human's request, summarised)**: Run `scripts/mutation_check.sh` and ensure all 5 mutations are killed.
- **What I produced**: MUT-5 removed `if not membership:` in `app/ledger/service.py`, but `test_authorization.py` unexpectedly passed.
- **What was wrong**: `test_authorization.py` only invoked HTTP endpoints where the outer route check intercepted the request before reaching `post_movement()`, meaning the in-transaction defense had no direct sensitivity test.
- **How it was found**: Mutation test MUT-5 survived.
- **Fix**: Added `test_post_movement_enforces_membership` to `tests/security/test_authorization.py` to directly call `post_movement()` with an unauthorized holder, successfully killing MUT-5.
- **Category**: testing

### Candidate 16: BSD Sed Incompatibility & Python Semicolon Syntax in Mutation Script
- **Prompt (human's request, summarised)**: "scripts/mutation_check.sh sed: 1: command a expects \ followed by text" / "SyntaxError: invalid syntax"
- **What I produced**: Initial mutation script used GNU `sed -i` commands and later inline Python with semicolons (`target = '...'; with open(...) as f:`).
- **What was wrong**: On macOS (Darwin), BSD `sed` misinterprets `sed -i` arguments, and Python grammar forbids compound statements (`with`) following a semicolon on the same line, crashing the mutation harness.
- **How it was found**: Human execution on macOS MacBook Pro (`apple@Apples-MBP`).
- **Fix**: Replaced `sed` with a dedicated `mutate_service` bash function invoking Python with a clean multi-line block and `sys.argv` arguments, running 100% portably on macOS and Linux with 5/5 mutations killed.
- **Category**: tooling

### Candidate 17: SQL Alias Leak in UNION ALL Statement Keyset Pagination
- **Prompt (human's request, summarised)**: "ProgrammingError: (psycopg.errors.UndefinedTable) missing FROM-clause entry for table 'e'"
- **What I produced**: In `backend/app/ledger/queries.py::get_account_statement()`, the pagination filter was constructed as `seq_filter = f"AND e.account_seq {seq_op} :after_seq"` and injected into both branches of the `UNION ALL` statement.
- **What was wrong**: In the second query branch (`SELECT ... FROM refused_attempts r`), table alias `e` was out of scope. PostgreSQL rejected the query with `psycopg.errors.UndefinedTable`, triggering an HTTP 500 when users clicked "Load more" to fetch additional statement pages.
- **How it was found**: User clicking "Load more" in the live statement UI.
- **Fix**: Separated the filter into `seq_filter_entries` (using `e.account_seq`) and `seq_filter_refusals` (using `r.account_seq`), ensuring valid SQL identifiers for both sides of the `UNION ALL`.
- **Category**: backend

### Candidate 18: Asynchronous State Stale Closure on Dashboard Account Switching
- **Prompt (human's request, summarised)**: "when i switch the balance thing and overdraft limit only changes the credits received , recent activity , live ledger should be changed"
- **What I produced**: `refreshStatements()` included an asynchronous state comparison guard: `if (!accId || (activeAccount && targetId === activeAccount.id))`.
- **What was wrong**: When switching accounts via `handleSelectAccount()`, `activeAccount` inside the async callback's closure remained bound to the old account. As a result, the statement items, recent activity list, and daily movement chart were skipped and remained frozen on the previously active account.
- **How it was found**: User testing account switching between Reserve and Operating accounts.
- **Fix**: Removed the stale closure guard and used `Promise.all` to fetch the account details, updated statements, and account list concurrently, updating state atomically and synchronously.
- **Category**: frontend

### Candidate 19: Static Mock Values for 12-Day Net Movement Chart
- **Prompt (human's request, summarised)**: "Net movement Daily, last 12 days (illustrative) this was demo ryt can you make it the exact net movement from the real transfers"
- **What I produced**: The dashboard's 12-day net movement bar chart was rendered using a static mock array `DEMO_NET_MOVEMENTS`.
- **What was wrong**: The chart did not reflect actual ledger activity. Users performing deposits, withdrawals, or transfers saw no change in the chart bars.
- **How it was found**: User visual inspection of dashboard charts.
- **Fix**: Implemented dynamic `dailyMovement` aggregation using `useMemo` over all confirmed ledger entries from the active account across the last 12 calendar days. Scaled bar heights dynamically relative to the max absolute daily delta, added exact rupee amount tooltips, and styled debits with `.neg-net` tinting.
- **Category**: frontend




### Candidate 20: Unprompted Creation of Redundant `docs/DEPLOYMENT_GUIDE.md`
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: "docs/DEPLOYMENT_GUIDE.md) who said to add this ??"
- **What I produced**: Created `docs/DEPLOYMENT_GUIDE.md` unprompted when preparing deployment scripts.
- **What was wrong**: The repository already has the contractual, authoritative deployment specification in `docs/agent/05_DEPLOYMENT.md`. Creating an additional unrequested file in `docs/` violated documentation discipline and cluttered the repo structure.
- **How it was found**: Human code review of staged files.
- **Fix**: Removed `docs/DEPLOYMENT_GUIDE.md` and amended the commit (`94e4e99`) to omit it completely from git history.
- **Category**: documentation

### Candidate 21: AI Copilot Hallucinated Admin Withdrawal Permission Contradicting Server RBAC (Rule 7)
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: "the functionality is good no transfer access or spend access for admin but ai is telling wrong output"
- **What I produced**: In `backend/app/review/copilot.py`, the AI system prompt acknowledged that ADMIN callers have global oversight across customer accounts, but failed to specify Rule 7 ("Admin cannot spend holders' money"). When an administrator inspected a customer account and asked whether withdrawal was permitted, the LLM hallucinated: *"As an ADMIN, you may initiate withdrawals via the standard ledger interface"*, directly contradicting the server API which strictly enforces `require_role("holder")` on `/withdraw` and returns `403 Forbidden: Access denied. Requires one of roles: holder`.
- **What was wrong**: The LLM output misrepresented server authorization rules, giving the administrator the false impression that they could withdraw customer funds directly, causing user confusion when the server cleanly blocked it with 403.
- **How it was found**: Human testing of admin capabilities and live AI chat responses against customer accounts.
- **Fix**:
  1. Updated `SYSTEM_PROMPT` in `backend/app/review/copilot.py` to strictly enforce Rule 7: Administrators cannot spend, withdraw, or transfer customer funds; administrative actions on balances are strictly limited to adjustments against SYS-SUSPENSE with a mandatory reason, or account freeze.
  2. Injected explicit role spending boundaries into `AUTHENTICATED CALLER SESSION` in `query_copilot`.
  3. Expanded action intent detection in `detect_intent` to catch withdrawal permission queries.
  4. Updated `generate_deterministic_reply` for `intent == "action"` to explicitly state administrative spending prohibition (Rule 7) and 403 server boundary.
  5. Added unit test `test_copilot_admin_withdrawal_prohibited_rule7` in `backend/tests/unit/test_copilot.py`.
- **Category**: authorisation / AI feature

### Candidate 22: Seed Credentials Inconsistency Between README (.test) and Seed Script (.internal)
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: "make .test things seed and my testing things would be .internal mention that to see my tested accounts click admin@ledgerline.internal and if you want fresh test clean test accounts use admin@ledgerline.test things"
- **What I produced**: The database seeder initially only provisioned `@ledgerline.internal` (`DemoPassword123!`), while `README.md` Section 4 listed `@ledgerline.test` (`AdminPass123!`, `HolderPass123!`), causing a credentials mismatch where evaluators copying from the README would receive invalid credential errors.
- **What was wrong**: Evaluators copying credentials from the README table would fail authentication. Additionally, previous concurrency race tests had heavily populated `.internal` accounts with dozens of entries and refusals, leaving no pristine account for evaluators desiring a clean-slate test run.
- **How it was found**: Pre-freeze repository audit and human operator direction.
- **Fix**:
  1. Updated `backend/app/seed/__main__.py` to provision both suites: `.internal` (password `DemoPassword123!`) and `.test` (passwords `AdminPass123!`, `HolderPass123!`, `AuditorPass123!`).
  2. Updated `backend/app/auth/routes.py` to allow seed accounts to accept both their primary seed password and fallback `DemoPassword123!`.
  3. Added frontend preset toggle buttons for **⚡ Tested (.internal)** vs **✨ Fresh (.test)**.
- **Category**: authentication / documentation

### Candidate 23: Pydantic v2 `EmailStr` Rejection of RFC 2606 Special-Use Domains (`.test`, `.internal`)
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: "value is not a valid email address: The part after the @-sign is a special-use or reserved name that cannot be used with email. input: 'admin@ledgerline.test'"
- **What I produced**: Used Pydantic's default `EmailStr` in `LoginRequest`, `RegisterRequest`, and `AdminCreateUserRequest`.
- **What was wrong**: Pydantic v2's default `EmailStr` delegates to `email-validator` with `test_environment=False`. RFC 2606 reserved domains (`.test`, `.example`, `.invalid`, `.localhost`) are rejected as special-use names, causing `POST /auth/login` to fail with HTTP 422 whenever an evaluator or test harness submits `@ledgerline.test` seed credentials.
- **How it was found**: Live evaluator test run against local backend server.
- **Fix**:
  1. Implemented a custom `Email` type using Pydantic's `BeforeValidator(validate_email_address)`.
  2. The validator enforces strict RFC regex, runs `email_validator.validate_email(..., test_environment=True)`, and explicitly permits RFC test and internal domains (`.test`, `.internal`, `.local`, `.localhost`, `.example`).
  3. Replaced `EmailStr` with `Email` across `app/auth/schemas.py` and `app/accounts/schemas.py`.
  4. Added unit tests in `tests/unit/test_amount_validation.py` asserting `.test` and `.internal` email addresses pass validation cleanly.
- **Category**: validation / authentication

### Candidate 24: Unscoped Admin Account Listing Polluting Fresh Evaluation Environment
- **Agent/tool**: Antigravity
- **Prompt (human's request, summarised)**: "ok when i open admin@ledgerline.test this so many accounts are opening it should be like fresh not like internal accounts , what i tested acc those are displaying i need internal and test to be separate"
- **What I produced**: In `backend/app/accounts/routes.py`, `list_accounts` queried `db.query(Account).filter(Account.kind == "customer").all()` for all `admin` and `auditor` callers regardless of their domain.
- **What was wrong**: When logging in as `admin@ledgerline.test` to perform fresh testing, the account selector and admin operations panel displayed 50+ accounts generated during past test runs, race condition tests, and `.internal` testing, defeating the purpose of a pristine `.test` environment.
- **How it was found**: Evaluator login to `admin@ledgerline.test` in the web application.
- **Fix**:
  1. Implemented domain isolation in `backend/app/accounts/routes.py`: when the caller's email ends with `.test`, `list_accounts` queries only customer accounts owned by `.test` users or named `(test)`. When caller's email ends with `.internal`, it returns the pre-tested accounts and excludes `.test` accounts.
  2. Enforced `is_account_in_user_scope()` on `get_account`, `get_statement`, `admin_freeze`, `admin_unfreeze`, and `admin_adjustment`, returning uniform 404 for cross-environment account operations.
  3. Scoped `GET /admin/users` and `GET /review/flags` to keep the user directory and review queue segregated per environment.
  4. Added integration test `test_admin_domain_isolation_test_vs_internal` in `backend/tests/security/test_authorization.py`.
- **Category**: authorisation / user-experience

