# Implementation Plan: LedgerLine Security & Integrity Remediation

Comprehensive technical blueprint to remediate all vulnerabilities from [`docs/BACKEND_AUDIT_REPORT.md`](file:///workspace/docs/BACKEND_AUDIT_REPORT.md), resolve newly identified architectural gaps across the codebase, and guarantee 100% adherence to Invariants I1–I8 and the 35/35 integrity mark rubric.

---

## 1. Goal Description

LedgerLine is built to satisfy strict financial invariants where no single rupee can be created, lost, or moved by unauthorized actors under high concurrency, replay attacks, or hostile tampering.

While the core mathematical accounting engine (double-entry zero-sum trigger, deterministic row-level lock ordering, balance floor check constraint, and SHA-256 hash chaining) is sound, a comprehensive code audit revealed:
1. **9 Identified Vulnerabilities/Bugs in [`BACKEND_AUDIT_REPORT.md`](file:///workspace/docs/BACKEND_AUDIT_REPORT.md)**:
   - **VULN-01 (Critical)**: Downward balance adjustments fail because `post_movement()` inappropriately enforces a customer `AccountMember` check on the admin caller.
   - **VULN-02 (Critical)**: Recording review decisions crashes with HTTP 500 due to mutating the immutable `review_flags.status` column against PostgreSQL's `forbid_mutation()` trigger.
   - **VULN-03 (High)**: Transfer endpoint allows peer transfers directly into system accounts (`SYS-EXTERNAL`, `SYS-SUSPENSE`).
   - **VULN-04 (High)**: Login rate limiter crashes on failed attempts due to calling `.as_string()` on a SQLAlchemy JSONB element.
   - **VULN-05 (Medium)**: Review flag status escalations misclassified as "dismissed".
   - **VULN-06 (Medium)**: Surveillance heuristic engine (`evaluate_transaction_for_flags`) is disconnected from live transaction flows.
   - **VULN-07 (Medium)**: Admin role permitted to execute direct external cash deposits, violating role segregation rules.
   - **VULN-08 (Low)**: Unhandled `ValueError` on malformed `Content-Length` headers crashes middleware with HTTP 500 instead of HTTP 400.
   - **VULN-09 (Low)**: Keyset statement pagination only supports ascending order, hindering reverse-chronological UI activity rendering.
   - **TEST-01 (High)**: Broken import interfaces, non-existent fixtures, and path bugs across 6 test files.

2. **7 Newly Uncovered Issues in the Codebase**:
   - **GAP-01 (Contractual Architecture)**: Missing `POST /admin/journals/{id}/reverse` endpoint. Contracted in `docs/ARCHITECTURE.md` Section 7 and `AGENTS.md` Section 6, but omitted from HTTP routing.
   - **GAP-02 (Frontend/Backend Contract Mismatch)**: Frontend sends `decision: "approved" | "dismissed"`, whereas backend expects `"approve" | "dismiss" | "escalate"`. Submitting review decisions via the UI fails with HTTP 422.
   - **GAP-03 (Contractual Test Missing)**: Contractual test file `test_property_conservation.py` (Hypothesis random operation sequences mandated in `AGENTS.md` Section 10) is completely missing.
   - **GAP-04 (Broken Concurrency Test)**: `tests/concurrency/test_idempotency_concurrent.py` contains outdated `AccountService`/`LedgerService` imports, incorrect fixtures (`db_session`, `seed_users`), and invalid column name `IdempotencyReplay.idempotency_key` (should be `key`).
   - **GAP-05 (Post-Lock DB Role Authorization)**: In Phase 3 of `post_movement()`, admin callers for adjustments/reversals were not validated against `users.role == 'admin'` directly in the database session, violating Invariant I6.
   - **GAP-06 (Self-Transfer Early Guard)**: `transfer()` route does not check if `from_account_id` and `dest_acc.id` resolve to the identical account prior to transaction dispatch.
   - **GAP-07 (Automated Mutation Check)**: Contractual script `scripts/mutation_check.sh` and report `docs/MUTATION_REPORT.md` are missing.

---

## 2. User Review Required

> [!IMPORTANT]
> **Admin Downward Adjustments & Role Segregation (VULN-01 & VULN-07)**
> - Customer `AccountMember` checks are strictly confined to peer transfers and withdrawals. Admin adjustments will bypass customer membership checks, but `post_movement()` will strictly verify against the database that the initiator user holds `role == 'admin'`.
> - `/accounts/{account_id}/deposit` will be restricted strictly to `require_role("holder")`. Admins must not deposit cash directly without an audited reason against `SUSPENSE`.

> [!WARNING]
> **Append-Only Immutability for Surveillance Flags (VULN-02 & VULN-05)**
> - `ReviewFlag` remains 100% immutable in compliance with Invariant I4 and PostgreSQL trigger `trg_review_flags_append_only_rows`.
> - Effective flag status (`open`, `reviewed`, `dismissed`, `escalated`) will be derived dynamically via an outer join / subquery on the immutable `review_decisions` table.
> - Backend will accept both `"approve"`/`"approved"` and `"dismiss"`/`"dismissed"`, normalizing them cleanly to ensure zero frontend UI breakage.

---

## 3. Open Questions

> [!NOTE]
> None. The architectural decisions, database triggers, and API specifications are definitively specified in [`AGENTS.md`](file:///workspace/AGENTS.md) and [`docs/ARCHITECTURE.md`](file:///workspace/docs/ARCHITECTURE.md).

---

## 4. Proposed Changes

```
+-----------------------------------------------------------------------------------------------------------------+
|                                              REMEDIATION FLOW                                                    |
|                                                                                                                 |
|  [Layer 1: Database & Core Ledger Engine]                                                                       |
|  backend/app/ledger/service.py          --> Fix Phase 3 AuthZ: Support admin adjustments/reversals & role check |
|  backend/app/ledger/queries.py          --> Fix VULN-09: Add order="asc"|"desc" keyset pagination               |
|  backend/app/ledger/schemas.py          --> Add ReversalRequest & order params                                  |
|                                                                                                                 |
|  [Layer 2: Auth, Accounts & Surveillance Routes]                                                                |
|  backend/app/auth/throttle.py           --> Fix VULN-04: Replace .as_string() with .astext                      |
|  backend/app/main.py                    --> Fix VULN-08: Safe integer parsing on Content-Length (HTTP 400)      |
|  backend/app/accounts/routes.py         --> Fix VULN-03: Block system accounts in peer transfers               |
|                                         --> Fix VULN-07: Restrict /deposit strictly to 'holder'                 |
|                                         --> Fix VULN-06: Connect evaluate_transaction_for_flags()               |
|                                         --> Fix GAP-01:  Add POST /admin/journals/{id}/reverse                  |
|  backend/app/review/routes.py           --> Fix VULN-02 & 05: Immutable status derivation from review_decisions |
|  backend/app/review/rules.py            --> Add transfer structuring heuristic check                           |
|  frontend/lib/api.ts                    --> Fix GAP-02: Synchronize review decision types & add reverse endpoint|
|                                                                                                                 |
|  [Layer 3: Test Suite Alignment & Invariant Proving]                                                           |
|  backend/tests/security/test_import_boundaries.py    --> Fix relative directory path (TEST-01)                  |
|  backend/tests/integration/test_refusals_recorded.py --> Fix AccountService/LedgerService & column names        |
|  backend/tests/integration/test_db_constraints.py    --> Fix AccountService & fixture names (TEST-01)          |
|  backend/tests/concurrency/test_idempotency_concurrent.py --> Modernize imports & column names (GAP-04)        |
|  backend/tests/unit/test_hashing_unit.py             --> Fix function names & argument types (TEST-01)          |
|  backend/tests/unit/test_sessions.py                 --> Align with session token hashing API (TEST-01)         |
|  backend/tests/unit/test_error_shape.py              --> Align status codes (409 Refusal) (TEST-01)            |
|  backend/tests/integration/test_property_conservation.py --> [NEW] Hypothesis random op sequence test (GAP-03)   |
|  scripts/mutation_check.sh                          --> [NEW] Contractual mutation check harness (GAP-07)      |
|  docs/MUTATION_REPORT.md                            --> [NEW] Mutation verification output (GAP-07)             |
+-----------------------------------------------------------------------------------------------------------------+
```

---

### Component 1: Core Ledger Engine & Queries

#### [MODIFY] [`backend/app/ledger/service.py`](file:///workspace/backend/app/ledger/service.py)
- **Phase 3 Authorization Hardening**:
  - Load the caller user record from `db` post-lock.
  - If `kind in ("adjustment", "reversal")`: Verify `caller.role == "admin"`. If not an admin, log `unauthorized_admin_action` security event and raise `ForbiddenError`. Exempt adjustments/reversals from the customer `AccountMember` check.
  - If `kind in ("withdrawal", "transfer")`: If `src_acc.kind == "customer"`, verify caller is in `AccountMember(src_acc.id, user_id)`. If missing, log `unauthorized_account_access` security event and raise uniform `NotFoundError("Account not found.")`.
  - If `kind == "deposit"`: If `dest_acc.kind == "customer"`, verify caller is in `AccountMember(dest_acc.id, user_id)`. If missing, raise uniform `NotFoundError`.

```python
# Phase 3: Authorize caller inside transaction post-lock (Invariant I6)
caller = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
if not caller:
    db.rollback()
    raise NotFoundError("User not found.")

if kind in ("adjustment", "reversal"):
    if caller.role != "admin":
        sec_event = SecurityEvent(
            actor_user_id=user_id,
            event="unauthorized_admin_action",
            detail={"action": kind, "caller_role": caller.role},
            request_id=request_id,
        )
        db.add(sec_event)
        db.commit()
        raise ForbiddenError("Only administrators may execute balance adjustments or reversals.")
else:
    # Customer-initiated money movements
    if src_acc.kind == "customer":
        membership = (
            db.query(AccountMember)
            .filter(AccountMember.account_id == src_acc.id, AccountMember.user_id == user_id)
            .first()
        )
        if not membership:
            sec_event = SecurityEvent(
                actor_user_id=user_id,
                event="unauthorized_account_access",
                detail={"account_id": str(src_acc.id), "action": kind},
                request_id=request_id,
            )
            db.add(sec_event)
            db.commit()
            raise NotFoundError("Account not found.")
    
    if kind == "deposit" and dest_acc.kind == "customer":
        membership = (
            db.query(AccountMember)
            .filter(AccountMember.account_id == dest_acc.id, AccountMember.user_id == user_id)
            .first()
        )
        if not membership:
            raise NotFoundError("Account not found.")
```

#### [MODIFY] [`backend/app/ledger/queries.py`](file:///workspace/backend/app/ledger/queries.py)
- Support directional keyset pagination (`order: Literal["asc", "desc"] = "asc"`).
- When `order == "desc"`: `WHERE account_seq < :after_seq` and `ORDER BY account_seq DESC`.
- When `order == "asc"`: `WHERE account_seq > :after_seq` and `ORDER BY account_seq ASC`.

#### [MODIFY] [`backend/app/ledger/schemas.py`](file:///workspace/backend/app/ledger/schemas.py)
- Add `ReversalRequest`:
```python
class ReversalRequest(StrictLedgerBaseModel):
    reason: str = Field(..., min_length=5, max_length=255, description="Mandatory audit reason for reversal")
```

---

### Component 2: Auth, Routes & Surveillance Pipeline

#### [MODIFY] [`backend/app/auth/throttle.py`](file:///workspace/backend/app/auth/throttle.py)
- Replace `.as_string() == email` with `.astext == email`:
```python
email_fails = (
    db.query(func.count(SecurityEvent.id))
    .filter(
        SecurityEvent.event == "login_failed",
        SecurityEvent.created_at >= cutoff,
        SecurityEvent.detail["email"].astext == email,
    )
    .scalar()
    or 0
)
```

#### [MODIFY] [`backend/app/main.py`](file:///workspace/backend/app/main.py)
- Safely parse `Content-Length` header with integer error handling and standardized HTTP 400 envelope:
```python
content_length = request.headers.get("content-length")
if content_length:
    try:
        length_val = int(content_length)
        if length_val < 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": {"code": "bad_request", "message": "Invalid Content-Length header.", "request_id": req_id}},
            )
        if length_val > 16 * 1024:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"error": {"code": "body_too_large", "message": "Request payload exceeds 16 KB limit.", "request_id": req_id}},
            )
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "bad_request", "message": "Invalid Content-Length header.", "request_id": req_id}},
        )
```

#### [MODIFY] [`backend/app/accounts/routes.py`](file:///workspace/backend/app/accounts/routes.py)
1. **Fix VULN-03**: Reject peer transfers targeting system accounts (`dest_acc.kind != "customer"`):
   ```python
   dest_acc = db.query(Account).filter(Account.number == req.to_account_number).first()
   if not dest_acc or dest_acc.status != "active" or dest_acc.kind != "customer":
       raise InvalidDestinationError()
   if req.from_account_id == dest_acc.id:
       raise ValidationError("Source and destination accounts must be distinct.")
   ```
2. **Fix VULN-07**: Restrict `/accounts/{account_id}/deposit` strictly to `require_role("holder")`.
3. **Fix VULN-06**: Hook `evaluate_transaction_for_flags(db, journal, acc_id, amount)` after commit in `deposit`, `withdraw`, `transfer`, `admin_adjustment`, and `admin_reverse`.
4. **Fix GAP-01**: Implement `POST /admin/journals/{journal_id}/reverse`:
   ```python
   @router.post("/admin/journals/{journal_id}/reverse", response_model=MovementResponse)
   def admin_reverse_journal(
       journal_id: UUID,
       req: ReversalRequest,
       response: Response,
       idempotency_key: str = Depends(require_idempotency_key),
       request_id: str = Depends(get_request_id),
       current_user: User = Depends(require_role("admin")),
       db: Session = Depends(get_db),
   ) -> MovementResponse:
       """Post an audited reversal journal (Admin only)."""
       orig_journal = db.query(Journal).filter(Journal.id == journal_id).first()
       if not orig_journal:
           raise NotFoundError("Original journal not found.")
       
       if orig_journal.kind == "reversal":
           raise ValidationError("Cannot reverse a reversal journal.")
       
       # Check if already reversed
       already_reversed = db.query(Journal).filter(Journal.reverses_journal_id == orig_journal.id).first()
       if already_reversed:
           raise ValidationError("Journal has already been reversed.")
       
       # Fetch entries
       entries = db.query(LedgerEntry).filter(LedgerEntry.journal_id == orig_journal.id).all()
       if len(entries) != 2:
           raise ValidationError("Only two-legged journals can be automatically reversed.")
       
       # Invert debit and credit legs
       debit_entry = next(e for e in entries if e.amount < 0)
       credit_entry = next(e for e in entries if e.amount > 0)
       
       movement, is_replayed = post_movement(
           db=db,
           user_id=current_user.id,
           idempotency_key=idempotency_key,
           request_id=request_id,
           kind="reversal",
           source_account_id=credit_entry.account_id,       # Inverted
           destination_account_id=debit_entry.account_id,   # Inverted
           amount=credit_entry.amount,
           raw_payload=req.model_dump(),
           memo=f"Reversal of {orig_journal.id}: {req.reason}",
           reverses_journal_id=orig_journal.id,
       )
       if is_replayed:
           response.headers["Idempotent-Replayed"] = "true"
       return movement
   ```

#### [MODIFY] [`backend/app/review/routes.py`](file:///workspace/backend/app/review/routes.py)
- **Fix VULN-02 & VULN-05 & GAP-02**:
  - Accept `decision: Literal["approve", "approved", "dismiss", "dismissed", "escalate"]`.
  - Normalize `"approved"` -> `"approve"`, `"dismissed"` -> `"dismiss"`.
  - DO NOT update `flag.status`. Persist the immutable decision in `ReviewDecision`.
  - In `list_flags(status: str = "open")`: Query flags joined with latest decision to compute effective status without table mutations.
```python
# Derive effective status dynamically
latest_decisions = (
    db.query(
        ReviewDecision.flag_id,
        ReviewDecision.decision,
        func.row_number().over(
            partition_by=ReviewDecision.flag_id,
            order_by=ReviewDecision.created_at.desc()
        ).label("rn")
    )
    .subquery()
)
```

#### [MODIFY] [`frontend/lib/api.ts`](file:///workspace/frontend/lib/api.ts)
- Update `decideReviewFlag`:
```typescript
async decideReviewFlag(
  flagId: number,
  decision: "approve" | "approved" | "dismiss" | "dismissed" | "escalate",
  reason: string
): Promise<void>
```
- Add `reverseJournal`:
```typescript
async reverseJournal(
  journalId: string,
  reason: string,
  idempotencyKey?: string
): Promise<{ result: MovementResponse; isReplayed: boolean }>
```

---

### Component 3: Test Suite Alignment & Automated Proofs

#### [MODIFY] [`backend/tests/security/test_import_boundaries.py`](file:///workspace/backend/tests/security/test_import_boundaries.py)
- Fix relative path calculation from `"..", "app", "review"` to `"..", "..", "app", "review"`.

#### [MODIFY] [`backend/tests/integration/test_refusals_recorded.py`](file:///workspace/backend/tests/integration/test_refusals_recorded.py)
- Replace `AccountService` and `LedgerService` with `create_customer_account` and `post_movement`.
- Replace `db_session` and `seed_users` fixtures with `db` and `test_users`.
- Replace `attempted_amount` attribute assertion with `refusal.amount`.

#### [MODIFY] [`backend/tests/integration/test_db_constraints.py`](file:///workspace/backend/tests/integration/test_db_constraints.py)
- Replace `AccountService` with `create_customer_account`.
- Replace `db_session` and `seed_users` fixtures with `db` and `test_users`.

#### [MODIFY] [`backend/tests/concurrency/test_idempotency_concurrent.py`](file:///workspace/backend/tests/concurrency/test_idempotency_concurrent.py)
- Replace `AccountService` and `LedgerService` with `create_customer_account` and `post_movement`.
- Replace `db_session` and `seed_users` fixtures with `db` and `test_users`.
- Fix column lookup `IdempotencyReplay.idempotency_key` to `IdempotencyReplay.key`.

#### [MODIFY] [`backend/tests/unit/test_hashing_unit.py`](file:///workspace/backend/tests/unit/test_hashing_unit.py)
- Replace non-existent `hash_request_payload` with `compute_request_hash`.
- Pass proper types (`bytes`, `UUID`, `datetime`) to `compute_entry_hash`.

#### [MODIFY] [`backend/tests/unit/test_sessions.py`](file:///workspace/backend/tests/unit/test_sessions.py)
- Test actual session functions `hash_token`, `create_session`, `get_user_from_token`, and `revoke_session`.

#### [MODIFY] [`backend/tests/unit/test_error_shape.py`](file:///workspace/backend/tests/unit/test_error_shape.py)
- Assert `status_code == 409` for `InsufficientFundsError` and `AccountFrozenError`.

#### [NEW] [`backend/tests/integration/test_property_conservation.py`](file:///workspace/backend/tests/integration/test_property_conservation.py)
- Implement contractual Hypothesis property-based test generating 50+ random sequences of deposits, transfers, withdrawals, and suspense adjustments across 4 distinct accounts.
- Assert that after every sequence:
  1. Net sum of all ledger entries for every journal == 0.
  2. Total customer balances == Sum of deposits - Sum of withdrawals (+/- adjustments).
  3. Global sum of all account balances (customer + external + suspense) is strictly 0.

#### [NEW] [`scripts/mutation_check.sh`](file:///workspace/scripts/mutation_check.sh)
- Automated bash script that sequentially mutates 5 critical defense lines:
  1. Remove `SELECT ... FOR UPDATE` row locks -> Expect race test failure.
  2. Remove Balance floor check in `post_movement` -> Expect overdraft test failure.
  3. Remove Idempotency unique constraint -> Expect duplicate key test failure.
  4. Disable `forbid_mutation()` trigger -> Expect append-only test failure.
  5. Remove Account membership authorization check -> Expect IDOR test failure.
- Compiles mutation score results into [`docs/MUTATION_REPORT.md`](file:///workspace/docs/MUTATION_REPORT.md).

#### [MODIFY] [`THREATS.md`](file:///workspace/THREATS.md)
- Update statuses from `TO VERIFY` to `CLOSED` with exact test suite citations for all audited threats.

---

## 5. Verification Plan

### Automated Tests
Once the execution phase is approved, the test suite will be run against the PostgreSQL database:
```bash
# 1. Run full contractual test suite
cd /workspace/backend && pytest tests/ -v

# 2. Run concurrency race and deadlock tests specifically (under high thread contention)
pytest tests/concurrency/test_no_overdraft_race.py -v
pytest tests/concurrency/test_deadlock_opposite_transfers.py -v
pytest tests/concurrency/test_idempotency_concurrent.py -v

# 3. Run Hypothesis property-based conservation tests
pytest tests/integration/test_property_conservation.py -v

# 4. Run Security and Append-Only Invariant tests
pytest tests/security/test_append_only.py -v
pytest tests/security/test_hash_chain.py -v
pytest tests/security/test_authorization.py -v
pytest tests/security/test_import_boundaries.py -v

# 5. Run mutation check script to generate docs/MUTATION_REPORT.md
bash /workspace/scripts/mutation_check.sh
```

### Manual Verification
1. **Admin Downward Adjustment**:
   - Issue `POST /admin/adjustments` with `amount: -5000` (paise) on an active customer account.
   - Confirm HTTP 200 return and negative debit in account statement against SUSPENSE.
2. **Review Flag Decision**:
   - Trigger a high-value transfer (> ₹5,00,000) or admin adjustment to generate a `ReviewFlag`.
   - Submit `POST /review/flags/{id}/decision` with decision `"approve"` and reason.
   - Confirm HTTP 200 return, zero trigger exceptions, and decision logged in `review_decisions`.
3. **Audit Verification**:
   - Call `GET /audit/verify` and verify `verified: true`, `is_valid: true`, `global_balance_sum: 0`, and `discrepancies: []`.
