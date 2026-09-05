"""Ugence Benchmark Registry Authority — BR-2C candidate head (0.3.0rc1).

Independent distribution ``ugence-benchmark-registry-authority``. The
**authority/registry layer** of the shared, platform-wide Benchmark Registry,
sitting above the **frozen identity layer** ``ugence-benchmark-registry`` and
never inside it.

Milestone boundary
------------------
* **BR-2A (0.1.0)** — registry and exact-resolution *contracts*: record, event,
  envelope and request shapes; the registry lifecycle vocabulary and its closed
  relation; one structural representation bound to each transition; typed
  refusals; ports as Protocols; new digest domains; pure validation.
  **No engine, no store, no verifier, no clock read, no resolver.**
* **BR-2B (0.2.0)** — the **non-authoritative lifecycle kernel**:
  transition validation, predecessor checks, terminality, and conflict and
  idempotency calculation over *caller-asserted* state. It ships **no store, no
  verifier, no clock, no append path and no authority-issued result**, and it
  **cannot admit, register, revoke or resolve**. It determines what transition
  *would be* valid; nothing here makes one occur.
* **BR-2C-0 (0.2.1, 0.2.2, 0.2.3)** — BR-2C's ratified **contract surface**,
  and no BR-2C capability. A **version rung, not a subphase** (D-33, D-36):
  the trust-anchor record, the three verified-result types, the reshaped ports
  (D-24, D-25, D-26), the anchor-resolution outcome (D-34) and the verified-
  result refusal subset (D-35); ``api.__all__`` 93 → 108 across the three.
* **BR-2C-RC (this release, 0.3.0rc1)** — the **BR-2C candidate head**. The
  three seams of ``BenchmarkApprovalVerifierPort`` implemented by
  ``BenchmarkEd25519Verifier`` on the D-41 pair (``cryptography`` verifies,
  ``PyNaCl`` validates the public-key point at anchor admission), inside the
  one dedicated module ``verifier.py``; ``BenchmarkDenyAllVerifier``, the
  **exact deny-all default**; the D-42 key-identifier and D-43 actor-identity
  grammar applied at construction; ``api.__all__`` 108 → 110. A **candidate
  version only**, ratified by the owner as such: it conveys no audit,
  independent-review or production-release claim. It cannot admit, register,
  revoke or resolve, holds no anchors and reads no clock — the directory and
  the trusted instant are both inputs. **Not reviewed, not audited, not
  0.3.0.**
* **BR-2C (0.3.0)** — BR-2C's closure: the same verifier after the D-38
  independent external cryptographic reviewer has been individually named and
  the review commissioned and completed, and D-32(4)'s external cryptographic
  audit obtained and recorded. Neither has occurred. The composition-root
  trust-resolver adapter and key entitlements stay with the composition root
  (D-04) and arrive with it.
* **BR-2D (0.4.0)** — the durable registry authority: persistence, the trusted
  clock, compare-and-set transitions, immutable event history, the process-local
  in-memory adapter, and the **first authoritative** admission, registration,
  revocation and exact resolution. Closes with the identity-locked composition
  root. Blocked on ADR DD-10.
* **BR-2E (0.5.0)** — production composition and operations: tenant
  authorization, service APIs, deployment controls, migrations,
  backup/recovery, observability, audit export.

Dependencies
------------
Exactly three runtime dependencies: ``ugence-benchmark-registry==0.1.*`` and
the D-41 pair, ``cryptography`` and ``PyNaCl``, both bounded on both sides and
both imported **only** inside ``verifier.py`` — plus the standard library.
Nothing else, in either direction — a dependency-boundary test proves this
package imports no other Ugence package, confines the pair to the one module,
and that at BR-2A delivery no package in the monorepo imports *this* one. That reverse fact is the **BR-2A
terminal state, not a permanent invariant**: BR-2C and later explicitly may
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
    BenchmarkPlanningOutcome,
    is_byte_identical_resubmission,
    plan_transition,
    plan_submission_outcome,
    BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN,
    BenchmarkTrustRole,
    BenchmarkTrustAnchorStatus,
    BenchmarkVerificationOutcome,
    BenchmarkTrustAnchorRecord,
    BenchmarkPublisherVerifiedResult,
    BenchmarkApprovalVerifiedResult,
    BenchmarkRevocationVerifiedResult,
    BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER,
    BENCHMARK_VERIFIED_RESULT_BOUND_FACTS,
    BENCHMARK_TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    BENCHMARK_PUBLISHER_VERIFIED_RESULT_DIGEST_DOMAIN,
    BENCHMARK_APPROVAL_VERIFIED_RESULT_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_VERIFIED_RESULT_DIGEST_DOMAIN,
    BenchmarkTrustAnchorResolution,
    BENCHMARK_VERIFICATION_REFUSAL_REASONS,
    BenchmarkDenyAllVerifier,
    BenchmarkEd25519Verifier,
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
    "BenchmarkTrustRole",
    "BenchmarkTrustAnchorStatus",
    "BenchmarkVerificationOutcome",
    "BenchmarkTrustAnchorRecord",
    "BenchmarkPublisherVerifiedResult",
    "BenchmarkApprovalVerifiedResult",
    "BenchmarkRevocationVerifiedResult",
    "BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER",
    "BENCHMARK_VERIFIED_RESULT_BOUND_FACTS",
    "BENCHMARK_TRUST_ANCHOR_RECORD_DIGEST_DOMAIN",
    "BENCHMARK_PUBLISHER_VERIFIED_RESULT_DIGEST_DOMAIN",
    "BENCHMARK_APPROVAL_VERIFIED_RESULT_DIGEST_DOMAIN",
    "BENCHMARK_REVOCATION_VERIFIED_RESULT_DIGEST_DOMAIN",
    # D-34: the anchor-resolution outcome. Appended, never inserted.
    "BenchmarkTrustAnchorResolution",
    # D-35: the refusal subset a verified result may carry.
    "BENCHMARK_VERIFICATION_REFUSAL_REASONS",
    # BR-2C candidate rung (0.3.0rc1): the candidate verifier and the exact
    # deny-all default. Candidate only — not reviewed, not audited, not 0.3.0.
    "BenchmarkDenyAllVerifier",
    "BenchmarkEd25519Verifier",
    "api",
]
