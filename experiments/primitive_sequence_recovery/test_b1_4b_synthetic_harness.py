#!/usr/bin/env python3
"""Tests for the B1.4b SYNTHETIC harness. SYNTHETIC ONLY — no real data, no dataset, no
Stage A. Proves the pipeline mechanics run and the terminal-label decision logic covers
all 10 labels.

    python3 test_b1_4b_synthetic_harness.py
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import b1_4b_synthetic_harness as H


def test_no_stage_a_import():
    # the harness must not IMPORT Stage A / symbolu_neural (mentions in comments are fine,
    # since the module documents that it deliberately does not use Stage A)
    import ast
    src = (HERE / "b1_4b_synthetic_harness.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert "symbolu_neural" not in a.name and "structural_v1" not in a.name
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "symbolu_neural" not in mod and "structural_v1" not in mod
    # and it must not be importable Stage A state via a module reference either
    assert "symbolu_neural" not in getattr(H, "__dict__", {})


def test_toy_operator_is_orthogonal():
    # synthetic operators mirror Stage A orthogonality (norm-preserving), but are toy
    import numpy as np
    m = H.toy_operator(np.array([0.3, -0.7, 0.5, 0.1]))
    assert np.allclose(m @ m.T, np.eye(4), atol=1e-9)
    assert abs(abs(np.linalg.det(m)) - 1.0) < 1e-9


def test_operators_noncommute_and_f3_order_sensitive():
    # F-3 must be order-sensitive (else the whole L2 claim is inert). NOTE: these particular
    # F-3 summaries are invariant to FULL reversal (‖[a,b]‖=‖[b,a]‖ and ‖prod-rprod‖ is
    # symmetric), so order-sensitivity is checked against a NON-reversal permutation.
    import numpy as np
    phon, ops, _ = H._synthetic_alphabet(k=6, seed=1)
    a = H.f3_features(np.array([2, 4, 3]), ops)     # distinct non-twin units
    b = H.f3_features(np.array([3, 2, 4]), ops)      # rotation, not a reversal
    assert not np.allclose(a, b), "F-3 features should change under a non-reversal permutation"


def test_cv_score_noise_near_chance_signal_high():
    import numpy as np
    rng = np.random.default_rng(0)
    n = 60
    X = rng.normal(size=(n, 3))
    y_noise = rng.normal(size=n)
    y_signal = X[:, 0] * 3.0 + 0.3 * rng.normal(size=n)
    assert H.cv_score(X, y_noise) <= H.CHANCE, "noise must score at/below chance"
    assert H.cv_score(X, y_signal) > H.CHANCE + H.MARGIN, "planted signal must score high"


def test_decide_label_covers_all_ten_labels():
    m = H.MARGIN
    ch = H.CHANCE
    hi = ch + 3 * m
    lo = ch - m if ch - m > 0 else 0.0
    base_lo = {x: lo for x in ("phonology", "bag", "shuffle", "random_relabel", "sentiment")}

    # SIGNAL
    assert H.decide_label({"f3": hi, **base_lo}) == "L1_L2_L3_ATTRIBUTE_SIGNAL"
    # F_COLLAPSES_TO_PHONOLOGY
    s = {"f3": hi, **base_lo}; s["phonology"] = hi
    assert H.decide_label(s) == "F_COLLAPSES_TO_PHONOLOGY"
    # BAG_OR_SHUFFLE_EXPLAINS
    s = {"f3": hi, **base_lo}; s["bag"] = hi
    assert H.decide_label(s) == "BAG_OR_SHUFFLE_EXPLAINS"
    # RANDOM_RELABEL_EXPLAINS
    s = {"f3": hi, **base_lo}; s["random_relabel"] = hi
    assert H.decide_label(s) == "RANDOM_RELABEL_EXPLAINS"
    # SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS
    s = {"f3": hi, **base_lo}; s["sentiment"] = hi
    assert H.decide_label(s) == "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS"
    # NULL_RETURN_BOTTOM
    assert H.decide_label({x: lo for x in H.METHODS}) == "NULL_RETURN_BOTTOM"
    # INCONCLUSIVE: f3 carries signal but does not beat the runner-up by margin, and the
    # runner-up is itself in the gray zone (below `strong`), so no baseline credibly explains
    s = {"f3": 0.48, "phonology": 0.34, "bag": 0.30, "shuffle": 0.29,
         "random_relabel": 0.28, "sentiment": 0.25}
    assert H.decide_label(s) == "INCONCLUSIVE"
    # validity gates (win regardless of scores)
    assert H.decide_label({"f3": hi, **base_lo}, {"y_not_independent": True}) == "Y_NOT_INDEPENDENT"
    assert H.decide_label({"f3": hi, **base_lo}, {"decoder_gloss_leak": True}) == "DECODER_LEAKAGE_INVALID"
    assert H.decide_label({"f3": hi, **base_lo}, {"word_leak": True}) == "WORD_LEAKAGE_INVALID"


def test_validity_gate_precedence_over_signal():
    # a planted signal + a leak must still be reported invalid, never as SIGNAL
    hi = H.CHANCE + 3 * H.MARGIN
    base_lo = {x: 0.0 for x in ("phonology", "bag", "shuffle", "random_relabel", "sentiment")}
    assert H.decide_label({"f3": hi, **base_lo}, {"decoder_gloss_leak": True}) != "L1_L2_L3_ATTRIBUTE_SIGNAL"


def test_pipeline_regimes_match_expected_labels():
    # the FULL synthetic pipeline (build -> F-3 -> Y -> CV score -> label) on each regime
    results = {r["case"]: r for r in H.run_all()}
    cases = {c["name"]: c for c in H.load_cases()}
    for name, res in results.items():
        exp = cases[name].get("expected_label")
        if exp is not None:
            assert res["label"] == exp, f"{name}: got {res['label']} expected {exp} scores={res['scores']}"


def test_positive_control_actually_detects_interaction():
    # the synthetic positive control MUST fire SIGNAL, else a real null would be uninformative
    res = {r["case"]: r for r in H.run_all()}["pipeline_interaction_signal"]
    assert res["label"] == "L1_L2_L3_ATTRIBUTE_SIGNAL"
    assert res["scores"]["f3"] > res["scores"]["phonology"] + H.MARGIN


def test_phonology_control_does_not_false_positive():
    res = {r["case"]: r for r in H.run_all()}["pipeline_phonology_collapses_f3"]
    assert res["label"] == "F_COLLAPSES_TO_PHONOLOGY"


def test_all_fixture_labels_are_declared():
    for c in H.load_cases():
        assert c["expected_label"] in H.LABELS


def run_all_tests():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed  (SYNTHETIC ONLY — no real data, no Stage A)")
    return True


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
