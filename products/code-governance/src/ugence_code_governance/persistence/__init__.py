"""Persistence boundary — narrow protocols, in-memory stores, and the durable
shadow store.

Persistence lives only in the product boundary. The in-memory repositories remain
the default (backward-compatible with MVP 1A/1B). The durable shadow store
(``DURABLE_SHADOW_REFERENCE``) is an opt-in, local, append-only, hash-linked,
integrity-verified SQLite store — **not** a production enforcement store, an
authoritative execution ledger, or an external database dependency.
"""
from __future__ import annotations

from .audit_bundle import (
    BUNDLE_VERSION,
    BundleVerification,
    export_governance_audit_bundle,
    verify_governance_audit_bundle,
)
from .durable_reconstruction import (
    DurableReconstructionResult,
    DurableReconstructionState,
    reconstruct_from_store,
)
from .envelope import RecordEnvelope, WorkflowEventRecord
from .journal import DurableWorkflowJournal
from .errors import (
    DurableStoreError,
    EventChainError,
    ImmutableViolationError,
    InjectedFailure,
    IntegrityFailure,
    ProhibitedFieldError,
    RecordCollisionError,
    ReferenceMissingError,
    SchemaError,
    SchemaIncompatibleError,
    TenantIsolationError,
    TransactionAbortedError,
)
from .memory import (
    InMemoryClaimManifestRepository,
    InMemoryEvidenceRepository,
    InMemoryGovernanceChainRepository,
    InMemoryPreparedActionRepository,
    InMemoryRecommendationRepository,
    InMemoryWorkflowRepository,
)
from .protocols import (
    ClaimManifestRepository,
    EvidenceRepository,
    GovernanceChainRepository,
    PreparedActionRepository,
    RecommendationRepository,
    WorkflowRepository,
)
from .recorder import (
    DurableShadowRecorder,
    rid_actiongate_projection,
    rid_cer_projection,
    rid_change_identity,
    rid_clearance_request,
    rid_decision_projection,
    rid_operational_snapshot,
    rid_prepared_action,
    rid_tap_projection,
    rid_workflow_revision,
)
from .recovery import RecoveryResult, recover_workflow
from .schema import (
    EXTERNAL_PROJECTION_TYPES,
    GENESIS,
    PersistenceMode,
    ReconstructionMode,
    RecordType,
    RecoveryStatus,
    STORE_CLASSIFICATION,
    STORE_SCHEMA_VERSION,
    WorkflowEventType,
)
from .serialization import (
    PROHIBITED_KEY_SUBSTRINGS,
    PayloadClassification,
    canonical_json,
    classify_key,
    serialize,
)
from .sqlite import DurableShadowStore, DurableStoreConfig, open_durable_store

__all__ = [
    # In-memory reference repositories (MVP 1A/1B).
    "EvidenceRepository",
    "ClaimManifestRepository",
    "RecommendationRepository",
    "PreparedActionRepository",
    "WorkflowRepository",
    "GovernanceChainRepository",
    "InMemoryEvidenceRepository",
    "InMemoryClaimManifestRepository",
    "InMemoryRecommendationRepository",
    "InMemoryPreparedActionRepository",
    "InMemoryWorkflowRepository",
    "InMemoryGovernanceChainRepository",
    # Durable shadow store (MVP 1C).
    "DurableShadowStore",
    "DurableStoreConfig",
    "open_durable_store",
    "DurableShadowRecorder",
    "DurableWorkflowJournal",
    "RecordEnvelope",
    "WorkflowEventRecord",
    "RecordType",
    "WorkflowEventType",
    "PersistenceMode",
    "RecoveryStatus",
    "ReconstructionMode",
    "EXTERNAL_PROJECTION_TYPES",
    "STORE_SCHEMA_VERSION",
    "STORE_CLASSIFICATION",
    "GENESIS",
    # Recovery + reconstruction.
    "RecoveryResult",
    "recover_workflow",
    "DurableReconstructionState",
    "DurableReconstructionResult",
    "reconstruct_from_store",
    # Audit bundle.
    "BUNDLE_VERSION",
    "BundleVerification",
    "export_governance_audit_bundle",
    "verify_governance_audit_bundle",
    # Serialization + data minimization.
    "serialize",
    "canonical_json",
    "classify_key",
    "PayloadClassification",
    "PROHIBITED_KEY_SUBSTRINGS",
    # Record-id helpers.
    "rid_change_identity",
    "rid_decision_projection",
    "rid_cer_projection",
    "rid_actiongate_projection",
    "rid_tap_projection",
    "rid_prepared_action",
    "rid_clearance_request",
    "rid_operational_snapshot",
    "rid_workflow_revision",
    # Errors.
    "DurableStoreError",
    "SchemaError",
    "SchemaIncompatibleError",
    "IntegrityFailure",
    "RecordCollisionError",
    "ImmutableViolationError",
    "EventChainError",
    "TenantIsolationError",
    "ProhibitedFieldError",
    "ReferenceMissingError",
    "TransactionAbortedError",
    "InjectedFailure",
]
