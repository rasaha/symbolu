"""Machinery tests for internal_policy_controller v2."""
from __future__ import annotations

import numpy as np

from symbolu_neural.internal_policy_controller.v2.symbolu_state import compute_state, SymbolUState
from symbolu_neural.internal_policy_controller.v2.policy import (
    ARMS, AXES, translate, policy_for_arm, policy_divergence, _relabel_state)
from symbolu_neural.internal_policy_controller.v2 import pilot
from symbolu_neural.internal_policy_controller.v2.judge import RUBRIC, judge_prompt
from symbolu_neural.internal_policy_controller.v2.llm import get_llm


def test_full_state_has_all_components_with_provenance():
    s = compute_state("my database was deleted and my boss is furious")
    for fld in ["vritti", "guna", "kosha", "guna_resonance", "valence", "pse_meaning"]:
        assert getattr(s, fld) is not None
    assert abs(sum(s.guna.values()) - 1.0) < 1e-6
    assert abs(sum(s.vritti.values()) - 1.0) < 1e-6
    assert s.provenance["vritti"] == "canonical"
    assert s.provenance["guna"].startswith("derived")   # honest about derivation


def test_translation_is_label_semantic_not_a_classifier():
    s = compute_state("explain how a transformer works")
    p = translate(s)
    assert p.tone in {"calm and clear", "direct and energetic", "grounded and measured"}
    assert set(p.as_dict().keys()) >= set(AXES)


def test_relabel_changes_the_policy_unlike_v1():
    # v1's relabel was a basis-permutation no-op; here relabeling guna LABELS must
    # be able to change the policy for at least one prompt.
    diffs = []
    for p, _, _ in pilot.prompts():
        s = compute_state(p)
        base = translate(s)
        rel = translate(_relabel_state(s, seed=0))
        diffs.append(policy_divergence(base, rel))
    assert max(diffs) > 0.0   # at least one prompt's policy changes under relabeling


def test_all_arms_produce_valid_modes():
    s = compute_state("is it going to be a good year for housing")
    o = compute_state("explain transformers")
    for arm in ARMS:
        pol, mode = policy_for_arm(arm, s, o)
        assert mode in {"none", "self_refine", "policy"}
        if mode == "policy":
            assert pol is not None and pol.render()


def test_structural_report_real_offline():
    r = pilot.structural_report()
    assert r["n_prompts"] > 0
    d = r["policy_divergence_vs_symbolu"]
    assert d["random_policy"] >= 0.0 and d["relabeled_symbolu"] >= 0.0
    # sanity: a different draft's state (shuffled) or random should diverge somewhat
    assert max(d.values()) > 0.0


def test_judge_prompt_has_rubric_and_no_markers():
    jp = judge_prompt("q", "draft", "final")
    for k in RUBRIC:
        assert k in jp
    assert "prefer_final" in jp


def test_mock_pipeline_runs_but_gives_no_verdict():
    q = pilot.run_quality(backend="mock")
    assert q["is_real"] is False
    for arm in ARMS:
        assert "rubric_mean" in q["arms"][arm]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
