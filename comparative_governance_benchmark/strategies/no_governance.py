"""Strategy A — No Governance.

Recommendation → proposed action → execution → basic outcome recording. No TAP,
no ActionGate, no governance constraints/obligations, no DGM authorization
lifecycle. Retains ordinary technical validation only.

Imports **neither** tap_provider nor actiongate_provider (enforced by test).
"""
from __future__ import annotations

from ..runners.determinism import make_id_factory
from ..runners.execution import build_execution_adapter, direct_dispatch
from ..runners.common import technical_valid
from ..schemas.result import NOT_APPLICABLE, NOT_PERFORMED, StrategyResult
from .protocol import zero_cost


class NoGovernanceStrategy:
    strategy_id = "no_governance"

    def run(self, scenario, *, registry_failure: bool = False) -> StrategyResult:
        cost = zero_cost()
        r = StrategyResult(scenario_id=scenario.scenario_id, strategy_id=self.strategy_id,
                           cost=cost)
        # assertions are accepted by the application without evaluation
        r.assertion_evaluated = False
        r.assertion_outcome = NOT_PERFORMED
        r.assertion_supported = "UNKNOWN"
        r.evidence_provenance_preserved = NOT_PERFORMED
        r.action_proposed = True

        # no governance information; only ordinary technical validity gates dispatch
        if not technical_valid(scenario):
            r.execution_outcome = "TECHNICAL_INVALID"
            r.final_governance_compliance = NOT_APPLICABLE
            return r

        pa = scenario.proposed_action
        adapter = build_execution_adapter(
            pa.action_type, scenario.execution,
            id_factory=make_id_factory(scenario.scenario_id + ":exec"))
        r.dispatch_attempted = True
        r.dispatch_allowed = True
        cost["execution_attempts"] += 1
        de = direct_dispatch(adapter, pa.action_type,
                             {k: str(v) for k, v in pa.parameters.items()})
        r.execution_attempted = True
        r.dispatched = de.dispatched
        r.execution_outcome = de.business_outcome
        # basic outcome recording only — no governance reconciliation
        r.reconciliation_performed = False
        r.reconciliation_outcome = NOT_PERFORMED
        r.authorization_outcome = NOT_PERFORMED
        r.constraints_issued = NOT_APPLICABLE
        r.constraints_enforced = NOT_APPLICABLE
        r.obligations_issued = NOT_APPLICABLE
        r.obligations_verified = NOT_APPLICABLE
        r.final_governance_compliance = NOT_APPLICABLE
        r.audit_events = 0
        r.trace_links = 0
        r.lifecycle_records = 0
        r.trace = {"scenario_id": scenario.scenario_id, "strategy": self.strategy_id,
                   "action": pa.action_type, "execution_outcome": r.execution_outcome}
        return r
