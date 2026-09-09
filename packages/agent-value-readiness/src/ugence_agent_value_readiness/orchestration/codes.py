"""Stable identity, status and trust-gap vocabulary for trusted orchestration.

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
    "SYSTEM_BINDING_AUTHENTICITY_ADVISORY",
    "ReadinessAssessmentStatus",
    "ReadinessIndicatorAdmissionStatus",
    "ReadinessInputVerificationStatus",
    "ReadinessTrustAdvisoryState",
    "ReadinessTrustGapCode",
]

#: Identity of the single canonical orchestration entry point.
ORCHESTRATOR_ID = "ugence.agent-value-readiness.trusted-readiness-orchestrator"

#: Version of the orchestration rule set implemented here. Bumped only when the
#: orchestration boundary itself changes (which stage runs, in what order, what
#: is independently rechecked, or what fails closed).
#:
#: The identifier is deliberately **platform-neutral**: it names a capability,
#: not an ADR milestone, and asserts **no** roadmap position.
#:
#: ``v0.2`` advances ``v0.1`` because the orchestration boundary itself changed:
#: :func:`~..service.assess_readiness` now **requires** an exact
#: ``AssessedSystemBinding`` and admits only catalog-recognized indicator
#: results. There is exactly **one** entry point — no lower-trust unbound path
#: is retained, so no second classification algorithm and no bypass exists.
#:
#: It is also deliberately **separate** from ``EVALUATOR_FORMULA_VERSION``
#: (``GV-3R-b.3``): this boundary wraps the deterministic evaluator and
#: introduces no second classification algorithm, so the evaluator's formula
#: version does not move.
READINESS_ORCHESTRATOR_VERSION = "ugence.readiness-orchestration/v0.2"

#: The stable advisory token for the permanent system-binding trust boundary.
#:
#: An ``AssessedSystemBinding`` is a **structural** artifact: it proves internal
#: consistency and digest-bound identity, never that the described system was
#: really deployed or that any authority attested it. Orchestration therefore
#: records this as a standing, permanently ``OUT_OF_SCOPE`` disposition rather
#: than silently implying the binding was authenticated. It is a fixed token in
#: the neutral ``READINESS_ORCHESTRATION_`` namespace — never free-form text —
#: and closing it requires a separately ratified system-binding verifier.
SYSTEM_BINDING_AUTHENTICITY_ADVISORY = (
    "READINESS_ORCHESTRATION_SYSTEM_BINDING_AUTHENTICITY_NOT_VERIFIED"
)


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


class ReadinessIndicatorAdmissionStatus(str, Enum):
    """Whether one supplied indicator result entered the sanitized case (M-3R.3).

    Admission is a **vocabulary** decision, not an evidence decision: it records
    that the result claims a recognized indicator definition, for the assessed
    system, under the assessed context. It asserts nothing about whether the
    underlying metric is true, observed, attributed or verified — those axes
    live on the result's own ``MetricClaim`` and are carried through unchanged.

    An excluded result influences readiness in **no** way. It is not downgraded,
    not treated as a failure, and not silently dropped: it keeps a summary
    naming the exact stable reason it was excluded.
    """

    #: Recognized by the bound catalog for its family and bound to this system.
    ADMITTED = "ADMITTED"
    #: No catalog is bound for this result's readiness family.
    CATALOG_MISSING = "CATALOG_MISSING"
    #: The bound catalog defines no entry with this indicator identity.
    NOT_CATALOGED = "NOT_CATALOGED"
    #: The cataloged definition disagrees about dimension, metric or target.
    DEFINITION_MISMATCH = "DEFINITION_MISMATCH"
    #: The result names a different assessed system binding, or names none.
    SYSTEM_BINDING_MISMATCH = "SYSTEM_BINDING_MISMATCH"
    #: More than one result was supplied for the same indicator identity.
    DUPLICATE = "DUPLICATE"


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
    """What orchestration did about one standing GV-3R-b honesty advisory.

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

    Every value carries the ``READINESS_ORCHESTRATION_`` namespace: a
    platform-neutral capability prefix that names no ADR milestone and asserts
    no roadmap position. Values are stable tokens consumers may branch on and
    are never repurposed.
    """

    # -- policy resolution -------------------------------------------------- #
    #: No trusted readiness-policy resolver was configured. Production default.
    POLICY_RESOLVER_NOT_CONFIGURED = "READINESS_ORCHESTRATION_POLICY_RESOLVER_NOT_CONFIGURED"
    #: The configured resolver raised. A failure is never a resolution.
    POLICY_RESOLVER_ERROR = "READINESS_ORCHESTRATION_POLICY_RESOLVER_ERROR"
    #: The configured resolver returned something that is not a
    #: ``PolicyResolution`` — a duck-typed answer is refused, not inspected.
    POLICY_RESOLVER_MALFORMED_RESULT = "READINESS_ORCHESTRATION_POLICY_RESOLVER_MALFORMED_RESULT"
    #: The shared authority did not resolve the exact reference at that instant.
    POLICY_RESOLUTION_UNRESOLVED = "READINESS_ORCHESTRATION_POLICY_RESOLUTION_UNRESOLVED"
    #: The answer is explicitly historical. A historical answer describes the
    #: past and never implies current validity, so it cannot govern a readiness
    #: assessment at ``evaluation_time``.
    POLICY_RESOLUTION_HISTORICAL_NOT_ACCEPTED = (
        "READINESS_ORCHESTRATION_POLICY_RESOLUTION_HISTORICAL_NOT_ACCEPTED"
    )
    #: The resolution carries no issuance record to bind provenance to.
    POLICY_RESOLUTION_ISSUANCE_RECORD_MISSING = (
        "READINESS_ORCHESTRATION_POLICY_RESOLUTION_ISSUANCE_RECORD_MISSING"
    )
    #: The resolved artifact is not a ``ReadinessPolicy``.
    POLICY_RESOLUTION_ARTIFACT_NOT_A_READINESS_POLICY = (
        "READINESS_ORCHESTRATION_POLICY_RESOLUTION_ARTIFACT_NOT_A_READINESS_POLICY"
    )
    #: The resolved artifact's complete ``PolicyReference`` (family, id, version,
    #: content digest, scope, tenant) is not the requested one.
    POLICY_RESOLUTION_REFERENCE_MISMATCH = "READINESS_ORCHESTRATION_POLICY_RESOLUTION_REFERENCE_MISMATCH"
    #: The requested reference's tenant identity is not the assessed tenant.
    POLICY_RESOLUTION_TENANT_MISMATCH = "READINESS_ORCHESTRATION_POLICY_RESOLUTION_TENANT_MISMATCH"
    #: The resolution's ``as_of`` is not the requested evaluation instant.
    POLICY_RESOLUTION_AS_OF_MISMATCH = "READINESS_ORCHESTRATION_POLICY_RESOLUTION_AS_OF_MISMATCH"
    #: The ``AssessmentContext`` does not bind exactly this readiness policy.
    POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH = (
        "READINESS_ORCHESTRATION_POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH"
    )
    #: The resolved policy does not govern the requested ``ReadinessTarget``.
    POLICY_RESOLUTION_TARGET_NOT_GOVERNED = "READINESS_ORCHESTRATION_POLICY_RESOLUTION_TARGET_NOT_GOVERNED"
    #: Defence in depth: the resolved artifact's own metadata is not
    #: ``APPROVED_ACTIVE`` even though resolution succeeded.
    POLICY_ARTIFACT_NOT_APPROVED_ACTIVE = "READINESS_ORCHESTRATION_POLICY_ARTIFACT_NOT_APPROVED_ACTIVE"
    #: Defence in depth: the resolved artifact is not effective at the
    #: evaluation instant even though resolution succeeded.
    POLICY_ARTIFACT_NOT_EFFECTIVE_AT_EVALUATION_TIME = (
        "READINESS_ORCHESTRATION_POLICY_ARTIFACT_NOT_EFFECTIVE_AT_EVALUATION_TIME"
    )

    # -- assessed-system binding (M-3R.3) ---------------------------------- #
    #: No ``AssessedSystemBinding`` was supplied. There is exactly one
    #: orchestration path and it requires one: an assessment that cannot say
    #: **which** system it describes is ``NOT_EVALUATED``, never a headline.
    SYSTEM_BINDING_REQUIRED = "READINESS_ORCHESTRATION_SYSTEM_BINDING_REQUIRED"
    #: The binding names a different ``AssessmentContext`` identity or carries a
    #: different canonical context digest than the assessment's own context.
    SYSTEM_BINDING_CONTEXT_MISMATCH = "READINESS_ORCHESTRATION_SYSTEM_BINDING_CONTEXT_MISMATCH"
    #: The binding's tenant is not the assessed tenant.
    SYSTEM_BINDING_TENANT_MISMATCH = "READINESS_ORCHESTRATION_SYSTEM_BINDING_TENANT_MISMATCH"
    #: The binding's subject is not the assessed subject.
    SYSTEM_BINDING_SUBJECT_MISMATCH = "READINESS_ORCHESTRATION_SYSTEM_BINDING_SUBJECT_MISMATCH"
    #: The binding's declared half-open effective period does not cover the
    #: evaluation instant.
    SYSTEM_BINDING_NOT_EFFECTIVE_AT_EVALUATION_TIME = (
        "READINESS_ORCHESTRATION_SYSTEM_BINDING_NOT_EFFECTIVE_AT_EVALUATION_TIME"
    )

    # -- gate-result verification ------------------------------------------ #
    #: No gate-result verifier was configured. Production default: deny.
    GATE_VERIFIER_NOT_CONFIGURED = "READINESS_ORCHESTRATION_GATE_VERIFIER_NOT_CONFIGURED"
    #: The configured gate verifier raised for at least one gate result.
    GATE_VERIFIER_ERROR = "READINESS_ORCHESTRATION_GATE_VERIFIER_ERROR"
    #: The gate verifier returned something that is not a
    #: ``GateResultVerification`` — a duck-typed attestation is refused.
    GATE_VERIFIER_MALFORMED_RESULT = "READINESS_ORCHESTRATION_GATE_VERIFIER_MALFORMED_RESULT"
    #: The verifier did not report ``VERIFIED`` for a supplied gate result.
    GATE_RESULT_NOT_VERIFIED = "READINESS_ORCHESTRATION_GATE_RESULT_NOT_VERIFIED"
    #: The verifier reported ``VERIFIED`` without attesting the supporting
    #: evidence / benchmark / threshold evaluation the gate actually relies on.
    GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE = (
        "READINESS_ORCHESTRATION_GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE"
    )
    #: The gate result is bound to a different readiness policy.
    GATE_RESULT_POLICY_REFERENCE_MISMATCH = "READINESS_ORCHESTRATION_GATE_RESULT_POLICY_REFERENCE_MISMATCH"
    #: The gate result was evaluated for a different ``ReadinessTarget``.
    GATE_RESULT_TARGET_MISMATCH = "READINESS_ORCHESTRATION_GATE_RESULT_TARGET_MISMATCH"
    #: The gate result names a gate that the **resolved** policy does not define.
    GATE_RESULT_GATE_NOT_IN_RESOLVED_POLICY = "READINESS_ORCHESTRATION_GATE_RESULT_GATE_NOT_IN_RESOLVED_POLICY"
    #: The embedded ``PolicyGate`` is not canonically identical to the resolved
    #: policy's gate of that id.
    GATE_RESULT_GATE_BODY_MISMATCH = "READINESS_ORCHESTRATION_GATE_RESULT_GATE_BODY_MISMATCH"
    #: More than one result was supplied for the same gate id. Every copy is
    #: rejected — a conflict is never resolved by picking one.
    GATE_RESULT_DUPLICATE = "READINESS_ORCHESTRATION_GATE_RESULT_DUPLICATE"
    #: A returned verification coordinate (gate, policy, tenant, subject,
    #: context, target or instant) is not the one that was requested.
    GATE_RESULT_VERIFICATION_BINDING_MISMATCH = (
        "READINESS_ORCHESTRATION_GATE_RESULT_VERIFICATION_BINDING_MISMATCH"
    )
    #: The verifier verified a different ``GateStatus`` than the one claimed.
    GATE_RESULT_VERIFIED_STATUS_MISMATCH = "READINESS_ORCHESTRATION_GATE_RESULT_VERIFIED_STATUS_MISMATCH"
    #: A rejected gate result names an applicable mandatory or conditional gate,
    #: so that required gate is **absent** for evaluator purposes.
    REQUIRED_GATE_RESULT_UNVERIFIED = "READINESS_ORCHESTRATION_REQUIRED_GATE_RESULT_UNVERIFIED"

    # -- condition verification -------------------------------------------- #
    #: No condition verifier was configured. Production default: no coverage.
    CONDITION_VERIFIER_NOT_CONFIGURED = "READINESS_ORCHESTRATION_CONDITION_VERIFIER_NOT_CONFIGURED"
    #: The configured condition verifier raised for at least one condition.
    CONDITION_VERIFIER_ERROR = "READINESS_ORCHESTRATION_CONDITION_VERIFIER_ERROR"
    #: The condition verifier returned something that is not a
    #: ``ConditionSetVerification``.
    CONDITION_VERIFIER_MALFORMED_RESULT = "READINESS_ORCHESTRATION_CONDITION_VERIFIER_MALFORMED_RESULT"
    #: The verifier did not report ``VERIFIED`` for a supplied condition, or did
    #: not independently establish it as ``APPROVED_ACTIVE`` in agreement with
    #: the supplied record.
    CONDITION_NOT_VERIFIED = "READINESS_ORCHESTRATION_CONDITION_NOT_VERIFIED"
    #: The verifier reported ``VERIFIED`` without attesting the approval
    #: authority, the approval evidence, or the owner/monitoring obligations.
    CONDITION_APPROVAL_NOT_VERIFIED = "READINESS_ORCHESTRATION_CONDITION_APPROVAL_NOT_VERIFIED"
    #: A returned verification coordinate is not the one that was requested.
    CONDITION_VERIFICATION_BINDING_MISMATCH = "READINESS_ORCHESTRATION_CONDITION_VERIFICATION_BINDING_MISMATCH"
    #: The verification names a different condition identity.
    CONDITION_IDENTITY_MISMATCH = "READINESS_ORCHESTRATION_CONDITION_IDENTITY_MISMATCH"
    #: The verification carries a different canonical condition digest.
    CONDITION_DIGEST_MISMATCH = "READINESS_ORCHESTRATION_CONDITION_DIGEST_MISMATCH"
    #: The verification covers a different concern than the condition names —
    #: one condition can never cover two concerns by identity ambiguity.
    CONDITION_SOURCE_REFERENCE_MISMATCH = "READINESS_ORCHESTRATION_CONDITION_SOURCE_REFERENCE_MISMATCH"
    #: More than one condition was supplied under the same condition id. Every
    #: copy is rejected.
    CONDITION_DUPLICATE = "READINESS_ORCHESTRATION_CONDITION_DUPLICATE"
    #: The condition names a reference the **resolved** policy does not define
    #: as a gate.
    CONDITION_CONCERN_NOT_IN_RESOLVED_POLICY = "READINESS_ORCHESTRATION_CONDITION_CONCERN_NOT_IN_RESOLVED_POLICY"
    #: The covered gate is not ``RequirementClass.CONDITIONAL`` — a mandatory
    #: concern is never compensable (D-6).
    CONDITION_CONCERN_NOT_CONDITIONAL = "READINESS_ORCHESTRATION_CONDITION_CONCERN_NOT_CONDITIONAL"
    #: The resolved policy does not mark the covered gate
    #: ``conditionally_compensable``.
    CONDITION_CONCERN_NOT_COMPENSABLE = "READINESS_ORCHESTRATION_CONDITION_CONCERN_NOT_COMPENSABLE"
    #: The condition is not active at the evaluation instant (proposed, expired,
    #: revoked, satisfied, not yet effective, or its window has elapsed).
    CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME = "READINESS_ORCHESTRATION_CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME"

    # -- indicator catalogs (M-3R.3) --------------------------------------- #
    #: An indicator result was supplied for a readiness family with no bound
    #: catalog, so no governed definition could recognize it. The result is
    #: excluded; it is never treated as a requirement, a failure or a pass.
    INDICATOR_CATALOG_MISSING = "READINESS_ORCHESTRATION_INDICATOR_CATALOG_MISSING"
    #: A bound catalog does not govern the readiness family it was bound under —
    #: an Adoption catalog can never stand in for an Intelligence one.
    INDICATOR_CATALOG_FAMILY_MISMATCH = "READINESS_ORCHESTRATION_INDICATOR_CATALOG_FAMILY_MISMATCH"
    #: A bound catalog is tenant-scoped to a different tenant, or the supplied
    #: catalog set's canonical digest is not the one the request bound.
    INDICATOR_CATALOG_REFERENCE_MISMATCH = (
        "READINESS_ORCHESTRATION_INDICATOR_CATALOG_REFERENCE_MISMATCH"
    )
    #: The bound catalog for that family defines no entry with this indicator
    #: identity. An uncataloged indicator is excluded and influences nothing.
    INDICATOR_NOT_CATALOGED = "READINESS_ORCHESTRATION_INDICATOR_NOT_CATALOGED"
    #: The cataloged definition binds a different family-specific dimension.
    INDICATOR_CATALOG_DIMENSION_MISMATCH = (
        "READINESS_ORCHESTRATION_INDICATOR_CATALOG_DIMENSION_MISMATCH"
    )
    #: The cataloged definition binds a different governed ``metric_id``, or a
    #: different task/outcome reference than the result reports against.
    INDICATOR_CATALOG_METRIC_MISMATCH = "READINESS_ORCHESTRATION_INDICATOR_CATALOG_METRIC_MISMATCH"
    #: The cataloged definition does not apply to the requested readiness target.
    INDICATOR_CATALOG_TARGET_MISMATCH = "READINESS_ORCHESTRATION_INDICATOR_CATALOG_TARGET_MISMATCH"
    #: The result declares a different ``AssessedSystemBinding`` than the one
    #: this assessment binds, or declares none. A result produced against one
    #: system version or configuration is never replayed under another.
    INDICATOR_RESULT_SYSTEM_BINDING_MISMATCH = (
        "READINESS_ORCHESTRATION_INDICATOR_RESULT_SYSTEM_BINDING_MISMATCH"
    )
    #: More than one result was supplied for the same indicator identity. Every
    #: copy is excluded — a conflict is never resolved by picking one.
    INDICATOR_RESULT_DUPLICATE = "READINESS_ORCHESTRATION_INDICATOR_RESULT_DUPLICATE"

    # -- evaluator invocation ---------------------------------------------- #
    #: The sanitized case was still refused by the deterministic evaluator.
    #: Defensive: the request contract already rejects self-contradictory input.
    #: Reaching it produces ``NOT_EVALUATED``, never a partial headline.
    EVALUATOR_REJECTED_SANITIZED_CASE = "READINESS_ORCHESTRATION_EVALUATOR_REJECTED_SANITIZED_CASE"
