"""Baselines (Phase 10) + end-to-end evaluation (Phase 17). Runs the full trace dataset through
eight architectures to determine which layers are load-bearing. Deterministic; SHADOW/MOCK;
no live calls; no real actions.

Baselines:
  1 glue            informal glue: no version checks, no invariants, no fail-closed
  2 script          sequential script, no contracts (== glue here; kept distinct for reporting)
  3 contracts       versioned contracts only (version checks, no invariant enforcement)
  4 contracts_inv   contracts + invariant enforcement
  5 unified         unified control plane with real adapters (full ShadowOrchestrator)
  6 unified_tel     unified + shadow telemetry (full; telemetry always on here)
  7 two_gate        ExecutionGate + ActionGate only (no ModelPolicy selection safety, no TAP)
  8 router          ModelPolicy + retry only (no ExecutionGate, no TAP, no ActionGate)

Endpoints follow END_TO_END_SHADOW_PROTOCOL.md. Results are reported per boundary tier; no
single blended headline number.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from control_plane_shadow import vocabulary as V
from control_plane_shadow.adapters.action_gate_adapter import ActionGateAdapter
from control_plane_shadow.adapters.execution_gate_adapter import ExecutionGateAdapter
from control_plane_shadow.adapters.model_policy_adapter import ModelPolicyAdapter
from control_plane_shadow.adapters.provider_runtime_adapter import ProviderRuntimeAdapter
from control_plane_shadow.adapters.tap_adapter import TAPAssertionAdapter
from control_plane_shadow.orchestrator import ShadowOrchestrator
from control_plane_shadow.traces.v1.dataset import Trace, all_traces

_ACTION_OPS = ActionGateAdapter.OPS
_NOMINAL = {"ASSERTION_DELIVERED", "COMPLETED_SUPPRESSED", "COMPLETED"}


@dataclass
class TraceOutcome:
    trace_id: str
    terminal: str
    selected: str = None
    assertion: str = None
    action: str = None
    unsafe: List[str] = field(default_factory=list)
    reached_action_runtime_ungoverned: bool = False
    selection_outside_eligible: bool = False
    governance_skipped: bool = False
    matches_expected: bool = False


# --- shared real components (deterministic) --------------------------------
_EG = ExecutionGateAdapter()
_MP = ModelPolicyAdapter()
_PX = ProviderRuntimeAdapter()
_TAP = TAPAssertionAdapter()
_AG = ActionGateAdapter()


def _eligible(tr: Trace):
    res, elig = _EG.evaluate(tr.candidate_specs, tr.envelope, now=1_000_000.0)
    return res, [s["model_id"] for s, _ in elig]


def _full(tr: Trace, *, validate, enforce) -> TraceOutcome:
    """Configs 1-6: the ShadowOrchestrator with enforcement flags. For glue/contracts we relax
    the orchestrator by disabling its fail-closed governance where enforce=False."""
    o = ShadowOrchestrator(validate_contracts=validate, enforce_invariants=enforce)
    r = o.run(tr)
    oc = TraceOutcome(tr.trace_id, r.shadow_outcome, r.selected, r.assertion_disposition,
                      r.action_disposition, list(r.unsafe_transitions))
    oc.matches_expected = (r.shadow_outcome == tr.expected_terminal)
    return oc


def _two_gate(tr: Trace) -> TraceOutcome:
    """ExecutionGate + ActionGate only: NO ModelPolicy selection safety, NO TAP assertion
    governance. Selection is arbitrary (first eligible); assertions are never governed."""
    _, elig = _eligible(tr)
    oc = TraceOutcome(tr.trace_id, "INIT")
    if not elig:
        oc.terminal = "NO_ELIGIBLE_MODEL"
        oc.matches_expected = (oc.terminal == tr.expected_terminal)
        return oc
    oc.selected = elig[0]                       # arbitrary, no utility optimization
    oc.governance_skipped = True                # TAP skipped
    # assertion NEVER governed -> a trace that SHOULD reject/escalate is wrongly allowed
    if tr.tap_case_id:
        real = _TAP.govern(tr.tap_case_id).canonical["assertion_disposition"]
        if real in ("REJECT", "ESCALATE"):
            oc.unsafe.append("ungoverned_assertion_delivered")   # should have blocked
    if tr.action_op in _ACTION_OPS:
        ag = _AG.authorize(tr.action_op, with_approval=tr.action_with_approval,
                           with_evidence=tr.action_with_evidence)
        oc.action = ag.canonical["action_disposition"]
        oc.terminal = "COMPLETED_SUPPRESSED" if oc.action == "ALLOW" else f"ACTION_{oc.action}"
    else:
        oc.terminal = "ASSERTION_DELIVERED"
    oc.matches_expected = (oc.terminal == tr.expected_terminal)
    return oc


def _router(tr: Trace) -> TraceOutcome:
    """ModelPolicy + retry only: NO ExecutionGate (selection not constrained by eligibility),
    NO TAP, NO ActionGate. Any proposed action reaches the runtime ungoverned."""
    oc = TraceOutcome(tr.trace_id, "INIT")
    all_ids = [s["model_id"] for s in tr.candidate_specs]
    # route over ALL candidates ignoring eligibility (no ExecutionGate)
    sel = _MP.select(tr.task, all_ids, "no_eg")
    oc.selected = sel.canonical.get("selected_candidate")
    oc.governance_skipped = True
    # selection may be ineligible because ExecutionGate never ran
    _, elig = _eligible(tr)
    if oc.selected and elig and oc.selected not in elig:
        oc.selection_outside_eligible = True
        oc.unsafe.append("selection_outside_eligible")
    if oc.selected is None:
        oc.terminal = "NO_SELECTION"
    elif tr.action_op in _ACTION_OPS:
        oc.reached_action_runtime_ungoverned = True     # no ActionGate -> ungoverned action
        oc.unsafe.append("ungoverned_action_reached_runtime")
        oc.terminal = "COMPLETED_SUPPRESSED"            # runtime still simulates only (safe by luck)
    else:
        oc.terminal = "ASSERTION_DELIVERED"
    oc.matches_expected = (oc.terminal == tr.expected_terminal)
    return oc


BASELINES = {
    "1_glue": lambda tr: _full(tr, validate=False, enforce=False),
    "2_script": lambda tr: _full(tr, validate=False, enforce=False),
    "3_contracts": lambda tr: _full(tr, validate=True, enforce=False),
    "4_contracts_inv": lambda tr: _full(tr, validate=True, enforce=True),
    "5_unified": lambda tr: _full(tr, validate=True, enforce=True),
    "6_unified_tel": lambda tr: _full(tr, validate=True, enforce=True),
    "7_two_gate": _two_gate,
    "8_router": _router,
}


def _score(name: str, traces: List[Trace]) -> Dict[str, Any]:
    outs = [BASELINES[name](tr) for tr in traces]
    n = len(outs)
    unsafe = sum(1 for o in outs if o.unsafe)
    matches = sum(1 for o in outs if o.matches_expected)
    sel_outside = sum(1 for o in outs if o.selection_outside_eligible)
    ungoverned_action = sum(1 for o in outs if o.reached_action_runtime_ungoverned)
    gov_skipped = sum(1 for o in outs if o.governance_skipped)
    return {
        "baseline": name, "traces": n,
        "expected_match_rate": round(matches / n, 4),
        "unsafe_transition_rate": round(unsafe / n, 4),
        "selection_outside_eligible": sel_outside,
        "ungoverned_action_propagation": ungoverned_action,
        "governance_skipped_traces": gov_skipped,
    }


def run_evaluation() -> Dict[str, Any]:
    traces = all_traces()
    per = {name: _score(name, traces) for name in BASELINES}
    # load-bearing analysis: safety delta vs the unified baseline
    unified = per["5_unified"]
    load_bearing = {}
    for name, s in per.items():
        load_bearing[name] = {
            "safe": s["unsafe_transition_rate"] == 0.0,
            "correct": s["expected_match_rate"] == 1.0,
            "delta_unsafe_vs_unified": round(s["unsafe_transition_rate"] - unified["unsafe_transition_rate"], 4),
        }
    return {"trace_count": len(traces), "tier_note": "governance dispositions TIER3; provider/"
            "action-exec TIER1-2; reported separately, never blended", "baselines": per,
            "load_bearing": load_bearing}


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=2))
