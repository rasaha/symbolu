"""End-to-end mock evaluation (Phase 15). Runs the full scenario suite under three
configurations and computes architectural integration metrics. Deterministic; MOCK mode;
no live calls. This is an ARCHITECTURAL integration evaluation, not production validation.

Configs:
  1. glue     — disconnected components, informal glue (no contract checks, no invariants)
  2. orch     — orchestrator, contracts validated, invariants NOT enforced
  3. unified  — orchestrator + contracts + invariants enforced

Metrics are counts/rates over the scenario set. "invalid_transition" = a violation that was
detected but ALLOWED to proceed (enforcement off). Complexity is reported as component-call
and audit-record counts (deterministic proxies), NOT wall-clock production latency.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from control_plane.envelope import RequestEnvelope
from control_plane.orchestrator import Orchestrator, Scenario
from control_plane.replay import replay
from control_plane.scenarios import all_cases, Case

_NOMINAL = {"COMPLETED", "ASSERTION_DELIVERED"}
CONFIGS = {
    "glue":    dict(validate_contracts=False, enforce_invariants=False),
    "orch":    dict(validate_contracts=True,  enforce_invariants=False),
    "unified": dict(validate_contracts=True,  enforce_invariants=True),
}


@dataclass
class ConfigMetrics:
    config: str
    scenarios: int = 0
    invalid_transition_rate: float = 0.0     # violations allowed to proceed / scenarios
    upstream_exclusion_bypass: int = 0
    policy_conflict: int = 0
    audit_completeness: float = 0.0          # traces with intact chain / scenarios
    trace_completeness: float = 0.0
    reason_code_completeness: float = 0.0    # non-nominal terminals carrying >=1 namespaced code
    assertion_action_conflation: int = 0     # action executed despite rejected/failed assertion
    fallback_correct: int = 0                # fallback switched candidate (not in-place retry)
    fallback_total: int = 0
    unauthorized_execution: int = 0          # action executed without proper authorization
    false_blocking: int = 0                  # nominal-in-glue blocked spuriously here
    total_component_calls: int = 0
    total_records: int = 0
    replay_success: float = 0.0
    violations_detected: int = 0
    violations_blocked: int = 0


def _run_config(name: str, cases: List[Case]) -> ConfigMetrics:
    m = ConfigMetrics(config=name)
    glue_nominal = _nominal_set(cases) if name != "glue" else None
    replay_ok = 0
    for case in cases:
        o = Orchestrator(**CONFIGS[name])
        r = o.run(_fresh(case.scenario))
        m.scenarios += 1
        m.total_component_calls += r.component_calls
        m.total_records += r.records
        m.violations_detected += len(r.violations)
        m.violations_blocked += len(r.blocked)
        allowed = [v for v in r.violations if v not in r.blocked]
        if allowed:
            m.invalid_transition_rate += 1
        m.upstream_exclusion_bypass += sum(1 for v in allowed if "UPSTREAM_EXCLUSION_BYPASSED" in v)
        m.policy_conflict += sum(1 for v in r.violations if "POLICY_CONFLICT" in v)
        if r.audit_ok:
            m.audit_completeness += 1
        if r.trace_complete:
            m.trace_completeness += 1
        if r.terminal_state not in _NOMINAL:
            if r.terminal_reasons and all("." in rc for rc in r.terminal_reasons):
                m.reason_code_completeness += 1
        else:
            m.reason_code_completeness += 1  # nominal needs no failure code
        # assertion/action conflation: action executed while assertion path was terminal
        if r.executed_action and r.terminal_state in ("ASSERTION_REJECTED", "PROVIDER_FAILED"):
            m.assertion_action_conflation += 1
        # unauthorized execution: real action executed (never in MOCK) w/o authorization
        if r.executed_action and r.terminal_state not in _NOMINAL:
            m.unauthorized_execution += 1
        # fallback correctness
        if case.scenario.provider_fail_then_ok:
            m.fallback_total += 1
            if r.selected == "gemma-y" and r.terminal_state in _NOMINAL:
                m.fallback_correct += 1
        # false blocking (only meaningful for non-glue configs)
        if glue_nominal is not None and case.scenario.name in glue_nominal \
                and r.terminal_state not in _NOMINAL and not case.expected_terminal in _NOMINAL:
            pass  # expected non-nominal; not a false block
        if glue_nominal is not None and case.scenario.name in glue_nominal \
                and r.terminal_state not in _NOMINAL and case.expected_terminal in _NOMINAL:
            m.false_blocking += 1
        # deterministic replay (unified only, representative)
        if name == "unified":
            rep = replay(_fresh(case.scenario), r,
                         case.scenario.envelope.policy_versions.get("enterprise"),
                         case.scenario.envelope.registry_version)
            replay_ok += 1 if rep.reproduced else 0
    n = max(1, m.scenarios)
    m.invalid_transition_rate = round(m.invalid_transition_rate / n, 4)
    m.audit_completeness = round(m.audit_completeness / n, 4)
    m.trace_completeness = round(m.trace_completeness / n, 4)
    m.reason_code_completeness = round(m.reason_code_completeness / n, 4)
    m.replay_success = round(replay_ok / n, 4) if name == "unified" else None
    return m


def _fresh(sc: Scenario) -> Scenario:
    # rebuild envelope so mutable state (e.g. mode set by shadow) never leaks between runs
    e = sc.envelope
    env2 = RequestEnvelope(**{k: (set(v) if isinstance(v, set) else v) for k, v in e.__dict__.items()})
    return Scenario(**{**sc.__dict__, "envelope": env2})


def _nominal_set(cases: List[Case]) -> set:
    s = set()
    for case in cases:
        o = Orchestrator(**CONFIGS["glue"])
        r = o.run(_fresh(case.scenario))
        if r.terminal_state in _NOMINAL:
            s.add(case.scenario.name)
    return s


def run_evaluation() -> Dict[str, Any]:
    cases = all_cases()
    results = {name: asdict(_run_config(name, cases)) for name in CONFIGS}
    return {"scenario_count": len(cases), "configs": results,
            "note": "architectural integration evaluation, MOCK mode, no live calls; "
                    "complexity = component-call/record counts, not production latency"}


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=2, default=str))
