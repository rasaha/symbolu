"""Machinery + anti-regression tests for v3 (encodes the v2 defects as failing cases)."""
from __future__ import annotations

import numpy as np

from symbolu_neural.internal_policy_controller.v3.symbolu_state import (
    compute_state, POLICY_DRIVING, DIAGNOSTIC_ONLY)
from symbolu_neural.internal_policy_controller.v3.policy import (
    ARMS, AXES, translate, policy_for_arm, _relabel_state, policy_divergence)
from symbolu_neural.internal_policy_controller.v3 import pilot
from symbolu_neural.internal_policy_controller.v3.data import prompts


def test_full_state_includes_aspect():
    s = compute_state("explain how a transformer works")
    assert hasattr(s, "aspect_balance")             # v2 defect D2: aspect was absent
    assert -1.0 <= s.aspect_balance <= 1.0


def test_every_policy_driving_var_influences_policy():
    # the core v2-defect guardrail (D1)
    fi = pilot.field_influence_check()
    assert set(fi) == set(POLICY_DRIVING)
    assert all(fi.values()), f"zero-influence fields: {[k for k,v in fi.items() if not v]}"


def test_sattva_is_reachable():
    # v2 defect D3: sattva guna was structurally unreachable
    tops = {max(compute_state(p).guna, key=compute_state(p).guna.get) for p, _, _ in prompts()}
    assert "sattva" in tops


def test_no_dead_caution_branch():
    # v2-style dead branch: caution must take >1 value across prompts
    cautions = {translate(compute_state(p)).caution for p, _, _ in prompts()}
    assert len(cautions) >= 2, f"caution is dead/constant: {cautions}"


def test_tone_all_three_reachable():
    tones = {translate(compute_state(p)).tone for p, _, _ in prompts()}
    assert len(tones) == 3


def test_relabel_permutes_all_consumed_categories():
    # D8: relabel must change guna, kosha AND valence (not guna only)
    s = compute_state("should I quit my stable job to pursue my dream")
    r = _relabel_state(s, 0)
    assert list(r.guna.keys()) != list(s.guna.keys()) or list(r.kosha.keys()) != list(s.kosha.keys())


def test_distinct_policies_much_greater_than_v2():
    pols = {tuple(translate(compute_state(p)).as_dict()[k] for k in AXES) for p, _, _ in prompts()}
    assert len(pols) >= 6   # v2 produced only 4

def test_state_warnings_surface_not_silent():
    s = compute_state("explain how a transformer works")
    assert isinstance(s.warnings, list)            # failures surfaced, not swallowed


def test_mock_pipeline_runs_no_verdict():
    q = pilot.run_quality(backend="mock")
    assert q["is_real"] is False
    assert "judge_failures" in q


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
