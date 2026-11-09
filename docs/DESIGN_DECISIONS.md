# LedgerLine — Design Decisions & Architectural Defense

> Written in accordance with `Problem_Statement.md` ("Where you have freedom — tell us what you chose not to build, and why") and `docs/agent/06_docs.md`.

---

## 1. Why PostgreSQL 16 (Never SQLite)
- **Real Concurrency & Row Locking**: SQLite uses table-level write locks. Under concurrent traffic, transactions serialize or fail with `database is locked`. PostgreSQL provides true row-level locking (`SELECT ... FOR UPDATE`), deferred constraint triggers (`DEFERRABLE INITIALLY DEFERRED`), and transactional DDL.
- **Defense-in-Depth Triggers**: PostgreSQL allows attaching PL/pgSQL constraint triggers that fire at `COMMIT`. If application code has a bug that creates or loses money, PostgreSQL itself rolls back the transaction.
- **Production Truth**: Evaluating financial concurrency on SQLite mocks gives a false sense of security. LedgerLine only runs on real PostgreSQL.

---

## 2. Why Double-Entry (Zero-Sum Conservation)
- **Conservation Law ($I_1$)**: Money cannot be created or destroyed. In single-entry systems, an error during debit leaves credit dangling. In double-entry bookkeeping, every transaction has at least two entries whose signed sum is identically zero ($\sum \text{amount} = 0$).
- **External World Representation**: External deposits and withdrawals are booked against `SYS-EXTERNAL`. A ₹500 deposit debits `SYS-EXTERNAL` by 50,000 paise and credits the customer account by 50,000 paise. The global sum of all balances in the database remains **identically 0**.
- **Admin Adjustments against `SYS-SUSPENSE`**: When an admin performs an adjustment, it is paired with `SYS-SUSPENSE`. Admin actions are auditable double-entry postings, not arbitrary balance overwrites.

---

## 3. Why Deterministic Sorted Row Locking (`ORDER BY id ASC`)
- **Deadlock Immunity**: If User A transfers money to User B at the same millisecond User B transfers to User A, an unordered locking strategy locks Account A then Account B in Thread 1, and Account B then Account A in Thread 2, causing a database deadlock (`40P01`).
- **Our Defense**: All money movements sort account IDs ascending before acquiring locks:
  ```sql
  SELECT * FROM accounts WHERE id IN (:src_id, :dest_id) ORDER BY id ASC FOR UPDATE;
  ```
  Both threads acquire locks in the exact same global order. Deadlocks are mathematically impossible.

---

## 4. Why Integer Paise (No Floats, No Decimals in Core)
- **Zero Rounding Error**: IEEE 754 floating-point arithmetic cannot represent decimal fractions precisely (e.g., `0.1 + 0.2 = 0.30000000000000004`). Over millions of transactions, rounding creates or loses paise.
- **Integer Representation**: All amounts are strictly positive integer paise stored in PostgreSQL `BIGINT` and Python `int`. ₹100.50 is stored as `10050`. Floats and decimals are rejected at schema validation.

---

## 5. Why Append-Only Triggers and Cryptographic Chains
- **Immutable Ledger**: In a financial database, `UPDATE` and `DELETE` on financial records are fatal.
- **Layered Defense**:
  1. The application role has no `UPDATE` or `DELETE` grants on ledger tables.
  2. `forbid_mutation()` database triggers raise exceptions if any update or deletion is attempted.
  3. Every entry computes `entry_hash = SHA256(prev_hash || canonical_fields)`. Any out-of-band manipulation by a database superuser immediately breaks the cryptographic hash chain.
- **Audit Verification Endpoint**: `/audit/verify` verifies the chain from genesis to head and reconciles every journal and global balance equation.

---

## 6. Why AI Never Moves Money
- **Human Authority**: Large Language Models are probabilistic and susceptible to prompt injection, hallucination, and non-deterministic behavior.
- **Strict Isolation**: AI is restricted to anomaly detection and narrative explanations in `app/review/`. The review module cannot import `post_movement()` and has only `SELECT` permissions on ledger tables.
- **Human Decision Audit Trail**: Every AI suggestion must be reviewed and decided by a human administrator, and the decision is permanently recorded in the append-only `review_decisions` table.
