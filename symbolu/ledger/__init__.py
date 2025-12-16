"""
Ledger Module
=============

Deterministic ledger replay verification for ontological projections.

Public API:
    - LedgerProjectionEntry: Frozen dataclass for ledger entries
    - LedgerStore: Append-only storage for entries
    - LedgerReplayVerifier: Deterministic replay verifier
    - ReplayError: Enum of failure codes
    - VerificationResult: Frozen result of verification

    - canonical_serialize: Canonical serialization function
    - compute_entry_hash: Compute entry hash
    - create_entry: Create entry with computed hash
    - record_projection: Record a projection to store

    - entry_to_dict: Convert entry to dict
    - dict_to_entry: Convert dict to entry
    - load_fixture: Load entries from fixture file
    - save_fixture: Save entries to fixture file
"""

from symbolu.ledger.ledger_replay_verifier import (
    LEDGER_REPLAY_INVARIANTS,
    LedgerProjectionEntry,
    LedgerReplayVerifier,
    ReplayError,
    VerificationResult,
    canonical_serialize,
    compute_entry_hash,
    create_entry,
    dict_to_entry,
    entry_to_dict,
    load_fixture,
    save_fixture,
)
from symbolu.ledger.ledger_store import (
    LedgerStore,
    record_projection,
)


__all__ = [
    "LEDGER_REPLAY_INVARIANTS",
    "LedgerProjectionEntry",
    "LedgerReplayVerifier",
    "LedgerStore",
    "ReplayError",
    "VerificationResult",
    "canonical_serialize",
    "compute_entry_hash",
    "create_entry",
    "dict_to_entry",
    "entry_to_dict",
    "load_fixture",
    "record_projection",
    "save_fixture",
]
