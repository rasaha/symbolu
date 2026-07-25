"""Strategy C — Assertion Governance Only.

Evidence → TAP → assessment → recommendation → decision → action → execution.
TAP gates the assertion (unsupported/indeterminate affect posture and halt the
action); there is NO ActionGate authorization, no action-governance constraints
or obligations. Actions execute directly if the assertion proceeds and the action
is technically valid.

Imports tap_provider but **never** actiongate_provider (enforced by test).
"""
from __future__ import annotations

from governance_providers.api import (
    AssertionAssessmentIntegration, AssertionGovernanceRequest)

from ..runners.common import run_case_flow, technical_valid
from ..runners.determinism import make_id_factory
from ..runners.execution import build_execution_adapter, direct_dispatch
from ..runners.dgm import build_services
from ..schemas.result import NOT_APPLICABLE, NOT_PERFORMED, StrategyResult
from ._tap_support import resolve_tap
from .protocol import zero_cost

_SUPPORTED = {"YES": "SUPPORTED", "NO": "UNSUPPORTED"}
_ASSERT_SUPPORTED = {"SUPPORTED": "YES", "UNSUPPORTED": "NO",
                     "CONSTRAINED": "CONSTRAINED", "INDETERMINATE": "UNKNOWN"}


class AssertionOnlyStrategy:
    strategy_id = "assertion_only"

    def run(self, scenario, *, registry_failure: bool = False) -> StrategyResult:
        cost = zero_cost()
        r = StrategyResult(scenario_id=scenario.scenario_id, strategy_id=self.strategy_id,
                           cost=cost)
        refs = tuple(e.evidence_id for e in scenario.evidence)

        provider, _rec = resolve_tap(scenario.assertion, scenario.tap_policy)
        req = AssertionGovernanceRequest(
            assertion=scenario.assertion, assertion_type=scenario.assertion_type,
            evidence_refs=refs, correlation_id=scenario.scenario_id)
        result = provider.evaluate(req)
        assessment = AssertionAssessmentIntegration(provider).assess(req)
        cost["assertion_evaluations"] += 1
        cost["provider_invocations"] += 1
        cost["assessment_records"] += 1
        if _is_failsafe(result):
            cost["failure_normalization_events"] += 1

        # human review: supply evidence for INDETERMINATE, re-evaluate
        if (result.coverage.value == "INDETERMINATE" and scenario.human_review
                and scenario.human_review.action == "supply_evidence"
                and scenario.human_review.reevaluate_tap is not None):
            r.human_review_requested = True
            r.human_review_completed = True
            r.human_authority = scenario.human_review.approver
            cost["human_review_events"] += 1
            provider2, _ = resolve_tap(scenario.assertion, scenario.human_review.reevaluate_tap)
            req2 = AssertionGovernanceRequest(
                assertion=scenario.assertion, assertion_type=scenario.assertion_type,
                evidence_refs=refs + tuple(e.evidence_id for e in scenario.human_review.added_evidence),
                correlation_id=scenario.scenario_id)
            result = provider2.evaluate(req2)
            assessment = AssertionAssessmentIntegration(provider2).assess(req2)
            cost["assertion_evaluations"] += 1
            cost["provider_invocations"] += 1

        r.assertion_evaluated = True
        r.assertion_outcome = result.coverage.value
        r.assertion_supported = _ASSERT_SUPPORTED[result.coverage.value]
        r.qualifiers_preserved = tuple(result.omitted_qualifiers)
        r.unsupported_components_preserved = tuple(result.unsupported_elements)
        r.evidence_provenance_preserved = "YES"
        r.action_proposed = True

        assessment_id = "tap-" + assessment.fingerprint[:12]
        dgm = build_services(scenario.scenario_id + ":C")
        flow = run_case_flow(dgm, scenario, coverage=result.coverage.value,
                             assessment_id=assessment_id)
        cost["recommendation_records"] += 1
        cost["decision_records"] += 1
        r.recommendation_posture = _posture(result.coverage.value)
        r.trace = {"scenario_id": scenario.scenario_id, "strategy": self.strategy_id,
                   "case_id": flow.case_id, "assessment_id": assessment_id,
                   "recommendation_id": flow.recommendation_id, "decision_id": flow.decision_id,
                   "tap_outcome": result.coverage.value, "proceeded": flow.proceeded}
        r.audit_events = len(dgm.audit_events())
        cost["audit_events"] = r.audit_events
        r.trace_links = 4
        cost["trace_links"] = r.trace_links
        r.lifecycle_records = 3

        # no action governance: authorization is simply not performed
        r.authorization_performed = False
        r.authorization_outcome = NOT_PERFORMED
        r.constraints_issued = NOT_APPLICABLE
        r.constraints_enforced = NOT_APPLICABLE
        r.obligations_issued = NOT_APPLICABLE
        r.obligations_verified = NOT_APPLICABLE

        if not flow.proceeded:
            r.execution_outcome = NOT_PERFORMED
            r.reconciliation_outcome = NOT_PERFORMED
            r.final_governance_compliance = NOT_APPLICABLE
            return r

        if not technical_valid(scenario):
            r.execution_outcome = "TECHNICAL_INVALID"
            r.final_governance_compliance = NOT_APPLICABLE
            return r

        pa = scenario.proposed_action
        adapter = build_execution_adapter(
            pa.action_type, scenario.execution,
            id_factory=make_id_factory(scenario.scenario_id + ":execC"))
        r.dispatch_attempted = True
        r.dispatch_allowed = True
        cost["execution_attempts"] += 1
        de = direct_dispatch(adapter, pa.action_type,
                             {k: str(v) for k, v in pa.parameters.items()})
        r.execution_attempted = True
        r.dispatched = de.dispatched
        r.execution_outcome = de.business_outcome
        r.reconciliation_performed = False           # no action-governance reconciliation
        r.reconciliation_outcome = NOT_PERFORMED
        r.final_governance_compliance = NOT_APPLICABLE
        r.trace["execution_outcome"] = r.execution_outcome
        return r


def _posture(coverage: str) -> str:
    return {"SUPPORTED": "ADVANCE", "CONSTRAINED": "HOLD",
            "UNSUPPORTED": "REJECT", "INDETERMINATE": "REQUEST_ADDITIONAL_EVIDENCE"}[coverage]


def _is_failsafe(result) -> bool:
    return (result.coverage.value == "INDETERMINATE"
            and any(x.startswith("reason:provider_error") for x in result.explanation_refs))
