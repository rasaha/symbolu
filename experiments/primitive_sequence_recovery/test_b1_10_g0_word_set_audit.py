"""Determinism + rule-compliance tests for the Gate G0 word-set distinctness audit. NO network, NO model.

Proves: deterministic (repeat run identical, order-independent); the frozen rule constants and tie-break are
applied; the facet↔varṇa bijection holds; semantic correctness is never inspected; no frozen artifact / run01
is modified; and the reported status is one of the four allowed values with a null selection when not testable.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import itertools
import json
import pathlib

import b1_10_g0_word_set_audit as G

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "b1_10_g0_audit"
ALLOWED_STATUS = {"G0_PASS_WORD_SET_SELECTED", "G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS",
                  "G0_BLOCKED_MISSING_SEMANTIC_SIM_SPEC", "G0_BLOCKED_INCOMPLETE_TIEBREAKER"}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _artifact_hashes():
    return {f: _sha(OUT / f) for f in ("candidate_table.json", "pairwise_binding.json",
                                       "pairwise_liberating.json", "combined_distinctness.json", "selection.json")}


def test_status_allowed_and_no_best_effort_selection():
    s = G.run_audit()
    assert s["status"] in ALLOWED_STATUS
    if s["status"] != "G0_PASS_WORD_SET_SELECTED":
        assert s["selected_word_set"] is None            # no best-effort set when not testable/blocked


def test_repeated_run_identical_hashes():
    G.run_audit(); h1 = _artifact_hashes()
    G.run_audit(); h2 = _artifact_hashes()
    assert h1 == h2, "audit outputs are not byte-identical across runs"


def test_order_independent():
    canonical = G.run_audit()
    saved = G.CANDIDATE_POOL
    try:
        G.CANDIDATE_POOL = sorted(saved, reverse=True)   # different input order
        permuted = G.run_audit()
        for k in ("status", "n_valid_candidates", "valid_candidates", "n_eligible_subsets", "selected_word_set"):
            assert permuted[k] == canonical[k], f"order changed {k}"
    finally:
        G.CANDIDATE_POOL = saved
        G.run_audit()                                    # restore canonical artifacts on disk


def test_rule_constants_frozen():
    assert G.K == 6
    assert G.MAX_FACET_JACCARD_CAP == 0.34
    assert G.MEAN_FACET_JACCARD_CAP == 0.20


def test_facet_varna_bijection():
    recs = {w: G.candidate_record(w) for w in G.CANDIDATE_POOL}
    valid = [w for w in G.CANDIDATE_POOL if recs[w]["valid_both_poles"]]
    for a, b in itertools.combinations(sorted(valid), 2):
        m = G.pair_metrics(recs[a], recs[b])
        assert m["facet_jaccard_binding"] == m["facet_jaccard_liberating"] == m["facet_jaccard"]


def test_valid_candidates_all_covered():
    recs = {w: G.candidate_record(w) for w in G.CANDIDATE_POOL}
    for w, r in recs.items():
        if r["valid_both_poles"]:
            assert not r["missing_varnas"] and r["facet_count"] >= 1


def test_eligibility_enforces_unique_facet_and_caps():
    # any eligible subset must satisfy caps AND per-word >=1 unique facet
    recs = {w: G.candidate_record(w) for w in G.CANDIDATE_POOL}
    valid = sorted(w for w in G.CANDIDATE_POOL if recs[w]["valid_both_poles"] and not recs[w]["leakage"])
    pair_j, pair_lex = {}, {}
    for a, b in itertools.combinations(valid, 2):
        m = G.pair_metrics(recs[a], recs[b]); pair_j[(a, b)] = m["facet_jaccard"]; pair_lex[(a, b)] = m["lexical_jaccard_mean"]
    for s in itertools.combinations(valid, 6):
        e = G.evaluate_subset(s, recs, pair_j, pair_lex)
        if e["eligible"]:
            assert e["max_facet_jaccard"] <= 0.34 and e["mean_facet_jaccard"] <= 0.20
            assert all(c >= 1 for c in e["unique_facet_counts"].values())


def test_semantic_correctness_never_inspected():
    s = G.run_audit()
    assert s["semantic_correctness_inspected"] is False
    assert "PENDING_SUPPLEMENTARY" in s["semantic_similarity_status"]


def test_no_network_or_model_imports():
    src = (HERE / "b1_10_g0_word_set_audit.py").read_text()
    for banned in ("import torch", "import transformers", "openai", "\nimport requests", "HfApi", "SentenceTransformer"):
        assert banned not in src


def test_frozen_artifacts_unchanged():
    G.run_audit()
    checks = {
        "frozen/b1_10_control_ext_items_v3_qwen.json": "885fc2f95627b0d35612ef5acdfedde2e5f068b8fac577a373b05f2f4ec04f3a",
        "frozen/b1_10_control_ext_v3_HARDENED_EVIDENCE_FREEZE_DECLARED.json": "e71889d44e90a86e11fb5fbe3a1db3d49b03db630aaba35d8a00233f596e0181",
        "frozen/b1_10_control_ext_items.json": "df76b7feb1aa8534f5bd62c57b429478f8ea523911ad0bd6bb38f556f2a00ba9",
        "B1_10_CONTROL_EXT_V3_RESULTS.md": None,   # existence only (content may legitimately differ across edits)
    }
    for f, exp in checks.items():
        assert (HERE / f).exists()
        if exp:
            assert _sha(HERE / f) == exp
