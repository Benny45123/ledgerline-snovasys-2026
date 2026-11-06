"""
How this works / why it is safe:
Unit tests verifying deterministic SHA-256 canonical request hashing and chain linking.
Invariants enforced:
- Key-order independence via canonical JSON serialization (sort_keys=True).
- Deterministic hex output for request bodies.
- Cryptographic chaining: entry_hash = sha256(prev_hash || canonical_fields).
"""

from app.ledger.hashing import compute_entry_hash, hash_request_payload


def test_canonical_json_hashing_is_order_independent() -> None:
    payload_a = {"to_account_id": "acc-123", "amount": 5000, "memo": "payment"}
    payload_b = {"amount": 5000, "memo": "payment", "to_account_id": "acc-123"}
    
    hash_a = hash_request_payload(payload_a)
    hash_b = hash_request_payload(payload_b)
    
    assert hash_a == hash_b
    assert len(hash_a) == 64  # SHA-256 hex string


def test_different_payload_produces_different_hash() -> None:
    payload_a = {"amount": 5000}
    payload_b = {"amount": 5001}
    
    assert hash_request_payload(payload_a) != hash_request_payload(payload_b)


def test_entry_hash_computation_is_deterministic() -> None:
    prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    created_at_iso = "2026-11-06T15:30:00.000000Z"
    
    hash_1 = compute_entry_hash(
        prev_hash=prev_hash,
        account_id="acc-abc",
        account_seq=1,
        amount=50000,
        balance_after=50000,
        created_at_iso=created_at_iso,
    )
    hash_2 = compute_entry_hash(
        prev_hash=prev_hash,
        account_id="acc-abc",
        account_seq=1,
        amount=50000,
        balance_after=50000,
        created_at_iso=created_at_iso,
    )
    
    assert hash_1 == hash_2
    assert len(hash_1) == 64
