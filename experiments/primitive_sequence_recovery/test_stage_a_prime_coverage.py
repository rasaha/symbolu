#!/usr/bin/env python3
"""Tests for the Stage A′ coverage-only harness. Repo-local pools only. NO Y, NO F-3, NO
semantic scoring, NO modification of frozen Stage A.

    python3 test_stage_a_prime_coverage.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_a_prime_coverage as A


def test_does_not_import_frozen_stage_a():
    import ast
    src = (HERE / "stage_a_prime_coverage.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert "symbolu_neural" not in a.name and "structural_v1" not in a.name
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "symbolu_neural" not in mod and "structural_v1" not in mod


def test_no_silent_fallback_reports_unsupported():
    # a character with no rule must be REPORTED as unsupported, not dropped silently
    r = A.normalize("a☃b", "A_PRIME_EN")   # snowman char has no rule
    assert "☃" in r["unsupported"]
    assert r["flag"] == "partial"
    # retention counts only consumed chars
    assert 0.0 < r["retention"] < 1.0


def test_normalizer_determinism():
    for w, tr in [("chair", "A_PRIME_EN"), ("krodha", "A_PRIME_SA"), ("vāyu", "A_PRIME_SA")]:
        assert A.normalize(w, tr) == A.normalize(w, tr)


def test_vaayu_now_decomposes_under_A_PRIME_SA():
    # vāyu failed the frozen 14-grapheme chart (v, ā, y, u all off-chart); Stage A′ must cover it
    r = A.normalize("vāyu", "A_PRIME_SA")
    assert r["flag"] == "full" and r["unsupported"] == []
    assert r["phonemes"] == ["v", "aa", "y", "u"]


def test_english_word_decomposes_fully():
    r = A.normalize("chair", "A_PRIME_EN")
    assert r["flag"] == "full" and r["unsupported"] == []
    assert r["retention"] == 1.0


def test_operators_orthogonal_and_finite():
    for name in A.PHONEMES:
        M = A.phoneme_operator(name)
        assert M.shape == (4, 4)
        assert np.all(np.isfinite(M))
        assert np.allclose(M @ M.T, np.eye(4), atol=1e-8), name


def test_operator_sanity_pass():
    s = A.operator_sanity()
    assert s["ok"], s["findings"]
    assert s["label"] == "STAGE_A_PRIME_OPERATOR_SANITY_PASS"


def test_semantic_leakage_audit_pass():
    a = A.semantic_leakage_audit()
    assert a["ok"], a["findings"]


def test_english_pool_extracts_only_word_field():
    # the loader must not pull dictionary_anchor / meaning fields
    import json
    raw = json.loads((HERE / "b1_3_revised_layer3" /
                      "b1_3_human_modulation_concrete_object_candidate_wordlist.json").read_text())
    words = A.load_pool_english()
    assert len(words) == len(raw["items"])
    assert all(isinstance(w, str) for w in words)
    # a known meaning string must NOT appear among extracted words
    anchors = {it.get("dictionary_anchor") for it in raw["items"]}
    assert not (set(words) & anchors)


def test_repo_local_coverage_meets_targets():
    sa = A.coverage_for_pool(A.load_pool_sanskrit(), "A_PRIME_SA")
    en = A.coverage_for_pool(A.load_pool_english(), "A_PRIME_EN")
    for c in (sa, en):
        assert c["char_retention"] >= A.RETENTION_TARGET, c
        assert c["full_fraction"] >= A.FULL_WORD_TARGET, c
        assert c["coverage_label"] == "STAGE_A_PRIME_COVERAGE_PASS"
        assert c["y_overlap"] == "Y_OVERLAP_PENDING"


def test_no_full_final_pass_without_Y():
    # even with repo-local coverage passing, the run must NOT claim a full final Stage A′ pass
    res = A.run_all()
    assert res["final_pass"] is False
    assert res["y_overlap"] == "Y_OVERLAP_PENDING"
    assert res["repo_local_coverage_label"] == "STAGE_A_PRIME_COVERAGE_PASS"
    assert res["operator_sanity"]["label"] == "STAGE_A_PRIME_OPERATOR_SANITY_PASS"


def run_all_tests():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed  (repo-local only; no Y, no F-3, no Stage A change)")
    return True


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
