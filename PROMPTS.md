# PROMPTS.md — AI Usage and Verification Log

This file documents the AI prompts, code generations, human corrections, and verification steps taken throughout the development of **LedgerLine** for the Snovasys Fresher Hiring Challenge 2026.

---

## 2026-11-06 15:30 IST — Landing Page UI Architecture & Implementation

### 1. User Prompt

> "hey iam building a project named ledgerline for snovasys u can read the problem statement in docs/Problem_Statement.md do note the docs/Instructions.md and i want you to build the frontend landing page with the ui inspiration i have pasted in frontend/LedgerLine — money you can prove.html build the same thing as the landing page of our application it should be responsive to mobile,web,laptop widths and do update the things we do in changlelog.md and prompts.md as instructed , for transparency do note all the tool calls and prompts u use for calling anything else note that cleanly in .ai/PROMPRS.md"
>
> Follow-up:
> "hey u dont need to download anything just build the landing page ui with the frontend nextjs setup"

### 2. What Was Generated

- Examined project guidelines in `AGENTS.md`, `docs/Instructions.md`, `docs/Problem_Statement.md`, and `docs/agent/02_frontend.md`.
- Analyzed the high-craft mockup in `frontend/LedgerLine — money you can prove.html`.
- Implemented `frontend/app/globals.css` with complete fintech design tokens, animations, responsive breakpoints, and dark mode support.
- Configured `frontend/app/layout.tsx` with Google Font preloading (`Inter`, `Inter Tight`, `Instrument Serif`, `JetBrains Mono`), viewport fit settings, and zero-flicker inline theme detection script.
- Built `frontend/app/page.tsx` as a responsive Next.js client component with:
  - 3D interactive phone mockup with real-time pointer tracking (`perspective: 1400px`).
  - Synchronized scroll-storytelling mechanism (`01 — BOOKS BALANCE`, `02 — EXACTLY ONCE`, `03 — PROVABLE`) driving the sticky phone stage.
  - Interactive statement ledger table with explicit visual hierarchy for credits, debits, duplicate replays, and refused transactions.
  - Three distinct role capability cards (`ADMIN`, `ACCOUNT HOLDER`, `AUDITOR`) with interactive CSS keyframe visualizers.
  - Callout band with animated matrix stream background.
  - Light/Dark theme toggle with localStorage persistence.

### 3. Issues Caught & Corrections

- **Hydration & SSR Safety**: The HTML prototype relied on immediate vanilla JS DOM mutations (`walk(h2)` and window event listeners). Porting directly would cause React hydration mismatch errors in Next.js App Router. Instead, headings were refactored into deterministic JSX word wrappers with `transitionDelay`, and DOM attribute checks were guarded inside `useEffect`.
- **Responsive Layout Collapse**: The prototype hid the sticky stage on mobile (`<900px`). Added mobile-friendly breakpoints (390px and 480px) and ensured all text and amounts fit comfortably without horizontal overflow.
- **Dependency Guard**: Avoided external runtime dependencies and unnecessary package downloads as instructed, utilizing native CSS animations and Next.js built-in features.

---

## 2026-11-06 15:37 IST — Turbopack CSS @import Rule Ordering Fix

### 1. User Prompt / Build Error

```
Next.js 16.4.5 Turbopack
Build Error
Parsing CSS source code failed
./app/globals.css.css (450:8)
Error: Parsing CSS source code failed
@import rules must precede all rules aside from @charset and @layer statements
```

### 2. What Was Produced

In `frontend/app/globals.css`, `@import url("https://fonts.googleapis.com/...");` was placed at line 3 directly following `@import "tailwindcss";`.

### 3. What Was Wrong

Tailwind CSS v4's Turbopack loader (`@tailwindcss/turbopack`) compiles `@import "tailwindcss";` by expanding it into hundreds of lines of base CSS reset and layer rules. In standard CSS specification, `@import` rules must precede all other CSS rules (except `@charset` and `@layer`). Consequently, PostCSS / Turbopack failed when parsing the `@import url(...)` after compiled rules.

### 4. How It Was Fixed

- Removed `@import url(...)` from `frontend/app/globals.css`.
- Relied on the Google Fonts `<link rel="stylesheet" ...>` tags already established in `frontend/app/layout.tsx`.
- Result: Clean compile with zero build warnings and no hydration flash.

---

## 2026-11-06 16:36 IST — Threats Analysis & Pre-Implementation Planning

### 1. User Prompt

> "/plan Start from AGENTS.md and follow its read order completely. Do not write code yet. Summarise the invariants in your own words, list the three riskiest parts of this build, and list any ambiguity or conflict you see between the documents. Wait for my answer."
>
> Follow-up:
> "have u gone through threats.md take a look at that too, i have pased the common types of attacks for u and do make sure to update in PROMPTS.md"

### 2. Analysis of THREATS.md

Analyzed all 46 threat vectors categorized into 7 domains:

- **A. Money & Concurrency (M1–M12)**: Addressed via single transaction execution, deterministic row locks (`SELECT ... FOR UPDATE ORDER BY id`), `balance_floor` DB CHECK constraint, and per-statement `lock_timeout = '3s'` returning 503 + Retry-After.
- **B. Exactly-Once (I1–I7)**: Addressed via transactional `idempotency_keys` insert-claim, blocking waiters on unique constraints, SHA-256 payload hash verification, and permanent retention of keys.
- **C. Authorisation (A1–A9)**: Addressed via in-transaction post-lock membership queries, uniform 404 responses for foreign accounts (no enumeration), strict Pydantic extra="forbid", and read-only auditor verification.
- **D. Ledger Tampering (L1–L7)**: Addressed via database trigger-level mutation blocks, privilege revocation (`REVOKE UPDATE, DELETE, TRUNCATE`), and DB-computed per-account SHA-256 hash chains verified by `/audit/verify`.
- **E. API & Platform (P1–P10)**: Addressed via parameterized queries, input size caps, strict JSON body parsing, and structured non-leaking error envelopes.
- **F. AI Review Feature (R1–R4)**: Isolated from ledger writes; AI suggestions and human admin decisions are stored immutably in append-only tables.
- **G. Knowingly Accepted Risks**: Single region / single DB (availability trade-off, cannot lose money); superuser tampering detectable but not preventable without external hash publication.

---

## 2026-11-06 17:00 IST — Backend Core Implementation & Architectural Enhancements

### 1. User Prompt
> "i have created the backend and cleanly structured the setup see the @AGENTS.md and start ur task @docs/agent/01_backend.md @docs/ARCHITECTURE.md take a llok at the architecture iam thinking off and u can improve if there are any flaws in the architecture try to improve it and say what you improved and initialize the backend structure , schema according to the architecture proceed with the given tech stack python,postgres database use supabase backend , authentication,sqlalchemy for ORM, fastapi as web http framework for backend,pydantic for data validation and iam approving the artifact the plan we discussed approve the artifact and visually show what is implementing and do update the prompts section"

### 2. Architecture Review & Improvements Made
1. **Cloud & Supabase Compatibility**: In `ARCHITECTURE.md`, hardcoded role creations (`CREATE ROLE ledgerline_app`) can fail on cloud managed databases. Made Alembic migrations role-adaptive, using conditional `DO $$ ... IF EXISTS` blocks while ensuring triggers remain the universal defensive backstop across all hosting environments.
2. **Deterministic Hash Chain Generation**: Established strict canonical string formatting (`to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')`) and calculated hashes atomically within the transaction to prevent application drift.
3. **Double-Entry Safeguards**: Structured `post_movement()` with explicit row locks (`SELECT ... FOR UPDATE ORDER BY id`) and verified zero-sum deferred constraint triggers.
4. **Information Disclosure Prevention**: Enforced uniform `404 Not Found` for any account not owned by the caller in `account_members` to eliminate account enumeration risks.

### 3. What Was Implemented
- Initialized complete backend structure:
  - `backend/app/config.py`: Environment validation with fail-fast production checks.
  - `backend/app/logging.py`: Structlog JSON logger with sensitive data redaction.
  - `backend/app/errors.py`: Domain AppError hierarchy and HTTP status mappers.
  - `backend/app/db/`: Base, psycopg3 pooled engine, and complete SQLAlchemy models matching `ARCHITECTURE.md`.
  - `backend/app/auth/`: Argon2id password hashing with constant-time dummy verification, 256-bit opaque tokens with SHA-256 storage, and progressive login throttling.
  - `backend/app/ledger/`: Single writer engine `post_movement()`, canonical JSON hashing, Pydantic strict paise models, and read-only interleaved statement queries.
  - `backend/app/accounts/`: Customer account lifecycle, system accounts (`EXTERNAL`, `SUSPENSE`), and admin freeze/unfreeze controls.
  - `backend/app/audit/`: Cryptographic hash chain verification engine (`/audit/verify`), duplicate replay logs, and security event auditing.
  - `backend/app/review/`: Deterministic anomaly detection rules isolated from ledger writes.
  - `backend/app/seed/`: Idempotent database seed script.
  - `backend/app/main.py`: FastAPI application factory with security headers, 16 KB body limit, and error envelopes.
  - `backend/migrations/`: Alembic environment and migrations (`0001_initial_schema.py`, `0002_triggers_and_roles.py`).
  - `backend/tests/`: Automated test suite covering conservation, 20-thread withdrawal races, idempotency deduplication, authorization boundaries, append-only trigger rejection, and hash chain tampering detection.


