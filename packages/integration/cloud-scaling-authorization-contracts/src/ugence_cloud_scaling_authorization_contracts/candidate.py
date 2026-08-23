"""``CapacityAuthorizationCandidate`` — a reconciled request for authorization.

**The word "candidate" is the contract.** This artifact is a request for authorization
that has not happened. It is not an authorization, not an envelope, not an ActionGate
result, not a credential and not an execution order. Holding one entitles the holder to
*ask* Phase 5B for an envelope, and to nothing else.

The artifact is structurally incapable of saying otherwise. It has no field named or
meaning ``authorized``, ``authority_granted``, ``envelope_issued``, ``actiongate_invoked``,
``credential_issued``, ``actuation_performed``, ``effect_verified`` or ``executable`` — not
as ``True``, and not as a fixed ``False``. A fixed ``False`` would still be a
*representation* of authority, one commit away from being flipped; absence cannot be
flipped. The suite asserts this over the dataclass fields, the canonical dictionary and
the whole distribution's source.

**Time.** This module reads no clock. Phase 5A imports no wall clock anywhere in the
package, accepts no ``now`` and no ``evaluation_time``, and generates no timestamp. It
carries Phase 4's validity facts, the attestation's ``issued_at`` and the decision's
``expires_at`` forward as **facts awaiting Phase 5B's trusted-clock evaluation**, under
field names that say so. Nothing here decides whether any of them is current: a candidate
never claims a recommendation, attestation, policy or decision is valid *now*.

Two of those facts are compared **against each other** at construction (R-12): an attestation
may not be issued before the subject was asserted, nor after the decision was evaluated. That
is a coherence check, not a freshness one — it reads no clock, needs none, and refuses only a
candidate whose own instants contradict each other. Whether any of them is *current* remains
Phase 5B's question, judged under its trusted clock.

**Trust.** Both signature-bearing inputs report ``PRESENT_BUT_NOT_TRUST_VERIFIED``. Phase
5A binds them structurally and verifies neither. That is the whole of what "structurally
bound but not trust-verified" means, and it is why this artifact grants nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from risk_authority.integrations import SubjectRiskDecision
from ugence_cloud_scaling_risk_integration import CapacityRiskSubjectProjection

from .attestation import ProducerAttestationEvidence
from .canonical import canonical_digest, require_canonical_digest
from .errors import AuthorizationCandidateRejectionReason as _Reason
from .errors import (
    CandidateDigestError,
    ExactTypeError,
    MagnitudeBoundError,
    PolicyTargetBindingError,
    ProducerAttestationError,
    TargetScopeError,
)
from .reconciliation import ReconciledPhase4Facts, reconcile_phase4
from .target import (
    POLICY_SCOPE_TENANT,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    PolicyTargetBindingReferenceV2,
)
from .trust import PHASE_5A_TRUST_STATE, EvidenceTrustState

__all__ = [
    "AUTHORIZATION_CANDIDATE_SCHEMA_VERSION",
    "CapacityAuthorizationCandidate",
    "build_capacity_authorization_candidate",
]

#: The canonical schema identifier for this artifact. "candidate" is in the tag itself, so
#: even a raw canonical dictionary read out of an audit log names what it is.
#: Moved to ``-2`` by 5B-1: the candidate gained a required field, so the serialized shape
#: a strict deserializer accepts changed. (The F-2 remediation moved the candidate *digest*
#: without moving this identifier, and correctly so — it changed what the payload covered,
#: not which fields the artifact carries.)
AUTHORIZATION_CANDIDATE_SCHEMA_VERSION: Final[str] = (
    "cloud-scaling-capacity-authorization-candidate-2"
)


def _digest_payload(
    *,
    schema_version: str,
    tenant_id: str,
    subject_id: str,
    subject_type: str,
    recommendation_id: str,
    recommendation_digest: str,
    context_digest: str,
    subject_digest: str,
    request_digest: str,
    decision_id: str,
    decision_snapshot_digest: str,
    decision_digest: str,
    disposition: str,
    risk_outcome: str,
    idempotency_key: str,
    evidence_references: tuple[str, ...],
    evidence_snapshot_digest: str,
    purpose: str,
    domain: str,
    action_type: str,
    magnitude_before: int,
    magnitude_after: int,
    requested_delta: int,
    target_scope: "ExecutionTargetScope",
    target_scope_digest: str,
    policy_binding: "PolicyTargetBindingReference",
    policy_binding_digest: str,
    policy_coordinate_binding: "PolicyTargetBindingReferenceV2",
    policy_coordinate_binding_digest: str,
    producer_attestation: "ProducerAttestationEvidence",
    producer_signing_payload_digest: str,
    producer_id: str,
    producer_key_id: str,
    subject_valid_from_fact: datetime,
    subject_valid_until_fact: datetime,
    subject_asserted_at_fact: datetime,
    decision_evaluated_at_fact: datetime,
    decision_expires_at_fact: datetime,
    attestation_issued_at_fact: datetime,
) -> dict[str, Any]:
    """The single definition of what a candidate digest covers.

    Used by both the builder (before the artifact exists) and the artifact's own
    ``digest_payload()``. One definition means the two can never disagree about the
    covered field set — a drift that would otherwise let a field silently leave the digest.
    """

    return {
        "schema_version": schema_version,
        "tenant_id": tenant_id,
        "subject_id": subject_id,
        "subject_type": subject_type,
        "recommendation_id": recommendation_id,
        "recommendation_digest": recommendation_digest,
        "context_digest": context_digest,
        "subject_digest": subject_digest,
        "request_digest": request_digest,
        "decision_id": decision_id,
        "decision_snapshot_digest": decision_snapshot_digest,
        "decision_digest": decision_digest,
        "disposition": disposition,
        "risk_outcome": risk_outcome,
        "idempotency_key": idempotency_key,
        "evidence_references": list(evidence_references),
        "evidence_snapshot_digest": evidence_snapshot_digest,
        "purpose": purpose,
        "domain": domain,
        "action_type": action_type,
        "magnitude_before": magnitude_before,
        "magnitude_after": magnitude_after,
        "requested_delta": requested_delta,
        # The COMPLETE canonical form of every carried artifact — not a digest standing
        # in for it, and not a hand-picked subset of its fields. Binding only a digest
        # while still *carrying* the object lets the two disagree: the object can be
        # swapped for a rogue one while the stale digest continues to validate, and the
        # candidate then carries evidence the digest never covered. These three lines are
        # what make "the candidate cannot carry different evidence under the same digest"
        # true rather than aspirational.
        "target_scope": target_scope.to_canonical_dict(),
        "policy_binding": policy_binding.to_canonical_dict(),
        "policy_coordinate_binding": policy_coordinate_binding.to_canonical_dict(),
        "producer_attestation": producer_attestation.to_canonical_dict(),
        # The derived digests and signing identity stay bound as well. They are redundant
        # given the full forms above, and deliberately so: a reader auditing the payload
        # sees the identity it expects without having to descend into a nested object.
        "target_scope_digest": target_scope_digest,
        "policy_binding_digest": policy_binding_digest,
        "policy_coordinate_binding_digest": policy_coordinate_binding_digest,
        "producer_signing_payload_digest": producer_signing_payload_digest,
        "producer_id": producer_id,
        "producer_key_id": producer_key_id,
        "subject_valid_from_fact": subject_valid_from_fact,
        "subject_valid_until_fact": subject_valid_until_fact,
        "subject_asserted_at_fact": subject_asserted_at_fact,
        "decision_evaluated_at_fact": decision_evaluated_at_fact,
        "decision_expires_at_fact": decision_expires_at_fact,
        "attestation_issued_at_fact": attestation_issued_at_fact,
        # Framed in deliberately: the digest commits to the fact that neither signature
        # was trust-verified when this candidate was built.
        "producer_attestation_trust_state": PHASE_5A_TRUST_STATE.value,
        "policy_binding_trust_state": PHASE_5A_TRUST_STATE.value,
    }


@dataclass(frozen=True)
class CapacityAuthorizationCandidate:
    """A reconciled, non-authoritative request for a future capacity authorization.

    Immutable and exact-typed. Every field is either a Phase 4 fact that reconciled, a
    structurally validated Phase 5 binding, or a digest over one of those. There is no
    authority field, because there is no authority.
    """

    # --- identity ---------------------------------------------------------------------
    tenant_id: str
    subject_id: str
    subject_type: str
    # --- Phase 4 chain ----------------------------------------------------------------
    recommendation_id: str
    recommendation_digest: str
    context_digest: str
    subject_digest: str
    request_digest: str
    decision_id: str
    decision_snapshot_digest: str
    decision_digest: str
    disposition: str
    risk_outcome: str
    idempotency_key: str
    evidence_references: tuple[str, ...]
    evidence_snapshot_digest: str
    # --- D-4 identifiers (module-owned; never caller-supplied) -------------------------
    purpose: str
    domain: str
    action_type: str
    # --- exact action parameters ------------------------------------------------------
    magnitude_before: int
    magnitude_after: int
    requested_delta: int
    # --- Phase 5 bindings -------------------------------------------------------------
    target_scope: ExecutionTargetScope
    target_scope_digest: str
    policy_binding: PolicyTargetBindingReference
    policy_binding_digest: str
    #: The complete Policy Authority coordinate (5B-1). Required, and required *because* an
    #: optional one would leave the residual it closes open by default.
    policy_coordinate_binding: PolicyTargetBindingReferenceV2
    policy_coordinate_binding_digest: str
    producer_attestation: ProducerAttestationEvidence
    producer_signing_payload_digest: str
    producer_id: str
    producer_key_id: str
    # --- Phase 4 validity FACTS — carried, never evaluated -----------------------------
    #: Named ``…_fact`` throughout: each is a timestamp Phase 5A copied forward without
    #: consulting a clock. Phase 5B evaluates them under its own trusted clock.
    subject_valid_from_fact: datetime
    subject_valid_until_fact: datetime
    subject_asserted_at_fact: datetime
    decision_evaluated_at_fact: datetime
    decision_expires_at_fact: datetime
    attestation_issued_at_fact: datetime
    # --- self ---------------------------------------------------------------------------
    candidate_digest: str
    schema_version: str = AUTHORIZATION_CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != AUTHORIZATION_CANDIDATE_SCHEMA_VERSION:
            raise CandidateDigestError(
                f"schema_version must be {AUTHORIZATION_CANDIDATE_SCHEMA_VERSION!r}",
                _Reason.UNSUPPORTED_SCHEMA_VERSION,
            )
        for name in (
            "target_scope",
            "policy_binding",
            "policy_coordinate_binding",
            "producer_attestation",
        ):
            value = getattr(self, name)
            expected = {
                "target_scope": ExecutionTargetScope,
                "policy_binding": PolicyTargetBindingReference,
                "policy_coordinate_binding": PolicyTargetBindingReferenceV2,
                "producer_attestation": ProducerAttestationEvidence,
            }[name]
            if type(value) is not expected:
                raise ExactTypeError(
                    f"{name} must be an exact {expected.__name__} "
                    f"(got {type(value).__name__})",
                    _Reason.UNSUPPORTED_EXACT_TYPE,
                )
        require_canonical_digest("candidate_digest", self.candidate_digest)
        expected_digest = canonical_digest(self.digest_payload())
        if self.candidate_digest != expected_digest:
            raise CandidateDigestError(
                "candidate_digest does not equal the digest of the canonical payload",
                _Reason.CANDIDATE_DIGEST_FAILURE,
            )

    # --- explicit non-authority ---------------------------------------------------------

    @property
    def trust_state(self) -> EvidenceTrustState:
        """``PRESENT_BUT_NOT_TRUST_VERIFIED`` — the candidate's own evidence posture.

        A read-only property, so ``object.__setattr__`` cannot forge it and a doctored
        instance dictionary cannot shadow it.
        """

        return PHASE_5A_TRUST_STATE

    @property
    def grants_authority(self) -> bool:
        """Always ``False``, and derived — never a stored field.

        This exists so a reader who asks the question gets an unambiguous answer, not so
        the answer can vary. It is not canonical, takes no part in the digest, and there
        is no branch anywhere in this package that could return ``True``.
        """

        return False

    def digest_payload(self) -> dict[str, Any]:
        """The canonical body the candidate digest covers.

        Binds the whole chain: schema, identity, every Phase 4 digest, the D-6 key, the
        D-4 identifiers, the exact action parameters, the execution target, the policy
        binding, the producer attestation's signing identity and payload digest, and the
        carried validity facts. Substituting any one of them changes this digest.

        Delegates to the module-level :func:`_digest_payload` so the builder and the
        artifact cannot drift into two different notions of what the digest covers.
        """

        return _digest_payload(
            schema_version=self.schema_version,
            tenant_id=self.tenant_id,
            subject_id=self.subject_id,
            subject_type=self.subject_type,
            recommendation_id=self.recommendation_id,
            recommendation_digest=self.recommendation_digest,
            context_digest=self.context_digest,
            subject_digest=self.subject_digest,
            request_digest=self.request_digest,
            decision_id=self.decision_id,
            decision_snapshot_digest=self.decision_snapshot_digest,
            decision_digest=self.decision_digest,
            disposition=self.disposition,
            risk_outcome=self.risk_outcome,
            idempotency_key=self.idempotency_key,
            evidence_references=self.evidence_references,
            evidence_snapshot_digest=self.evidence_snapshot_digest,
            purpose=self.purpose,
            domain=self.domain,
            action_type=self.action_type,
            magnitude_before=self.magnitude_before,
            magnitude_after=self.magnitude_after,
            requested_delta=self.requested_delta,
            target_scope=self.target_scope,
            target_scope_digest=self.target_scope_digest,
            policy_binding=self.policy_binding,
            policy_binding_digest=self.policy_binding_digest,
            policy_coordinate_binding=self.policy_coordinate_binding,
            policy_coordinate_binding_digest=self.policy_coordinate_binding_digest,
            producer_attestation=self.producer_attestation,
            producer_signing_payload_digest=self.producer_signing_payload_digest,
            producer_id=self.producer_id,
            producer_key_id=self.producer_key_id,
            subject_valid_from_fact=self.subject_valid_from_fact,
            subject_valid_until_fact=self.subject_valid_until_fact,
            subject_asserted_at_fact=self.subject_asserted_at_fact,
            decision_evaluated_at_fact=self.decision_evaluated_at_fact,
            decision_expires_at_fact=self.decision_expires_at_fact,
            attestation_issued_at_fact=self.attestation_issued_at_fact,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {**self.digest_payload(), "candidate_digest": self.candidate_digest}

    def digest(self) -> str:
        return canonical_digest(self.digest_payload())


def build_capacity_authorization_candidate(
    *,
    projection: CapacityRiskSubjectProjection,
    decision: SubjectRiskDecision,
    producer_attestation: ProducerAttestationEvidence,
    policy_binding: PolicyTargetBindingReference,
    policy_coordinate_binding: PolicyTargetBindingReferenceV2,
    target_scope: ExecutionTargetScope,
) -> CapacityAuthorizationCandidate:
    """Reconcile Phase 4 and the Phase 5 bindings, then build the candidate. Or refuse.

    Every argument must be an **exact** instance of its type; subclasses, duck-typed
    look-alikes and ``object.__new__`` fabrications are refused before anything is read.
    Reconciliation completes in full before any part of the candidate is constructed, so a
    rejection leaves no partial artifact.

    The builder consumes the *validated values returned by* :func:`reconcile_phase4` and
    never re-reads ``projection`` or ``decision`` afterwards, closing the check-then-use
    window a property-backed subclass would otherwise open.

    :raises ExactTypeError: an argument is not the exact required type.
    :raises ReconciliationError: Phase 4 did not reconcile.
    :raises ProducerAttestationError: the attestation is missing, malformed or misbound.
    :raises PolicyTargetBindingError: either policy reference is missing, malformed or
        misbound, or the two disagree about which policy they name.
    :raises TargetScopeError: the target scope contradicts the projected subject.
    :raises MagnitudeBoundError: the requested magnitude or delta exceeds its maximum.
    """

    # --- exact-type admission, before any attribute is read ---------------------------
    for name, value, expected in (
        ("producer_attestation", producer_attestation, ProducerAttestationEvidence),
        ("policy_binding", policy_binding, PolicyTargetBindingReference),
        (
            "policy_coordinate_binding",
            policy_coordinate_binding,
            PolicyTargetBindingReferenceV2,
        ),
        ("target_scope", target_scope, ExecutionTargetScope),
    ):
        if value is None:
            reason = {
                "producer_attestation": _Reason.MISSING_PRODUCER_ATTESTATION,
                "policy_binding": _Reason.MISSING_POLICY_TARGET_BINDING,
                "policy_coordinate_binding": _Reason.MISSING_POLICY_COORDINATE_BINDING,
                "target_scope": _Reason.TARGET_SUBSTITUTION,
            }[name]
            raise ExactTypeError(f"{name} is required", reason)
        if type(value) is not expected:
            raise ExactTypeError(
                f"{name} must be an exact {expected.__name__} "
                f"(got {type(value).__name__})",
                _Reason.UNSUPPORTED_EXACT_TYPE,
            )

    # --- Phase 4 reconciliation, in full, before anything is built --------------------
    facts: ReconciledPhase4Facts = reconcile_phase4(projection, decision)

    # --- single read of the Phase 5 artifacts ------------------------------------------
    a_recommendation_id = producer_attestation.recommendation_id
    a_recommendation_digest = producer_attestation.recommendation_digest
    a_signing_payload_digest = producer_attestation.signing_payload_digest
    a_producer_id = producer_attestation.producer_id
    a_producer_key_id = producer_attestation.producer_key_id
    a_issued_at = producer_attestation.issued_at

    s_tenant = target_scope.tenant_id
    s_account = target_scope.account_id
    s_compute_group = target_scope.compute_group
    s_resource_class = target_scope.resource_class
    s_action_type = target_scope.action_type
    s_magnitude_before = target_scope.magnitude_before
    s_requested_magnitude = target_scope.requested_magnitude
    s_max_magnitude = target_scope.max_permitted_magnitude
    s_max_delta = target_scope.max_permitted_delta
    s_environment = target_scope.environment
    s_region = target_scope.region
    s_zone = target_scope.zone
    s_digest = target_scope.digest()

    b_target_scope_digest = policy_binding.target_scope_digest
    b_max_magnitude = policy_binding.max_permitted_magnitude
    b_max_delta = policy_binding.max_permitted_delta
    b_digest = policy_binding.digest()
    b_policy_id = policy_binding.policy_id
    b_policy_version = policy_binding.policy_version

    c_policy_id = policy_coordinate_binding.policy_id
    c_policy_version = policy_coordinate_binding.policy_version
    c_target_scope_digest = policy_coordinate_binding.target_scope_digest
    c_policy_scope = policy_coordinate_binding.policy_scope
    c_policy_tenant_id = policy_coordinate_binding.policy_tenant_id
    c_digest = policy_coordinate_binding.digest()

    # --- the attestation must bind THIS recommendation ---------------------------------
    if a_recommendation_digest != facts.recommendation_digest:
        raise ProducerAttestationError(
            "the producer attestation binds a different recommendation_digest — an "
            "attestation for another recommendation is not evidence for this one",
            _Reason.PRODUCER_ATTESTATION_CONTENT_MISMATCH,
        )

    # --- the attestation's instant must cohere with the Phase 4 facts (R-12) -----------
    # Not a freshness judgement and not a clock read. Both sides are instants this builder
    # already holds, compared against **each other** rather than against "now" — which is
    # exactly the class of error nothing downstream can see. Gate 13 (5B-2) compares each of
    # the candidate's six carried instants against an injected ``as_of`` and never against
    # another, so a candidate whose attestation was stamped a year before the assertion it
    # attests to verified: consistent with the instant, inconsistent with itself. The builder
    # is the only place that holds all six, so the refusal belongs here.
    #
    # Two comparisons, and deliberately only two. Every other ordering among the six is
    # already refused upstream, and re-checking it here would duplicate an invariant Phase 5A
    # does not own: ``valid_from <= asserted_at <= valid_until`` by Risk Authority's
    # ``SubjectContext.__post_init__``; ``evaluated_at`` inside that window by the v2 seam
    # *before* it stamps the decision it returns; ``expires_at = evaluated_at + TTL`` by
    # Decision Authority. ``issued_at`` is the one instant no upstream contract relates to any
    # other — 5B-0A §11 carries it forward deliberately unjudged, leaving the bounds to a
    # later phase — so it is the only one a candidate can state incoherently.
    #
    # Nothing here bounds ``issued_at`` against ``subject_valid_until``. That pair was put to
    # the owner and declined: it is the attestation freshness window 5B-0A §11 refused to
    # invent, and the ``evaluated_at`` bound below already sits inside the subject window.
    if a_issued_at < facts.subject_asserted_at:
        raise ProducerAttestationError(
            f"the producer attestation was issued at {a_issued_at.isoformat()}, before the "
            f"subject was asserted at {facts.subject_asserted_at.isoformat()} — an "
            "attestation cannot attest a recommendation that had not yet been made",
            _Reason.ATTESTATION_INSTANT_INCOHERENT,
        )
    if a_issued_at > facts.decision_evaluated_at:
        raise ProducerAttestationError(
            f"the producer attestation was issued at {a_issued_at.isoformat()}, after the "
            f"decision was evaluated at {facts.decision_evaluated_at.isoformat()} — the "
            "producer signs at the Controller output boundary, so an attestation minted "
            "after the evaluation it precedes is not the evidence that evaluation saw",
            _Reason.ATTESTATION_INSTANT_INCOHERENT,
        )

    # --- the target scope must be the projected subject, not a substitute --------------
    if s_tenant != facts.tenant_id:
        raise TargetScopeError(
            "the execution target scope names a different tenant", _Reason.TENANT_MISMATCH
        )
    if not s_account:
        raise TargetScopeError(
            "the execution target scope carries no account binding",
            _Reason.MISSING_ACCOUNT_BINDING,
        )
    if s_action_type != facts.action_type:
        raise TargetScopeError(
            f"the execution target scope names action {s_action_type!r} but the decision "
            f"was made for {facts.action_type!r}",
            _Reason.ACTION_SUBSTITUTION,
        )
    if s_magnitude_before != facts.magnitude_before:
        raise TargetScopeError(
            "the execution target scope's magnitude_before differs from the projection's",
            _Reason.TARGET_SUBSTITUTION,
        )
    if s_requested_magnitude != facts.magnitude_after:
        raise TargetScopeError(
            "the execution target scope's requested_magnitude differs from the "
            "projection's magnitude_after",
            _Reason.TARGET_SUBSTITUTION,
        )
    # The projected subject facts are authoritative for placement; a scope may not quietly
    # relocate the action to another region, zone, cluster or resource.
    for label, scope_value, projected_value, reason in (
        ("environment", s_environment, facts.environment, _Reason.TARGET_SUBSTITUTION),
        ("region", s_region, facts.region, _Reason.TARGET_SUBSTITUTION),
        ("zone", s_zone, facts.zone, _Reason.TARGET_SUBSTITUTION),
        ("compute_group", s_compute_group, facts.compute_group, _Reason.TARGET_SUBSTITUTION),
        ("resource_class", s_resource_class, facts.resource_class, _Reason.TARGET_SUBSTITUTION),
    ):
        if scope_value != projected_value:
            raise TargetScopeError(
                f"the execution target scope's {label} ({scope_value!r}) is not the "
                f"projected subject's ({projected_value!r})",
                reason,
            )

    # --- the policy binding must bind THIS scope, with agreeing bounds -----------------
    if b_target_scope_digest != s_digest:
        raise PolicyTargetBindingError(
            "the policy binding references a different execution target scope",
            _Reason.POLICY_TARGET_CONTENT_MISMATCH,
        )
    if b_max_magnitude != s_max_magnitude or b_max_delta != s_max_delta:
        raise PolicyTargetBindingError(
            "the execution target scope's bounds do not agree with the policy binding's",
            _Reason.POLICY_TARGET_CONTENT_MISMATCH,
        )

    # --- the two policy references must name ONE policy, bound to THIS scope -----------
    # A candidate that carries two policy references can state a contradiction: a V1 binding
    # for policy A beside a coordinate for policy B. Both halves would be individually
    # well-formed, and a consumer reading the bounds off one while reconciling a verified
    # proof against the other would be reading bounds the proof does not cover. So the
    # agreement is a construction-time refusal, not a downstream consumer's problem.
    #
    # Three fields, and deliberately only three (5B-1 D-5B1-1). The issuer and key are NOT
    # cross-checked: ``policy_issuer``/``policy_key_id`` are Phase 5A identifiers with no
    # ratified correspondence to the authority's ``issuing_authority_id``/``key_id``, and
    # inventing one here would be this package asserting something about the Policy Authority
    # that no ratified clause supports.
    #
    # The coordinate's tenant *is* compared, since 5B-2 closed R-9 — but only when the policy
    # is TENANT-scoped. The original note here said it was not compared at all, reasoning that
    # the authority's global tenant is the empty string so a global policy legitimately bounds
    # a tenant-scoped action. That is a correct reason not to compare *unconditionally*, and
    # not a reason not to compare: it argues for the scope guard below, which is the shape
    # ``uvi-policy-contracts`` already uses.
    if c_policy_id != b_policy_id or c_policy_version != b_policy_version:
        raise PolicyTargetBindingError(
            f"the candidate's two policy references disagree: the binding names "
            f"{b_policy_id!r}@{b_policy_version!r} and the coordinate names "
            f"{c_policy_id!r}@{c_policy_version!r}. A candidate may carry one policy "
            "identity, not two",
            _Reason.POLICY_COORDINATE_CONTENT_MISMATCH,
        )
    if c_target_scope_digest != s_digest:
        raise PolicyTargetBindingError(
            "the policy coordinate binding references a different execution target scope; a "
            "coordinate not bound to this scope could be transplanted onto another target",
            _Reason.POLICY_COORDINATE_CONTENT_MISMATCH,
        )

    # --- a TENANT-scoped policy may bound only its own tenant's action (R-9) -----------
    # Both references can agree perfectly and the coordinate can be bound to this very scope
    # while the policy belongs to somebody else. Keyed on the scope, never on a bare equality:
    # a GLOBAL policy carries the empty tenant, so `!=` alone would refuse every global policy
    # in the platform. Mirrors ``uvi-policy-contracts`` ``contracts/context.py``.
    if (
        c_policy_scope == POLICY_SCOPE_TENANT
        and c_policy_tenant_id != facts.tenant_id
    ):
        raise PolicyTargetBindingError(
            f"cross-tenant policy binding: the coordinate names a {POLICY_SCOPE_TENANT}-scoped "
            f"policy belonging to tenant {c_policy_tenant_id!r}, but this candidate's action "
            f"is for tenant {facts.tenant_id!r}. A tenant's policy does not bound another "
            "tenant's action",
            _Reason.CROSS_TENANT_POLICY_BINDING,
        )

    # --- bounds, enforced against the policy-carried maxima ----------------------------
    if s_requested_magnitude > b_max_magnitude:
        raise MagnitudeBoundError(
            f"requested magnitude {s_requested_magnitude} exceeds the policy maximum "
            f"{b_max_magnitude}",
            _Reason.REQUESTED_MAGNITUDE_ABOVE_MAXIMUM,
        )
    if facts.requested_delta > b_max_delta:
        raise MagnitudeBoundError(
            f"requested delta {facts.requested_delta} exceeds the policy maximum delta "
            f"{b_max_delta}",
            _Reason.DELTA_ABOVE_MAXIMUM,
        )

    # --- build from validated values only ---------------------------------------------
    payload_source = dict(
        tenant_id=facts.tenant_id,
        subject_id=facts.subject_id,
        subject_type=facts.subject_type,
        recommendation_id=a_recommendation_id,
        recommendation_digest=facts.recommendation_digest,
        context_digest=facts.context_digest,
        subject_digest=facts.subject_digest,
        request_digest=facts.request_digest,
        decision_id=facts.decision_id,
        decision_snapshot_digest=facts.decision_snapshot_digest,
        decision_digest=facts.decision_digest,
        disposition=facts.disposition,
        risk_outcome=facts.risk_outcome,
        idempotency_key=facts.idempotency_key,
        evidence_references=facts.evidence_references,
        evidence_snapshot_digest=facts.evidence_snapshot_digest,
        purpose=facts.purpose,
        domain=facts.domain,
        action_type=facts.action_type,
        magnitude_before=facts.magnitude_before,
        magnitude_after=facts.magnitude_after,
        requested_delta=facts.requested_delta,
        target_scope=target_scope,
        target_scope_digest=s_digest,
        policy_binding=policy_binding,
        policy_binding_digest=b_digest,
        policy_coordinate_binding=policy_coordinate_binding,
        policy_coordinate_binding_digest=c_digest,
        producer_attestation=producer_attestation,
        producer_signing_payload_digest=a_signing_payload_digest,
        producer_id=a_producer_id,
        producer_key_id=a_producer_key_id,
        subject_valid_from_fact=facts.subject_valid_from,
        subject_valid_until_fact=facts.subject_valid_until,
        subject_asserted_at_fact=facts.subject_asserted_at,
        decision_evaluated_at_fact=facts.decision_evaluated_at,
        decision_expires_at_fact=facts.decision_expires_at,
        attestation_issued_at_fact=a_issued_at,
    )
    # The digest is computed from the same single helper the artifact's own
    # ``digest_payload()`` uses, so there is exactly one definition of what the candidate
    # digest covers. ``__post_init__`` then re-derives it independently and refuses the
    # construction if the two ever disagree.
    candidate_digest = canonical_digest(
        _digest_payload(
            schema_version=AUTHORIZATION_CANDIDATE_SCHEMA_VERSION, **payload_source
        )
    )

    return CapacityAuthorizationCandidate(
        **payload_source, candidate_digest=candidate_digest
    )
