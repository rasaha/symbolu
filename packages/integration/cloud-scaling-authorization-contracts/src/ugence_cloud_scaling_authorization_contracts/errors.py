"""Typed errors and rejection reasons for the Phase 5A authorization-binding boundary.

Every failure here is **fail-closed**: no ``CapacityAuthorizationCandidate`` is produced,
partially produced, or cached. There is no permissive branch, no "warn and continue" and
no downgrade path — an unknown state, an unsupported schema version or an unexpected
exception is a rejection, never a candidate.

The reason vocabulary is deliberately *structural*. Not one member says a signature is
authentic, a producer is trusted, a policy is in force or a decision is currently valid:
Phase 5A cannot establish any of those, so it must not have a word for them.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "CloudScalingAuthorizationContractError",
    "CandidateConstructionError",
    "ExactTypeError",
    "CanonicalFieldError",
    "ReconciliationError",
    "ProducerAttestationError",
    "PolicyTargetBindingError",
    "TargetScopeError",
    "MagnitudeBoundError",
    "CandidateDigestError",
    "AuthorizationCandidateRejectionReason",
]


class CloudScalingAuthorizationContractError(Exception):
    """Base class for every Phase 5A failure. Carries an optional typed reason."""

    def __init__(
        self, message: str, reason: "AuthorizationCandidateRejectionReason | None" = None
    ) -> None:
        super().__init__(message)
        self.reason = reason


class CandidateConstructionError(CloudScalingAuthorizationContractError):
    """A candidate could not be constructed. The base of every rejection below."""


class ExactTypeError(CandidateConstructionError):
    """A source artifact was not the exact required type (subclasses are refused)."""


class CanonicalFieldError(CandidateConstructionError):
    """A field is missing, unknown, malformed, non-NFC or not canonically representable."""


class ReconciliationError(CandidateConstructionError):
    """The Phase 4C projection and the Risk Authority decision did not reconcile."""


class ProducerAttestationError(CandidateConstructionError):
    """The producer attestation is absent, malformed, or bound to something else.

    Never raised to mean "the signature failed verification": Phase 5A does not verify
    signatures. It means the evidence is structurally unusable or binds the wrong digest.
    """


class PolicyTargetBindingError(CandidateConstructionError):
    """The policy/target binding is absent, malformed, or inconsistent with the subject."""


class TargetScopeError(CandidateConstructionError):
    """The execution target scope is malformed or contradicts the projected subject."""


class MagnitudeBoundError(CandidateConstructionError):
    """A requested magnitude or delta exceeds the policy-bound maximum."""


class TemporalOrderingError(CandidateConstructionError):
    """The carried instants are individually valid and collectively impossible (R-12).

    Distinct from :class:`ReconciliationError`, which means a fact disagrees with its source.
    Here every fact matches its source and the *ordering between them* is unsatisfiable, so a
    reader is pointed at the relationship rather than sent to re-check the inputs.
    """


class CandidateDigestError(CandidateConstructionError):
    """The candidate digest could not be computed, or did not equal the carried value."""


class AuthorizationCandidateRejectionReason(str, Enum):
    """The closed, typed rejection vocabulary (ADR Phase 5 §14).

    Every member is a **refusal**. There is deliberately no success member: a successful
    reconciliation returns a candidate, not a reason, so there is no value here that a
    caller could mistake for an approval.
    """

    # --- admission -------------------------------------------------------------------
    UNSUPPORTED_EXACT_TYPE = "unsupported_exact_type"
    MALFORMED_CANONICAL_FIELD = "malformed_canonical_field"
    UNKNOWN_FIELD = "unknown_field"
    NON_CANONICAL_IDENTIFIER = "non_canonical_identifier"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"

    # --- Phase 4 reconciliation ------------------------------------------------------
    PROJECTION_RECONCILIATION_FAILED = "projection_reconciliation_failed"
    TENANT_MISMATCH = "tenant_mismatch"
    SUBJECT_MISMATCH = "subject_mismatch"
    RECOMMENDATION_MISMATCH = "recommendation_mismatch"
    CONTEXT_DIGEST_MISMATCH = "context_digest_mismatch"
    SUBJECT_DIGEST_MISMATCH = "subject_digest_mismatch"
    REQUEST_DIGEST_MISMATCH = "request_digest_mismatch"
    DECISION_DIGEST_MISMATCH = "decision_digest_mismatch"
    DECISION_NOT_ALLOW_FAMILY = "decision_not_allow_family"
    MISSING_BINDING_DECISION = "missing_binding_decision"
    MISSING_DECISION_SNAPSHOT = "missing_decision_snapshot"
    MISSING_EXPIRY_FACT = "missing_expiry_fact"
    #: R-12b. Its own member rather than ``DECISION_DIGEST_MISMATCH``: the digest is intact
    #: and the snapshot is exactly what the authority bound. What is wrong is that a
    #: timestamp the candidate carries is not sourced from — or does not agree with — the
    #: digest-bound artifact it is supposed to project. A source failure, not a corrupt
    #: artifact, and an operator would look in a different place for each.
    #:
    #: Named for *binding*, never authenticity: Phase 5A verifies no signature, so a member
    #: claiming a value is "authenticated" would overstate what this package establishes.
    #: ``test_no_rejection_reason_asserts_authenticity`` enforces that, and caught exactly
    #: this member under its first name.
    DECISION_INSTANT_NOT_BOUND = "decision_instant_not_bound"
    IDEMPOTENCY_KEY_MISMATCH = "idempotency_key_mismatch"
    D4_IDENTIFIER_MISMATCH = "d4_identifier_mismatch"

    # --- producer attestation (structural only) --------------------------------------
    MISSING_PRODUCER_ATTESTATION = "missing_producer_attestation"
    MALFORMED_PRODUCER_ATTESTATION = "malformed_producer_attestation"
    PRODUCER_ATTESTATION_CONTENT_MISMATCH = "producer_attestation_content_mismatch"
    UNSUPPORTED_SIGNING_PURPOSE = "unsupported_signing_purpose"
    FORGED_TRUST_STATE = "forged_trust_state"

    # --- policy / target binding (structural only) -----------------------------------
    MISSING_POLICY_TARGET_BINDING = "missing_policy_target_binding"
    MALFORMED_POLICY_TARGET_BINDING = "malformed_policy_target_binding"
    POLICY_TARGET_CONTENT_MISMATCH = "policy_target_content_mismatch"

    # --- the policy coordinate carried inside the candidate (structural only) ---------
    #: Still structural, and still nothing about authenticity: a coordinate is *named* here,
    #: never resolved. Phase 5B-0B verifies it. These three members exist because "the
    #: candidate carries no coordinate", "the coordinate is malformed" and "the two policy
    #: references in one candidate name different policies" are three different refusals, and
    #: the third is the one 5B-1 exists to make possible.
    MISSING_POLICY_COORDINATE_BINDING = "missing_policy_coordinate_binding"
    MALFORMED_POLICY_COORDINATE_BINDING = "malformed_policy_coordinate_binding"
    POLICY_COORDINATE_CONTENT_MISMATCH = "policy_coordinate_content_mismatch"
    #: R-9 (5B-2). Its own member, deliberately not folded into the mismatch above: the
    #: two references agree perfectly and the coordinate is bound to this very scope. What
    #: is wrong is that the policy belongs to another tenant, which is a scope violation
    #: rather than a content disagreement, and a reader triaging one should not be handed
    #: the other. Named as ``uvi-policy-contracts`` names it.
    CROSS_TENANT_POLICY_BINDING = "cross_tenant_policy_binding"
    MISSING_ACCOUNT_BINDING = "missing_account_binding"
    #: ETS-3. The provider half of the governed account identity named a token outside the
    #: closed vocabulary. Distinct from ``NON_CANONICAL_IDENTIFIER``, which says the string
    #: is malformed: this one says it is well-formed and not a provider this contract knows.
    UNSUPPORTED_CLOUD_PROVIDER = "unsupported_cloud_provider"
    #: ETS-4, the two halves of the Azure resource-group rule. They are separate members
    #: because they are opposite failures — one scope cannot address its target, the other
    #: carries a digest-bound field its provider has no meaning for — and a reader triaging
    #: one must not be handed the other.
    MISSING_RESOURCE_GROUP_BINDING = "missing_resource_group_binding"
    RESOURCE_GROUP_NOT_APPLICABLE = "resource_group_not_applicable"
    ACTION_SUBSTITUTION = "action_substitution"
    TARGET_SUBSTITUTION = "target_substitution"
    REQUESTED_MAGNITUDE_ABOVE_MAXIMUM = "requested_magnitude_above_maximum"
    DELTA_ABOVE_MAXIMUM = "delta_above_maximum"

    # --- temporal coherence among the carried facts (R-12, 5B-2) ----------------------
    #: The six carried instants must be coherent *with each other*, not merely with the
    #: instant a verifier is later handed. Three members rather than one: the subject window,
    #: the decision window and the attestation each fail for a different reason, and a reader
    #: triaging one should not be handed the others.
    #:
    #: These are ordering violations, deliberately separate from
    #: ``PROJECTION_RECONCILIATION_FAILED``: the values reconcile perfectly against their
    #: sources and are individually well-formed. What is wrong is the relationship between
    #: them.
    SUBJECT_TEMPORAL_ORDERING = "subject_temporal_ordering"
    DECISION_TEMPORAL_ORDERING = "decision_temporal_ordering"
    ATTESTATION_TEMPORAL_ORDERING = "attestation_temporal_ordering"

    # --- evidence + digest -----------------------------------------------------------
    INVALID_EVIDENCE_BINDING = "invalid_evidence_binding"
    CANDIDATE_DIGEST_FAILURE = "candidate_digest_failure"
