"""Stable identity, status and trust-gap vocabulary for GV-3R-c orchestration.

Every value is a stable token a consumer may branch on; values are never
repurposed. Codes are emitted in **enum declaration order**, never in the order
the caller supplied its inputs, so an identical assessment always produces an
identical ordered code tuple.

None of these codes asserts that anything was verified by *this* package. They
record which configured trust boundary answered, and what remained unproven.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ORCHESTRATOR_ID",
    "READINESS_ORCHESTRATOR_VERSION",
    "ReadinessAssessmentStatus",
    "ReadinessInputVerificationStatus",
    "ReadinessTrustAdvisoryState",
    "ReadinessTrustGapCode",
]

#: Identity of the single canonical orchestration entry point.
ORCHESTRATOR_ID = "ugence.agent-value-readiness.trusted-readiness-orchestrator"

#: Version of the ratified orchestration rule set implemented here. Bumped only
#: when the orchestration boundary itself changes (which stage runs, in what
#: order, what is independently rechecked, or what fails closed).
#:
#: It is deliberately **separate** from
#: ``EVALUATOR_FORMULA_VERSION`` (``GV-3R-b.3``): GV-3R-c adds a fail-closed
#: trust boundary *around* the deterministic evaluator and introduces no second
#: classification algorithm, so the evaluator's formula version does not move.
READINESS_ORCHESTRATOR_VERSION = "GV-3R-c.1"


class ReadinessAssessmentStatus(str, Enum):
    """Whether a readiness headline exists at all.

    The two values are not two tiers: :attr:`NOT_EVALUATED` means the trusted
    boundary refused, so ``evaluate_readiness`` was never called and **no**
    classification, determination or headline of any kind exists.
    """

    #: A trust gap prevented evaluation. No readiness classification exists.
    NOT_EVALUATED = "NOT_EVALUATED"
    #: The deterministic GV-3R-b evaluator ran exactly once over sanitized input.
    EVALUATED = "EVALUATED"


class ReadinessInputVerificationStatus(str, Enum):
    """The outcome a configured input verifier reports for one supplied input.

    Only :attr:`VERIFIED` can make an input eligible to influence the
    evaluation, and only after the orchestrator independently rechecks every
    coordinate the verifier returned. Every other member fails closed.
    """

    #: The verifier attests the claimed status and its supporting inputs.
    VERIFIED = "VERIFIED"
    #: No verifier is configured for this input class — deny by default.
    NO_VERIFIER_CONFIGURED = "NO_VERIFIER_CONFIGURED"
    #: Supporting evidence could not be verified.
    EVIDENCE_NOT_VERIFIED = "EVIDENCE_NOT_VERIFIED"
    #: A referenced benchmark could not be resolved to an exact governed version.
    BENCHMARK_NOT_RESOLVED = "BENCHMARK_NOT_RESOLVED"
    #: The metric-to-threshold evaluation behind the claimed status is unproven.
    THRESHOLD_EVALUATION_NOT_VERIFIED = "THRESHOLD_EVALUATION_NOT_VERIFIED"
    #: An approval authority or approval evidence binding could not be verified.
    APPROVAL_NOT_VERIFIED = "APPROVAL_NOT_VERIFIED"
    #: The verifier found the input bound to a different policy, gate, condition,
    #: tenant, subject, context, target or instant than the one requested.
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    #: The verifier failed. A failure is never an acceptance.
    VERIFIER_ERROR = "VERIFIER_ERROR"


class ReadinessTrustAdvisoryState(str, Enum):
    """What GV-3R-c did about one standing GV-3R-b honesty advisory.

    The standalone evaluator emits advisories precisely because it cannot verify
    external trust boundaries. Orchestration never deletes them: it records, per
    advisory, which configured boundary resolved it — or that it remains open.
    """

    #: Resolved by trusted resolution through the shared Policy Authority.
    RESOLVED_BY_POLICY_RESOLUTION = "RESOLVED_BY_POLICY_RESOLUTION"
    #: Resolved by the configured gate-result verifier for every admitted result.
    RESOLVED_BY_GATE_VERIFICATION = "RESOLVED_BY_GATE_VERIFICATION"
    #: Resolved by the configured condition verifier for every admitted condition.
    RESOLVED_BY_CONDITION_VERIFICATION = "RESOLVED_BY_CONDITION_VERIFICATION"
    #: Still open — nothing in this assessment proved it.
    UNRESOLVED = "UNRESOLVED"
    #: Not a gap this phase can close; it states a permanent boundary.
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ReadinessTrustGapCode(str, Enum):
    """Why one input, or the whole assessment, was not trusted.

    Emitted in declaration order. Every gap is explicit: nothing is silently
    accepted, downgraded to a warning, or folded into a generic failure.
    """

    # -- policy resolution -------------------------------------------------- #
    #: No trusted readiness-policy resolver was configured. Production default.
    POLICY_RESOLVER_NOT_CONFIGURED = "GV3RC_POLICY_RESOLVER_NOT_CONFIGURED"
    #: The configured resolver raised. A failure is never a resolution.
    POLICY_RESOLVER_ERROR = "GV3RC_POLICY_RESOLVER_ERROR"
    #: The configured resolver returned something that is not a
    #: ``PolicyResolution`` — a duck-typed answer is refused, not inspected.
    POLICY_RESOLVER_MALFORMED_RESULT = "GV3RC_POLICY_RESOLVER_MALFORMED_RESULT"
    #: The shared authority did not resolve the exact reference at that instant.
    POLICY_RESOLUTION_UNRESOLVED = "GV3RC_POLICY_RESOLUTION_UNRESOLVED"
    #: The answer is explicitly historical. A historical answer describes the
    #: past and never implies current validity, so it cannot govern a readiness
    #: assessment at ``evaluation_time``.
    POLICY_RESOLUTION_HISTORICAL_NOT_ACCEPTED = (
        "GV3RC_POLICY_RESOLUTION_HISTORICAL_NOT_ACCEPTED"
    )
    #: The resolution carries no issuance record to bind provenance to.
    POLICY_RESOLUTION_ISSUANCE_RECORD_MISSING = (
        "GV3RC_POLICY_RESOLUTION_ISSUANCE_RECORD_MISSING"
    )
    #: The resolved artifact is not a ``ReadinessPolicy``.
    POLICY_RESOLUTION_ARTIFACT_NOT_A_READINESS_POLICY = (
        "GV3RC_POLICY_RESOLUTION_ARTIFACT_NOT_A_READINESS_POLICY"
    )
    #: The resolved artifact's complete ``PolicyReference`` (family, id, version,
    #: content digest, scope, tenant) is not the requested one.
    POLICY_RESOLUTION_REFERENCE_MISMATCH = "GV3RC_POLICY_RESOLUTION_REFERENCE_MISMATCH"
    #: The requested reference's tenant identity is not the assessed tenant.
    POLICY_RESOLUTION_TENANT_MISMATCH = "GV3RC_POLICY_RESOLUTION_TENANT_MISMATCH"
    #: The resolution's ``as_of`` is not the requested evaluation instant.
    POLICY_RESOLUTION_AS_OF_MISMATCH = "GV3RC_POLICY_RESOLUTION_AS_OF_MISMATCH"
    #: The ``AssessmentContext`` does not bind exactly this readiness policy.
    POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH = (
        "GV3RC_POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH"
    )
    #: The resolved policy does not govern the requested ``ReadinessTarget``.
    POLICY_RESOLUTION_TARGET_NOT_GOVERNED = "GV3RC_POLICY_RESOLUTION_TARGET_NOT_GOVERNED"
    #: Defence in depth: the resolved artifact's own metadata is not
    #: ``APPROVED_ACTIVE`` even though resolution succeeded.
    POLICY_ARTIFACT_NOT_APPROVED_ACTIVE = "GV3RC_POLICY_ARTIFACT_NOT_APPROVED_ACTIVE"
    #: Defence in depth: the resolved artifact is not effective at the
    #: evaluation instant even though resolution succeeded.
    POLICY_ARTIFACT_NOT_EFFECTIVE_AT_EVALUATION_TIME = (
        "GV3RC_POLICY_ARTIFACT_NOT_EFFECTIVE_AT_EVALUATION_TIME"
    )

    # -- gate-result verification ------------------------------------------ #
    #: No gate-result verifier was configured. Production default: deny.
    GATE_VERIFIER_NOT_CONFIGURED = "GV3RC_GATE_VERIFIER_NOT_CONFIGURED"
    #: The configured gate verifier raised for at least one gate result.
    GATE_VERIFIER_ERROR = "GV3RC_GATE_VERIFIER_ERROR"
    #: The gate verifier returned something that is not a
    #: ``GateResultVerification`` — a duck-typed attestation is refused.
    GATE_VERIFIER_MALFORMED_RESULT = "GV3RC_GATE_VERIFIER_MALFORMED_RESULT"
    #: The verifier did not report ``VERIFIED`` for a supplied gate result.
    GATE_RESULT_NOT_VERIFIED = "GV3RC_GATE_RESULT_NOT_VERIFIED"
    #: The verifier reported ``VERIFIED`` without attesting the supporting
    #: evidence / benchmark / threshold evaluation the gate actually relies on.
    GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE = (
        "GV3RC_GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE"
    )
    #: The gate result is bound to a different readiness policy.
    GATE_RESULT_POLICY_REFERENCE_MISMATCH = "GV3RC_GATE_RESULT_POLICY_REFERENCE_MISMATCH"
    #: The gate result was evaluated for a different ``ReadinessTarget``.
    GATE_RESULT_TARGET_MISMATCH = "GV3RC_GATE_RESULT_TARGET_MISMATCH"
    #: The gate result names a gate that the **resolved** policy does not define.
    GATE_RESULT_GATE_NOT_IN_RESOLVED_POLICY = "GV3RC_GATE_RESULT_GATE_NOT_IN_RESOLVED_POLICY"
    #: The embedded ``PolicyGate`` is not canonically identical to the resolved
    #: policy's gate of that id.
    GATE_RESULT_GATE_BODY_MISMATCH = "GV3RC_GATE_RESULT_GATE_BODY_MISMATCH"
    #: More than one result was supplied for the same gate id. Every copy is
    #: rejected — a conflict is never resolved by picking one.
    GATE_RESULT_DUPLICATE = "GV3RC_GATE_RESULT_DUPLICATE"
    #: A returned verification coordinate (gate, policy, tenant, subject,
    #: context, target or instant) is not the one that was requested.
    GATE_RESULT_VERIFICATION_BINDING_MISMATCH = (
        "GV3RC_GATE_RESULT_VERIFICATION_BINDING_MISMATCH"
    )
    #: The verifier verified a different ``GateStatus`` than the one claimed.
    GATE_RESULT_VERIFIED_STATUS_MISMATCH = "GV3RC_GATE_RESULT_VERIFIED_STATUS_MISMATCH"
    #: A rejected gate result names an applicable mandatory or conditional gate,
    #: so that required gate is **absent** for evaluator purposes.
    REQUIRED_GATE_RESULT_UNVERIFIED = "GV3RC_REQUIRED_GATE_RESULT_UNVERIFIED"

    # -- condition verification -------------------------------------------- #
    #: No condition verifier was configured. Production default: no coverage.
    CONDITION_VERIFIER_NOT_CONFIGURED = "GV3RC_CONDITION_VERIFIER_NOT_CONFIGURED"
    #: The configured condition verifier raised for at least one condition.
    CONDITION_VERIFIER_ERROR = "GV3RC_CONDITION_VERIFIER_ERROR"
    #: The condition verifier returned something that is not a
    #: ``ConditionSetVerification``.
    CONDITION_VERIFIER_MALFORMED_RESULT = "GV3RC_CONDITION_VERIFIER_MALFORMED_RESULT"
    #: The verifier did not report ``VERIFIED`` for a supplied condition, or did
    #: not independently establish it as ``APPROVED_ACTIVE`` in agreement with
    #: the supplied record.
    CONDITION_NOT_VERIFIED = "GV3RC_CONDITION_NOT_VERIFIED"
    #: The verifier reported ``VERIFIED`` without attesting the approval
    #: authority, the approval evidence, or the owner/monitoring obligations.
    CONDITION_APPROVAL_NOT_VERIFIED = "GV3RC_CONDITION_APPROVAL_NOT_VERIFIED"
    #: A returned verification coordinate is not the one that was requested.
    CONDITION_VERIFICATION_BINDING_MISMATCH = "GV3RC_CONDITION_VERIFICATION_BINDING_MISMATCH"
    #: The verification names a different condition identity.
    CONDITION_IDENTITY_MISMATCH = "GV3RC_CONDITION_IDENTITY_MISMATCH"
    #: The verification carries a different canonical condition digest.
    CONDITION_DIGEST_MISMATCH = "GV3RC_CONDITION_DIGEST_MISMATCH"
    #: The verification covers a different concern than the condition names —
    #: one condition can never cover two concerns by identity ambiguity.
    CONDITION_SOURCE_REFERENCE_MISMATCH = "GV3RC_CONDITION_SOURCE_REFERENCE_MISMATCH"
    #: More than one condition was supplied under the same condition id. Every
    #: copy is rejected.
    CONDITION_DUPLICATE = "GV3RC_CONDITION_DUPLICATE"
    #: The condition names a reference the **resolved** policy does not define
    #: as a gate.
    CONDITION_CONCERN_NOT_IN_RESOLVED_POLICY = "GV3RC_CONDITION_CONCERN_NOT_IN_RESOLVED_POLICY"
    #: The covered gate is not ``RequirementClass.CONDITIONAL`` — a mandatory
    #: concern is never compensable (D-6).
    CONDITION_CONCERN_NOT_CONDITIONAL = "GV3RC_CONDITION_CONCERN_NOT_CONDITIONAL"
    #: The resolved policy does not mark the covered gate
    #: ``conditionally_compensable``.
    CONDITION_CONCERN_NOT_COMPENSABLE = "GV3RC_CONDITION_CONCERN_NOT_COMPENSABLE"
    #: The condition is not active at the evaluation instant (proposed, expired,
    #: revoked, satisfied, not yet effective, or its window has elapsed).
    CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME = "GV3RC_CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME"

    # -- evaluator invocation ---------------------------------------------- #
    #: The sanitized case was still refused by the deterministic evaluator.
    #: Defensive: the request contract already rejects self-contradictory input.
    #: Reaching it produces ``NOT_EVALUATED``, never a partial headline.
    EVALUATOR_REJECTED_SANITIZED_CASE = "GV3RC_EVALUATOR_REJECTED_SANITIZED_CASE"
