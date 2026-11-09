# LedgerLine — Money Movement with a Ledger You Can Prove

> **Snovasys Fresher Hiring Challenge 2026**  
> *"One rupee created, lost, or moved by the wrong person costs the system. A small system that is always right beats a large one that leaks."*

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16.4-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 1. What is LedgerLine?

LedgerLine is a high-integrity financial core and provable double-entry bookkeeping system designed to move money with mathematical certainty. In LedgerLine:

1. **Books Balance**: Every rupee moved has equal, opposite debits and credits. The sum of all accounts (including the external world) is always zero.
2. **Exactly Once**: Every state mutation requires an `Idempotency-Key`. Replaying the same key never moves money twice and returns the exact original response.
3. **Provable History**: The ledger is append-only. Each entry is cryptographically linked to the previous via a per-account SHA-256 hash chain verified by database triggers and audit endpoints.

---

## 2. Futuristic UI/UX, 3D Assets & Typography Architecture

The frontend is crafted as a high-density, institutional-grade fintech dashboard combining reactive micro-interactions, spatial 3D elements, and editorial typographic hierarchy.

```
frontend/
├── app/
│   ├── layout.tsx         # Preconnected typography, safe viewport bounds, anti-flicker theme script
│   ├── page.tsx           # 3D interactive hero, sticky scroll storytelling, ledger table, role cards
│   └── globals.css        # Fintech design tokens, keyframe animations, responsive media queries
└── public/                # Static assets & SVG icons
```

### Aesthetic & Visual Identity
- **Dark & Light Mode Engine**: Dynamic CSS tokens (`--bg`, `--bg2`, `--fg`, `--mut`, `--line`, `--tint`, `--acc`, `--bad`) persisted via `localStorage` with zero-flash pre-hydration scripts.
- **Glassmorphism & Contrast**: Multi-layered backdrop blurs (`backdrop-filter: blur(20px)`), hairline borders (`rgba(255,255,255,0.08)`), and high-contrast accessibility (WCAG AA compliant).
- **Matrix Streamer**: Animated, multi-column transactional log streams embedded into visual divider bands.

### Interactive 3D Phone Stage (`perspective: 1400px`)
- **Spatial Pointer Tracking**: The hero features an interactive 3D phone model rendered using hardware-accelerated CSS perspective matrices. It tracks pointer coordinates dynamically with smooth inertia transitions (`rotateX`, `rotateY`, `scale3d`).
- **Floating Ambient HUD Cards**: Floating status pills (e.g. duplicate retry toast `Idempotent-Replayed: true`) hover above the stage in 3D z-space.
- **Motion Accessibility**: Automatically detects `prefers-reduced-motion` to smoothly disable 3D tilts and animations for users sensitive to motion.

### Typography System
- **Editorial Display**: *Instrument Serif* — used for emotive section markers and high-impact hero headings.
- **Primary Interface**: *Inter Tight* & *Inter* — engineered for dense tabular screens, clear forms, and high-legibility UI labels.
- **Financial Monospace**: *JetBrains Mono* — zero-width drift, tabular figures (`font-variant-numeric: tabular-nums`), ensuring debit and credit columns align down to the paise.

### Choreographed Sticky Storytelling
- The `#how` section synchronizes three distinct steps with the sticky 3D preview through an `IntersectionObserver`:
  1. `01 — BOOKS BALANCE`: Visualizes dual-entry balancing in real time.
  2. `02 — EXACTLY ONCE`: Simulates network retries and duplicate rejection.
  3. `03 — PROVABLE`: Visualizes cryptographic block linking and tamper rejection.

---

## 3. Backend Architecture & Integrity Engine

```
backend/
├── app/
│   ├── main.py            # FastAPI factory, security middleware, 16 KB body limit, error envelopes
│   ├── config.py          # Pydantic Settings with fail-fast production rules & MAX_AMOUNT_PAISE cap
│   ├── logging.py         # Structlog JSON logger with credential & token redaction
│   ├── errors.py          # AppError taxonomy & standardized RFC envelopes
│   ├── deps.py            # Bearer token auth, request_id binding, role guards
│   ├── db/
│   │   ├── base.py        # SQLAlchemy DeclarativeBase
│   │   ├── engine.py      # Psycopg3 pooled connection manager
│   │   └── models.py      # Complete double-entry schema matching ARCHITECTURE.md
│   ├── auth/              # Argon2id hashing, 256-bit opaque tokens, progressive delay throttle
│   ├── ledger/            # Sole money movement pipeline post_movement(), SHA-256 hash chaining
│   ├── accounts/          # Account lifecycle, system accounts (EXTERNAL, SUSPENSE), admin freeze
│   ├── audit/             # 4-point cryptographic audit & reconciliation engine (/audit/verify)
│   ├── review/            # Surveillance heuristics isolated from ledger writes
│   └── seed/              # Idempotent DB seeder
├── migrations/            # Alembic migrations with PostgreSQL triggers (append-only, sum=0, parity)
└── tests/                 # Stratified test suites (concurrency, integration, security, unit)
```

### The Sole Money Movement Pipeline: `post_movement()`
All money movement in the entire codebase passes exclusively through `app/ledger/service.py::post_movement()`. It executes inside a single database transaction across 6 strict phases:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Caller / Frontend
    participant Svc as post_movement()
    participant DB as PostgreSQL 16 (READ COMMITTED)
    
    Client->>Svc: Request Movement (Idempotency-Key: X)
    
    rect rgb(240, 248, 255)
    Note over Svc,DB: Phase 1: Claim Idempotency Key
    Svc->>DB: INSERT INTO idempotency_keys
    alt Conflict & Committed
        Svc-->>Client: Replay stored result (Idempotent-Replayed: true)
    else In-Flight
        DB-->>Svc: Blocks until in-flight commits
    end
    end

    rect rgb(255, 250, 240)
    Note over Svc,DB: Phase 2: Deterministic Row Locks
    Svc->>DB: SELECT * FROM accounts WHERE id IN (...) ORDER BY id FOR UPDATE
    DB-->>Svc: Locked account rows (Deadlock Immune)
    end

    rect rgb(255, 245, 245)
    Note over Svc,DB: Phase 3 & 4: In-Transaction Auth & Floor Check
    Svc->>DB: Verify membership in account_members
    alt Insufficient Funds OR Frozen
        Note over Svc,DB: Phase 5: Commit Refusal
        Svc->>DB: INSERT INTO refused_attempts
        Svc->>DB: UPDATE idempotency_keys SET status_code=422
        Svc->>DB: COMMIT
        Svc-->>Client: 422 Refused (Recorded, Non-500)
    end
    end

    rect rgb(245, 255, 245)
    Note over Svc,DB: Phase 6: Double-Entry Execution
    Svc->>DB: INSERT INTO journals (sums to 0)
    Svc->>DB: INSERT INTO ledger_entries (seq, balance_after, prev_hash, entry_hash)
    Svc->>DB: UPDATE accounts SET balance = balance_after
    Svc->>DB: COMMIT (Triggers verify sum=0, append-only, parity)
    Svc-->>Client: 201 Created (Confirmed State)
    end
```

### Inviolable PostgreSQL Defense-in-Depth Triggers
- **`forbid_mutation`**: Rejects any `UPDATE`, `DELETE`, or `TRUNCATE` issued against `journals`, `ledger_entries`, `refused_attempts`, or audit logs.
- **`journal_sums_to_zero`**: Deferred constraint trigger running at `COMMIT`, guaranteeing $\sum \text{entries} = 0$.
- **`balance_cache_matches_entry`**: Asserts that `accounts.balance == balance_after` of that account's latest ledger entry.
- **`CHECK (balance >= -overdraft_limit)`**: Enforces the balance floor at the database disk level.

---

## 4. Role Permissions & Seed Credentials

Authentication uses Argon2id password hashing and 256-bit cryptographically secure opaque bearer tokens. Foreign account lookups return uniform `404 Not Found` (never 403) to eliminate account enumeration attacks.

| Role | Seed Email | Password | Allowed Capabilities |
| :--- | :--- | :--- | :--- |
| **`admin`** | `admin@ledgerline.test` | `AdminPass123!` | Create accounts, freeze/unfreeze accounts, execute system adjustments against SUSPENSE. Cannot spend user money. |
| **`holder`** | `holder1@ledgerline.test` | `HolderPass123!` | Deposit, withdraw, transfer between owned accounts, inspect keyset-paginated statements. |
| **`holder`** | `holder2@ledgerline.test` | `HolderPass123!` | Counterparty account for transfer verification. |
| **`auditor`** | `auditor@ledgerline.test` | `AuditorPass123!` | Strictly read-only. Inspect ledger entries, call `/audit/verify`, inspect replay logs. All POST/PUT routes return 403. |

---

## 5. Stratified Test Suites

The test suite is stratified into four dedicated directories inside `backend/tests/`:

```
backend/tests/
├── concurrency/
│   ├── test_no_overdraft_race.py              # 20 parallel threads withdrawal race against ₹100
│   ├── test_deadlock_opposite_transfers.py    # 40 concurrent alternating transfers (A->B vs B->A)
│   └── test_idempotency_concurrent.py         # 20 concurrent identical key submissions
├── integration/
│   ├── test_conservation.py                   # Multi-account zero-sum conservation test
│   ├── test_db_constraints.py                # PostgreSQL CHECK & trigger constraint tests
│   ├── test_idempotency.py                    # Sequential deduplication & payload reuse detection
│   └── test_refusals_recorded.py              # Invariant I5: Refusal rows committed to DB
├── security/
│   ├── test_authorization.py                  # RBAC, auditor read-only locks, uniform 404s
│   ├── test_append_only.py                    # Trigger mutation rejection on ledger tables
│   ├── test_hash_chain.py                     # Tamper detection pinpointing exact broken sequence
│   └── test_import_boundaries.py              # Architectural layer isolation
└── unit/
    ├── test_amount_validation.py              # Pydantic validation: integer paise, strict extra="forbid"
    ├── test_error_shape.py                    # RFC standardized error envelope format
    ├── test_hashing_unit.py                   # Canonical JSON hashing & SHA-256 linking
    └── test_sessions.py                       # 256-bit token entropy & expiration logic
```

---

## 6. Getting Started Locally

### Prerequisites
- Python 3.12+ & `uv` package manager
- Node.js 20+ & `pnpm` (or `npm`)
- PostgreSQL 16 (Local Docker or Supabase / Neon connection)

### 1. Database & Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure environment variables
export DATABASE_URL_APP="postgresql://postgres:postgres@localhost:5432/ledgerline"
export ENV="dev"
export SESSION_TTL_MINUTES="1440"
export ALLOWED_ORIGINS="http://localhost:3000"
export MAX_AMOUNT_PAISE="10000000000"

# Apply Alembic migrations (creates tables & triggers)
alembic upgrade head

# Seed database with initial users and system accounts
python -m app.seed

# Start the FastAPI backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend API will be live at: `http://localhost:8000` (Docs at `/docs`).

### 2. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies and start development server
pnpm install
pnpm dev
```

Frontend UI will be live at: `http://localhost:3000`.

---

## 7. Try the Hostile Scenarios (Verify via `curl`)

### A. Idempotent Transfer & Replay
```bash
# 1. Login as holder1
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"holder1@ledgerline.test","password":"HolderPass123!"}' | jq -r '.token')

# 2. Execute transfer with Idempotency-Key
KEY="demo-key-$(date +%s)"
curl -i -X POST http://localhost:8000/transfers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"from_account_id":"<ACC_ID>","to_account_id":"<DEST_ID>","amount":25000}'

# 3. Replay exact same request: returns identical result with Idempotent-Replayed: true
curl -i -X POST http://localhost:8000/transfers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"from_account_id":"<ACC_ID>","to_account_id":"<DEST_ID>","amount":25000}'
```

### B. Run Cryptographic Audit Verification
```bash
# Login as auditor
AUDITOR_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"auditor@ledgerline.test","password":"AuditorPass123!"}' | jq -r '.token')

# Trigger cryptographic verification: recomputes SHA-256 chains and reconciles balances
curl -s -X GET http://localhost:8000/audit/verify \
  -H "Authorization: Bearer $AUDITOR_TOKEN" | jq .
```

---

## 8. AI Usage & Honesty Disclosure

In accordance with the hiring challenge guidelines, AI tools were used for architecture planning, boilerplate generation, and adversarial test scaffolding. All prompts, tool suggestions, rejected approaches, and corrections are recorded in [`PROMPTS.md`](file:///workspace/PROMPTS.md). Full agent coordination logs are preserved in [`.ai/`](file:///workspace/.ai/).

---

## 9. Deliverables & Documentation Index

| Deliverable | Location | Description |
| :--- | :--- | :--- |
| **API Reference** | [`docs/API.md`](file:///workspace/docs/API.md) | Exhaustive endpoint specification: who may call it, request/response, and effect on money. |
| **Threat Model** | [`THREATS.md`](file:///workspace/THREATS.md) | 46 concrete threats across concurrency, idempotency, auth, and tampering—all closed by tests. |
| **Mutation Testing** | [`docs/MUTATION_REPORT.md`](file:///workspace/docs/MUTATION_REPORT.md) | Contractual proof: 5/5 core security mechanisms crippled and killed by test suites. |
| **AI Prompts Log** | [`PROMPTS.md`](file:///workspace/PROMPTS.md) | 12 dated sessions detailing human instructions, AI bugs, tool calls, and verified fixes. |
| **Architecture Specification** | [`docs/ARCHITECTURE.md`](file:///workspace/docs/ARCHITECTURE.md) | Detailed 6-phase atomic movement protocol, hash chaining, and invariant proofs. |
| **Database Schema** | [`docs/DB_SCHEMA.md`](file:///workspace/docs/DB_SCHEMA.md) | Full PostgreSQL schema, constraints, triggers, and immutability rules. |
| **Design Decisions** | [`docs/DESIGN_DECISIONS.md`](file:///workspace/docs/DESIGN_DECISIONS.md) | Plain-English rationale for PostgreSQL 16, double-entry, sorted locking, and integer paise. |
| **Unfinished & Scope Cuts** | [`docs/UNFINISHED.md`](file:///workspace/docs/UNFINISHED.md) | Transparent register of deliberate trade-offs, accepted risks, and in-progress items. |
| **Submission Write-Up** | [`docs/WRITEUP.md`](file:///workspace/docs/WRITEUP.md) | Official 750-word write-up and answers to the 6 submission portal questions. |

---

## 10. License

This project is licensed under the MIT License — see the [LICENSE](file:///workspace/LICENSE) file for details.
