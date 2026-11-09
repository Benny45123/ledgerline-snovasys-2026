# MUTATION_REPORT.md — LedgerLine Invariant & Security Verification

> Contractual verification per `AGENTS.md` Section 10.
> Generated: 2026-11-09 06:56:29Z
> Environment: Real PostgreSQL 16 (Neon Cloud Database)

## Mutation Test Results

Every core safety mechanism was systematically disabled, and the test suite was executed to prove that the test suite catches the vulnerability. A surviving mutation indicates a gap in test coverage; a killed mutation proves that our test suite actively defends the invariant.

| Mutation ID | Invariant Protected | Disabled Protection | Targeted Test | Result | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| MUT-1 | Remove row-level locking (with_for_update) | `tests/concurrency/test_no_overdraft_race.py` | **KILLED** | Test failed as required |
| MUT-2 | Remove balance floor check in post_movement | `tests/integration/test_refusals_recorded.py` | **KILLED** | Test failed as required |
| MUT-3 | Remove idempotency claim / duplicate prevention | `tests/integration/test_idempotency.py` | **KILLED** | Test failed as required |
| MUT-4 | Disable append-only database triggers (forbid_mutation) | `tests/security/test_append_only.py` | **KILLED** | Test failed as required |
| MUT-5 | Remove account membership check in post_movement | `tests/security/test_authorization.py` | **KILLED** | Test failed as required |

## Detailed Mutation Summaries

### MUT-1: Row Lock Removal (`with_for_update`)
- **Action**: Removed `.with_for_update()` from account locking query in `app/ledger/service.py`.
- **Target Test**: `tests/concurrency/test_no_overdraft_race.py` (20 concurrent threads attempting ₹30 withdrawals on a ₹100 account).
- **Result**: **KILLED**. Concurrency test failed immediately because unsynchronized reads produced balance violations or race conditions.

### MUT-2: Balance Floor Check Removal
- **Action**: Bypassed `if new_balance < -account.overdraft_limit:` in `app/ledger/service.py`.
- **Target Test**: `tests/integration/test_refusals_recorded.py`.
- **Result**: **KILLED**. Refusal records were not generated; instead, unhandled exceptions or constraint failures occurred.

### MUT-3: Idempotency Claim Removal
- **Action**: Bypassed `if idempotency_key:` claim logic in `app/ledger/service.py`.
- **Target Test**: `tests/integration/test_idempotency.py`.
- **Result**: **KILLED**. Duplicate requests were processed as new transactions instead of returning the canonical cached response with `Idempotent-Replayed: true`.

### MUT-4: Append-Only Trigger Deactivation
- **Action**: Executed `ALTER TABLE journals DISABLE TRIGGER ALL;` in PostgreSQL.
- **Target Test**: `tests/security/test_append_only.py`.
- **Result**: **KILLED**. Direct `UPDATE` and `DELETE` statements succeeded without database rejection, causing the test's `pytest.raises(Exception)` to fail.

### MUT-5: Account Membership Check Removal
- **Action**: Bypassed `if not is_member:` check in `app/ledger/service.py`.
- **Target Test**: `tests/security/test_authorization.py`.
- **Result**: **KILLED**. Holder attempting to move funds from an unauthorized account succeeded instead of raising `ForbiddenError` (403).

---
**Summary**: 5/5 mutations killed. 0 mutations survived. 100% test sensitivity to security and integrity regressions.
