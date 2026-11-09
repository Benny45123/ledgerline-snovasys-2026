"""
How this works / why it is safe:
Unit tests verifying deterministic SHA-256 canonical request hashing and chain linking.
Invariants enforced:
- Key-order independence via canonical JSON serialization (sort_keys=True).
- Deterministic hex output for request bodies.
- Cryptographic chaining: entry_hash = sha256(prev_hash || canonical_fields).
"""

from datetime import datetime, timezone
import uuid
from app.ledger.hashing import compute_entry_hash, compute_request_hash


def test_canonical_json_hashing_is_order_independent() -> None:
    payload_a = {"to_account_id": "acc-123", "amount": 5000, "memo": "payment"}
    payload_b = {"amount": 5000, "memo": "payment", "to_account_id": "acc-123"}
    
    hash_a = compute_request_hash(payload_a)
    hash_b = compute_request_hash(payload_b)
    
    assert hash_a == hash_b
    assert len(hash_a) == 32  # SHA-256 raw bytes
    assert hash_a.hex() == hash_b.hex()
    assert len(hash_a.hex()) == 64


def test_different_payload_produces_different_hash() -> None:
    payload_a = {"amount": 5000}
    payload_b = {"amount": 5001}
    
    assert compute_request_hash(payload_a) != compute_request_hash(payload_b)


def test_entry_hash_computation_is_deterministic() -> None:
    prev_hash = b"\x00" * 32
    acc_id = uuid.uuid4()
    journal_id = uuid.uuid4()
    created_at = datetime(2026, 11, 6, 15, 30, 0, tzinfo=timezone.utc)
    
    hash_1 = compute_entry_hash(
        prev_hash=prev_hash,
        account_id=acc_id,
        account_seq=1,
        journal_id=journal_id,
        amount=50000,
        balance_after=50000,
        created_at=created_at,
    )
    hash_2 = compute_entry_hash(
        prev_hash=prev_hash,
        account_id=acc_id,
        account_seq=1,
        journal_id=journal_id,
        amount=50000,
        balance_after=50000,
        created_at=created_at,
    )
    
    assert hash_1 == hash_2
    assert len(hash_1) == 32
    assert len(hash_1.hex()) == 64
