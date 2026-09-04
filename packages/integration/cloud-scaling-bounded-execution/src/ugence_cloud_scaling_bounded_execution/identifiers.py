"""Ratified identifiers for Phase 5D (ADR 5D, D-1 … D-5)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

__all__ = [
    "ISSUER_ID",
    "PROVIDER_ID",
    "SIGNATURE_ALGORITHM",
    "RECORD_SCHEMA_VERSION",
    "RECORD_ID_PREFIX",
    "DEFAULT_DISPATCH_DEADLINE",
    "DISPATCHABLE_ACTION_TYPES",
]

#: The seam is the issuer of every operations-local authorization it mints (D-1).
ISSUER_ID: Final[str] = "ugence.cloud-scaling.bounded-execution"
#: The provider named on every record and effect observation.
PROVIDER_ID: Final[str] = "ugence.cloud-scaling-operations"
SIGNATURE_ALGORITHM: Final[str] = "hmac-sha256"
RECORD_SCHEMA_VERSION: Final[str] = "cloud-scaling-bounded-execution-record-1"
RECORD_ID_PREFIX: Final[str] = "bxr.v1:"
#: How long a dispatch may stay in flight before the ledger treats it as uncertain.
DEFAULT_DISPATCH_DEADLINE: Final[timedelta] = timedelta(minutes=5)
#: The capacity action types the operations executor can carry out (one ``scale``).
#: ``no_change`` derives no credential (5X) and ``coordinated`` has no single-target
#: operation, so neither is dispatchable here.
DISPATCHABLE_ACTION_TYPES: Final[frozenset] = frozenset({"scale_up", "scale_down"})
