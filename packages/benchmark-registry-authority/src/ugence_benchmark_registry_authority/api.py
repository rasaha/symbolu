"""Canonical public API for the Ugence Benchmark Registry Authority (BR-2A).

The deliberately curated, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_benchmark_registry_authority`).
``public_api.json`` snapshots this surface and
``tests/packaging/test_public_api.py`` asserts they agree — in the source tree,
in the built wheel, in the built sdist, and in an isolated installed runtime.

What this surface contains
--------------------------
The structural contract layer of **BR-2A**: "Registry and exact-resolution
*contracts*." Ratified as D-01 through D-17.

* the three inbound assertion **envelopes** — publisher submission, independent
  approval, revocation — carrying *declared* signature material;
* the six **administrative chain payloads**, one structural representation per
  transition, each nesting its exact predecessor and deriving every upstream
  digest;
* the two **read payloads**, distinct exact types so a historical answer can
  never be consumed as a current one;
* the two **request shapes** and the two **registry scope expectations**;
* one deterministic canonicalization path and one digest path, versioned and
  domain-separated across fifteen minted domains;
* the five-member BR-2 **registration lifecycle**, its closed transition
  relation, and the immutable transition-to-payload binding;
* the seventeen-member BR-2 **refusal vocabulary**, disjoint from BR-1's frozen
  seventeen, and its total classification into seven fault classes;
* four **inert Protocol ports** and one frozen consistency descriptor.

What this surface does **not** contain
--------------------------------------
**No registry, no store, no resolver, no admission engine, no signature
verifier, no key parser, no trust store or anchor, no approval verifier, no
clock read, no selection API, no supersession implementation, no adapter
registry, no identity allow-list, no production composition root and no
cryptographic dependency.**

There is no ``latest()``, no ``current()``, no ``active()``, no mutable alias, no
implicit version selection, no fallback and no compatibility coercion anywhere in
this package — and D-07 requires them to be *unrepresentable* rather than merely
absent, which is why every request carries an exact
:class:`~ugence_benchmark_registry.BenchmarkCoordinate` that refused every
floating token at its own construction.

The authority-issued result types ``BenchmarkAdmissionDecision``,
``BenchmarkRegistrationEvent`` and ``BenchmarkResolution`` are **reserved and
undefined**. Their caller-constructible structural counterparts here are all
suffixed ``Payload``, and every one of them permanently derives
``authority_verified``, ``publisher_authenticity_established``,
``approval_authenticity_established``, ``registry_admission_established`` and
``trusted_resolution_established`` as :data:`False` — as read-only properties
with no constructor argument, no assignment path and no subclass hook.

Nothing here is a benchmark result, an observed measurement, a comparison, a
piece of evidence, a verification **receipt**, a policy decision, a readiness
determination, an authorization or a monetary value. "Receipt" is the
trusted-evidence layer's word under ADR §6.4: registry-generated artifacts are
called records or events, and no component issues the independent verification
receipt validating its own action.
"""

from __future__ import annotations

from .contracts import (
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
    BenchmarkPlanningOutcome,
    is_byte_identical_resubmission,
    plan_transition,
    plan_submission_outcome,
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
    "BenchmarkPlanningOutcome",
    "is_byte_identical_resubmission",
    "plan_transition",
    "plan_submission_outcome",
    "BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN",
    "BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN",
    "BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN",
]
