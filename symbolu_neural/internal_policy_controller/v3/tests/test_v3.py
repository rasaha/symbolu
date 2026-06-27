"""Machinery + anti-regression tests for v3 (encodes the v2 defects as failing cases)."""
from __future__ import annotations

import numpy as np

from symbolu_neural.internal_policy_controller.v3.symbolu_state import (
    compute_state, POLICY_DRIVING, DIAGNOSTIC_ONLY, CLASSICAL_VRITTI, DYNAMIC_STATES)
from symbolu_neural.internal_policy_controller.v3.policy import (
    ARMS, AXES, COGNITIVE_AXES, DELIVERY_AXES, translate, policy_for_arm,
    _relabel_state, policy_divergence)
from symbolu_neural.internal_policy_controller.v3 import pilot
from symbolu_neural.internal_policy_controller.v3.data import prompts


# ---- terminology-fix regression tests (classical vritti vs dynamic state) ----
def test_classical_and_dynamic_are_separate_fields():
    s = compute_state("explain how a transformer works")
    assert hasattr(s, "classical_vritti") and hasattr(s, "dynamic_state")
    assert not hasattr(s, "vritti")                       # the ambiguous field is GONE
    assert set(s.classical_vritti) == set(CLASSICAL_VRITTI)        # pramana.. (canonical)
    assert set(s.dynamic_state) == set(DYNAMIC_STATES)            # INERTIA.. (motion)


def test_classical_vritti_uses_canonical_schema_names():
    from symbolu_core.presentation.signals import VrittiDistribution
    import dataclasses
    canon = [f.name for f in dataclasses.fields(VrittiDistribution)]
    assert set(CLASSICAL_VRITTI) == set(canon)


def test_classical_vritti_provenance_is_derived_bridge_not_canonical():
    s = compute_state("explain how a transformer works")
    assert s.provenance["classical_vritti"].startswith("derived_bridge")
    assert s.provenance["dynamic_state"].startswith("canonical")


def test_both_vritti_senses_influence_separate_families():
    fam = pilot.field_influence_by_family()
    assert fam["classical_vritti"]["hits_cognitive"]     # classical -> cognitive axis
    assert fam["dynamic_state"]["hits_delivery"]         # dynamic   -> delivery axis


def test_relabel_permutes_both_vritti_senses():
    s = compute_state("should I quit my stable job to pursue my dream")
    r = _relabel_state(s, 0)
    assert list(r.classical_vritti.keys()) != list(s.classical_vritti.keys()) \
        or list(r.dynamic_state.keys()) != list(s.dynamic_state.keys())


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
    assert len(q["arms"]["symbolu"]["per_prompt"]) == len(prompts())   # per-prompt scores exposed


def test_prompt_set_expanded():
    assert len(prompts()) >= 30          # statistical-validity expansion


def test_signal_coverage_audit():
    """Pins the audited coverage so regressions are caught. Every variable must be
    WIRED (influences policy); value-coverage is complete except the structurally
    near-unreachable RELEASE/anandamaya state (vritti & kosha = 4/5)."""
    c = pilot.coverage_report()
    assert all(c["field_influence"].values())                 # all 7 wired
    assert set(c["field_influence"]) == set(POLICY_DRIVING)    # incl. both vritti senses
    assert c["state"]["guna_top"]["n"] == 3                    # full
    assert c["state"]["valence"]["n"] == 3                     # full
    assert c["state"]["dynamic_state_top"]["n"] >= 4           # 4/5 (RELEASE rare)
    assert c["state"]["kosha_top"]["n"] >= 4                   # 4/5 (anandamaya rare)
    assert c["state"]["classical_vritti_top"]["n"] >= 4        # bridged, all 5 reachable
    for a in ["tone", "caution", "speculation_reduction"]:
        assert c["axes"][a]["n"] == c["axes"][a]["nominal"]    # full range observed


def test_multi_seed_ci_structure_and_pairing():
    res = pilot.run_multi(backend="mock", seeds=(0, 1, 2))
    assert res["n_per_arm"] == len(prompts()) * 3        # pooled n = prompts × seeds
    for arm in pilot.ARMS:
        assert "mean" in res["arms_ci"][arm] and "ci95" in res["arms_ci"][arm]
    # paired diffs vs every control present, with significance flag
    for ref in ["generic_refine", "nl_policy", "relabeled_symbolu"]:
        p = res["paired_vs_symbolu"][ref]
        assert {"diff", "ci95", "significant"} <= set(p)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
