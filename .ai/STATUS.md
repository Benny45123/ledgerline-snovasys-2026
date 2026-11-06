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

## In Progress
- [ ] Frontend dashboard, move money, and audit screen integration with the backend API.

## Blocked
- None.

## Next Steps
- Implement frontend BFF routes and user screens (Dashboard, Move Money with idempotency key generation, Statements, Audit Explorer).
- Implement the `LedgerChain3D` component with `@react-three/fiber` and SVG fallback.

