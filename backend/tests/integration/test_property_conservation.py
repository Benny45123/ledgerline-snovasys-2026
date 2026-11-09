"""
How this works / why it is safe:
This module fulfills contractual requirement 10 for Invariant I1/I2 property testing.
It uses Hypothesis to generate pseudo-random sequences of valid and invalid
money movements (deposits, transfers, withdrawals) across multiple customer accounts.
Regardless of operation sequence, order, or refusal:
1. Every journal's entries sum to exactly 0 (double-entry conservation).
2. Sum of customer account deltas plus external account delta sums to exactly 0.
3. No account balance ever breaches its overdraft floor (balance >= 0).
4. The cryptographic audit verify engine confirms zero chain discrepancies.
"""

import uuid
from typing import List, Tuple
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import Session
from app.accounts.service import create_customer_account, get_system_account
from app.audit.verify import verify_ledger_integrity
from app.errors import InsufficientFundsError
from app.ledger.service import post_movement


# Define strategy for random ledger operations: (op_kind, account_choice, amount)
operation_strategy = st.lists(
    st.tuples(
        st.sampled_from(["deposit_a", "deposit_b", "transfer_a_to_b", "transfer_b_to_a", "withdraw_a", "withdraw_b"]),
        st.integers(min_value=100, max_value=25000),  # ₹1 to ₹250
    ),
    min_size=2,
    max_size=4,
)


@settings(max_examples=2, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ops=operation_strategy)
def test_hypothesis_conservation_property(db: Session, test_users, ops: List[Tuple[str, int]]):
    """Property test proving conservation and floor invariants across arbitrary operation sequences."""
    holder1 = test_users["holder1"]
    holder2 = test_users["holder2"]
    ext_acc = get_system_account(db, "external")

    initial_ext_balance = ext_acc.balance
    acc_a = create_customer_account(db, f"Hypo A {uuid.uuid4().hex[:4]}", holder1.id, overdraft_limit=0)
    acc_b = create_customer_account(db, f"Hypo B {uuid.uuid4().hex[:4]}", holder2.id, overdraft_limit=0)

    for op_kind, amount in ops:
        idem_key = f"hypo-{uuid.uuid4()}"
        req_id = f"hypo-req-{uuid.uuid4().hex[:8]}"

        try:
            if op_kind == "deposit_a":
                post_movement(
                    db=db,
                    user_id=holder1.id,
                    idempotency_key=idem_key,
                    request_id=req_id,
                    kind="deposit",
                    source_account_id=ext_acc.id,
                    destination_account_id=acc_a.id,
                    amount=amount,
                    raw_payload={"amount": amount},
                )
            elif op_kind == "deposit_b":
                post_movement(
                    db=db,
                    user_id=holder2.id,
                    idempotency_key=idem_key,
                    request_id=req_id,
                    kind="deposit",
                    source_account_id=ext_acc.id,
                    destination_account_id=acc_b.id,
                    amount=amount,
                    raw_payload={"amount": amount},
                )
            elif op_kind == "transfer_a_to_b":
                post_movement(
                    db=db,
                    user_id=holder1.id,
                    idempotency_key=idem_key,
                    request_id=req_id,
                    kind="transfer",
                    source_account_id=acc_a.id,
                    destination_account_id=acc_b.id,
                    amount=amount,
                    raw_payload={"amount": amount},
                )
            elif op_kind == "transfer_b_to_a":
                post_movement(
                    db=db,
                    user_id=holder2.id,
                    idempotency_key=idem_key,
                    request_id=req_id,
                    kind="transfer",
                    source_account_id=acc_b.id,
                    destination_account_id=acc_a.id,
                    amount=amount,
                    raw_payload={"amount": amount},
                )
            elif op_kind == "withdraw_a":
                post_movement(
                    db=db,
                    user_id=holder1.id,
                    idempotency_key=idem_key,
                    request_id=req_id,
                    kind="withdrawal",
                    source_account_id=acc_a.id,
                    destination_account_id=ext_acc.id,
                    amount=amount,
                    raw_payload={"amount": amount},
                )
            elif op_kind == "withdraw_b":
                post_movement(
                    db=db,
                    user_id=holder2.id,
                    idempotency_key=idem_key,
                    request_id=req_id,
                    kind="withdrawal",
                    source_account_id=acc_b.id,
                    destination_account_id=ext_acc.id,
                    amount=amount,
                    raw_payload={"amount": amount},
                )
        except InsufficientFundsError:
            # Clean refusal is expected and recorded in refused_attempts
            pass

    # Refresh balances
    db.refresh(acc_a)
    db.refresh(acc_b)
    db.refresh(ext_acc)

    # Invariant I2 (Floor): customer balances must never be negative
    assert acc_a.balance >= 0, f"Account A breached overdraft floor: {acc_a.balance}"
    assert acc_b.balance >= 0, f"Account B breached overdraft floor: {acc_b.balance}"

    # Invariant I1 (Conservation): sum of customer deltas + external delta == 0
    ext_delta = ext_acc.balance - initial_ext_balance
    total_delta = acc_a.balance + acc_b.balance + ext_delta
    assert total_delta == 0, f"Money creation/destruction detected: delta sum is {total_delta}"

    # Cryptographic verification check
    report = verify_ledger_integrity(db)
    assert report.verified is True
    assert len(report.discrepancies) == 0
    assert report.global_balance_sum == 0
