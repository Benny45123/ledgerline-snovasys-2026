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

## In Progress
- [ ] Implement three.js 3D hash chain visualizer (`LedgerChain3D.tsx`) with `@react-three/fiber` and SVG fallback.

## Blocked
- None.

## Next Steps
- Implement `LedgerChain3D` component for 3D glass block chain rendering.
- Complete final deployment check and verification.


