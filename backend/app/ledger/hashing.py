"""
How this works / why it is safe:
This module handles deterministic cryptographic hashing for idempotency payloads and ledger chains.
JSON serialization sorts keys and removes whitespace so identical semantic payloads yield identical hashes.
Hash chain digests link each ledger entry to its account predecessor (prev_hash), establishing an
immutable Merkle-like chain. Any superuser modification to past amounts or sequences invalidates
subsequent hashes and is detected by /audit/verify.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID


def compute_request_hash(payload: Dict[str, Any]) -> bytes:
    """Compute deterministic SHA-256 digest of a request payload."""
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).digest()


def compute_entry_hash(
    prev_hash: bytes,
    account_id: UUID,
    account_seq: int,
    journal_id: UUID,
    amount: int,
    balance_after: int,
    created_at: datetime,
) -> bytes:
    """Compute the SHA-256 entry hash matching the database trigger specification."""
    # Format timestamp to UTC ISO-8601 with microseconds
    ts_utc = created_at.astimezone(timezone.utc)
    ts_str = ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    canonical_str = (
        f"{str(account_id)}|{account_seq}|{str(journal_id)}|{amount}|{balance_after}|{ts_str}"
    )
    hasher = hashlib.sha256()
    hasher.update(prev_hash)
    hasher.update(canonical_str.encode("utf-8"))
    return hasher.digest()


def compute_refusal_hash(
    prev_hash: bytes,
    account_id: UUID,
    account_seq: int,
    amount: int,
    balance_at: int,
    reason_code: str,
    created_at: datetime,
) -> bytes:
    """Compute the SHA-256 refusal hash matching the database trigger specification."""
    ts_utc = created_at.astimezone(timezone.utc)
    ts_str = ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    canonical_str = (
        f"{str(account_id)}|{account_seq}|{amount}|{balance_at}|{reason_code}|{ts_str}"
    )
    hasher = hashlib.sha256()
    hasher.update(prev_hash)
    hasher.update(canonical_str.encode("utf-8"))
    return hasher.digest()
