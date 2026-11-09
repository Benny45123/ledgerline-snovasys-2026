# LedgerLine — Official Submission Write-Up & Evaluation Answers

> **Snovasys Fresher Hiring Challenge 2026**  
> **Challenge**: "LedgerLine, money movement with a ledger you can prove"  
> **Candidate Track**: Individual Assessment  

---

## Part 1: Comprehensive System Write-Up (750 Words)

### 1. What We Built
LedgerLine is a high-integrity financial core and provable double-entry bookkeeping engine designed to move money with mathematical certainty. Financial systems fail when books stop balancing (lost credits, double pays, race conditions) or when nobody can prove what happened after an incident. LedgerLine solves both problems completely through three non-negotiable laws:
1. **The Books Always Balance**: Every money movement is modeled as a balanced double-entry journal where signed entries sum to exactly zero ($\sum \text{entries} = 0$). External money enters and leaves through a dedicated `EXTERNAL` world account, ensuring the global balance across all accounts is always zero.
2. **Exactly Once**: Every state mutation requires an `Idempotency-Key` scoped to `(user_id, key)` with a stored SHA-256 digest of the canonical request body. Replaying the same key returns the exact cached HTTP response with header `Idempotent-Replayed: true` and logs an append-only replay record without moving money again.
3. **Provable History**: The ledger is strictly append-only. Every entry is cryptographically linked to the previous entry via a per-account SHA-256 hash chain (`entry_hash = sha256(prev_hash || canonical_fields)`). An audit verification engine (`GET /audit/verify`) traverses every entry, recomputes hashes, reconciles cached balances, and flags any database tampering.

### 2. The Integrity & Concurrency Model (In Our Own Words)
All money movement in the entire codebase is channeled through a single, tightly constrained function: `app/ledger/service.py::post_movement()`. It executes inside a single database transaction across six deterministic phases:
- **Phase 1 (Idempotency Claim)**: An `INSERT` into `idempotency_keys` is executed first. If the key already committed, the stored response is returned immediately. If an identical request is in flight, it blocks on the PostgreSQL unique index until the first commits, preventing double-execution.
- **Phase 2 (Deterministic Row Locks)**: Involved accounts are locked using `SELECT ... FOR UPDATE ORDER BY id ASC`. Sorting account IDs in ascending order mathematically prevents AB/BA deadlock cycles when concurrent transfers race in opposite directions.
- **Phase 3 (In-Transaction Authorisation)**: The caller's entitlement to debit the source account is verified directly from DB state inside the locked transaction, immune to client-supplied claims or stale cache reads.
- **Phase 4 (Balance Floor Check)**: The source account's post-movement balance is evaluated against `-overdraft_limit` (default ₹0). If funds are insufficient or the account is frozen, the transaction does not crash.
- **Phase 5 (Refusal as a Record)**: On failure, a `refused_attempts` row is committed with running balance, caller identity, and refusal reason. The 422 refusal response is saved to the idempotency key, preserving a complete audit record of rejected attempts.
- **Phase 6 (Atomic Double-Entry Posting)**: On success, the journal and signed entries are inserted, `balance_after` is recorded, the per-account hash chain is updated, and account cached balances are adjusted before `COMMIT`.

PostgreSQL defense-in-depth triggers reinforce these invariants:
- A deferred constraint trigger asserts $\sum \text{entries} = 0$ at transaction commit.
- Immutability triggers on `journals`, `ledger_entries`, and `refused_attempts` reject any `UPDATE`, `DELETE`, or `TRUNCATE`.
- A database-level `CHECK (balance >= -overdraft_limit)` prevents overdrafts even if application code fails.

### 3. What We Deliberately Did Not Build (and Why)
1. **Multi-Currency (FX) Settlement**: LedgerLine is strictly single-currency (INR, represented as integer paise). Adding FX introduces rounding errors, floating-point drift, and spread calculation edge cases. In an integrity challenge where one lost rupee costs the assessment, a mathematically watertight single-currency engine is superior.
2. **Multi-Region Distributed Consensus**: We selected a single PostgreSQL 16 cluster over distributed multi-master databases (e.g. CockroachDB) to eliminate network split-brain anomalies and relaxed isolation risks.
3. **Autonomous AI Money Execution**: AI surveillance heuristics (`app/review/`) flag unusual patterns (velocity spikes, large transfers), but the machine is strictly forbidden from moving money. A human administrator must authorise every decision.

### 4. How AI Was Used and Where It Was Caught
AI was leveraged for planning, scaffolding, and writing hostile concurrency test cases. However, AI suggestions frequently introduced critical financial bugs:
- **Deadlocks in Opposite Transfers**: Scaffolding locked accounts in arbitrary argument order (`from_account`, then `to_account`). Under 40 parallel opposite transfers, this caused PostgreSQL `40P01` deadlocks. Caught and fixed by enforcing sorted locking (`ORDER BY id ASC`).
- **Idempotency Replay Row Contention**: AI placed `.with_for_update()` on idempotency replay lookups, serializing read queries. Caught and replaced with read-only select.
- **Float Rounding in Audit Verification**: AI wrote verification logic using `Decimal` / `float` sums that introduced precision drift. Caught and replaced with integer paise sums.
All AI errors and human corrections are documented in [`PROMPTS.md`](file:///workspace/PROMPTS.md).

---

## Part 2: Answers to the 6 Submission Portal Questions

### Question 1: Project Title, One-Line Description & Problem Solved
- **Title**: LedgerLine — High-Integrity Financial Core & Provable Double-Entry Ledger
- **One-Line Description**: Move money so the books always balance, the same request never pays twice, and every movement or refusal is cryptographically provable.
- **Problem Solved**:
  LedgerLine solves the three critical vulnerabilities of money movement systems:
  1. *Unbalanced Books*: Solved by atomic double-entry journals where $\sum \text{entries} = 0$ enforced by deferred PostgreSQL triggers, integer paise representation (`BIGINT`), and database CHECK constraints preventing overdrafts.
  2. *Duplicate Payment on Retries*: Solved by Phase 1 idempotency key claims scoped to `(user_id, key)` with payload SHA-256 verification and an append-only replay log.
  3. *Unprovable / Tampered Records*: Solved by append-only ledger tables with trigger-level mutation blocks, per-account SHA-256 hash chains, and real-time cryptographic audit verification (`/audit/verify`).

---

### Question 2: What Works Now (With Test Proofs)
Every core requirement is implemented and verified against cloud PostgreSQL 16:
- **Single-Writer Core**: `app/ledger/service.py::post_movement()` handles all balance mutations.
- **Role-Based Access Control**:
  - `admin`: Account creation, account freezing, manual adjustments against SUSPENSE. Cannot spend user money.
  - `holder`: Deposits, withdrawals, transfers between owned accounts, statement exploration.
  - `auditor`: Strictly read-only access. Non-GET routes return 403.
- **Statement & Refusal Records**: Keyset-paginated statements show debits, credits, running balances, and refused attempts with reasons.
- **Adversarial Test Suites (Passing)**:
  - `tests/concurrency/test_no_overdraft_race.py`: 20 concurrent threads race to withdraw ₹30 from a ₹100 account; exactly 3 succeed, 17 cleanly refused, final balance ₹10.
  - `tests/concurrency/test_deadlock_opposite_transfers.py`: 40 alternating transfers between accounts A and B run concurrently with zero deadlocks.
  - `tests/concurrency/test_idempotency_concurrent.py`: 20 threads submit the same idempotency key simultaneously; exactly 1 executes, 19 receive cached replay.
  - `tests/integration/test_conservation.py`: Global zero-sum conservation verified across deposits, transfers, and withdrawals.
  - `tests/integration/test_property_conservation.py`: Hypothesis property-based testing runs arbitrary operational sequences and proves invariants hold.
  - `tests/security/test_append_only.py`: Database triggers block `UPDATE` and `DELETE` on journals, entries, and refusal tables.
  - `tests/security/test_hash_chain.py`: Simulated tampering of a past entry is detected by `/audit/verify`, pinpointing the exact corrupt sequence.
  - `scripts/mutation_check.sh`: 5/5 core mutations killed (row lock, balance check, idempotency constraint, triggers, membership auth).

---

### Question 3: How to Run (From a Clean Clone)
```bash
# 1. Clone repository
git clone <REPO_URL>
cd ledgerline-snovasys-2026

# 2. Backend setup (Python 3.12, PostgreSQL 16)
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment variables
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ledgerline"
export ENV="dev"
export SESSION_TTL_MINUTES="1440"
export ALLOWED_ORIGINS="http://localhost:3000"
export MAX_AMOUNT_PAISE="10000000000"

# Apply migrations and seed data
alembic upgrade head
python -m app.seed

# Run tests
pytest tests/ -v

# Run mutation check
bash ../scripts/mutation_check.sh

# Start backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Frontend setup (in a separate terminal)
cd ../frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

### Question 4: AI Tools Used
- **Claude 3.5 Sonnet / Claude 3.7 Sonnet (Anthropic)**: Architecture design, PostgreSQL trigger formulation, and adversarial concurrency test authoring.
- **OpenAI GPT-4o / o1-preview**: Edge-case threat modeling for `THREATS.md`, property-based testing schemas (Hypothesis), and RFC error format specifications.
- **Antigravity CLI Agent (Google DeepMind)**: Real-time code implementation, mutation testing orchestration, linting, and full documentation synchronization.

---

### Question 5: What the AI Got Wrong (Bugs Caught & Fixed)
Per challenge instructions, at least 5 dated entries with at least 2 on money/concurrency and 2 on auth/audit are documented in [`PROMPTS.md`](file:///workspace/PROMPTS.md):
1. **Deadlock in Opposite Concurrent Transfers (Money / Concurrency)**:
   - *AI Proposal*: Locked accounts in order of function arguments (`acc_from`, then `acc_to`).
   - *What Was Wrong*: Concurrent requests transferring A $\rightarrow$ B and B $\rightarrow$ A acquired locks in reverse order, creating classic deadlocks (`psycopg.errors.DeadlockDetected: 40P01`).
   - *Correction*: Sorted account IDs deterministically (`ORDER BY id ASC`) before executing `SELECT ... FOR UPDATE`.
2. **Idempotency Key Lock Contention (Concurrency / Idempotency)**:
   - *AI Proposal*: Queried existing idempotency records with `.with_for_update()`.
   - *What Was Wrong*: Concurrent replayed requests queued on the row lock rather than performing lightweight read-only replays, causing latency spikes and timeouts.
   - *Correction*: Removed row lock on read-only replay checks; relied solely on unique constraint blocking during insertion.
3. **Auditor Privilege Escalation (Authorisation / Access Control)**:
   - *AI Proposal*: Allowed auditors to access account statement download endpoints with write audit log hooks.
   - *What Was Wrong*: Auditor role could trigger state modifications, violating strict read-only guarantees.
   - *Correction*: Enforced strict RBAC dependency rejecting all non-GET requests from auditors with uniform 403.
4. **Account Enumeration via 403 Responses (Authorisation / Security)**:
   - *AI Proposal*: Returned 403 Forbidden when a user attempted to access an account they did not own.
   - *What Was Wrong*: Allowed malicious callers to enumerate valid vs invalid account UUIDs across the system.
   - *Correction*: Replaced with uniform 404 Not Found for any account the caller has no membership in.
5. **Mutation Check DB State Pollution (Audit Trail / Testing)**:
   - *AI Proposal*: Executed mutation check tests that modified ledger rows without rollback guards.
   - *What Was Wrong*: Mutation checks left corrupt entries in the database, causing subsequent `/audit/verify` tests to fail.
   - *Correction*: Wrapped mutation tests in `try...finally` restoration blocks to guarantee atomic cleanup.

---

### Question 6: What Is Not Finished (Honest Gaps & Scope Cuts)
From [`docs/UNFINISHED.md`](file:///workspace/docs/UNFINISHED.md):
1. **Three.js WebGL Block Canvas**: The system provides an interactive SVG/CSS animated block chain visualizer on the landing page and audit console. The heavy `@react-three/fiber` WebGL glass canvas was deferred to prioritize mobile performance and fast bundle loading.
2. **Scheduled Batch Transfers**: All transfers are immediate synchronous transactions. Automated batch/payroll scheduling remains future work.
3. **External Cryptographic Anchoring**: Per-account hash chains are validated internally in PostgreSQL. Anchoring the chain root to an external transparency log (e.g. RFC 3161 timestamping service) was deferred.
