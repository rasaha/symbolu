"""The fail-closed readiness orchestration boundary (GV-3R-c, milestone M-3R.3+).

One canonical entry point — :func:`assess_readiness` — wraps the ratified
GV-3R-b evaluator in a trust boundary and proves, for a single assessment, that

1. the **exact** ``ReadinessPolicy`` was resolved through a configured shared
   Policy Authority boundary at the evaluation instant;
2. every gate result capable of influencing the classification was accepted only
   after a configured verifier attested it under the complete binding;
3. every condition capable of compensating a conditional concern was accepted
   only after a configured verifier attested it;
4. tenant, subject, context, target, policy, gate, condition and time bindings
   are consistent everywhere;
5. only sanitized inputs reached ``evaluate_readiness``;
6. every remaining trust gap is explicit, typed and deterministic;
7. the result stays advisory and authorizes no deployment.

What it is not
--------------
**No second classification algorithm exists here.** The readiness tier is
selected by exactly one function — the GV-3R-b ``evaluate_readiness`` — called
at most once, over a freshly built case. This module removes untrusted inputs;
it never re-derives, adjusts, overrides or second-guesses a classification, and
it never accepts one from a caller.

Stage order, and why it is fixed
--------------------------------
======  ===================================  =========================================
stage   what it establishes                  on failure
======  ===================================  =========================================
1       trusted policy resolution            ``NOT_EVALUATED``; **no** later stage runs
2       gate-result verification             the result is absent for the evaluator
3       condition verification                the control provides no coverage
4       one ``evaluate_readiness`` call       an advisory determination + trace
======  ===================================  =========================================

**Policy-resolution failure dominates all gate information.** Under it, no gate
verifier and no condition verifier is called, ``evaluate_readiness`` never runs,
no classification or determination is produced, and the failure outcome
preserves no usable policy material — only the stable typed gap codes and the
reference the caller already holds.

Sanitization is subtraction, never substitution
-----------------------------------------------
An unverified gate result is treated as **absent**, not as ``PASS``, not as
``INDETERMINATE`` and not as a caller-flavoured hint. Because the ratified
precedence derives its required-gate inventory from the **resolved policy body**
(never from the supplied results), a removed required result becomes a missing
required gate — ``NOT_ASSESSABLE`` — unless an independently verified mandatory
``FAIL`` already proves ``NOT_READY``. That precedence is the merged GV-3R-b
algorithm, unchanged: nothing in this module alters it.

Determinism
-----------
The system clock is never read; ``request.evaluation_time`` is the only instant,
and it is passed unchanged to resolution, to every verifier, and to the
evaluator. Inputs are processed in canonical id order, gap codes are emitted in
enum declaration order, and no randomness, uuid, environment lookup, network
call or mutable global participates — so a reordered request yields an identical
trace and an identical digest.
"""

from __future__ import annotations

from typing import Optional

from ugence_policy_authority.api import (
    PolicyResolution,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    uvi_coordinate,
)
from ugence_uvi_policy_contracts.api import (
    PolicyGate,
    PolicyLifecycleState,
    PolicyScope,
    ReadinessPolicy,
    RequirementClass,
)

from ..contracts.conditions import ConditionSet
from ..contracts.enums import ConditionStatus
from ..contracts.gates import GateResult
from ..evaluation.case import ReadinessEvaluationCase
from ..evaluation.codes import EVALUATOR_FORMULA_VERSION, ReadinessAdvisoryCode
from ..evaluation.errors import ReadinessEvaluationError
from ..evaluation.evaluator import evaluate_readiness
from .codes import (
    ORCHESTRATOR_ID,
    READINESS_ORCHESTRATOR_VERSION,
    ReadinessAssessmentStatus,
    ReadinessInputVerificationStatus,
    ReadinessTrustAdvisoryState,
    ReadinessTrustGapCode,
)
from .contracts import (
    ConditionSetVerification,
    ConditionVerificationRequest,
    GateResultVerification,
    GateVerificationRequest,
    ReadinessAssessmentRequest,
)
from .deny import (
    DenyAllConditionSetVerifier,
    DenyAllGateResultVerifier,
    DenyAllReadinessPolicyResolver,
)
from .errors import ReadinessAssessmentError
from .trace import (
    ConditionVerificationSummary,
    GateVerificationSummary,
    ReadinessAssessmentDisposition,
    ReadinessAssessmentOutcome,
    ReadinessAssessmentTrace,
)

__all__ = ["assess_readiness"]

_G = ReadinessTrustGapCode
_V = ReadinessInputVerificationStatus
_S = ReadinessTrustAdvisoryState
_A = ReadinessAdvisoryCode


def assess_readiness(
    request: ReadinessAssessmentRequest,
    *,
    policy_resolver=None,
    gate_verifier=None,
    condition_verifier=None,
) -> ReadinessAssessmentOutcome:
    """Orchestrate one fail-closed readiness assessment.

    :param request: the complete, immutable assessment input. It carries no
        classification, no trust boolean and no policy body — the governing
        ``ReadinessPolicy`` arrives only through the resolution boundary.
    :param policy_resolver: the configured
        :class:`~.protocols.ReadinessPolicyResolver`. **Omitting it denies**:
        the deny-all resolver is used and the assessment is ``NOT_EVALUATED``.
        Wiring a real one is a composition-root trust decision.
    :param gate_verifier: the configured
        :class:`~.protocols.GateResultVerifier`. **Omitting it denies**: no gate
        result can influence the classification.
    :param condition_verifier: the configured
        :class:`~.protocols.ConditionSetVerifier`. **Omitting it denies**: no
        compensating control provides coverage.
    :raises ReadinessAssessmentError: only when ``request`` is not a
        :class:`ReadinessAssessmentRequest`. Every trust failure is an outcome
        with typed gap codes, never an exception.
    :returns: a :class:`~.trace.ReadinessAssessmentOutcome` — advisory, never a
        deployment authorization, and unsigned.
    """

    if not isinstance(request, ReadinessAssessmentRequest):
        raise ReadinessAssessmentError(
            "assess_readiness.request must be a ReadinessAssessmentRequest"
        )

    gaps: set[ReadinessTrustGapCode] = set()

    # ------------------------------------------------------------------ #
    # Stage 1 — trusted policy resolution
    # ------------------------------------------------------------------ #
    resolution, resolved_policy = _resolve(request, policy_resolver, gaps)
    if gaps or resolved_policy is None:
        return _not_evaluated(request, resolution, gaps, policy_accepted=False)

    # ------------------------------------------------------------------ #
    # Stage 2 — gate-result verification against the RESOLVED policy
    # ------------------------------------------------------------------ #
    resolved_gates: dict[str, PolicyGate] = {g.gate_id: g for g in resolved_policy.gates}
    gate_summaries, admitted_gates = _verify_gate_results(
        request, resolved_gates, gate_verifier, gaps
    )

    # ------------------------------------------------------------------ #
    # Stage 3 — condition verification against the RESOLVED policy
    # ------------------------------------------------------------------ #
    condition_summaries, admitted_conditions = _verify_conditions(
        request, resolved_gates, condition_verifier, gaps
    )

    # ------------------------------------------------------------------ #
    # Stage 4 — exactly one call into the ratified evaluator
    # ------------------------------------------------------------------ #
    try:
        case = ReadinessEvaluationCase(
            case_id=request.assessment_id,
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            context=request.context,
            # The policy body comes from resolution, never from the request.
            readiness_policy=resolved_policy,
            readiness_policy_ref=request.readiness_policy_ref,
            requested_target=request.requested_target,
            intelligence_results=request.intelligence_results,
            capability_results=request.capability_results,
            adoption_results=request.adoption_results,
            gate_results=admitted_gates,
            conditions=admitted_conditions,
            advisory_composite=request.advisory_composite,
            evidence_refs=request.evidence_refs,
            assessment_window_ref=request.assessment_window_ref,
        )
        evaluation = evaluate_readiness(case, evaluation_time=request.evaluation_time)
    except ReadinessEvaluationError:
        # Defensive: the request contract already rejects self-contradictory
        # input. If the sanitized case is still refused, that is a trust gap and
        # a NOT_EVALUATED outcome — never a partial or improvised headline.
        gaps.add(_G.EVALUATOR_REJECTED_SANITIZED_CASE)
        return _not_evaluated(
            request,
            resolution,
            gaps,
            # Stage 1 did hold here; only the evaluator refused.
            policy_accepted=True,
            gate_summaries=gate_summaries,
            condition_summaries=condition_summaries,
        )

    trace = _build_trace(
        request,
        resolution,
        gaps,
        gate_summaries=gate_summaries,
        condition_summaries=condition_summaries,
        conditions_supplied=bool(request.conditions),
        composite_supplied=request.advisory_composite is not None,
        policy_accepted=True,
    )
    return ReadinessAssessmentOutcome(
        status=ReadinessAssessmentStatus.EVALUATED,
        trace=trace,
        evaluation=evaluation,
    )


# --------------------------------------------------------------------------- #
# Stage 1 — policy resolution
# --------------------------------------------------------------------------- #
def _resolve(
    request: ReadinessAssessmentRequest,
    policy_resolver,
    gaps: set,
) -> tuple[Optional[PolicyResolution], Optional[ReadinessPolicy]]:
    """Resolve the exact readiness policy, then recheck the answer independently.

    Every check below is performed by the orchestrator itself over the returned
    resolution. A resolver that says "resolved" therefore cannot get a different
    policy, a different tenant, a different instant, or an artifact the context
    does not bind, admitted.
    """

    reference = request.readiness_policy_ref

    if policy_resolver is None:
        gaps.add(_G.POLICY_RESOLVER_NOT_CONFIGURED)
        policy_resolver = DenyAllReadinessPolicyResolver()
    elif not callable(getattr(policy_resolver, "resolve_readiness_policy", None)):
        # A duck-typed object that merely looks like a resolver is refused, not
        # probed further.
        gaps.add(_G.POLICY_RESOLVER_MALFORMED_RESULT)
        return None, None

    # The reference's own declared tenant identity is what the authority is
    # asked about; the assessed tenant is checked separately below, so a
    # tenant-scoped policy belonging to another tenant can never be admitted.
    try:
        resolution = policy_resolver.resolve_readiness_policy(
            reference=reference,
            expected_tenant_id=reference.tenant_id,
            as_of=request.evaluation_time,
        )
    except Exception:  # noqa: BLE001 - any resolver failure is a closed door
        gaps.add(_G.POLICY_RESOLVER_ERROR)
        return None, None

    if not isinstance(resolution, PolicyResolution):
        gaps.add(_G.POLICY_RESOLVER_MALFORMED_RESULT)
        return None, None

    if resolution.status is not PolicyResolutionStatus.RESOLVED:
        # An UNRESOLVED resolution structurally carries no policy and no record,
        # so there is nothing further to recheck: this is the whole answer.
        gaps.add(_G.POLICY_RESOLUTION_UNRESOLVED)
        return resolution, None
    if resolution.historical:
        # A historical answer describes the past. It never implies current
        # validity, so it cannot govern an assessment at this instant.
        gaps.add(_G.POLICY_RESOLUTION_HISTORICAL_NOT_ACCEPTED)
    if resolution.as_of != request.evaluation_time:
        gaps.add(_G.POLICY_RESOLUTION_AS_OF_MISMATCH)
    if resolution.requested_coordinate != uvi_coordinate(reference):
        gaps.add(_G.POLICY_RESOLUTION_REFERENCE_MISMATCH)
    if resolution.record is None:
        gaps.add(_G.POLICY_RESOLUTION_ISSUANCE_RECORD_MISSING)

    policy = resolution.policy
    if not isinstance(policy, ReadinessPolicy):
        gaps.add(_G.POLICY_RESOLUTION_ARTIFACT_NOT_A_READINESS_POLICY)
        return resolution, None

    # Complete PolicyReference equality: family, id, version, content digest,
    # scope and tenant, all together. No partial or floating match.
    if policy.reference != reference:
        gaps.add(_G.POLICY_RESOLUTION_REFERENCE_MISMATCH)
    if resolution.record is not None and resolution.record.coordinate != uvi_coordinate(reference):
        gaps.add(_G.POLICY_RESOLUTION_REFERENCE_MISMATCH)

    # Tenant binding: a TENANT-scoped policy must belong to the assessed tenant;
    # a GLOBAL-scoped policy carries the canonical empty tenant component.
    if reference.scope is PolicyScope.TENANT:
        if reference.tenant_id != request.tenant_id:
            gaps.add(_G.POLICY_RESOLUTION_TENANT_MISMATCH)
    elif reference.tenant_id:
        gaps.add(_G.POLICY_RESOLUTION_TENANT_MISMATCH)

    # The assessment must actually be governed by this exact policy.
    if request.context.readiness_ref != reference:
        gaps.add(_G.POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH)

    if request.requested_target not in policy.readiness_targets:
        gaps.add(_G.POLICY_RESOLUTION_TARGET_NOT_GOVERNED)

    # Defence in depth. Trusted resolution already enforces lifecycle and the
    # effective period; re-reading the resolved artifact's own metadata means a
    # resolver that skipped them still cannot get an inactive or out-of-period
    # policy past this boundary.
    metadata = policy.metadata
    if metadata.lifecycle_state is not PolicyLifecycleState.APPROVED_ACTIVE:
        gaps.add(_G.POLICY_ARTIFACT_NOT_APPROVED_ACTIVE)
    if not metadata.is_effective_at(request.evaluation_time):
        gaps.add(_G.POLICY_ARTIFACT_NOT_EFFECTIVE_AT_EVALUATION_TIME)

    if gaps:
        return resolution, None
    return resolution, policy


# --------------------------------------------------------------------------- #
# Stage 2 — gate-result verification
# --------------------------------------------------------------------------- #
def _verify_gate_results(
    request: ReadinessAssessmentRequest,
    resolved_gates: dict,
    gate_verifier,
    gaps: set,
) -> tuple[tuple[GateVerificationSummary, ...], tuple[GateResult, ...]]:
    """Admit only gate results a configured verifier attested under this binding.

    A rejected result is **absent** for the evaluator. It is never downgraded to
    a weaker status, never treated as ``PASS``, and never silently dropped from
    the record: it keeps a summary carrying its stable rejection reason.
    """

    if gate_verifier is None:
        gaps.add(_G.GATE_VERIFIER_NOT_CONFIGURED)
        gate_verifier = DenyAllGateResultVerifier()
        verifier_callable = gate_verifier.verify_gate_result
    else:
        candidate = getattr(gate_verifier, "verify_gate_result", None)
        verifier_callable = candidate if callable(candidate) else None
        if verifier_callable is None:
            # Recorded up front, exactly as a malformed resolver is. A broken
            # composition root must never be quieter than an absent one, even
            # when this assessment happens to supply no gate result to reject.
            gaps.add(_G.GATE_VERIFIER_MALFORMED_RESULT)

    duplicates = _duplicate_keys(g.gate_id for g in request.gate_results)
    summaries: list[GateVerificationSummary] = []
    admitted: list[GateResult] = []

    for result in sorted(request.gate_results, key=lambda g: (g.gate_id, g.canonical_digest())):
        owned = resolved_gates.get(result.gate_id)
        reject: list[ReadinessTrustGapCode] = []
        status = _V.REFERENCE_MISMATCH
        verifier_id = ""
        detail = ""

        if result.gate_id in duplicates:
            # A conflict is never resolved by choosing one copy.
            reject.append(_G.GATE_RESULT_DUPLICATE)
            detail = "more than one result was supplied for this gate id"
        if result.readiness_policy_ref != request.readiness_policy_ref:
            reject.append(_G.GATE_RESULT_POLICY_REFERENCE_MISMATCH)
        if result.requested_target is not request.requested_target:
            reject.append(_G.GATE_RESULT_TARGET_MISMATCH)
        if owned is None:
            reject.append(_G.GATE_RESULT_GATE_NOT_IN_RESOLVED_POLICY)
        elif owned != result.policy_gate or (
            owned.canonical_digest() != result.policy_gate.canonical_digest()
        ):
            # The embedded gate must be canonically identical to the resolved
            # policy's gate of that id — a redefined or borrowed gate is refused.
            reject.append(_G.GATE_RESULT_GATE_BODY_MISMATCH)

        if not reject:
            status, verifier_id, detail, verification_gaps = _run_gate_verifier(
                request, result, owned, verifier_callable
            )
            reject.extend(verification_gaps)

        admitted_here = not reject
        if admitted_here:
            admitted.append(result)
        else:
            gaps.update(reject)
            if owned is not None and _is_required(owned, request):
                # An unverified required gate is missing for evaluator purposes.
                gaps.add(_G.REQUIRED_GATE_RESULT_UNVERIFIED)

        summaries.append(
            GateVerificationSummary(
                gate_id=result.gate_id,
                claimed_status=result.status,
                verification_status=status,
                admitted=admitted_here,
                verifier_id=verifier_id,
                gate_digest=result.policy_gate.canonical_digest(),
                trust_gap_codes=_ordered_codes(reject),
                detail=detail,
            )
        )

    return tuple(summaries), tuple(admitted)


def _run_gate_verifier(
    request: ReadinessAssessmentRequest,
    result: GateResult,
    owned: PolicyGate,
    verifier_callable,
) -> tuple[ReadinessInputVerificationStatus, str, str, list]:
    """Call the verifier, then recheck every coordinate it returned."""

    if verifier_callable is None:
        return _V.VERIFIER_ERROR, "", "the configured gate verifier is not callable", [
            _G.GATE_VERIFIER_MALFORMED_RESULT
        ]

    verification_request = GateVerificationRequest(
        assessment_id=request.assessment_id,
        tenant_id=request.tenant_id,
        subject_id=request.subject_id,
        context_digest=request.context_digest,
        readiness_policy_ref=request.readiness_policy_ref,
        requested_target=request.requested_target,
        evaluation_time=request.evaluation_time,
        # The gate as RESOLVED — never the caller's copy.
        policy_gate=owned,
        gate_digest=owned.canonical_digest(),
        claimed_status=result.status,
        gate_result_digest=result.canonical_digest(),
        observed_claim_refs=result.observed_claim_refs,
        evidence_refs=result.evidence_refs,
        reason_codes=result.reason_codes,
        window_ref=result.window_ref,
    )

    try:
        verification = verifier_callable(verification_request)
    except Exception:  # noqa: BLE001 - a verifier failure is never an acceptance
        return _V.VERIFIER_ERROR, "", "the configured gate verifier raised", [
            _G.GATE_VERIFIER_ERROR
        ]

    if not isinstance(verification, GateResultVerification):
        # Duck-typed attestations are refused rather than inspected.
        return _V.VERIFIER_ERROR, "", "the gate verifier returned a foreign object", [
            _G.GATE_VERIFIER_MALFORMED_RESULT
        ]

    verifier_id = verification.verifier_id
    if verification.status is not _V.VERIFIED:
        return (
            verification.status,
            verifier_id,
            verification.detail,
            [_G.GATE_RESULT_NOT_VERIFIED],
        )

    reject: list[ReadinessTrustGapCode] = []
    if (
        verification.gate_id != result.gate_id
        or verification.gate_digest != owned.canonical_digest()
        or verification.readiness_policy_ref != request.readiness_policy_ref
        or verification.tenant_id != request.tenant_id
        or verification.subject_id != request.subject_id
        or verification.context_digest != request.context_digest
        or verification.requested_target is not request.requested_target
        or verification.verified_at != request.evaluation_time
    ):
        reject.append(_G.GATE_RESULT_VERIFICATION_BINDING_MISMATCH)
    if verification.verified_status is not result.status:
        reject.append(_G.GATE_RESULT_VERIFIED_STATUS_MISMATCH)

    # A VERIFIED answer must actually cover what the gate relies on. Evidence,
    # benchmark resolution and threshold evaluation are the gate verifier's
    # responsibility — the readiness orchestrator performs none of them and
    # never substitutes caller metadata for a missing attestation.
    if (result.evidence_refs or result.observed_claim_refs) and not verification.evidence_verified:
        reject.append(_G.GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE)
    threshold = owned.threshold
    if threshold is not None:
        if not verification.threshold_evaluation_verified:
            reject.append(_G.GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE)
        if threshold.benchmark_ref is not None and not verification.benchmark_resolved:
            reject.append(_G.GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE)

    return _V.VERIFIED, verifier_id, verification.detail, reject


# --------------------------------------------------------------------------- #
# Stage 3 — condition verification
# --------------------------------------------------------------------------- #
def _verify_conditions(
    request: ReadinessAssessmentRequest,
    resolved_gates: dict,
    condition_verifier,
    gaps: set,
) -> tuple[tuple[ConditionVerificationSummary, ...], tuple[ConditionSet, ...]]:
    """Admit only compensating controls a configured verifier attested.

    A control that is not admitted provides **no coverage** and never reaches
    the evaluator, while staying fully visible in the trace with its stable
    rejection reason.
    """

    if not request.conditions:
        return (), ()

    if condition_verifier is None:
        gaps.add(_G.CONDITION_VERIFIER_NOT_CONFIGURED)
        condition_verifier = DenyAllConditionSetVerifier()
        verifier_callable = condition_verifier.verify_condition
    else:
        candidate = getattr(condition_verifier, "verify_condition", None)
        verifier_callable = candidate if callable(candidate) else None
        if verifier_callable is None:
            gaps.add(_G.CONDITION_VERIFIER_MALFORMED_RESULT)

    duplicates = _duplicate_keys(c.condition_id for c in request.conditions)
    summaries: list[ConditionVerificationSummary] = []
    admitted: list[ConditionSet] = []

    for condition in sorted(
        request.conditions, key=lambda c: (c.condition_id, c.canonical_digest())
    ):
        owned = resolved_gates.get(condition.source_gate_or_finding_ref)
        reject: list[ReadinessTrustGapCode] = []
        status = _V.REFERENCE_MISMATCH
        verifier_id = ""
        detail = ""

        if condition.condition_id in duplicates:
            reject.append(_G.CONDITION_DUPLICATE)
            detail = "more than one condition was supplied under this id"
        if owned is None:
            reject.append(_G.CONDITION_CONCERN_NOT_IN_RESOLVED_POLICY)
        else:
            if owned.requirement_class is not RequirementClass.CONDITIONAL:
                # D-6: a mandatory concern is never waivable or compensable.
                reject.append(_G.CONDITION_CONCERN_NOT_CONDITIONAL)
            elif not owned.conditionally_compensable:
                reject.append(_G.CONDITION_CONCERN_NOT_COMPENSABLE)
        # Half-open activity at the explicit evaluation instant: proposed,
        # expired, revoked, satisfied, not-yet-effective and elapsed controls all
        # fail here, before any verifier is consulted.
        if not condition.is_active_at(request.evaluation_time):
            reject.append(_G.CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME)

        if not reject:
            status, verifier_id, detail, verification_gaps = _run_condition_verifier(
                request, condition, owned, verifier_callable
            )
            reject.extend(verification_gaps)

        admitted_here = not reject
        if admitted_here:
            admitted.append(condition)
        else:
            gaps.update(reject)

        summaries.append(
            ConditionVerificationSummary(
                condition_id=condition.condition_id,
                source_gate_or_finding_ref=condition.source_gate_or_finding_ref,
                claimed_status=condition.current_status,
                verification_status=status,
                admitted=admitted_here,
                verifier_id=verifier_id,
                condition_digest=condition.canonical_digest(),
                trust_gap_codes=_ordered_codes(reject),
                detail=detail,
            )
        )

    return tuple(summaries), tuple(admitted)


def _run_condition_verifier(
    request: ReadinessAssessmentRequest,
    condition: ConditionSet,
    owned: PolicyGate,
    verifier_callable,
) -> tuple[ReadinessInputVerificationStatus, str, str, list]:
    """Call the condition verifier, then recheck every coordinate it returned."""

    if verifier_callable is None:
        return _V.VERIFIER_ERROR, "", "the configured condition verifier is not callable", [
            _G.CONDITION_VERIFIER_MALFORMED_RESULT
        ]

    verification_request = ConditionVerificationRequest(
        assessment_id=request.assessment_id,
        tenant_id=request.tenant_id,
        subject_id=request.subject_id,
        context_digest=request.context_digest,
        readiness_policy_ref=request.readiness_policy_ref,
        requested_target=request.requested_target,
        evaluation_time=request.evaluation_time,
        condition_id=condition.condition_id,
        condition_digest=condition.canonical_digest(),
        source_gate_or_finding_ref=condition.source_gate_or_finding_ref,
        policy_gate=owned,
        gate_digest=owned.canonical_digest(),
        claimed_status=condition.current_status,
        approving_authority_ref=condition.approving_authority_ref,
        approved_mitigation_ref=condition.approved_mitigation_ref,
        accountable_owner=condition.accountable_owner,
        scope_exposure_limit=condition.scope_exposure_limit,
        monitoring_requirement=condition.monitoring_requirement,
        revocation_trigger=condition.revocation_trigger,
        evidence_refs=condition.evidence_refs,
        effective_from=condition.effective_from,
        effective_to=condition.effective_to,
        expiry=condition.expiry,
    )

    try:
        verification = verifier_callable(verification_request)
    except Exception:  # noqa: BLE001 - a verifier failure is never an acceptance
        return _V.VERIFIER_ERROR, "", "the configured condition verifier raised", [
            _G.CONDITION_VERIFIER_ERROR
        ]

    if not isinstance(verification, ConditionSetVerification):
        return _V.VERIFIER_ERROR, "", "the condition verifier returned a foreign object", [
            _G.CONDITION_VERIFIER_MALFORMED_RESULT
        ]

    verifier_id = verification.verifier_id
    if verification.status is not _V.VERIFIED:
        return (
            verification.status,
            verifier_id,
            verification.detail,
            [_G.CONDITION_NOT_VERIFIED],
        )

    reject: list[ReadinessTrustGapCode] = []
    if verification.condition_id != condition.condition_id:
        reject.append(_G.CONDITION_IDENTITY_MISMATCH)
    if verification.condition_digest != condition.canonical_digest():
        reject.append(_G.CONDITION_DIGEST_MISMATCH)
    if (
        verification.source_gate_or_finding_ref != condition.source_gate_or_finding_ref
        or verification.covered_gate_id != owned.gate_id
        or verification.gate_digest != owned.canonical_digest()
    ):
        # One control covers exactly one concern; identity ambiguity is refused.
        reject.append(_G.CONDITION_SOURCE_REFERENCE_MISMATCH)
    if (
        verification.readiness_policy_ref != request.readiness_policy_ref
        or verification.tenant_id != request.tenant_id
        or verification.subject_id != request.subject_id
        or verification.context_digest != request.context_digest
        or verification.requested_target is not request.requested_target
        or verification.verified_at != request.evaluation_time
        or verification.effective_from != condition.effective_from
        or verification.effective_to != condition.effective_to
        or verification.expiry != condition.expiry
    ):
        reject.append(_G.CONDITION_VERIFICATION_BINDING_MISMATCH)
    # The verifier's own established status must be APPROVED_ACTIVE and must
    # agree with the record; approval authority, approval evidence and the
    # owner/monitoring obligations must all be attested.
    if (
        verification.verified_status is not ConditionStatus.APPROVED_ACTIVE
        or verification.verified_status is not condition.current_status
    ):
        reject.append(_G.CONDITION_NOT_VERIFIED)
    if not (
        verification.approval_authority_verified
        and verification.approval_evidence_verified
        and verification.owner_and_monitoring_verified
    ):
        reject.append(_G.CONDITION_APPROVAL_NOT_VERIFIED)

    return _V.VERIFIED, verifier_id, verification.detail, reject


# --------------------------------------------------------------------------- #
# Outcome assembly
# --------------------------------------------------------------------------- #
def _not_evaluated(
    request: ReadinessAssessmentRequest,
    resolution: Optional[PolicyResolution],
    gaps: set,
    *,
    policy_accepted: bool,
    gate_summaries: tuple = (),
    condition_summaries: tuple = (),
) -> ReadinessAssessmentOutcome:
    """A refusal. No classification and no determination, ever."""

    trace = _build_trace(
        request,
        resolution,
        gaps,
        gate_summaries=gate_summaries,
        condition_summaries=condition_summaries,
        conditions_supplied=bool(request.conditions),
        composite_supplied=request.advisory_composite is not None,
        policy_accepted=policy_accepted,
    )
    return ReadinessAssessmentOutcome(
        status=ReadinessAssessmentStatus.NOT_EVALUATED, trace=trace, evaluation=None
    )


def _build_trace(
    request: ReadinessAssessmentRequest,
    resolution: Optional[PolicyResolution],
    gaps: set,
    *,
    gate_summaries: tuple,
    condition_summaries: tuple,
    conditions_supplied: bool,
    composite_supplied: bool,
    policy_accepted: bool,
) -> ReadinessAssessmentTrace:
    # The authority's own answer is reported verbatim — including the case where
    # it resolved but a later independent recheck still refused the artifact, so
    # the trace never overstates *or* understates what the boundary said.
    if resolution is None:
        status = PolicyResolutionStatus.UNRESOLVED
        reason = PolicyResolutionReason.NOT_FOUND
    else:
        status = resolution.status
        reason = resolution.reason

    # Policy material is disclosed only when stage 1 held in full. A refusal
    # carries no issuance record reference and no resolved-policy digest; the
    # requested reference is the caller's own input and discloses nothing new.
    if policy_accepted and resolution is not None:
        issuance_record_ref = resolution.record.record_id if resolution.record else ""
        resolved_policy_digest = resolution.policy.canonical_digest()
    else:
        issuance_record_ref = ""
        resolved_policy_digest = ""

    admitted_gate_ids = tuple(sorted(s.gate_id for s in gate_summaries if s.admitted))
    rejected_gate_ids = tuple(sorted(s.gate_id for s in gate_summaries if not s.admitted))
    admitted_condition_ids = tuple(
        sorted(s.condition_id for s in condition_summaries if s.admitted)
    )
    rejected_condition_ids = tuple(
        sorted(s.condition_id for s in condition_summaries if not s.admitted)
    )

    return ReadinessAssessmentTrace(
        assessment_id=request.assessment_id,
        tenant_id=request.tenant_id,
        subject_id=request.subject_id,
        context_digest=request.context_digest,
        readiness_policy_ref=request.readiness_policy_ref,
        requested_target=request.requested_target,
        evaluation_time=request.evaluation_time,
        request_digest=request.canonical_digest(),
        policy_resolution_status=status,
        policy_resolution_reason=reason,
        policy_resolution_accepted=policy_accepted,
        issuance_record_ref=issuance_record_ref,
        resolved_policy_digest=resolved_policy_digest,
        gate_verifications=tuple(gate_summaries),
        condition_verifications=tuple(condition_summaries),
        admitted_gate_ids=admitted_gate_ids,
        rejected_gate_ids=rejected_gate_ids,
        admitted_condition_ids=admitted_condition_ids,
        rejected_condition_ids=rejected_condition_ids,
        trust_gap_codes=_ordered_codes(gaps),
        dispositions=_dispositions(
            resolved=policy_accepted,
            admitted_gate_ids=admitted_gate_ids,
            rejected_gate_ids=rejected_gate_ids,
            admitted_condition_ids=admitted_condition_ids,
            rejected_condition_ids=rejected_condition_ids,
            conditions_supplied=conditions_supplied,
            composite_supplied=composite_supplied,
        ),
        orchestrator_id=ORCHESTRATOR_ID,
        orchestrator_version=READINESS_ORCHESTRATOR_VERSION,
        evaluator_formula_version=EVALUATOR_FORMULA_VERSION,
    )


def _dispositions(
    *,
    resolved: bool,
    admitted_gate_ids: tuple,
    rejected_gate_ids: tuple,
    admitted_condition_ids: tuple,
    rejected_condition_ids: tuple,
    conditions_supplied: bool,
    composite_supplied: bool,
) -> tuple[ReadinessAssessmentDisposition, ...]:
    """Reconcile every standing GV-3R-b advisory against what was actually proven.

    Nothing here is marked resolved because a caller supplied a boolean or a
    structurally complete record: an advisory is closed only by the configured
    boundary that actually answered.
    """

    entries: list[ReadinessAssessmentDisposition] = [
        ReadinessAssessmentDisposition(
            advisory_code=_A.ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION.value,
            state=_S.OUT_OF_SCOPE,
            detail=(
                "permanent boundary: readiness stays advisory and this phase mints no "
                "deployment authorization"
            ),
        ),
        ReadinessAssessmentDisposition(
            advisory_code=_A.POLICY_AUTHENTICITY_NOT_VERIFIED.value,
            state=(
                _S.RESOLVED_BY_POLICY_RESOLUTION if resolved else _S.UNRESOLVED
            ),
            detail=(
                "the exact policy reference resolved through the configured shared Policy "
                "Authority boundary at the evaluation instant"
                if resolved
                else "no trusted resolution of the exact policy reference was obtained"
            ),
        ),
        ReadinessAssessmentDisposition(
            advisory_code=_A.GATE_STATUS_STRUCTURALLY_SUPPLIED.value,
            # Resolved only when EVERY supplied gate result was verified. One
            # rejected result leaves the advisory open: that gate's status was
            # never proven, and the assessment is poorer for it — even though
            # the rejected result influenced nothing.
            state=(
                _S.RESOLVED_BY_GATE_VERIFICATION
                if admitted_gate_ids and not rejected_gate_ids
                else _S.UNRESOLVED
            ),
            detail=(
                "every supplied gate result was verified by the configured verifier, including "
                "the evidence, benchmark resolution and threshold evaluation each gate relies on"
                if admitted_gate_ids and not rejected_gate_ids
                else (
                    f"{len(rejected_gate_ids)} of "
                    f"{len(admitted_gate_ids) + len(rejected_gate_ids)} supplied gate results "
                    "were not verified and are absent from the evaluation, so their status — "
                    "and the benchmark and evidence authenticity behind it — remains unproven"
                )
            ),
        ),
        ReadinessAssessmentDisposition(
            advisory_code=_A.EVIDENCE_CLASSIFICATION_PRESERVED.value,
            state=_S.OUT_OF_SCOPE,
            detail=(
                "permanent guarantee: evidence axes are carried through unchanged and never "
                "elevated by orchestration"
            ),
        ),
        ReadinessAssessmentDisposition(
            advisory_code=_A.READINESS_IS_LEADING_INDICATOR_ONLY.value,
            state=_S.OUT_OF_SCOPE,
            detail="permanent boundary: this phase adds no realized-outcome measurement",
        ),
    ]

    if conditions_supplied:
        covered = bool(admitted_condition_ids) and not rejected_condition_ids
        entries.append(
            ReadinessAssessmentDisposition(
                advisory_code=_A.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED.value,
                state=_S.RESOLVED_BY_CONDITION_VERIFICATION if covered else _S.UNRESOLVED,
                detail=(
                    "every supplied control had its approving authority and approval evidence "
                    "attested by the configured verifier"
                    if covered
                    else (
                        f"{len(rejected_condition_ids)} of "
                        f"{len(admitted_condition_ids) + len(rejected_condition_ids)} supplied "
                        "controls were not verified and provide no coverage"
                    )
                ),
            )
        )
        entries.append(
            ReadinessAssessmentDisposition(
                advisory_code=_A.CONDITION_SCOPE_NOT_TENANT_BOUND.value,
                state=_S.RESOLVED_BY_CONDITION_VERIFICATION if covered else _S.UNRESOLVED,
                detail=(
                    "the merged ConditionSet has no tenant field; the configured verifier "
                    "attested the tenant, subject and context binding for every supplied control"
                    if covered
                    else (
                        "at least one control's tenant, subject or context binding was never "
                        "attested"
                    )
                ),
            )
        )

    if composite_supplied:
        entries.append(
            ReadinessAssessmentDisposition(
                advisory_code=_A.COMPOSITE_CARRIED_NOT_USED_IN_SELECTION.value,
                state=_S.OUT_OF_SCOPE,
                detail=(
                    "permanent boundary: the advisory composite is carried through and never "
                    "participates in selecting a tier"
                ),
            )
        )

    return tuple(entries)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _ordered_codes(selected) -> tuple[str, ...]:
    """Emit gap codes in enum declaration order — never in input order."""

    chosen = {c.value for c in selected}
    return tuple(member.value for member in ReadinessTrustGapCode if member.value in chosen)


def _duplicate_keys(values) -> frozenset:
    seen: set = set()
    duplicates: set = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return frozenset(duplicates)


def _is_required(gate: PolicyGate, request: ReadinessAssessmentRequest) -> bool:
    """Whether the resolved policy makes this gate required for the target."""

    return request.requested_target in gate.applicability and gate.requirement_class in (
        RequirementClass.MANDATORY,
        RequirementClass.CONDITIONAL,
    )
