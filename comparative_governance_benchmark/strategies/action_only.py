"""Strategy B — Action Governance Only.

Application-accepted assertion → recommendation → decision → ActionGate →
constraint enforcement → execution → reconciliation. Assertions are NOT
independently checked against evidence (no TAP); ActionGate governs the proposed
action, enforcing constraints and obligations and refusing to dispatch
denied/indeterminate actions.

Imports actiongate_provider but **never** tap_provider (enforced by test).
"""
from __future__ import annotations

import hashlib

from governance_providers.api import ProviderResolutionError

from ..runners.common import run_action_flow, run_case_flow
from ..runners.dgm import build_services
from ..runners.execution import build_execution_adapter
from ..runners.determinism import make_id_factory
from ..schemas.result import NOT_APPLICABLE, NOT_PERFORMED, StrategyResult
from ._actiongate_support import resolve_actiongate
from .protocol import zero_cost


class ActionOnlyStrategy:
    strategy_id = "action_only"

    def run(self, scenario, *, registry_failure: bool = False) -> StrategyResult:
        cost = zero_cost()
        r = StrategyResult(scenario_id=scenario.scenario_id, strategy_id=self.strategy_id,
                           cost=cost)
        pa = scenario.proposed_action

        # assertion accepted by the application without evaluation
        r.assertion_evaluated = False
        r.assertion_outcome = NOT_PERFORMED
        r.assertion_supported = "UNKNOWN"
        r.qualifiers_preserved = NOT_PERFORMED
        r.unsupported_components_preserved = NOT_PERFORMED
        r.evidence_provenance_preserved = NOT_PERFORMED
        r.action_proposed = True
        r.recommendation_posture = "ADVANCE"          # trusted; app proceeds to the action

        # execution adapter shared with all strategies (fairness B12)
        adapter = build_execution_adapter(
            pa.action_type, scenario.execution,
            id_factory=make_id_factory(scenario.scenario_id + ":execB"))

        seed = scenario.scenario_id + ":B"
        try:
            control_plane, _rec = resolve_actiongate(pa.action_type, scenario.action_policy,
                                                     seed=seed, register=not registry_failure)
        except ProviderResolutionError:
            # registry failure → no authorization, fail-safe: nothing dispatches
            r.authorization_performed = True
            r.authorization_outcome = "INDETERMINATE"
            r.provider_failures = 1
            cost["failure_normalization_events"] += 1
            r.execution_outcome = NOT_PERFORMED
            r.reconciliation_outcome = "NONE"
            r.final_governance_compliance = NOT_APPLICABLE
            r.trace = {"scenario_id": scenario.scenario_id, "strategy": self.strategy_id,
                       "authorization_outcome": "INDETERMINATE", "dispatched": False}
            return r

        dgm = build_services(seed, control_plane=control_plane, execution_adapter=adapter)
        assessment_id = "app-" + hashlib.sha256(scenario.assertion.encode()).hexdigest()[:12]
        flow = run_case_flow(dgm, scenario, coverage="SUPPORTED", assessment_id=assessment_id)
        cost["assessment_records"] += 1
        cost["recommendation_records"] += 1
        cost["decision_records"] += 1

        approval, waived, requested = _human(scenario)
        r.human_review_requested = requested
        r.human_review_completed = requested and approval is not None
        if requested:
            cost["human_review_events"] += 1
            r.human_authority = scenario.human_review.approver if scenario.human_review else ""

        action = run_action_flow(dgm, scenario, flow.decision_id, approval=approval, waived=waived)
        cost["authorization_evaluations"] += 1
        cost["provider_invocations"] += 1
        cost["authorization_records"] += 1
        cost["constraint_checks"] += len(action.constraints)
        cost["obligation_checks"] += len(action.obligations)
        if action.action_failsafe:
            r.provider_failures = 1
            cost["failure_normalization_events"] += 1

        r.authorization_performed = True
        r.authorization_outcome = action.authorization_outcome
        r.constraints_issued = tuple(action.constraints)
        r.constraints_enforced = ("ENFORCED" if action.enforcement_allowed is not None
                                  else NOT_APPLICABLE)
        r.obligations_issued = tuple(action.obligations)
        r.obligations_verified = "VERIFIED" if action.obligation_records else NOT_APPLICABLE
        r.dispatch_attempted = action.enforcement_allowed is True
        r.dispatch_allowed = action.enforcement_allowed is True
        r.execution_attempted = action.dispatched
        r.dispatched = action.dispatched
        r.execution_outcome = action.execution_outcome
        r.reconciliation_performed = action.dispatched
        r.reconciliation_outcome = action.reconciliation
        r.final_governance_compliance = action.compliance
        if action.dispatched:
            cost["execution_attempts"] += 1
            cost["reconciliation_attempts"] += 1

        r.audit_events = len(dgm.audit_events())
        cost["audit_events"] = r.audit_events
        r.trace_links = 6
        cost["trace_links"] = r.trace_links
        r.lifecycle_records = 5
        r.trace = {"scenario_id": scenario.scenario_id, "strategy": self.strategy_id,
                   "case_id": flow.case_id, "decision_id": flow.decision_id,
                   "authorization_id": action.authorization_id,
                   "authorization_outcome": action.authorization_outcome,
                   "dispatched": action.dispatched, "reconciliation": action.reconciliation}
        return r


def _human(scenario):
    """Return (approval, waived, requested) for the action-governance human path."""
    hr = scenario.human_review
    if hr and hr.action == "approve_action":
        return True, False, True
    if hr and hr.action == "decline_action":
        return False, False, True
    return None, False, False
