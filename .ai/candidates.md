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


