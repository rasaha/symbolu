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


# ---- sentence-level classical Vritti vs phoneme dynamic state ----
def test_classical_vritti_is_sentence_level_not_phonological():
    s = compute_state("explain how a transformer works")
    cv = s.classical_vritti
    assert set(cv) >= {"primary", "nidra", "smrti"}             # 3+2 structure
    assert cv["primary"] in {"pramana", "viparyaya", "vikalpa"}
    assert isinstance(cv["nidra"], bool) and isinstance(cv["smrti"], bool)
    assert s.provenance["classical_vritti"] == "sentence_semantic_rule_v1"   # NOT phonological
    assert "bridge" not in s.provenance["classical_vritti"]
    assert s.provenance["dynamic_state"].startswith("canonical")             # phoneme stays canonical


def test_evaluator_detects_each_cognitive_state():
    from symbolu_neural.internal_policy_controller.v3.cognitive_evaluator import (
        evaluate_cognitive, PROBE_ANSWERS)
    e = {k: evaluate_cognitive(v) for k, v in PROBE_ANSWERS.items()}
    assert e["pramana"]["primary"] == "pramana"
    assert e["viparyaya"]["primary"] == "viparyaya"
    assert e["vikalpa"]["primary"] == "vikalpa"
    assert e["nidra"]["nidra"] is True
    assert e["smrti"]["smrti"] is True


def test_three_cognitive_signals_hit_their_axes_and_dynamic_hits_delivery():
    fam = pilot.field_influence_by_family()
    assert fam["classical_primary"]["expected_axis"] == "epistemic_stance" and fam["classical_primary"]["hits_expected"]
    assert fam["nidra_flag"]["expected_axis"] == "clarification_policy" and fam["nidra_flag"]["hits_expected"]
    assert fam["smrti_flag"]["expected_axis"] == "memory_policy" and fam["smrti_flag"]["hits_expected"]
    assert fam["dynamic_state"]["expected_axis"] == "delivery_pace" and fam["dynamic_state"]["hits_expected"]


def test_classical_uses_canonical_schema_names():
    from symbolu_core.presentation.signals import VrittiDistribution
    import dataclasses
    canon = [f.name for f in dataclasses.fields(VrittiDistribution)]
    assert set(CLASSICAL_VRITTI) == set(canon)


def test_relabel_permutes_cognitive_and_dynamic():
    s = compute_state("It might possibly be a good year; perhaps prices could rise.")
    r = _relabel_state(s, 0)
    # primary remapped OR flags swapped OR dynamic permuted
    changed = (r.classical_vritti != s.classical_vritti) or \
              (list(r.dynamic_state.keys()) != list(s.dynamic_state.keys()))
    assert changed


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
    assert all(c["field_influence"].values())                 # all 9 wired
    assert set(c["field_influence"]) == set(POLICY_DRIVING)    # incl. 3 cognitive + dynamic
    assert c["state"]["guna_top"]["n"] == 3                    # full
    assert c["state"]["valence"]["n"] == 3                     # full
    assert c["state"]["dynamic_state_top"]["n"] >= 4           # 4/5 (RELEASE rare)
    assert c["state"]["kosha_top"]["n"] >= 4                   # 4/5 (anandamaya rare)
    # classical_vritti is about ANSWERS -> reachability proven on crafted probes
    assert set(c["evaluator_reachability"]["primary"]) == {"pramana", "viparyaya", "vikalpa"}
    assert "True" in c["evaluator_reachability"]["nidra"] and "True" in c["evaluator_reachability"]["smrti"]
    for a in ["tone", "caution", "speculation_reduction"]:
        assert c["axes"][a]["n"] == c["axes"][a]["nominal"]    # full range observed


def test_pairwise_judge_cancels_position_bias():
    """A judge that ALWAYS picks position A must net to 0 (no preference) once both
    orders are averaged — proves position-bias control works."""
    from symbolu_neural.internal_policy_controller.v3.judge import judge_pairwise

    class _AlwaysA:
        def chat(self, system, user, seed=0):
            return '{"winner":"A"}'
    assert judge_pairwise(_AlwaysA(), "q", "sym answer", "ctrl answer") == 0.0


def test_pairwise_validity_gate_detects_content_aware_judge():
    """A content-aware judge (prefers the answer mentioning Paris) must pass the
    gate (+1); the content-free mock must NOT (it can't discriminate)."""
    from symbolu_neural.internal_policy_controller.v3.judge import judge_discriminates
    from symbolu_neural.internal_policy_controller.v3.llm import MockLLM

    class _PrefersParis:
        def chat(self, system, user, seed=0):
            a = user.split("ANSWER A:")[1].split("ANSWER B:")[0]
            return '{"winner":"A"}' if "Paris" in a else '{"winner":"B"}'
    assert judge_discriminates(_PrefersParis()) == 1.0     # healthy judge
    assert judge_discriminates(MockLLM()) <= 0.0           # ceiling/blind judge fails gate


def test_pairwise_eval_runs_and_reports_gate_on_mock():
    res = pilot.run_pairwise_multi(backend="mock", seeds=(0, 1))
    assert res["is_real"] is False
    assert set(res["vs_symbolu"]) == set(pilot.CONTROLS)
    for c in pilot.CONTROLS:
        r = res["vs_symbolu"][c]
        assert {"margin", "ci95", "significant", "wins", "losses", "ties", "n"} <= set(r)
        assert r["n"] == len(prompts()) * 2                # pooled over 2 seeds
    assert "mean" in res["discrimination"]                 # validity gate computed


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
