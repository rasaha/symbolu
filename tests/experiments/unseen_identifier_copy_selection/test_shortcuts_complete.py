"""Fixture-only tests for the completed twelve-baseline shortcut suite and cross-seed aggregation.

Uses only fixture seeds. Verifies the four completed baselines are deterministic, use no answer key,
sit at chance on opaque identifiers, and that aggregation is an example-count-weighted mean with
per-seed/per-split frequency isolation, threshold equality, and competence-floor comparison.
"""
from __future__ import annotations

import pytest

from experiments.unseen_identifier_copy_selection.config import CANDIDATE_COUNT, FIXTURE_SEEDS
from experiments.unseen_identifier_copy_selection.shortcuts import (
    BASELINE_NAMES,
    SHORTCUT_BOUND,
    SHORTCUT_FWER,
    _baseline_counts_on,
    _baselines_on,
    _decide,
    _pickers,
    _selection_examples,
    aggregate_shortcuts,
    binom_sf_ge,
    holm_reject,
    shortcut_scores,
)
from experiments.unseen_identifier_copy_selection.tasks import generate_split

FS = FIXTURE_SEEDS[0]
NEW_FOUR = ("source_target_cooccurrence", "seen_id_frequency", "output_template_leakage", "task_label_leakage")


def test_exactly_twelve_baselines_present():
    exs = _selection_examples(generate_split("C2", "unseen", FS, n=30))
    scores = _baselines_on(exs)
    assert len(scores) == 12
    assert set(scores) == set(BASELINE_NAMES)
    for name in NEW_FOUR:
        assert name in scores


def test_new_baselines_are_deterministic():
    exs = _selection_examples(generate_split("C6", "unseen", FS, n=40))
    pickers_a = _pickers(exs)
    pickers_b = _pickers(exs)
    for name in NEW_FOUR:
        preds_a = [pickers_a[name](e) for e in exs]
        preds_b = [pickers_b[name](e) for e in exs]
        assert preds_a == preds_b


def test_new_baselines_use_no_answer_key():
    # Every picker chooses among the example's own candidate targets; it never returns the gold via a
    # path that reads expected_output. We assert predictions are drawn from the candidate set only.
    exs = _selection_examples(generate_split("C7", "unseen", FS, n=40))
    pickers = _pickers(exs)
    for e in exs:
        candidates = [t for _, t in e.pairs]
        for name in NEW_FOUR:
            assert pickers[name](e) in candidates


def test_source_target_cooccurrence_ignores_the_gold_label():
    # If we relabel gold to always be candidate[1], the co-occurrence baseline (which never reads the
    # gold) must produce byte-identical predictions.
    from dataclasses import replace

    exs = _selection_examples(generate_split("C2", "unseen", FS, n=30))
    relabelled = [replace(e, expected_output=[t for _, t in e.pairs][1]).with_hash() for e in exs]
    pk_orig = _pickers(exs)
    pk_relabel = _pickers(relabelled)
    assert [pk_orig["source_target_cooccurrence"](e) for e in exs] == \
           [pk_relabel["source_target_cooccurrence"](e) for e in relabelled]


def test_all_twelve_sit_at_chance_on_opaque_ids():
    import statistics
    chance = 1.0 / CANDIDATE_COUNT
    agg: dict[str, list[float]] = {}
    for seed in FIXTURE_SEEDS:
        for split in ("C2", "C4", "C6", "C7"):
            exs = _selection_examples(generate_split(split, "unseen", seed, n=80))
            for name, value in _baselines_on(exs).items():
                agg.setdefault(name, []).append(value)
    for name in NEW_FOUR:
        assert abs(statistics.mean(agg[name]) - chance) <= 0.03, (name, statistics.mean(agg[name]))


def test_counts_have_applicable_denominator():
    exs = _selection_examples(generate_split("C2", "unseen", FS, n=24))
    counts = _baseline_counts_on(exs)
    for name in BASELINE_NAMES:
        correct, applicable = counts[name]
        assert applicable == 24
        assert 0 <= correct <= applicable


def test_aggregation_is_example_count_weighted():
    # Two synthetic per-seed results with different applicable counts; aggregate must weight by count.
    floor = 1.0 / CANDIDATE_COUNT + SHORTCUT_BOUND
    r1 = {"chance": 1.0 / CANDIDATE_COUNT, "bound": floor, "all_pass": True,
          "per_split": {"C2": {"n": 10, "baselines": {"first_target": 0.5},
                               "counts": {"first_target": [5, 10]}, "competence_floor": floor, "pass": True}}}
    r2 = {"chance": 1.0 / CANDIDATE_COUNT, "bound": floor, "all_pass": True,
          "per_split": {"C2": {"n": 90, "baselines": {"first_target": 0.0},
                               "counts": {"first_target": [0, 90]}, "competence_floor": floor, "pass": True}}}
    agg = aggregate_shortcuts([r1, r2])
    # weighted score = (5 + 0) / (10 + 90) = 0.05, NOT the unweighted mean 0.25
    assert agg["per_split"]["C2"]["baselines"]["first_target"] == pytest.approx(0.05)
    assert agg["per_split"]["C2"]["per_seed_scores"]["first_target"] == [0.5, 0.0]


def test_aggregation_threshold_equality_passes():
    floor = 1.0 / CANDIDATE_COUNT + SHORTCUT_BOUND
    correct = round(floor * 100)  # score exactly at the floor
    r = {"chance": 1.0 / CANDIDATE_COUNT, "bound": floor, "all_pass": True,
         "per_split": {"C2": {"n": 100, "baselines": {"b": floor},
                              "counts": {"b": [correct, 100]}, "competence_floor": floor, "pass": True}}}
    agg = aggregate_shortcuts([r])
    assert agg["per_split"]["C2"]["baselines"]["b"] == pytest.approx(correct / 100)
    assert agg["per_split"]["C2"]["pass"] is (correct / 100 <= floor)


def test_aggregation_blocks_when_over_floor():
    floor = 1.0 / CANDIDATE_COUNT + SHORTCUT_BOUND
    r = {"chance": 1.0 / CANDIDATE_COUNT, "bound": floor, "all_pass": False,
         "per_split": {"C2": {"n": 100, "baselines": {"leaky": 0.9},
                              "counts": {"leaky": [90, 100]}, "competence_floor": floor, "pass": False}}}
    agg = aggregate_shortcuts([r])
    assert agg["all_pass"] is False


def test_per_seed_frequency_isolation():
    # Frequency state is built inside each (seed, split); shortcut_scores on one seed never sees
    # another seed's identifiers. Distinct seeds yield disjoint identifier sets.
    s0 = {i for e in generate_split("C2", "unseen", FIXTURE_SEEDS[0], n=40) for i in e.context_ids}
    s1 = {i for e in generate_split("C2", "unseen", FIXTURE_SEEDS[1], n=40) for i in e.context_ids}
    assert s0.isdisjoint(s1)


def test_zero_applicable_is_an_error():
    with pytest.raises(ValueError):
        aggregate_shortcuts([{"chance": 1.0 / CANDIDATE_COUNT, "bound": 0.38,
                              "per_split": {"C2": {"counts": {"b": [0, 0]}, "baselines": {"b": 0.0}}}}])


# ---- corrective-PR: sampling-aware gate (exact binomial + Holm-Bonferroni) ----

CHANCE = 1.0 / CANDIDATE_COUNT
SPLITS = ("C2", "C3", "C4", "C5", "C6", "C7")


def _family(at_chance_n: int = 180, override=None):
    """A realistic family of 6 selection splits x 12 baselines. Every baseline sits at chance
    (k = round(n/3)); `override=(split, baseline, k, n)` injects one comparison for a test."""
    k_chance = round(at_chance_n * CHANCE)
    per_split_counts = {}
    for s in SPLITS:
        per_split_counts[s] = {name: [k_chance, at_chance_n] for name in BASELINE_NAMES}
    if override:
        s, b, k, n = override
        per_split_counts[s][b] = [k, n]
    return per_split_counts


def test_binom_sf_ge_known_values():
    assert binom_sf_ge(0, 10, 0.3) == 1.0            # P(X>=0) = 1
    assert binom_sf_ge(11, 10, 0.3) == 0.0           # impossible
    assert binom_sf_ge(10, 10, 0.5) == pytest.approx(0.5 ** 10)  # all-heads tail
    # monotone non-increasing in k
    tails = [binom_sf_ge(k, 180, CHANCE) for k in range(50, 90)]
    assert all(tails[i] >= tails[i + 1] for i in range(len(tails) - 1))


def test_holm_reject_step_down():
    assert holm_reject([1e-10, 0.5, 0.9], 0.05) == [True, False, False]
    assert holm_reject([0.02, 0.03], 0.05) == [True, True]      # 0.02<=.025 then 0.03<=.05
    assert holm_reject([0.04, 0.04], 0.05) == [False, False]    # 0.04>.025 -> step-down stops
    assert holm_reject([], 0.05) == []


def test_marginal_noise_does_not_block():
    # 0.4056 (=73/180) is ~+2 sigma above chance -- pure noise across 72 comparisons. MUST NOT block.
    dec = _decide(_family(override=("C2", "first_target", 73, 180)), CHANCE)
    assert dec["n_comparisons"] == 72
    assert dec["all_pass"] is True
    assert dec["per_split"]["C2"]["blocked"] == []


def test_injected_leak_blocks():
    # 0.60 (=108/180) is a genuine leak; it must block even after Holm correction over 72 comparisons.
    dec = _decide(_family(override=("C2", "first_target", 108, 180)), CHANCE)
    assert dec["all_pass"] is False
    assert "first_target" in dec["per_split"]["C2"]["blocked"]


def test_multiplicity_matters():
    # The SAME modest exceedance (73/180) blocks when tested alone (family of 1) but not within the
    # full family of 72 -- demonstrating the multiple-comparison control does real work.
    alone = _decide({"C2": {"first_target": [73, 180]}}, CHANCE)
    assert alone["n_comparisons"] == 1
    assert alone["all_pass"] is False
    full = _decide(_family(override=("C2", "first_target", 73, 180)), CHANCE)
    assert full["all_pass"] is True


def test_practical_leg_required():
    # A tiny effect can be statistically significant at huge n yet fall below the +0.05 practical
    # margin; the dual condition must NOT block it (0.36 > chance but < chance+0.05).
    dec = _decide(_family(override=("C2", "first_target", 3600, 10000)), CHANCE)
    assert dec["per_split"]["C2"]["baselines"]["first_target"] == pytest.approx(0.36)
    assert dec["all_pass"] is True


def test_all_at_chance_passes():
    dec = _decide(_family(), CHANCE)
    assert dec["all_pass"] is True
    assert dec["fwer"] == SHORTCUT_FWER
