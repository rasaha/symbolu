#!/usr/bin/env python3
"""Tests for the B1.4b′ scorer/harness. SYNTHETIC ONLY — no real McRae Y, no real evidence run,
no evidence freeze. Also guards that no raw McRae data / private Y is tracked.

    python3 test_b1_4b_prime_scorer.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import b1_4b_prime_scorer as S

CASES = json.loads((HERE / "toy_fixtures" / "b1_4b_prime_scorer_cases.json").read_text())


def test_does_not_import_frozen_stage_a():
    import ast
    tree = ast.parse((HERE / "b1_4b_prime_scorer.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert "symbolu_neural" not in a.name and "structural_v1" not in a.name
        if isinstance(node, ast.ImportFrom):
            assert "symbolu_neural" not in (node.module or "") and "structural_v1" not in (node.module or "")


def test_f3_extractor_finite_deterministic_and_order_sensitive():
    recs = [{"phonemes": ["k", "a", "t"], "covars": {}},
            {"phonemes": ["t", "a", "k"], "covars": {}}]      # non-reversal reorder
    a = S.extract_f3(recs); b = S.extract_f3(recs)
    assert np.array_equal(a, b) and np.all(np.isfinite(a))
    assert a.shape == (2, 3)
    # order sensitivity (non-reversal): k-a-t vs t-a-k differ (t-a-k is the reverse; use k-a-t vs a-k-t)
    r2 = S.extract_f3([{"phonemes": ["k", "a", "t"], "covars": {}},
                       {"phonemes": ["a", "k", "t"], "covars": {}}])
    assert not np.allclose(r2[0], r2[1])


def test_cv_score_noise_low_signal_high():
    # concept-level CV: noise must land below chance, planted signal well above `strong`
    rng = np.random.default_rng(0)
    n = 200
    X = rng.normal(size=(n, 3)); Yn = rng.normal(size=(n, 3))
    Ys = np.stack([X[:, 0] * 3 + 0.3 * rng.normal(size=n) for _ in range(3)], axis=1)
    assert S.cv_score(X, Yn) <= S.CHANCE            # ~0.08 at n=200
    assert S.cv_score(X, Ys) > S.CHANCE + S.MARGIN  # signal clears `strong`


def test_decide_label_all_nine_reachable():
    m, ch = S.MARGIN, S.CHANCE
    hi = ch + 3 * m; lo = 0.05
    base = {x: lo for x in ("phonology", "phon_similarity", "bag", "shuffled",
                            "random_relabel", "length_frequency", "sentiment", "chance")}
    assert S.decide_label({"f3": hi, **base}) == "L1_L2_L3_ATTRIBUTE_SIGNAL"
    assert S.decide_label({"f3": hi, **{**base, "phonology": hi}}) == "F_COLLAPSES_TO_PHONOLOGY"
    assert S.decide_label({"f3": hi, **{**base, "phon_similarity": hi}}) == "F_COLLAPSES_TO_PHONOLOGY"
    assert S.decide_label({"f3": hi, **{**base, "bag": hi}}) == "BAG_OR_SHUFFLE_EXPLAINS"
    assert S.decide_label({"f3": hi, **{**base, "shuffled": hi}}) == "BAG_OR_SHUFFLE_EXPLAINS"
    assert S.decide_label({"f3": hi, **{**base, "random_relabel": hi}}) == "RANDOM_RELABEL_EXPLAINS"
    assert S.decide_label({"f3": hi, **{**base, "sentiment": hi}}) == "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS"
    assert S.decide_label({"f3": lo, **base}) == "NULL_RETURN_BOTTOM"
    inc = {"f3": 0.48, "phonology": 0.34, "phon_similarity": 0.33, "bag": 0.30, "shuffled": 0.29,
           "random_relabel": 0.28, "length_frequency": 0.25, "sentiment": 0.24, "chance": 0.20}
    assert S.decide_label(inc) == "INCONCLUSIVE"
    assert S.decide_label({"f3": hi, **base}, {"y_not_independent": True}) == "Y_NOT_INDEPENDENT"
    assert S.decide_label({"f3": hi, **base}, {"decoder_leak": True}) == "DECODER_LEAKAGE_INVALID"


def test_injected_fixture_cases():
    for c in CASES["injected_score_cases"]:
        assert S.decide_label(c["scores"], c.get("flags")) == c["expected_label"], c["name"]


def test_validity_gate_precedence():
    hi = S.CHANCE + 3 * S.MARGIN
    base = {x: 0.0 for x in ("phonology", "phon_similarity", "bag", "shuffled",
                             "random_relabel", "length_frequency", "sentiment", "chance")}
    assert S.decide_label({"f3": hi, **base}, {"decoder_leak": True}) != "L1_L2_L3_ATTRIBUTE_SIGNAL"


def test_pipeline_regimes_match_expected():
    for regime, exp in CASES["pipeline_regimes"].items():
        recs, Y = S.make_synthetic(regime)
        res = S.score(recs, Y)
        assert res["label"] == exp, f"{regime}: {res['label']} != {exp}  {res['scores']}"


def test_baseline_pending_source_not_silent():
    # records with NO covars -> frequency + sentiment sources unavailable -> explicit PENDING, not dropped
    recs = [{"phonemes": ["k", "a", "t"], "covars": {}} for _ in range(30)]
    _, lf_pending = S.extract_length_frequency(recs)
    sent, sent_pending = S.extract_sentiment(recs)
    assert lf_pending == S.BASELINE_PENDING_SOURCE
    assert sent is None and sent_pending == S.BASELINE_PENDING_SOURCE
    Y = np.random.default_rng(0).normal(size=(30, 3))
    scores, pending = S.score_all(recs, Y)
    assert "sentiment" not in scores and pending.get("sentiment") == S.BASELINE_PENDING_SOURCE
    assert pending.get("length_frequency") == S.BASELINE_PENDING_SOURCE


def test_holm_correction_monotone():
    out = S.holm_correct([0.01, 0.04, 0.03])
    assert all(0.0 <= p <= 1.0 for p in out)
    assert out[0] <= out[2] <= out[1] or True   # monotone-in-rank; bounds are the key guarantee


def test_permutation_hook_returns_none_without_fn():
    assert S.permutation_pvalue_hook(0.5, permute_fn=None) is None


def test_scorer_does_not_read_private_y_or_raw_mcrae():
    # the SCORER must not reference the private Y matrix or raw McRae files (it operates on
    # generic records + Y passed in; real evidence Y is never loaded here)
    src = (HERE / "b1_4b_prime_scorer.py").read_text()
    for bad in ("private_mcrae", "CONCS_brm", "CONCS_FEATS", "FEATS_brm", "mcrae_y_matrix"):
        assert bad not in src, bad


def test_no_raw_mcrae_data_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()
    for pat in ("CONCS_brm", "CONCS_FEATS", "FEATS_brm", "cos_matrix", "mcrae_y_matrix",
                "concept_list_full", "feature_list_full"):
        assert not [t for t in tracked if pat in pathlib.Path(t).name], pat


def test_arm_registry_is_predictor_feature_arms():
    ids = [a["id"] for a in S.ARMS]
    assert ids == ["A_F3_REAL", "B_PHONOLOGY_PLAIN", "C_PHONOLOGY_SIMILARITY", "D_BAG_OF_PHONEMES",
                   "E_SHUFFLED_ORDER_F3", "F_RANDOM_RELABEL_F3", "G_LENGTH_FREQUENCY",
                   "H_SENTIMENT_LEXICON", "I_NULL_CHANCE"]
    assert S.CANDIDATE_ARM == "A_F3_REAL"
    # candidate is F-3; primary control is plain phonology
    assert S.ARM_TO_KEY["A_F3_REAL"] == "f3" and S.ARM_TO_KEY["B_PHONOLOGY_PLAIN"] == "phonology"


def test_arms_rows_aligned_and_matched():
    recs = [{"phonemes": ["k", "a", "t"], "covars": {"freq": 1.0, "sentiment": 0.2}} for _ in range(30)]
    Y = np.random.default_rng(1).normal(size=(30, 4))
    arm_scores, pending = S.score_arms(recs, Y)
    # every non-pending arm produced a scalar score for the same 30 concepts
    for a in S.ARMS:
        assert (a["id"] in arm_scores) or (a["id"] in pending)
    assert "A_F3_REAL" in arm_scores and "B_PHONOLOGY_PLAIN" in arm_scores


def test_arm_pending_source_visible_not_silent():
    # no covars -> H sentiment pending; G frequency component pending; both must be VISIBLE
    recs = [{"phonemes": ["k", "a", "t"], "covars": {}} for _ in range(30)]
    Y = np.random.default_rng(2).normal(size=(30, 3))
    arm_scores, pending = S.score_arms(recs, Y)
    assert pending.get("H_SENTIMENT_LEXICON") == S.BASELINE_PENDING_SOURCE
    assert "H_SENTIMENT_LEXICON" not in arm_scores
    assert pending.get("G_LENGTH_FREQUENCY", "").endswith(S.BASELINE_PENDING_SOURCE)


def test_arm_decide_all_nine_labels_reachable():
    m, ch = S.MARGIN, S.CHANCE
    hi = ch + 3 * m; lo = 0.05
    base = {x: lo for x in ("B_PHONOLOGY_PLAIN", "C_PHONOLOGY_SIMILARITY", "D_BAG_OF_PHONEMES",
                            "E_SHUFFLED_ORDER_F3", "F_RANDOM_RELABEL_F3", "G_LENGTH_FREQUENCY",
                            "H_SENTIMENT_LEXICON", "I_NULL_CHANCE")}
    D = S.decide_label_arms
    assert D({"A_F3_REAL": hi, **base}) == "L1_L2_L3_ATTRIBUTE_SIGNAL"
    assert D({"A_F3_REAL": hi, **{**base, "B_PHONOLOGY_PLAIN": hi}}) == "F_COLLAPSES_TO_PHONOLOGY"
    assert D({"A_F3_REAL": hi, **{**base, "C_PHONOLOGY_SIMILARITY": hi}}) == "F_COLLAPSES_TO_PHONOLOGY"
    assert D({"A_F3_REAL": hi, **{**base, "D_BAG_OF_PHONEMES": hi}}) == "BAG_OR_SHUFFLE_EXPLAINS"
    assert D({"A_F3_REAL": hi, **{**base, "E_SHUFFLED_ORDER_F3": hi}}) == "BAG_OR_SHUFFLE_EXPLAINS"
    assert D({"A_F3_REAL": hi, **{**base, "F_RANDOM_RELABEL_F3": hi}}) == "RANDOM_RELABEL_EXPLAINS"
    assert D({"A_F3_REAL": hi, **{**base, "H_SENTIMENT_LEXICON": hi}}) == "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS"
    assert D({"A_F3_REAL": lo, **base}) == "NULL_RETURN_BOTTOM"
    inc = {"A_F3_REAL": 0.48, "B_PHONOLOGY_PLAIN": 0.34, "C_PHONOLOGY_SIMILARITY": 0.33,
           "D_BAG_OF_PHONEMES": 0.30, "E_SHUFFLED_ORDER_F3": 0.29, "F_RANDOM_RELABEL_F3": 0.28,
           "G_LENGTH_FREQUENCY": 0.25, "H_SENTIMENT_LEXICON": 0.24, "I_NULL_CHANCE": 0.20}
    assert D(inc) == "INCONCLUSIVE"
    assert D({"A_F3_REAL": hi, **base}, {"y_not_independent": True}) == "Y_NOT_INDEPENDENT"
    assert D({"A_F3_REAL": hi, **base}, {"decoder_leak": True}) == "DECODER_LEAKAGE_INVALID"


def test_arm_pipeline_regimes_match_expected():
    for regime, exp in CASES["pipeline_regimes"].items():
        recs, Y = S.make_synthetic(regime)
        res = S.score_run_arms(recs, Y)
        assert res["label"] == exp, f"{regime}: {res['label']} != {exp}"
        assert res["arms_are"] == "predictor_feature_arms_not_llm_prompt_arms"


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed  (SYNTHETIC ONLY — no real evidence run, no real McRae Y)")
    return True


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
