"""The deterministic readiness-**determination** evaluator (GV-3R-b, M-3R.2).

One canonical entry point — :func:`evaluate_readiness` — selects exactly one
:class:`ReadinessClassification` from a complete
:class:`~ugence_agent_value_readiness.evaluation.case.ReadinessEvaluationCase`
at an explicit, caller-supplied ``evaluation_time``.

What this is
------------
A **determination evaluator over structurally supplied gate results**, not a
metric-evaluation engine. It consumes ``GateResult.status`` as recorded by an
upstream evaluator and never recomputes it: the merged contracts carry a
``GovernedThreshold`` as an opaque literal-or-benchmark whose unit and
comparison semantics are not machine-resolvable yet, so **no metric-to-threshold
comparison is performed here**. It therefore performs no evidence admission, no
evidence verification, no benchmark resolution, no policy-authenticity
verification and no causal attribution, and it is never an authorization to
deploy.

What it does
------------
Derives the authoritative gate inventory from the ``ReadinessPolicy`` body,
proves the supplied gate results are complete for the requested target, applies
the ratified precedence, resolves conditional compensation against
``ConditionSet`` records active at ``evaluation_time``, and emits an advisory
``AgentValueReadinessDetermination`` with a deterministic trace.

Precedence (first matching rule wins)
-------------------------------------
======  =========================================================  =======================
Rule    Condition                                                  Classification
======  =========================================================  =======================
R1      any applicable mandatory ``FAIL``                          ``NOT_READY``
R2      a structural assessability gap                             ``NOT_ASSESSABLE``
R3      an applicable mandatory ``INDETERMINATE`` (no ``FAIL``)    ``NOT_ASSESSABLE``
R4      unresolved conditional concern, not compensable            ``NOT_READY``
R5      compensable concern without active covering condition      ``NOT_READY``
R6      PILOT: mandatory all ``PASS``, concerns covered            ``PILOT_READY``
R7      PRODUCTION: concerns remain, all actively covered          ``READY_WITH_CONDITIONS``
R8      PRODUCTION: nothing unresolved, no open active condition   ``DEPLOYMENT_READY``
======  =========================================================  =======================

**Why R1 precedes R2.** ADR §8 / D-6 make a mandatory ``FAIL`` unconditional:
``MANDATORY FAIL ⇒ NOT_READY`` carries no exception clause, and the merged
``AgentValueReadinessDetermination`` consistency guard *rejects* any
classification other than ``NOT_READY`` while a blocking gate is present — so a
gap could not be reported as ``NOT_ASSESSABLE`` without discarding the failure
from the record, which would hide it. Every assessability gap is still recorded
in the trace and reason codes when R1 fires; nothing is silently dropped.

A definite mandatory ``FAIL`` dominates unrelated ``INDETERMINATE`` results
(``{FAIL, INDETERMINATE, PASS} ⇒ NOT_READY``). No condition, composite,
Intelligence score, Capability strength or Adoption score can override it.

Determinism
-----------
The evaluator never reads the system clock — ``evaluation_time`` is mandatory,
keyword-only and must be timezone-aware. Every output collection is ordered by
gate id, condition id, or code declaration order, so the classification, ordered
reason codes, gate sets, condition coverage and canonical digests do not depend
on the order the caller supplied its inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import PolicyGate, ReadinessTarget, RequirementClass

from ..contracts._util import require_tzaware
from ..contracts.conditions import ConditionSet
from ..contracts.determination import AgentValueReadinessDetermination
from ..contracts.enums import ConditionStatus, GateStatus, ReadinessClassification
from ..contracts.errors import ReadinessContractError
from ..contracts.gates import GateResult
from .case import ReadinessEvaluationCase
from .codes import (
    EVALUATOR_FORMULA_VERSION,
    EVALUATOR_ID,
    ConditionDecisionCode,
    ReadinessAdvisoryCode,
    ReadinessReasonCode,
    ReadinessRuleId,
)
from .errors import ReadinessEvaluationError
from .trace import ConditionDecision, ReadinessEvaluationResult, ReadinessEvaluationTrace

__all__ = ["evaluate_readiness"]

_RC = ReadinessReasonCode
_AC = ReadinessAdvisoryCode
_CD = ConditionDecisionCode


# --------------------------------------------------------------------------- #
# Internal working state (never exported)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _ConditionOutcome:
    condition: ConditionSet
    code: ConditionDecisionCode
    accepted: bool
    active: bool


def evaluate_readiness(
    case: ReadinessEvaluationCase,
    *,
    evaluation_time: datetime,
) -> ReadinessEvaluationResult:
    """Select one advisory readiness classification for ``case``.

    :param case: the complete, immutable evaluation input. It carries **no**
        classification field — the caller states facts, this function selects the
        tier.
    :param evaluation_time: an explicit, timezone-aware instant. Mandatory and
        keyword-only: condition activity is resolved against it and the system
        clock is never read, so the evaluation is reproducible.
    :raises ReadinessEvaluationError: only for structurally malformed or
        self-contradictory inputs. An incomplete but valid assessment returns a
        ``NOT_ASSESSABLE`` determination instead.
    :returns: a :class:`ReadinessEvaluationResult` — an advisory determination
        plus a deterministic explanatory trace. Never a deployment authorization.
    """

    if not isinstance(case, ReadinessEvaluationCase):
        raise ReadinessEvaluationError(
            "evaluate_readiness.case must be a ReadinessEvaluationCase"
        )
    try:
        require_tzaware(evaluation_time, "evaluate_readiness.evaluation_time")
    except ReadinessContractError as exc:  # surface the evaluator's own error type
        raise ReadinessEvaluationError(str(exc)) from exc

    target = case.requested_target
    policy_gates: dict[str, PolicyGate] = {g.gate_id: g for g in case.readiness_policy.gates}
    results: dict[str, GateResult] = {g.gate_id: g for g in case.gate_results}

    applicable_gates = case.applicable_policy_gates
    applicable_ids = tuple(g.gate_id for g in applicable_gates)
    diagnostic_ids = tuple(g.gate_id for g in case.diagnostic_policy_gates)

    # -- gate-set completeness: the POLICY is the authoritative inventory ---- #
    required_gates = tuple(
        g
        for g in applicable_gates
        if g.requirement_class in (RequirementClass.MANDATORY, RequirementClass.CONDITIONAL)
    )
    missing_required = tuple(
        sorted(g.gate_id for g in required_gates if g.gate_id not in results)
    )

    # -- precedence facts, all derived from the supplied results ------------- #
    mandatory_failures = tuple(sorted(g.gate_id for g in case.gate_results if g.is_blocking))
    mandatory_indeterminate = tuple(
        sorted(g.gate_id for g in case.gate_results if g.is_applicable_mandatory_indeterminate)
    )
    unresolved_conditional = tuple(
        sorted(g.gate_id for g in case.gate_results if g.is_applicable_conditional_unresolved)
    )
    non_compensable = tuple(
        gid for gid in unresolved_conditional if not policy_gates[gid].conditionally_compensable
    )
    compensable_unresolved = tuple(
        gid for gid in unresolved_conditional if gid not in set(non_compensable)
    )

    # -- condition resolution ------------------------------------------------ #
    outcomes = _resolve_conditions(
        case=case,
        evaluation_time=evaluation_time,
        policy_gates=policy_gates,
        results=results,
        applicable_ids=frozenset(applicable_ids),
        unresolved_conditional=frozenset(unresolved_conditional),
    )
    accepted_by_gate: dict[str, list[str]] = {}
    for o in outcomes:
        if o.accepted:
            accepted_by_gate.setdefault(o.condition.source_gate_or_finding_ref, []).append(
                o.condition.condition_id
            )
    uncovered = tuple(gid for gid in compensable_unresolved if gid not in accepted_by_gate)
    accepted_condition_ids = tuple(sorted(o.condition.condition_id for o in outcomes if o.accepted))

    # -- assessability gaps -------------------------------------------------- #
    gaps: set[ReadinessReasonCode] = set()

    bound = case.context.readiness_ref
    if bound is None:
        gaps.add(_RC.READINESS_POLICY_NOT_BOUND_TO_CONTEXT)
    elif bound != case.readiness_policy_ref:
        gaps.add(_RC.READINESS_POLICY_REF_CONTEXT_MISMATCH)

    if target not in case.readiness_policy.readiness_targets:
        gaps.add(_RC.REQUESTED_TARGET_NOT_GOVERNED_BY_POLICY)

    if not _has_applicable(case.intelligence_results, target):
        gaps.add(_RC.INTELLIGENCE_RESULT_MISSING)
    if not _has_applicable(case.capability_results, target):
        gaps.add(_RC.CAPABILITY_RESULT_MISSING)
    if not _has_applicable(case.adoption_results, target):
        gaps.add(_RC.ADOPTION_RESULT_MISSING)

    if missing_required:
        gaps.add(_RC.APPLICABLE_GATE_RESULT_MISSING)

    # An open control implies an unresolved concern: an active condition naming
    # an applicable gate that is not currently unresolved contradicts itself (it
    # is exactly what DEPLOYMENT_READY forbids). A condition naming a diagnostic
    # gate, a finding, or an unknown reference is simply not coverage — not a gap.
    if _has_dangling_active_condition(outcomes, results, frozenset(applicable_ids)):
        gaps.add(_RC.ACTIVE_CONDITION_WITHOUT_UNRESOLVED_CONCERN)

    # Recorded as an assessability gap for the trace (ADR §7 row 2), but it has
    # its own precedence rule (R3) so it is not folded into the R2 test.
    gap_codes_for_trace = set(gaps)
    if mandatory_indeterminate:
        gap_codes_for_trace.add(_RC.MANDATORY_GATE_INDETERMINATE)

    # -- rule selection (first match wins) ----------------------------------- #
    reasons: set[ReadinessReasonCode] = set(gap_codes_for_trace)

    if mandatory_failures:
        rule = ReadinessRuleId.MANDATORY_FAIL
        classification = ReadinessClassification.NOT_READY
        reasons.add(_RC.MANDATORY_GATE_FAILED)
    elif gaps:
        rule = ReadinessRuleId.ASSESSABILITY_GAP
        classification = ReadinessClassification.NOT_ASSESSABLE
    elif mandatory_indeterminate:
        rule = ReadinessRuleId.MANDATORY_INDETERMINATE
        classification = ReadinessClassification.NOT_ASSESSABLE
    elif non_compensable:
        rule = ReadinessRuleId.CONDITIONAL_NOT_COMPENSABLE
        classification = ReadinessClassification.NOT_READY
        reasons.add(_RC.ALL_APPLICABLE_MANDATORY_GATES_PASSED)
        reasons.add(_RC.CONDITIONAL_CONCERN_NOT_COMPENSABLE)
    elif uncovered:
        rule = ReadinessRuleId.CONDITIONAL_UNCOVERED
        classification = ReadinessClassification.NOT_READY
        reasons.add(_RC.ALL_APPLICABLE_MANDATORY_GATES_PASSED)
        reasons.add(_RC.CONDITIONAL_CONCERN_WITHOUT_ACTIVE_COVERAGE)
    else:
        reasons.add(_RC.ALL_APPLICABLE_MANDATORY_GATES_PASSED)
        if unresolved_conditional:
            reasons.add(_RC.CONDITIONAL_CONCERNS_COVERED_BY_ACTIVE_CONDITIONS)
        else:
            reasons.add(_RC.NO_UNRESOLVED_APPLICABLE_CONCERN)
        if target is ReadinessTarget.PILOT:
            # The enum has no PILOT_READY_WITH_CONDITIONS tier: a covered pilot
            # concern stays PILOT_READY and carries its bounded pilot controls.
            rule = ReadinessRuleId.PILOT_READY
            classification = ReadinessClassification.PILOT_READY
            reasons.add(_RC.PILOT_SCOPE_IS_BOUNDED)
        elif unresolved_conditional:
            rule = ReadinessRuleId.READY_WITH_CONDITIONS
            classification = ReadinessClassification.READY_WITH_CONDITIONS
        else:
            rule = ReadinessRuleId.DEPLOYMENT_READY
            classification = ReadinessClassification.DEPLOYMENT_READY

    # -- advisories: what this result does NOT prove ------------------------- #
    advisories: set[ReadinessAdvisoryCode] = {
        _AC.ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION,
        _AC.POLICY_AUTHENTICITY_NOT_VERIFIED,
        _AC.GATE_STATUS_STRUCTURALLY_SUPPLIED,
        _AC.EVIDENCE_CLASSIFICATION_PRESERVED,
        _AC.READINESS_IS_LEADING_INDICATOR_ONLY,
    }
    if case.conditions:
        advisories.add(_AC.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED)
        advisories.add(_AC.CONDITION_SCOPE_NOT_TENANT_BOUND)
    if case.advisory_composite is not None:
        advisories.add(_AC.COMPOSITE_CARRIED_NOT_USED_IN_SELECTION)

    reason_codes = _ordered(ReadinessReasonCode, reasons)
    advisory_codes = _ordered(ReadinessAdvisoryCode, advisories)
    gap_codes = _ordered(ReadinessReasonCode, gap_codes_for_trace)

    # -- attach conditions to the determination ------------------------------ #
    # Accepted coverage plus every condition that is NOT active at
    # ``evaluation_time`` (historical / proposed / expired / revoked / satisfied).
    # An *active* condition that covers nothing is deliberately not attached — it
    # would contradict the determination's own "an active control implies an
    # unresolved concern" rule — but it is fully recorded in the trace.
    attached = tuple(
        sorted(
            (o.condition for o in outcomes if o.accepted or not o.active),
            key=lambda c: c.condition_id,
        )
    )

    determination = AgentValueReadinessDetermination(
        assessment_id=case.case_id,
        tenant_id=case.tenant_id,
        subject_id=case.subject_id,
        context=case.context,
        readiness_policy_ref=case.readiness_policy_ref,
        requested_target=target,
        classification=classification,
        created_at=evaluation_time,
        intelligence_results=tuple(sorted(case.intelligence_results, key=lambda r: r.result_id)),
        capability_results=tuple(sorted(case.capability_results, key=lambda r: r.result_id)),
        adoption_results=tuple(sorted(case.adoption_results, key=lambda r: r.result_id)),
        gate_results=tuple(sorted(case.gate_results, key=lambda g: g.gate_id)),
        conditions=attached,
        # Carried through unchanged; never consulted when selecting the tier.
        advisory_composite=case.advisory_composite,
        reason_codes=reason_codes + advisory_codes,
        evidence_digest=case.canonical_input_digest(),
    )

    trace = ReadinessEvaluationTrace(
        evaluator_id=EVALUATOR_ID,
        formula_version=EVALUATOR_FORMULA_VERSION,
        rule_id=rule.value,
        classification=classification,
        requested_target=target,
        evaluation_time=evaluation_time,
        applicable_gate_ids=applicable_ids,
        diagnostic_gate_ids=diagnostic_ids,
        missing_required_gate_ids=missing_required,
        mandatory_failure_gate_ids=mandatory_failures,
        mandatory_indeterminate_gate_ids=mandatory_indeterminate,
        unresolved_conditional_gate_ids=unresolved_conditional,
        non_compensable_conditional_gate_ids=non_compensable,
        uncovered_conditional_gate_ids=uncovered,
        accepted_condition_ids=accepted_condition_ids,
        condition_decisions=tuple(
            ConditionDecision(
                condition_id=o.condition.condition_id,
                source_gate_or_finding_ref=o.condition.source_gate_or_finding_ref,
                decision_code=o.code.value,
                accepted=o.accepted,
            )
            for o in outcomes
        ),
        assessability_gap_codes=gap_codes,
        reason_codes=reason_codes,
        advisory_codes=advisory_codes,
        input_ref_ids=_input_refs(case),
        input_digest=case.canonical_input_digest(),
        advisory_composite_carried=case.advisory_composite is not None,
    )

    return ReadinessEvaluationResult(determination=determination, trace=trace)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _ordered(enum_cls, selected) -> tuple[str, ...]:
    """Emit codes in enum declaration order — never in input order."""

    chosen = {c.value for c in selected}
    return tuple(member.value for member in enum_cls if member.value in chosen)


def _has_applicable(results, target: ReadinessTarget) -> bool:
    """Whether any indicator result declares itself applicable to ``target``."""

    return any(target in r.applicable_targets for r in results)


def _resolve_conditions(
    *,
    case: ReadinessEvaluationCase,
    evaluation_time: datetime,
    policy_gates: dict,
    results: dict,
    applicable_ids: frozenset,
    unresolved_conditional: frozenset,
) -> tuple[_ConditionOutcome, ...]:
    """Classify every supplied ``ConditionSet``, ordered by ``condition_id``.

    A condition is accepted as coverage only when **all** hold: it names an
    applicable ``CONDITIONAL`` gate that the policy marks
    ``conditionally_compensable``; that gate is genuinely unresolved
    (``FAIL``/``INDETERMINATE``); the condition is ``APPROVED_ACTIVE``; and it is
    active at ``evaluation_time`` under the merged half-open interval
    ``effective_from <= t < effective_to`` and ``t < expiry``. Structural
    completeness (approving authority, accountable owner, scope, monitoring,
    evidence, revocation trigger, effective_from) is guaranteed by the
    ``ConditionSet`` constructor for ``APPROVED_ACTIVE`` and re-asserted here.

    Acceptance is structural only: no approving authority is resolved, and the
    condition carries no tenant/subject field on the merged contract, so its
    scope is **not** matched against the assessed tenant or subject.
    """

    outcomes: list[_ConditionOutcome] = []
    for c in sorted(case.conditions, key=lambda x: x.condition_id):
        active = c.is_active_at(evaluation_time)
        code = _classify_condition(
            condition=c,
            evaluation_time=evaluation_time,
            policy_gates=policy_gates,
            results=results,
            applicable_ids=applicable_ids,
            unresolved_conditional=unresolved_conditional,
        )
        outcomes.append(
            _ConditionOutcome(
                condition=c,
                code=code,
                accepted=code is _CD.ACCEPTED_ACTIVE_COVERAGE,
                active=active,
            )
        )
    return tuple(outcomes)


def _classify_condition(
    *,
    condition: ConditionSet,
    evaluation_time: datetime,
    policy_gates: dict,
    results: dict,
    applicable_ids: frozenset,
    unresolved_conditional: frozenset,
) -> ConditionDecisionCode:
    ref = condition.source_gate_or_finding_ref
    gate = policy_gates.get(ref)
    if gate is None:
        return _CD.CONCERN_NOT_A_POLICY_GATE
    if ref not in applicable_ids:
        return _CD.CONCERN_NOT_APPLICABLE_TO_TARGET
    if gate.requirement_class is not RequirementClass.CONDITIONAL:
        # D-6: a mandatory concern is never eligible for a compensating control.
        return _CD.CONCERN_NOT_CONDITIONAL
    if ref not in unresolved_conditional:
        return _CD.CONCERN_NOT_UNRESOLVED
    if not gate.conditionally_compensable:
        # CONDITIONAL alone is not enough — the policy must say so explicitly.
        return _CD.CONCERN_NOT_COMPENSABLE

    status = condition.current_status
    if status is ConditionStatus.PROPOSED:
        return _CD.STATUS_PROPOSED
    if status is ConditionStatus.EXPIRED:
        return _CD.STATUS_EXPIRED
    if status is ConditionStatus.REVOKED:
        return _CD.STATUS_REVOKED
    if status is ConditionStatus.SATISFIED:
        return _CD.STATUS_SATISFIED_HISTORICAL

    # APPROVED_ACTIVE — resolve the declared window at the supplied instant.
    if condition.effective_from is not None and evaluation_time < condition.effective_from:
        return _CD.NOT_YET_EFFECTIVE
    if condition.effective_to is not None and evaluation_time >= condition.effective_to:
        return _CD.WINDOW_ENDED
    if condition.expiry is not None and evaluation_time >= condition.expiry:
        return _CD.EXPIRED_AT_EVALUATION_TIME
    if not condition.is_active_at(evaluation_time):  # pragma: no cover - defensive
        return _CD.WINDOW_ENDED
    if not _is_structurally_complete(condition):  # pragma: no cover - defensive
        return _CD.STATUS_PROPOSED
    return _CD.ACCEPTED_ACTIVE_COVERAGE


def _is_structurally_complete(condition: ConditionSet) -> bool:
    """Re-assert the completeness the ``ConditionSet`` constructor guarantees.

    Defensive only: an ``APPROVED_ACTIVE`` record cannot be constructed without
    these fields. Kept explicit so the requirement is visible at the decision
    point rather than assumed.
    """

    return bool(
        condition.approved_mitigation_ref
        and condition.approving_authority_ref
        and condition.accountable_owner
        and condition.scope_exposure_limit
        and condition.monitoring_requirement
        and condition.revocation_trigger
        and condition.evidence_refs
        and condition.effective_from is not None
    )


def _has_dangling_active_condition(
    outcomes: tuple[_ConditionOutcome, ...],
    results: dict,
    applicable_ids: frozenset,
) -> bool:
    """An active control over an applicable concern that is not unresolved.

    A concern is unresolved when its supplied result is ``FAIL`` or
    ``INDETERMINATE``. An active control over an applicable gate that ``PASS``es
    (or has no supplied result at all) contradicts the record: an open control
    implies an unresolved concern. A control over a *diagnostic* gate, a finding,
    or an unknown reference is not a contradiction — it is simply not coverage.
    """

    for o in outcomes:
        if not o.active:
            continue
        ref = o.condition.source_gate_or_finding_ref
        if ref not in applicable_ids:
            continue
        result: Optional[GateResult] = results.get(ref)
        if result is None or result.status is GateStatus.PASS:
            return True
    return False


def _input_refs(case: ReadinessEvaluationCase) -> tuple[str, ...]:
    """Sorted, de-duplicated evidence/claim/window references seen on the input."""

    refs: set[str] = set(case.evidence_refs)
    if case.assessment_window_ref:
        refs.add(case.assessment_window_ref)
    for group in (case.intelligence_results, case.capability_results, case.adoption_results):
        for r in group:
            refs.update(r.evidence_refs)
    for g in case.gate_results:
        refs.update(g.evidence_refs)
        refs.update(g.observed_claim_refs)
        if g.window_ref:
            refs.add(g.window_ref)
    for c in case.conditions:
        refs.update(c.evidence_refs)
    return tuple(sorted(refs))
