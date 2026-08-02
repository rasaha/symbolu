"""Durable shadow-store schema constants, record/event/recovery vocabularies.

Machine-readable companions: ``docs/store_schema.json``, ``docs/record_types.json``,
``docs/workflow_event_types.json``, ``docs/recovery_statuses.json``.
"""
from __future__ import annotations

from enum import Enum

#: Store schema version. A store with a *newer* schema is rejected (fail closed).
STORE_SCHEMA_VERSION = "code_governance.shadow_store.v1"
SERIALIZATION_VERSION = "code_governance.shadow_serialization.v1"
FINGERPRINT_DOMAIN_VERSION = "v1"

#: Fingerprint domains (domain-separated SHA-256 via fingerprints.domain_hash).
DOMAIN_PAYLOAD = "cg.shadow.payload.v1"
DOMAIN_ENVELOPE = "cg.shadow.envelope.v1"
DOMAIN_EVENT = "cg.shadow.event.v1"
DOMAIN_BUNDLE = "cg.shadow.bundle.v1"

#: Genesis previous-fingerprint for the first record/event in an ordered chain.
GENESIS = "cg-shadow:genesis"


class RecordType(str, Enum):
    """Product-owned + external-audit-projection record types."""

    GOVERNED_CHANGE_IDENTITY = "GOVERNED_CHANGE_IDENTITY"
    EVIDENCE_RECORD = "EVIDENCE_RECORD"
    CLAIM_MANIFEST = "CLAIM_MANIFEST"
    CLAIM_EVALUATION = "CLAIM_EVALUATION"
    TAP_RESULT_PROJECTION = "TAP_RESULT_PROJECTION"
    GOVERNANCE_RECOMMENDATION = "GOVERNANCE_RECOMMENDATION"
    DECISION_RECORD_PROJECTION = "DECISION_RECORD_PROJECTION"
    CONTEXT_ENVELOPE_PROJECTION = "CONTEXT_ENVELOPE_PROJECTION"
    PREPARED_MERGE_ACTION = "PREPARED_MERGE_ACTION"
    ACTIONGATE_RESULT_PROJECTION = "ACTIONGATE_RESULT_PROJECTION"
    OPERATIONAL_SNAPSHOT = "OPERATIONAL_SNAPSHOT"
    TRUSTED_SIGNAL_PROJECTION = "TRUSTED_SIGNAL_PROJECTION"
    CLEARANCE_REQUEST_PROJECTION = "CLEARANCE_REQUEST_PROJECTION"
    ACTION_CLEARANCE_EVALUATION = "ACTION_CLEARANCE_EVALUATION"
    HUMAN_INTERVENTION_ASSESSMENT = "HUMAN_INTERVENTION_ASSESSMENT"
    WORKFLOW_REVISION = "WORKFLOW_REVISION"
    GOVERNANCE_CHAIN = "GOVERNANCE_CHAIN"


#: Record types that are AUDIT PROJECTIONS of externally-owned authoritative
#: records. A stored projection is audit evidence, never a newly issued authority.
EXTERNAL_PROJECTION_TYPES = frozenset({
    RecordType.TAP_RESULT_PROJECTION,
    RecordType.DECISION_RECORD_PROJECTION,
    RecordType.CONTEXT_ENVELOPE_PROJECTION,
    RecordType.ACTIONGATE_RESULT_PROJECTION,
})


class WorkflowEventType(str, Enum):
    """Append-only workflow-event journal event types (shadow only)."""

    STAGE_COMMITTED = "STAGE_COMMITTED"
    STAGE_FAILED_CLOSED = "STAGE_FAILED_CLOSED"
    REVISION_SUPERSEDED = "REVISION_SUPERSEDED"


class PersistenceMode(str, Enum):
    """Workflow persistence mode. There is no enforcement mode."""

    IN_MEMORY_SHADOW = "IN_MEMORY_SHADOW"
    DURABLE_SHADOW = "DURABLE_SHADOW"


class RecoveryStatus(str, Enum):
    """Curated restart-recovery vocabulary (not execution reconciliation)."""

    RECOVERED_COMPLETE = "RECOVERED_COMPLETE"
    RECOVERED_PENDING = "RECOVERED_PENDING"
    RECOVERED_STALE = "RECOVERED_STALE"
    RECOVERED_BLOCKED = "RECOVERED_BLOCKED"
    INCOMPLETE_TRANSACTION_ROLLED_BACK = "INCOMPLETE_TRANSACTION_ROLLED_BACK"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"
    REFERENCE_MISSING = "REFERENCE_MISSING"
    TENANT_MISMATCH = "TENANT_MISMATCH"


class ReconstructionMode(str, Enum):
    """Durable reconstruction / verification modes (no live network in 1C)."""

    STORED_PROJECTION_ONLY = "STORED_PROJECTION_ONLY"
    VERIFY_WITH_SUPPLIED_RESOLVER = "VERIFY_WITH_SUPPLIED_RESOLVER"


#: The store classification. It is NOT a production enforcement store.
STORE_CLASSIFICATION = "DURABLE_SHADOW_REFERENCE"


__all__ = [
    "STORE_SCHEMA_VERSION", "SERIALIZATION_VERSION", "FINGERPRINT_DOMAIN_VERSION",
    "DOMAIN_PAYLOAD", "DOMAIN_ENVELOPE", "DOMAIN_EVENT", "DOMAIN_BUNDLE", "GENESIS",
    "RecordType", "EXTERNAL_PROJECTION_TYPES", "WorkflowEventType", "PersistenceMode",
    "RecoveryStatus", "ReconstructionMode", "STORE_CLASSIFICATION",
]
