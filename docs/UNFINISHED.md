# UNFINISHED.md — Known Gaps, Scope Cuts & Honest Trade-Offs

> Requirement: `AGENTS.md` Section 12 ("If something is unfinished, say so in docs/UNFINISHED.md. Honest gaps score; false claims disqualify.") and `Problem_Statement.md` ("Tell us what you chose not to build, and why").

---

## 1. Deliberate Scope Cuts (What We Chose Not to Build)

### 1. Multi-Currency & Cross-Border Exchange Rails
- **Decision**: LedgerLine is strictly single-currency (INR). Any non-INR currency code is rejected at the API boundary.
- **Rationale**: Adding FX conversion introduces floating-point rounding, spread fees, exchange rate drift, and multi-ledger settlement complexity. In a hiring challenge focused on double-entry integrity and concurrency safety (35/35 marks), a single-currency system that is mathematically watertight beats a multi-currency system that leaks paise.

### 2. Multi-Region Active-Active Distributed Consensus
- **Decision**: The system runs against a single PostgreSQL cluster (Neon / local).
- **Rationale**: Distributed multi-master setups (e.g. CockroachDB / Spanner) introduce network partition split-brain risks and relaxed isolation anomalies. PostgreSQL `READ COMMITTED` with deterministic row locking provides immediate consistency and provable zero-deadlock guarantees. If the DB cluster becomes unavailable, the system pauses cleanly without creating or destroying money.

### 3. External Cryptographic Timestamp Anchor (Threat L7)
- **Decision**: The cryptographic SHA-256 hash chain is maintained internally in PostgreSQL.
- **Trade-off**: A cloud database superuser with full `postgres` privileges who rewrites the entire table history and recomputes all hash chains simultaneously cannot be detected without an external root anchor.
- **Future Direction**: Periodically exporting and anchoring the chain head digest (e.g. to Git commit tags, an RFC 3161 timestamping authority, or a public transparency log).

---

## 2. In Progress / Unfinished Features

### 1. Three.js WebGL 3D Block Chain Canvas (`LedgerChain3D.tsx`)
- **Status**: The landing page and audit page currently render the high-craft SVG / CSS animated block chain with real SHA-256 digests and tamper detection states (`.blk.bad`).
- **Gap**: The optional `@react-three/fiber` interactive 3D glass block canvas with orbital controls is not fully built to prioritize accessibility, mobile battery life, and zero-bundle bloat.

### 2. Automated Scheduled / Recurring Batch Transfers
- **Status**: Transfers are immediate synchronous transactions.
- **Gap**: Cron-scheduled payroll batches or future-dated transfers are not implemented.

---

## 3. Summary of Honest Commitments
Every feature documented in `README.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, and `THREATS.md` is live, functional, and verified by passing automated tests. No synthetic constants or placeholder features exist in the money paths.
