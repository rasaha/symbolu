"""Ugence Benchmark Registry Authority — BR-2A registry and resolution contracts.

Independent distribution ``ugence-benchmark-registry-authority``. The
**authority/registry layer** of the shared, platform-wide Benchmark Registry,
sitting above the **frozen identity layer** ``ugence-benchmark-registry`` and
never inside it.

Milestone boundary
------------------
* **BR-2A (this release, 0.1.0)** — registry and exact-resolution *contracts*:
  record, event, envelope and request shapes; the registry lifecycle vocabulary
  and its closed relation; one structural representation bound to each
  transition; typed refusals; ports as Protocols; new digest domains; pure
  validation. **No engine, no store, no verifier, no clock read, no resolver.**
* **BR-2B (0.2.0)** — admission and the append-only process-local registry. Its
  verifier is *injected* and defaults to exact deny-all, with a test proving
  nothing can reach ``ADMITTED``.
* **BR-2C (0.3.0)** — publisher trust and signature verification. Blocked on an
  audited cryptographic verifier and a composition-root trust-resolver design.
* **BR-2D (0.4.0)** — durable store and production composition. Blocked on ADR
  DD-10.

Dependencies
------------
Exactly one runtime dependency: ``ugence-benchmark-registry==0.1.*``, plus the
standard library. Nothing else, in either direction — a dependency-boundary test
proves this package imports no other Ugence package, and that at BR-2A delivery
no package in the monorepo imports *this* one. That reverse fact is the **BR-2A
terminal state, not a permanent invariant**: BR-2B and later explicitly may
depend on BR-2A after their own ratification.

The frozen layer stays frozen
------------------------------
``ugence-benchmark-registry`` remains at ``0.1.0`` with its zero-dependency proof
intact. This package adds no BR-1 field, changes no BR-1 digest, appends no
member to BR-1's frozen refusal enum, and never mutates a stored BR-1 canonical
artifact or its identity digest. BR-2 behaviour never goes inside BR-1.
"""

from __future__ import annotations

from . import api
from .api import (
    BenchmarkRegistryContractError,
    BenchmarkRegistryCanonicalizationError,
    BenchmarkRegistryLifecycleError,
    BenchmarkRegistryCompositionError,
    BenchmarkRegistrationState,
    BenchmarkAdmissionOutcome,
    BenchmarkSignatureProfile,
    BenchmarkRegistryRefusalReason,
    BenchmarkRegistryFaultClass,
    BenchmarkRegistryConsistencyScope,
    BenchmarkRegistryConsistencyClaim,
    BenchmarkConfusableNormalizationPosture,
    BenchmarkPublisherSubmissionEnvelope,
    BenchmarkApprovalEnvelope,
    BenchmarkRevocationEnvelope,
    BenchmarkSubmissionRecordPayload,
    BenchmarkAdmissionDecisionPayload,
    BenchmarkPostAdmissionRejectionEventPayload,
    BenchmarkRegistrationEventPayload,
    BenchmarkRevocationEventPayload,
    BenchmarkConflictRecordPayload,
    BenchmarkResolutionRecordPayload,
    BenchmarkHistoricalRecordPayload,
    require_exact_resolution_record_payload,
    require_exact_historical_record_payload,
    BenchmarkExactResolutionRequest,
    BenchmarkHistoricalInspectionRequest,
    PlatformRegistryScopeExpectation,
    TenantRegistryScopeExpectation,
    BenchmarkRegistryScopeExpectation,
    canonical_bytes,
    canonical_digest,
    canonical_domain_inventory,
    is_valid_registration_transition,
    require_valid_registration_transition,
    bound_payload_for_transition,
    require_bound_payload_for_transition,
    fault_class_for,
    BenchmarkRegistryStorePort,
    BenchmarkPublisherTrustDirectoryPort,
    BenchmarkApprovalVerifierPort,
    BenchmarkClockPort,
    BenchmarkRegistryStoreConsistencyDescriptor,
    BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION,
    BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_SUBMISSION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_ADMISSION_DECISION_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_POST_ADMISSION_REJECTION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_REGISTRATION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_CONFLICT_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS,
    BENCHMARK_REGISTRATION_STATE_ORDER,
    BENCHMARK_TERMINAL_REGISTRATION_STATES,
    BENCHMARK_BANNED_REGISTRATION_STATE_NAMES,
    BENCHMARK_REGISTRATION_TRANSITIONS,
    BENCHMARK_TRANSITION_PAYLOAD_BINDING,
    BENCHMARK_UNBOUND_PAYLOAD_TYPES,
    BENCHMARK_REGISTRY_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES,
    BENCHMARK_SIGNING_FRAME_VERSION,
    BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
    BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_SIGNING_FRAME_SPECIFICATION,
    BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS,
    BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT,
    BENCHMARK_REGISTRY_DECLARED_CONSISTENCY,
    BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES,
    BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT,
    BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES,
    BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES,
    BenchmarkRegistrationRecordPresence,
    BenchmarkRegistrySnapshotAssertion,
    BenchmarkTransitionPlan,
    BenchmarkTransitionRefusal,
    BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN,
)
from .version import __version__

__all__ = [
    "__version__",
    "BenchmarkRegistryContractError",
    "BenchmarkRegistryCanonicalizationError",
    "BenchmarkRegistryLifecycleError",
    "BenchmarkRegistryCompositionError",
    "BenchmarkRegistrationState",
    "BenchmarkAdmissionOutcome",
    "BenchmarkSignatureProfile",
    "BenchmarkRegistryRefusalReason",
    "BenchmarkRegistryFaultClass",
    "BenchmarkRegistryConsistencyScope",
    "BenchmarkRegistryConsistencyClaim",
    "BenchmarkConfusableNormalizationPosture",
    "BenchmarkPublisherSubmissionEnvelope",
    "BenchmarkApprovalEnvelope",
    "BenchmarkRevocationEnvelope",
    "BenchmarkSubmissionRecordPayload",
    "BenchmarkAdmissionDecisionPayload",
    "BenchmarkPostAdmissionRejectionEventPayload",
    "BenchmarkRegistrationEventPayload",
    "BenchmarkRevocationEventPayload",
    "BenchmarkConflictRecordPayload",
    "BenchmarkResolutionRecordPayload",
    "BenchmarkHistoricalRecordPayload",
    "require_exact_resolution_record_payload",
    "require_exact_historical_record_payload",
    "BenchmarkExactResolutionRequest",
    "BenchmarkHistoricalInspectionRequest",
    "PlatformRegistryScopeExpectation",
    "TenantRegistryScopeExpectation",
    "BenchmarkRegistryScopeExpectation",
    "canonical_bytes",
    "canonical_digest",
    "canonical_domain_inventory",
    "is_valid_registration_transition",
    "require_valid_registration_transition",
    "bound_payload_for_transition",
    "require_bound_payload_for_transition",
    "fault_class_for",
    "BenchmarkRegistryStorePort",
    "BenchmarkPublisherTrustDirectoryPort",
    "BenchmarkApprovalVerifierPort",
    "BenchmarkClockPort",
    "BenchmarkRegistryStoreConsistencyDescriptor",
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
    "api",
]
