"""The deterministic GV-3R-b Agent Value Readiness evaluator.

``evaluate_readiness`` consumes a :class:`ReadinessEvaluationCase` (which carries
the complete ``ReadinessPolicy`` body and the structurally supplied indicator /
gate / condition results) and **selects** one advisory
:class:`ReadinessClassification`. It is:

* **deterministic** — identical inputs + identical ``evaluation_time`` produce an
  identical classification, ordered reason codes, gate sets, and digest; outputs
  are canonically ordered by stable identifier and never depend on input order;
* **non-financial** — no money, ROI, or forecast; it never consults an
  :class:`AdvisoryComposite` when selecting the tier;
* **non-authoritative** — it consumes ``GateResult.status`` as *structurally
  supplied, authority-unverified* input. It performs **no** evidence admission /
  verification, benchmark resolution, metric-to-threshold calculation,
  policy-authenticity check, or causal attribution, and it **never** upgrades a
  MetricClaim's evidence axes. It is a *determination evaluator over structurally
  supplied gate results*, not a metric-evaluation engine, and it authorizes no
  deployment.

Decision ordering (fail-closed): a definite applicable **mandatory FAIL**
dominates (⇒ ``NOT_READY``) even when another required gate result is missing —
the outcome cannot become ready by supplying the missing gate. Otherwise a
missing applicable required (MANDATORY or CONDITIONAL) gate result ⇒
``NOT_ASSESSABLE`` (never a silent PASS); then an applicable mandatory
**INDETERMINATE** ⇒ ``NOT_ASSESSABLE``; then conditional resolution selects the
ready tier.
"""

from __future__ import annotations

from datetime import datetime

from ugence_uvi_policy_contracts.api import RequirementClass, ReadinessTarget

from ..contracts.determination import AgentValueReadinessDetermination
from ..contracts.enums import ConditionStatus, GateStatus, ReadinessClassification
from ..contracts.evaluation import (
    EvaluationTrace,
    ReadinessEvaluationCase,
    ReadinessEvaluationError,
    ReadinessEvaluationResult,
    ReadinessReasonCode as RC,
    ReadinessRule,
)

__all__ = ["evaluate_readiness", "EVALUATOR_VERSION"]

EVALUATOR_VERSION = "gv3r-b-1.0.0"

_ADVISORY_ALWAYS = (
    RC.ADVISORY_POLICY_AUTHENTICITY_NOT_VERIFIED,
    RC.ADVISORY_EVIDENCE_RETAINS_SOURCE_CLASSIFICATION,
    RC.ADVISORY_NOT_DEPLOYMENT_AUTHORIZATION,
)


def evaluate_readiness(
    case: ReadinessEvaluationCase,
    *,
    evaluation_time: datetime,
) -> ReadinessEvaluationResult:
    """Select one advisory readiness classification for ``case`` at
    ``evaluation_time`` (mandatory, timezone-aware; the system clock is never
    read). Returns the chosen :class:`AgentValueReadinessDetermination` plus a
    deterministic :class:`EvaluationTrace`.
    """

    if not isinstance(case, ReadinessEvaluationCase):
        raise ReadinessEvaluationError("evaluate_readiness expects a ReadinessEvaluationCase")
    if not isinstance(evaluation_time, datetime):
        raise ReadinessEvaluationError("evaluate_readiness.evaluation_time must be a datetime")
    if evaluation_time.tzinfo is None or evaluation_time.tzinfo.utcoffset(evaluation_time) is None:
        raise ReadinessEvaluationError("evaluate_readiness.evaluation_time must be timezone-aware (the system clock is never read)")

    target = case.requested_target
    policy_gates = {g.gate_id: g for g in case.readiness_policy.gates}
    applicable_gate_ids = tuple(sorted(gid for gid, g in policy_gates.items() if target in g.applicability))
    results_by_id = {gr.gate_id: gr for gr in case.gate_results}
    diagnostic_gate_ids = tuple(sorted(gr.gate_id for gr in case.gate_results if gr.is_diagnostic))

    applicable_mandatory_ids = [gid for gid in applicable_gate_ids if policy_gates[gid].requirement_class is RequirementClass.MANDATORY]
    applicable_conditional_ids = [gid for gid in applicable_gate_ids if policy_gates[gid].requirement_class is RequirementClass.CONDITIONAL]

    # Facts derived ONLY from supplied results (never assumed PASS).
    mand_fail_ids = tuple(sorted(gid for gid in applicable_mandatory_ids
                                 if gid in results_by_id and results_by_id[gid].is_blocking))
    mand_indet_ids = tuple(sorted(gid for gid in applicable_mandatory_ids
                                  if gid in results_by_id and results_by_id[gid].is_applicable_mandatory_indeterminate))
    missing_mandatory = [gid for gid in applicable_mandatory_ids if gid not in results_by_id]
    missing_conditional = [gid for gid in applicable_conditional_ids if gid not in results_by_id]

    reasons: list = []
    gaps: list = []
    rejected_condition_reasons: list[str] = []
    accepted_condition_ids: tuple[str, ...] = ()
    unresolved_conditional_ids: tuple[str, ...] = ()

    # ---- 1. definite mandatory FAIL dominates (fail-closed) --------------
    if mand_fail_ids:
        classification = ReadinessClassification.NOT_READY
        rule = ReadinessRule.NOT_READY_MANDATORY_FAIL
        reasons.append(RC.MANDATORY_GATE_FAIL)
        det_conditions = ()

    # ---- 2. completeness: missing applicable required gate --------------
    elif missing_mandatory or missing_conditional:
        classification = ReadinessClassification.NOT_ASSESSABLE
        rule = ReadinessRule.NOT_ASSESSABLE_INCOMPLETE
        if missing_mandatory:
            gaps.append(RC.MISSING_APPLICABLE_MANDATORY_GATE)
        if missing_conditional:
            gaps.append(RC.MISSING_APPLICABLE_CONDITIONAL_GATE)
        reasons.extend(gaps)
        det_conditions = ()

    # ---- 3. mandatory INDETERMINATE (no FAIL) ---------------------------
    elif mand_indet_ids:
        classification = ReadinessClassification.NOT_ASSESSABLE
        rule = ReadinessRule.NOT_ASSESSABLE_MANDATORY_INDETERMINATE
        gaps.append(RC.MANDATORY_GATE_INDETERMINATE)
        reasons.append(RC.MANDATORY_GATE_INDETERMINATE)
        det_conditions = ()

    # ---- 4. all mandatory PASS -> conditional resolution ----------------
    else:
        reasons.append(RC.ALL_MANDATORY_PASS)
        unresolved = [results_by_id[gid] for gid in applicable_conditional_ids
                      if results_by_id[gid].is_applicable_conditional_unresolved]
        unresolved_conditional_ids = tuple(sorted(gr.gate_id for gr in unresolved))

        noncompensable = [gr for gr in unresolved if not gr.policy_gate.conditionally_compensable]
        accepted: dict[str, list[str]] = {}
        uncovered: list[str] = []

        if noncompensable:
            classification = ReadinessClassification.NOT_READY
            rule = ReadinessRule.NOT_READY_CONDITIONAL_NONCOMPENSABLE
            reasons.append(RC.CONDITIONAL_CONCERN_NONCOMPENSABLE)
            det_conditions = ()
        else:
            # find an active covering condition for each unresolved (compensable) concern
            for gr in unresolved:
                covering = [c for c in case.conditions
                            if c.source_gate_or_finding_ref == gr.gate_id and c.is_active_at(evaluation_time)]
                if covering:
                    accepted[gr.gate_id] = sorted(c.condition_id for c in covering)
                else:
                    uncovered.append(gr.gate_id)
            # record rejected/non-covering conditions deterministically
            for c in case.conditions:
                src = c.source_gate_or_finding_ref
                if src in unresolved_conditional_ids:
                    if not c.is_active_at(evaluation_time):
                        rejected_condition_reasons.append(f"{c.condition_id}: {RC.CONDITION_INACTIVE_AT_EVALUATION.value}")
                else:
                    rejected_condition_reasons.append(f"{c.condition_id}: {RC.CONDITION_DOES_NOT_COVER_CONCERN.value}")

            if uncovered:
                classification = ReadinessClassification.NOT_READY
                rule = ReadinessRule.NOT_READY_CONDITIONAL_UNCOVERED
                reasons.append(RC.CONDITIONAL_CONCERN_UNCOVERED)
                det_conditions = ()
            else:
                # every unresolved conditional concern is compensable + covered
                accepted_condition_ids = tuple(sorted({cid for cids in accepted.values() for cid in cids}))
                active_covering = tuple(sorted(
                    (c for c in case.conditions
                     if c.source_gate_or_finding_ref in unresolved_conditional_ids and c.is_active_at(evaluation_time)),
                    key=lambda c: c.condition_id))
                if unresolved_conditional_ids:
                    reasons.append(RC.CONDITIONAL_CONCERN_COMPENSATED)
                else:
                    reasons.append(RC.NO_UNRESOLVED_CONCERNS)

                if target is ReadinessTarget.PILOT:
                    classification = ReadinessClassification.PILOT_READY
                    rule = ReadinessRule.PILOT_READY
                    det_conditions = active_covering  # bounded pilot controls
                elif unresolved_conditional_ids:
                    classification = ReadinessClassification.READY_WITH_CONDITIONS
                    rule = ReadinessRule.READY_WITH_CONDITIONS
                    det_conditions = active_covering
                else:
                    classification = ReadinessClassification.DEPLOYMENT_READY
                    rule = ReadinessRule.DEPLOYMENT_READY
                    # retain only historical SATISFIED conditions whose gate now PASSES
                    det_conditions = tuple(sorted(
                        (c for c in case.conditions
                         if c.current_status is ConditionStatus.SATISFIED
                         and results_by_id.get(c.source_gate_or_finding_ref) is not None
                         and results_by_id[c.source_gate_or_finding_ref].status is GateStatus.PASS),
                        key=lambda c: c.condition_id))

    # ---- advisories (trust boundary) ------------------------------------
    reasons.extend(_ADVISORY_ALWAYS)
    if det_conditions:
        reasons.append(RC.ADVISORY_CONDITION_APPROVAL_NOT_VERIFIED)

    reason_codes = _canonical_reasons(reasons)
    det_reason_strings = tuple(rc.value for rc in reason_codes)

    determination = AgentValueReadinessDetermination(
        assessment_id=case.case_id,
        tenant_id=case.tenant_id,
        subject_id=case.subject_id,
        context=case.context,
        readiness_policy_ref=case.readiness_policy_ref,
        requested_target=target,
        classification=classification,
        created_at=evaluation_time,
        intelligence_results=case.intelligence_results,
        capability_results=case.capability_results,
        adoption_results=case.adoption_results,
        gate_results=case.gate_results,
        conditions=det_conditions,
        advisory_composite=case.advisory_composite,  # carried through, never consulted
        reason_codes=det_reason_strings,
    )

    trace = EvaluationTrace(
        evaluator_version=EVALUATOR_VERSION,
        selected_rule=rule,
        requested_target=target,
        applicable_gate_ids=applicable_gate_ids,
        diagnostic_gate_ids=diagnostic_gate_ids,
        mandatory_fail_gate_ids=mand_fail_ids,
        mandatory_indeterminate_gate_ids=mand_indet_ids,
        unresolved_conditional_gate_ids=unresolved_conditional_ids,
        accepted_condition_ids=accepted_condition_ids,
        rejected_condition_reasons=tuple(sorted(rejected_condition_reasons)),
        assessability_gap_codes=_canonical_reasons(gaps),
        reason_codes=reason_codes,
        input_digest=case.canonical_digest(),
    )

    return ReadinessEvaluationResult(determination=determination, trace=trace)


def _canonical_reasons(reasons) -> tuple:
    """Deduplicate + canonically order reason codes by their string value."""

    seen = {}
    for rc in reasons:
        seen[rc.value] = rc
    return tuple(seen[v] for v in sorted(seen))
