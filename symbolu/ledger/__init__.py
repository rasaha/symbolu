"""
Ledger Module
=============

Deterministic ledger replay verification for ontological projections.

Public API:
    - LedgerProjectionEntry: Frozen dataclass for ledger entries (legacy)
    - LedgerEntry: Frozen dataclass with hash chain (spec-compliant)
    - LedgerStore: Append-only storage for entries (legacy)
    - LedgerEntryStore: Append-only storage with hash chain (spec-compliant)
    - LedgerReplayVerifier: Deterministic replay verifier (legacy)
    - verify_ledger_replay: Standalone verification function (spec-compliant)
    - ReplayError: Enum of failure codes
    - VerificationResult: Frozen result of verification

    - canonical_serialize: Canonical serialization function
    - compute_entry_hash: Compute entry hash (legacy)
    - compute_entry_id: Compute entry_id with hash chain (spec-compliant)
    - create_entry: Create entry with computed hash (legacy)
    - create_ledger_entry: Create entry with hash chain (spec-compliant)
    - record_projection: Record a projection to store (legacy)
    - record_ledger_entry: Record projection with hash chain (spec-compliant)

    - entry_to_dict: Convert entry to dict (legacy)
    - dict_to_entry: Convert dict to entry (legacy)
    - ledger_entry_to_dict: Convert LedgerEntry to dict (spec-compliant)
    - dict_to_ledger_entry: Convert dict to LedgerEntry (spec-compliant)
    - load_fixture: Load entries from fixture file
    - save_fixture: Save entries to fixture file
"""

from symbolu.ledger.ledger_replay_verifier import (
    LEDGER_REPLAY_INVARIANTS,
    MAPPING_VERSION,
    LedgerEntry,
    LedgerProjectionEntry,
    LedgerReplayVerifier,
    ReplayError,
    VerificationResult,
    canonical_serialize,
    compute_entry_hash,
    compute_entry_id,
    create_entry,
    create_ledger_entry,
    dict_to_entry,
    dict_to_ledger_entry,
    entry_to_dict,
    ledger_entry_to_dict,
    load_fixture,
    save_fixture,
    verify_ledger_replay,
)
from symbolu.ledger.ledger_store import (
    LedgerEntryStore,
    LedgerStore,
    record_ledger_entry,
    record_projection,
)


__all__ = [
    "LEDGER_REPLAY_INVARIANTS",
    "MAPPING_VERSION",
    "LedgerEntry",
    "LedgerEntryStore",
    "LedgerProjectionEntry",
    "LedgerReplayVerifier",
    "LedgerStore",
    "ReplayError",
    "VerificationResult",
    "canonical_serialize",
    "compute_entry_hash",
    "compute_entry_id",
    "create_entry",
    "create_ledger_entry",
    "dict_to_entry",
    "dict_to_ledger_entry",
    "entry_to_dict",
    "ledger_entry_to_dict",
    "load_fixture",
    "record_ledger_entry",
    "record_projection",
    "save_fixture",
    "verify_ledger_replay",
]
