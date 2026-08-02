"""Read-only enterprise signal adapters for Code Governance (MVP 1D).

Every adapter is strictly read-only and produces **data only** — an
``AdapterResult``. Adapters never authorize, approve, merge, execute, or mutate a
workflow or an external system. GitHub facts are read over a GET/HEAD-only
transport; non-GitHub enterprise sources are integrated as supplied, validated
snapshots. Source failures fail closed and never become positive signals.
"""
from __future__ import annotations

from .change_window_snapshot import ChangeWindowSnapshotAdapter
from .control_status_snapshot import ControlStatusSnapshotAdapter
from .errors import (
    AdapterConfigurationError,
    AdapterError,
    AdapterFailureCode,
    AdapterResponseError,
    ArtifactIdentityMismatch,
    CredentialLeakError,
    NON_RETRYABLE_FAILURES,
    ReadOnlyBoundaryViolation,
)
from .github_readonly import (
    ADAPTER_ID as GITHUB_ADAPTER_ID,
    FORBIDDEN_WRITE_PERMISSIONS,
    GitHubReadOnlyAdapter,
    REQUIRED_READ_PERMISSIONS,
    RetryPolicy,
)
from .identity_snapshot import IdentitySnapshotAdapter
from .incident_snapshot import IncidentSnapshotAdapter
from .models import (
    AdapterCapability,
    AdapterFetchStatus,
    AdapterIdentity,
    AdapterRequest,
    AdapterResult,
    AdapterSourceIdentity,
    CollectedSignalFact,
    FactConsistency,
    ProvenanceMetadata,
    source_response_fingerprint,
)
from .normalization import NormalizedOperationalInput, normalize_results
from .protocols import ReadOnlyAdapter
from .registry import AdapterRegistryEntry, AdapterRegistryProjection
from .snapshot_schemas import (
    SNAPSHOT_SCHEMAS,
    ValidatedSnapshot,
    snapshot_digest,
    validate_supplied_snapshot,
)
from .target_health_snapshot import TargetHealthSnapshotAdapter
from .transport import (
    FakeReadOnlyTransport,
    RawResponse,
    ReadOnlyResponse,
    ReadOnlyTransport,
    TransportPolicy,
)

__all__ = [
    # models
    "AdapterRequest", "AdapterResult", "AdapterIdentity", "AdapterSourceIdentity",
    "AdapterCapability", "CollectedSignalFact", "FactConsistency", "AdapterFetchStatus",
    "ProvenanceMetadata", "source_response_fingerprint",
    # protocol
    "ReadOnlyAdapter",
    # transport
    "ReadOnlyTransport", "FakeReadOnlyTransport", "TransportPolicy", "ReadOnlyResponse",
    "RawResponse",
    # registry
    "AdapterRegistryEntry", "AdapterRegistryProjection",
    # normalization
    "NormalizedOperationalInput", "normalize_results",
    # github adapter
    "GitHubReadOnlyAdapter", "RetryPolicy", "GITHUB_ADAPTER_ID",
    "REQUIRED_READ_PERMISSIONS", "FORBIDDEN_WRITE_PERMISSIONS",
    # snapshot adapters
    "IdentitySnapshotAdapter", "ChangeWindowSnapshotAdapter", "IncidentSnapshotAdapter",
    "TargetHealthSnapshotAdapter", "ControlStatusSnapshotAdapter",
    "SNAPSHOT_SCHEMAS", "ValidatedSnapshot", "snapshot_digest", "validate_supplied_snapshot",
    # errors
    "AdapterError", "ReadOnlyBoundaryViolation", "AdapterConfigurationError",
    "AdapterResponseError", "ArtifactIdentityMismatch", "CredentialLeakError",
    "AdapterFailureCode", "NON_RETRYABLE_FAILURES",
]
