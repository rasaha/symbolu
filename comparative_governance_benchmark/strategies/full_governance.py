"""Strategy D — Full Governance Architecture.

Reuses the validated Phase 5I pilot workflow unchanged (assertion → assessment →
recommendation → decision → ActionGate → constraint enforcement → execution →
obligation verification → reconciliation), then adapts the pilot's ``ScenarioRun``
into the neutral benchmark result. Reusing the pilot guarantees Strategy D
reproduces Phase 5I (invariant B4).

Imports the pilot (and therefore both providers) — permitted for the full strategy.
"""
from __future__ import annotations

from enterprise_validation_pilot.runners.workflow import run_scenario as pilot_run

from ..schemas.result import NOT_APPLICABLE, NOT_PERFORMED, StrategyResult
from .protocol import zero_cost

_ASSERT_SUPPORTED = {"SUPPORTED": "YES", "UNSUPPORTED": "NO",
                     "CONSTRAINED": "CONSTRAINED", "INDETERMINATE": "UNKNOWN"}
_AUTHORIZED = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}


class FullGovernanceStrategy:
    strategy_id = "full_governance"

    def run(self, scenario, *, registry_failure: bool = False) -> StrategyResult:
        run = pilot_run(scenario)
        cost = zero_cost()
        r = StrategyResult(scenario_id=scenario.scenario_id, strategy_id=self.strategy_id,
                           cost=cost)

        # assertion layer
        r.assertion_evaluated = True
        r.assertion_outcome = run.tap_outcome
        r.assertion_supported = _ASSERT_SUPPORTED.get(run.tap_outcome, "UNKNOWN")
        r.qualifiers_preserved = tuple(run.omitted_qualifiers)
        r.unsupported_components_preserved = tuple(run.unsupported_components)
        r.evidence_provenance_preserved = "YES"
        r.action_proposed = True
        r.recommendation_posture = run.recommendation_posture
        cost["assertion_evaluations"] = 1
        cost["provider_invocations"] = 1
        cost["assessment_records"] = 1
        cost["recommendation_records"] = 1
        cost["decision_records"] = 1
        if run.tap_failsafe:
            cost["failure_normalization_events"] += 1
        if run.human_review_applied:
            r.human_review_requested = True
            r.human_review_completed = True
            r.human_authority = run.human_authority
            cost["human_review_events"] += 1
            if run.human_review_applied == "supply_evidence":
                cost["assertion_evaluations"] += 1
                cost["provider_invocations"] += 1

        # registry resolution failure → action side fails safe (assertion side stands)
        if registry_failure:
            r.authorization_performed = True
            r.authorization_outcome = "INDETERMINATE"
            r.constraints_issued = NOT_APPLICABLE
            r.obligations_issued = NOT_APPLICABLE
            r.provider_failures = 1
            cost["failure_normalization_events"] += 1
            r.execution_outcome = NOT_PERFORMED
            r.reconciliation_outcome = "NONE"
            r.final_governance_compliance = NOT_APPLICABLE
            r.audit_events = len(run.audit_milestones)
            r.trace_links = 6
            r.lifecycle_records = 4
            r.trace = dict(run.trace, registry_failure=True, dispatched=False)
            return r

        # action layer
        if not run.proceeded_to_action:
            r.authorization_performed = False
            r.authorization_outcome = NOT_PERFORMED
            r.constraints_issued = NOT_APPLICABLE
            r.obligations_issued = NOT_APPLICABLE
            r.final_governance_compliance = NOT_APPLICABLE
        else:
            r.authorization_performed = True
            r.authorization_outcome = run.actiongate_outcome
            r.constraints_issued = tuple(run.constraints)
            r.constraints_enforced = ("ENFORCED" if run.enforcement_allowed is not None
                                      else NOT_APPLICABLE)
            r.obligations_issued = tuple(run.obligations)
            r.obligations_verified = "VERIFIED" if run.obligation_records else NOT_APPLICABLE
            r.action_failsafe = run.action_failsafe
            r.provider_failures += 1 if run.action_failsafe else 0
            cost["authorization_evaluations"] = 1
            cost["provider_invocations"] += 1
            cost["authorization_records"] = 1
            cost["constraint_checks"] = len(run.constraints)
            cost["obligation_checks"] = len(run.obligations)
            if run.action_failsafe:
                cost["failure_normalization_events"] += 1

        r.dispatch_attempted = run.enforcement_allowed is True
        r.dispatch_allowed = run.enforcement_allowed is True
        r.execution_attempted = run.dispatched
        r.dispatched = run.dispatched
        r.execution_outcome = run.business_outcome or (
            "SUCCEEDED" if run.execution_behavior == "DISPATCHED_SUCCESS" else NOT_PERFORMED)
        r.reconciliation_performed = run.dispatched
        r.reconciliation_outcome = run.reconciliation if run.dispatched else NOT_PERFORMED
        r.final_governance_compliance = run.compliance_verdict
        if run.dispatched:
            cost["execution_attempts"] = 1
            cost["reconciliation_attempts"] = 1

        r.audit_events = len(run.audit_milestones)
        cost["audit_events"] = r.audit_events
        r.trace_links = sum(1 for k in ("case_id", "assessment_id", "recommendation_id",
                                        "decision_id", "authorization_id", "reconciliation_id")
                            if run.trace.get(k))
        cost["trace_links"] = r.trace_links
        r.lifecycle_records = 3 + (2 if run.proceeded_to_action else 0)
        r.trace = dict(run.trace)
        return r
