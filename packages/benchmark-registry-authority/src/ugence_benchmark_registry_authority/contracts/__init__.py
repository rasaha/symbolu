"""BR-2 registry-authority contracts — shapes and pure validation only.

Nothing in this subpackage executes a registry operation. There is no admission
engine, no store, no resolver, no verifier, no key parser, no trust store, no
clock read, no selection API, no supersession implementation, no adapter
registry and no composition root — and every one of those absences is asserted
by ``tests/packaging/test_milestone_boundary.py`` rather than promised here.

Import order is load-bearing: the contract-type registry is populated by the
modules that define contracts and then **sealed** by :mod:`._seal`, which is
imported last. After that point the encoder's exact-type boundary is closed for
the life of the process.
"""

from __future__ import annotations

from ._authority import (
    BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES,
    BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES,
)
from .binding import (
    BENCHMARK_TRANSITION_PAYLOAD_BINDING,
    BENCHMARK_UNBOUND_PAYLOAD_TYPES,
    bound_payload_for_transition,
    require_bound_payload_for_transition,
)
from .canonical import (
    BENCHMARK_ADMISSION_DECISION_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_CONFLICT_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    BENCHMARK_POST_ADMISSION_REJECTION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_REGISTRATION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION,
    BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS,
    BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_SUBMISSION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN,
    BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN,
    canonical_bytes,
    canonical_digest,
    canonical_domain_inventory,
)
from .chain import (
    BenchmarkAdmissionDecisionPayload,
    BenchmarkConflictRecordPayload,
    BenchmarkPostAdmissionRejectionEventPayload,
    BenchmarkRegistrationEventPayload,
    BenchmarkRevocationEventPayload,
    BenchmarkSubmissionRecordPayload,
)
from .confusable import (
    BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS,
    BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT,
)
from .enums import (
    BENCHMARK_BANNED_REGISTRATION_STATE_NAMES,
    BENCHMARK_REGISTRATION_STATE_ORDER,
    BENCHMARK_TERMINAL_REGISTRATION_STATES,
    BenchmarkAdmissionOutcome,
    BenchmarkConfusableNormalizationPosture,
    BenchmarkRegistrationRecordPresence,
    BenchmarkRegistrationState,
    BenchmarkRegistryConsistencyClaim,
    BenchmarkRegistryConsistencyScope,
    BenchmarkRegistryFaultClass,
    BenchmarkSignatureProfile,
)
from .envelopes import (
    BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
    BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_SIGNING_FRAME_SPECIFICATION,
    BENCHMARK_SIGNING_FRAME_VERSION,
    BenchmarkApprovalEnvelope,
    BenchmarkPublisherSubmissionEnvelope,
    BenchmarkRevocationEnvelope,
)
from .errors import (
    BenchmarkRegistryCanonicalizationError,
    BenchmarkRegistryCompositionError,
    BenchmarkRegistryContractError,
    BenchmarkRegistryLifecycleError,
)
from .kernel import (
    BenchmarkRegistrySnapshotAssertion,
    BenchmarkTransitionPlan,
    BenchmarkTransitionRefusal,
)
from .lifecycle import (
    BENCHMARK_REGISTRATION_TRANSITIONS,
    is_valid_registration_transition,
    require_valid_registration_transition,
)
from .ports import (
    BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT,
    BENCHMARK_REGISTRY_DECLARED_CONSISTENCY,
    BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES,
    BenchmarkApprovalVerifierPort,
    BenchmarkClockPort,
    BenchmarkPublisherTrustDirectoryPort,
    BenchmarkRegistryStoreConsistencyDescriptor,
    BenchmarkRegistryStorePort,
)
from .read_payloads import (
    BenchmarkHistoricalRecordPayload,
    BenchmarkResolutionRecordPayload,
    require_exact_historical_record_payload,
    require_exact_resolution_record_payload,
)
from .reasons import (
    BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES,
    BENCHMARK_REGISTRY_REFUSAL_REASONS,
    BenchmarkRegistryRefusalReason,
    fault_class_for,
)
from .requests import (
    BenchmarkExactResolutionRequest,
    BenchmarkHistoricalInspectionRequest,
    BenchmarkRegistryScopeExpectation,
    PlatformRegistryScopeExpectation,
    TenantRegistryScopeExpectation,
)

# Imported last. Every module that registers a contract type has been imported
# by now, so this is the point at which the registry is closed for the life of
# the process. The marker is imported rather than the module so the dependency
# is a real name a linter and a reader can both see.
from ._seal import CONTRACT_TYPE_REGISTRY_SEALED  # noqa: E402  isort:skip

if not CONTRACT_TYPE_REGISTRY_SEALED:  # pragma: no cover - import-time invariant
    raise RuntimeError(
        "the BR-2A contract-type registry was not sealed during package import"
    )

__all__ = [
    # typed contract-validation errors
    "BenchmarkRegistryContractError",
    "BenchmarkRegistryCanonicalizationError",
    "BenchmarkRegistryLifecycleError",
    "BenchmarkRegistryCompositionError",
    # closed vocabularies
    "BenchmarkRegistrationState",
    "BenchmarkAdmissionOutcome",
    "BenchmarkSignatureProfile",
    "BenchmarkRegistryRefusalReason",
    "BenchmarkRegistryFaultClass",
    "BenchmarkRegistryConsistencyScope",
    "BenchmarkRegistryConsistencyClaim",
    "BenchmarkConfusableNormalizationPosture",
    # inbound assertion envelopes
    "BenchmarkPublisherSubmissionEnvelope",
    "BenchmarkApprovalEnvelope",
    "BenchmarkRevocationEnvelope",
    # the administrative chain
    "BenchmarkSubmissionRecordPayload",
    "BenchmarkAdmissionDecisionPayload",
    "BenchmarkPostAdmissionRejectionEventPayload",
    "BenchmarkRegistrationEventPayload",
    "BenchmarkRevocationEventPayload",
    "BenchmarkConflictRecordPayload",
    # read payloads
    "BenchmarkResolutionRecordPayload",
    "BenchmarkHistoricalRecordPayload",
    "require_exact_resolution_record_payload",
    "require_exact_historical_record_payload",
    # requests and scope expectations
    "BenchmarkExactResolutionRequest",
    "BenchmarkHistoricalInspectionRequest",
    "PlatformRegistryScopeExpectation",
    "TenantRegistryScopeExpectation",
    "BenchmarkRegistryScopeExpectation",
    # one canonicalization path, one digest path
    "canonical_bytes",
    "canonical_digest",
    "canonical_domain_inventory",
    # the closed registration relation and its one-payload-per-transition binding
    "is_valid_registration_transition",
    "require_valid_registration_transition",
    "bound_payload_for_transition",
    "require_bound_payload_for_transition",
    # refusal classification
    "fault_class_for",
    # inert ports and the inert consistency descriptor
    "BenchmarkRegistryStorePort",
    "BenchmarkPublisherTrustDirectoryPort",
    "BenchmarkApprovalVerifierPort",
    "BenchmarkClockPort",
    "BenchmarkRegistryStoreConsistencyDescriptor",
    # pinned constants
    "BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION",
    "BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN",
    "BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN",
    "BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN",
    "BENCHMARK_SUBMISSION_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_ADMISSION_DECISION_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_POST_ADMISSION_REJECTION_EVENT_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_REGISTRATION_EVENT_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_REVOCATION_EVENT_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_CONFLICT_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN",
    "BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN",
    "BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN",
    "BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN",
    "BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS",
    "BENCHMARK_REGISTRATION_STATE_ORDER",
    "BENCHMARK_TERMINAL_REGISTRATION_STATES",
    "BENCHMARK_BANNED_REGISTRATION_STATE_NAMES",
    "BENCHMARK_REGISTRATION_TRANSITIONS",
    "BENCHMARK_TRANSITION_PAYLOAD_BINDING",
    "BENCHMARK_UNBOUND_PAYLOAD_TYPES",
    "BENCHMARK_REGISTRY_REFUSAL_REASONS",
    "BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS",
    "BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES",
    "BENCHMARK_SIGNING_FRAME_VERSION",
    "BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN",
    "BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN",
    "BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN",
    "BENCHMARK_SIGNING_FRAME_SPECIFICATION",
    "BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS",
    "BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT",
    "BENCHMARK_REGISTRY_DECLARED_CONSISTENCY",
    "BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES",
    "BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT",
    "BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES",
    "BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES",
    "BenchmarkRegistrationRecordPresence",
    "BenchmarkRegistrySnapshotAssertion",
    "BenchmarkTransitionPlan",
    "BenchmarkTransitionRefusal",
    "BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN",
    "BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN",
    "BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN",
]
