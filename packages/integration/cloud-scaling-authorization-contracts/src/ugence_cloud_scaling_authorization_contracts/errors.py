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
    MISSING_ACCOUNT_BINDING = "missing_account_binding"
    ACTION_SUBSTITUTION = "action_substitution"
    TARGET_SUBSTITUTION = "target_substitution"
    REQUESTED_MAGNITUDE_ABOVE_MAXIMUM = "requested_magnitude_above_maximum"
    DELTA_ABOVE_MAXIMUM = "delta_above_maximum"

    # --- evidence + digest -----------------------------------------------------------
    INVALID_EVIDENCE_BINDING = "invalid_evidence_binding"
    CANDIDATE_DIGEST_FAILURE = "candidate_digest_failure"
