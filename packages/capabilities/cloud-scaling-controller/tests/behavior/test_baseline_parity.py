"""Behavior-baseline parity: the packaged controller must reproduce the frozen
pre-packaging behavior exactly (deterministic projection, identity_deviation excluded).

This is the authoritative behavior check — expected outcomes come from the frozen
baseline fixture, not hand-written magic numbers.
"""

from __future__ import annotations

import support


def _replay_from_baseline():
    baseline = support.load_baseline()
    scenarios = {}
    for name, steps in baseline["scenarios"].items():
        inputs = [s["_input"] for s in steps]
        scenarios[name] = support.run_steps(inputs)
    return baseline, scenarios


def test_baseline_hash_matches():
    baseline, scenarios = _replay_from_baseline()
    assert support.scenarios_hash(scenarios) == baseline["baseline_sha256"]


def test_baseline_per_step_decision_fields_match():
    baseline, scenarios = _replay_from_baseline()
    decision_fields = (
        "recommendation", "replica_delta", "action_score", "pressure",
        "plasticity", "gain", "damping", "coherence", "step",
        "metrics_snapshot", "explanation",
    )
    for name, expected_steps in baseline["scenarios"].items():
        got_steps = scenarios[name]
        assert len(got_steps) == len(expected_steps), name
        for i, (exp, got) in enumerate(zip(expected_steps, got_steps)):
            for f in decision_fields:
                assert got[f] == exp[f], f"{name}[{i}].{f}: {got[f]!r} != {exp[f]!r}"


def test_baseline_covers_expected_scenarios():
    baseline = support.load_baseline()
    expected = {
        "hold_steady", "sudden_spike", "scale_in_after_calm",
        "deploy_active_resistance", "restart_resistance", "gradual_growth",
        "latency_cascade", "unplanned_loss",
    }
    assert expected.issubset(set(baseline["scenarios"]))
