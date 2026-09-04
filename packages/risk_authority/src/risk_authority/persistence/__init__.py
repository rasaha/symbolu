"""Persistence: repository contracts, in-memory reference, durable SQLite store, Postgres DDL."""

from __future__ import annotations

from .codec import decode_dataclass, decode_envelope, encode_envelope
from .errors import (
    PersistenceConflictError,
    PersistenceProductionModeError,
    PersistenceStorageError,
)
from .in_memory import (
    InMemoryAuthorityRegistry,
    InMemoryControlResultRepository,
    InMemoryDecisionRepository,
    InMemoryEnvelopeRepository,
    InMemoryEvidenceRepository,
    InMemoryGovernanceEventStore,
    InMemoryRiskCaseRepository,
)
from .sqlite import (
    SQLITE_STORE_SCHEMA_VERSION,
    SqliteIdAllocator,
    SqliteRevocationState,
    SqliteRiskAuthorityStore,
)
from .repositories import (
    AuthorityRegistry,
    ControlResultRepository,
    DecisionRepository,
    EnvelopeRepository,
    EvidenceRepository,
    GovernanceEventStore,
    RiskCaseRepository,
)

__all__ = [
    "RiskCaseRepository",
    "DecisionRepository",
    "EnvelopeRepository",
    "AuthorityRegistry",
    "ControlResultRepository",
    "EvidenceRepository",
    "GovernanceEventStore",
    "InMemoryRiskCaseRepository",
    "InMemoryDecisionRepository",
    "InMemoryEnvelopeRepository",
    "InMemoryAuthorityRegistry",
    "InMemoryControlResultRepository",
    "InMemoryEvidenceRepository",
    "InMemoryGovernanceEventStore",
    "SqliteRiskAuthorityStore",
    "SqliteRevocationState",
    "SqliteIdAllocator",
    "SQLITE_STORE_SCHEMA_VERSION",
    "PersistenceStorageError",
    "PersistenceConflictError",
    "PersistenceProductionModeError",
    "decode_dataclass",
    "encode_envelope",
    "decode_envelope",
]
