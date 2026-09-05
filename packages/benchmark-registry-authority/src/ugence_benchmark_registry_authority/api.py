"""Canonical public API for the Ugence Benchmark Registry Authority (BR-2C candidate, 0.3.0rc1).

The deliberately curated, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_benchmark_registry_authority`).
``public_api.json`` snapshots this surface and
``tests/packaging/test_public_api.py`` asserts they agree — in the source tree,
in the built wheel, in the built sdist, and in an isolated installed runtime.

What this surface contains
--------------------------
The curated surface at **0.3.0rc1**. It carries BR-2A's ratified "Registry
and exact-resolution *contracts*" — D-01 through D-17 — the **non-authoritative
lifecycle kernel** BR-2B adds on top of them, BR-2C's contract surface, and —
new at this candidate rung — the two implementations of the approval-verifier
port: the candidate verifier and the exact deny-all default.

* the three inbound assertion **envelopes** — publisher submission, independent
  approval, revocation — carrying *declared* signature material;
* the six **administrative chain payloads**, one structural representation per
  transition, each nesting its exact predecessor and deriving every upstream
  digest;
* the two **read payloads**, distinct exact types so a historical answer can
  never be consumed as a current one;
* the two **request shapes** and the two **registry scope expectations**;
* one deterministic canonicalization path and one digest path, versioned and
  domain-separated across twenty-two minted domains;
* the five-member BR-2 **registration lifecycle**, its closed transition
  relation, and the immutable transition-to-payload binding;
* the twenty-four-member BR-2 **refusal vocabulary**, disjoint from BR-1's
  frozen seventeen, and its total classification into seven fault classes;
* four **inert Protocol ports** and one frozen consistency descriptor;
* the three **lifecycle-kernel contracts** BR-2B adds — the caller-asserted
  registry snapshot, the admissible transition plan and its typed refusal —
  and the total planning functions over them;
* the four **BR-2C trust and verification contracts** ratified by D-24, D-25 and
  D-26 — the immutable role-scoped trust-anchor record and the three distinct
  exact verified-result types that replaced the ``bool``-returning approval-
  verifier and publisher-trust-directory seams;
* :class:`BenchmarkTrustAnchorResolution` (D-34) — the anchor-resolution
  outcome that replaced ``Optional[BenchmarkTrustAnchorRecord]`` at the
  trust-directory seam, binding the exact ``(role, identity, key_id)`` triple it
  was asked and carrying an anchor record **XOR** one of the seam's two typed
  refusals, so absence and unavailability can never collapse into one answer;
* :data:`BENCHMARK_VERIFICATION_REFUSAL_REASONS` (D-35) — the twelve of the
  twenty-four a ``REFUSED`` verified result may carry, **derived from the
  fault-class map and never written out**, so an appended member classifies
  itself in or out rather than waiting for a hand-edited list to catch up.

The candidate verifier, and why this is ``0.3.0rc1`` and not ``0.3.0``
-------------------------------------------------------------------------
* :class:`BenchmarkEd25519Verifier` — the three verification seams on the D-41
  pair, inside the one dedicated module ``verifier.py``; and
* :class:`BenchmarkDenyAllVerifier` — the exact deny-all default.

D-23 classifies BR-2C as blocked on both unratified governance and audited
cryptographic engineering. The governance half was cleared at ``BR-2C-0``
(D-24 to D-26, D-32 to D-43). The owner then ruled that candidate engineering
and testing may begin before the D-38 reviewer — an independent external
cryptographic reviewer — is individually named or the review commissioned, and
ratified ``0.3.0rc1`` as a **candidate version only**. This release is that
candidate: engineered and tested, not reviewed, not audited, and never
described as either. ``0.3.0`` — BR-2C's closure — is not taken until that
review and D-32(4)'s external audit are commissioned, completed and recorded.
``BR-2C-RC`` sits between ``BR-2C-0`` and ``BR-2C`` in ``tests/_milestones.py``'s
ladder; it is a **version rung, not a subphase**, and it mints no closure
audit.

``0.3.0`` was not available. §35.1 defines it as the *audited verifier*, which
this release does not ship and D-32 forbids any artifact of this package from
describing as audited, independently reviewed or production-ready until an
external cryptographic audit is obtained and recorded. Taking it would also map
this distribution to BR-2C in the ladder and unlock **twelve** capability
tokens: the eight at ``tests/packaging/test_milestone_boundary.py`` —
``signature_verifier``, ``key_parser``, ``trust_anchor_store``,
``approval_verifier`` and their unseparated spellings — and four more from the
exported-symbol table at ``tests/contract/test_confusable_and_ports.py``:
``denyall``, ``deny_all``, ``verifier`` and ``trust_store``.

Those bans are not the only mechanical enforcement, and D-33 records that too:
the ban on a declared cryptographic dependency, on importing another authority's
package, on any cryptographic call in this tree, on any concrete class
satisfying a port, and on any cryptographic module being imported at all are
**unconditional at every rung**, and no version bump moves them. What no test in
this repository can assert is the external cryptographic audit itself, which
D-32(4) makes a hard precondition to any production use.

What this surface does **not** contain
--------------------------------------
**No registry, no store, no resolver, no admission engine, no trust store or
anchor, no anchor directory, no clock read, no selection API, no supersession
implementation, no adapter registry, no identity allow-list, no production
composition root, no signer, and no cryptographic import outside
``verifier.py``.**

The BR-2C contracts above are **shapes, not capability**; the capability is the
two verifier classes and nothing else. A trust-anchor record type is not a
trust store, and the ports that name the store, the anchor-resolution seam and
the clock remain
inert :class:`typing.Protocol` declarations that nothing in this package
satisfies — asserted structurally by
``tests/contract/test_confusable_and_ports.py``, not promised here. **The
verifier these contracts describe does not exist and has not been audited.**

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
    BenchmarkTrustRole,
    BenchmarkTrustAnchorStatus,
    BenchmarkVerificationOutcome,
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
    BenchmarkTrustAnchorRecord,
    BenchmarkTrustAnchorResolution,
    BenchmarkPublisherVerifiedResult,
    BenchmarkApprovalVerifiedResult,
    BenchmarkRevocationVerifiedResult,
    BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER,
    BENCHMARK_VERIFICATION_REFUSAL_REASONS,
    BENCHMARK_VERIFIED_RESULT_BOUND_FACTS,
    BENCHMARK_TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    BENCHMARK_PUBLISHER_VERIFIED_RESULT_DIGEST_DOMAIN,
    BENCHMARK_APPROVAL_VERIFIED_RESULT_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_VERIFIED_RESULT_DIGEST_DOMAIN,
)
from .verifier import (
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
    # BR-2C's ratified contract surface (D-24, D-25, D-26). Appended, never
    # inserted, so no consumer's recorded position in this list moves.
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
    # D-34: the anchor-resolution outcome the trust-directory seam returns.
    # Appended, never inserted.
    "BenchmarkTrustAnchorResolution",
    # D-35: the refusal subset a verified result may carry. Appended,
    # never inserted.
    "BENCHMARK_VERIFICATION_REFUSAL_REASONS",
    # BR-2C candidate rung (0.3.0rc1): the two implementations of the
    # approval-verifier port — the D-41 candidate verifier and the exact
    # deny-all default. Appended, never inserted. Candidate only: not
    # reviewed, not audited, not 0.3.0.
    "BenchmarkDenyAllVerifier",
    "BenchmarkEd25519Verifier",
]
