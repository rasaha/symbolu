"""v4 tests — the high-fidelity translator must preserve far more ontology information
than v3, and the gate-valid pairwise harness must still run."""
from __future__ import annotations

from symbolu_neural.internal_policy_controller.v3.symbolu_state import compute_state
from symbolu_neural.internal_policy_controller.v3.policy import _relabel_state
from symbolu_neural.internal_policy_controller.v4.policy_v4 import (
    translate_v4, PolicySpecV4, ARMS)
from symbolu_neural.internal_policy_controller.v4 import pilot_v4
from symbolu_neural.internal_policy_controller.v3.data import prompts


def test_v4_prompt_carries_distributions_and_numbers():
    """The v4 prompt must verbalize the distribution (percentages) and the continuous
    values (signed numbers) — the exact information v3 discarded."""
    s = compute_state("explain how a transformer neural network works")
    txt = translate_v4(s).render()
    assert "%" in txt                                  # distribution probabilities present
    assert "mix" in txt                                # named blends (vritti/guna/kosha mix)
    # at least one signed continuous value (aspect/resonance) carried verbatim
    import re
    assert re.search(r"[-+]\d\.\d\d", txt)


def test_v4_preserves_more_information_than_v3():
    """v4 must beat v3 on the fair, apples-to-apples comparisons: it de-genericizes the
    prompt and makes label scrambles move more of it. (Relabel divergence is capped
    because ~30% of the policy is continuous-magnitude-driven and label-invariant — so
    we assert real, defensible gains, not an inflated number.)"""
    b = pilot_v4.bottleneck_report_v4()
    # field-level relabel divergence (direct analog of v3's 34%) beats v3
    assert b["v4"]["field_div"] > b["v3"]["field_div"] and b["v4"]["field_div"] > 0.40
    # token-level relabel divergence MORE THAN DOUBLES v3's
    assert b["v4"]["token_div"] > 2 * b["v3"]["token_div"]
    # the bottleneck fix: v4 prompts are far less generic than v3's near-generic prompts
    assert b["v4"]["divergence_from_generic"] > 0.40
    assert b["v4"]["divergence_from_generic"] > 3 * b["v3"]["divergence_from_generic"]


def test_v4_prompts_are_all_distinct():
    """Continuous values mean every prompt-state yields a distinct prompt (v3 collapsed
    36 -> 24)."""
    b = pilot_v4.bottleneck_report_v4()
    assert b["distinct_prompts"] == b["n_prompts"]


def test_v4_relabel_actually_changes_policy():
    s = compute_state("should I quit my stable job to pursue my dream")
    a = translate_v4(s).render()
    bx = translate_v4(_relabel_state(s, 0)).render()
    assert a != bx


def test_v4_pairwise_runs_and_gates_on_mock():
    res = pilot_v4.run_pairwise_multi_v4(backend="mock", seeds=(0, 1))
    assert res["is_real"] is False
    assert set(res["vs_symbolu"]) == set(pilot_v4.CONTROLS)
    for c in pilot_v4.CONTROLS:
        r = res["vs_symbolu"][c]
        assert {"margin", "ci95", "significant", "wins", "losses", "ties", "n"} <= set(r)
        assert r["n"] == len(prompts()) * 2
    assert "mean" in res["discrimination"]


def test_v4_arms_match_v3_for_comparability():
    assert ARMS == ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
                    "random_policy", "shuffled_symbolu", "relabeled_symbolu", "symbolu"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
