"""Deterministic tests for B1.12 Gate-G1 v1.2 (normalized ordered semantic-component instrument). No judges."""
import hashlib
import json
import pathlib
import re
from collections import Counter

import b1_12_g1_semantic_components_v1_2 as S

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "b1_12_g1_semantic_components_v1_2"

S.stage1_inventory()
S.stage2_descriptors()
_R = S.stage3_audit()


def _j(n):
    return json.loads((OUT / n).read_text())


def test_coverage_100_and_no_unmapped():
    cov = _j("coverage_report.json")
    assert cov["selected_set_coverage_pct"] == 100.0
    assert cov["coverage_outcome"] == "G1_COMPONENT_COVERAGE_COMPLETE"
    assert cov["n_developmental_gap"] == 0 and cov["n_unmapped"] == 0


def test_schema_completeness_and_stable_ids():
    entries = _j("component_descriptor_map.json")["entries"]
    fields = {"atomic_identity", "stable_component_id", "source_tier", "source_status",
              "original_frozen_gloss", "normalized_component_descriptor", "source_reference",
              "source_hash", "review_status", "development_only", "notes"}
    ids = [e["stable_component_id"] for e in entries]
    assert len(entries) == 18 and len(set(ids)) == 18
    for e in entries:
        assert fields <= set(e) and e["normalized_component_descriptor"]


def test_source_backed_fidelity_verbatim():
    lex = {r["canonical_parser_unit"]: r for r in
           json.loads((HERE / "frozen" / "varna_native_stage1_merged_v1.json").read_text())["rows"]}
    for e in _j("component_descriptor_map.json")["entries"]:
        u = e["atomic_identity"].split(":")[1]
        assert e["original_frozen_gloss"] == lex[u]["binding_vritti"]      # exact verbatim, binding pole


def test_no_prohibited_progression_terms():
    q = _j("descriptor_quality_audit.json")
    assert q["prohibited_progression_term_hits"] == {}


def test_abd_multiset_equal_and_order_relations():
    arms = _j("arm_render_examples.json")["arms"]
    for c, a in arms.items():
        assert a["A_multiset_ids"] == a["B_multiset_ids"] == a["D_multiset_ids"]   # identical component multiset
        assert a["A_true_order"] != a["B_order_scramble"]                          # A/B order differs
        d_ids = [ln.split(": ", 1)[1] for ln in a["D_unordered_inventory"]]
        # D is canonical (its component-id order is sorted)
        assert a["D_multiset_ids"] == sorted(a["D_multiset_ids"])


def test_identical_template_footprint_and_masked_parity():
    arms = _j("arm_render_examples.json")["arms"]
    for c, a in arms.items():
        n = len(a["A_true_order"])
        assert len(a["B_order_scramble"]) == len(a["D_unordered_inventory"]) == n
        # every line begins with the position tag skeleton
        for arm in ("A_true_order", "B_order_scramble", "D_unordered_inventory"):
            assert all(re.match(rf"position {i+1}: ", a[arm][i]) for i in range(n))
        assert a["masked"] == [f"position {i+1}: {S.MASK}" for i in range(n)]      # masked parity


def test_repetition_preserved_by_multiset_length():
    arms = _j("arm_render_examples.json")["arms"]
    for c, a in arms.items():
        assert len(a["A_true_order"]) == len(a["A_multiset_ids"])   # repeats (if any) preserved as duplicate ids


def test_no_target_word_transliteration_in_renders():
    pool = {w["id"]: w for w in json.loads(
        (HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json").read_text())["words"]}
    arms = _j("arm_render_examples.json")["arms"]
    blob = json.dumps(arms, ensure_ascii=False).lower()
    for c in S.SELECTED:
        for tok in (pool[c]["iast"].lower(), pool[c]["gloss"].lower()):
            assert not re.search(r"\b" + re.escape(tok) + r"\b", blob), (c, tok)


def test_raw_sanskrit_terms_flagged_as_leak_vector():
    q = _j("descriptor_quality_audit.json")
    assert len(q["raw_sanskrit_term_descriptors"]) >= 5      # affliction glosses embed raw Sanskrit terms


def test_descriptor_duplicate_and_length_tier_leakage():
    q = _j("descriptor_quality_audit.json")
    assert q["exact_duplicates"] == 0
    assert q["length_leakage_vowel_vs_consonant_disjoint"] is True   # persists after normalization (37>36)
    assert q["source_tier_leakage_disjoint"] is True
    assert "DESCRIPTOR_LENGTH_LEAKAGE" in q["quality_outcomes"]
    assert "DESCRIPTOR_NEUTRALITY_FAILURE" in q["quality_outcomes"]


def test_domain_mismatch_and_unordered_identifies_word():
    q = _j("descriptor_quality_audit.json")
    m = _j("g1_v1_2_manifest.json")
    assert q["domain_match"] is False and q["n_affliction_tendency"] >= 15
    assert m["unordered_inventory_identifies_word"] is True   # distinct inventories -> no order headroom
    assert m["abd_parity_multiset_equal"] is True


def test_verdict_blocked_descriptor_quality():
    m = _j("g1_v1_2_manifest.json")
    assert m["verdict"] == "G1_BLOCKED_DESCRIPTOR_QUALITY"
    assert m["coverage"]["outcome"] == "G1_COMPONENT_COVERAGE_COMPLETE"
    assert m["length_leakage_persists_after_normalization"] is True


def test_deterministic_rerun_and_inputs_untouched():
    b1 = (OUT / "arm_render_examples.json").read_bytes()
    S.stage1_inventory(); S.stage2_descriptors(); S.stage3_audit()
    assert (OUT / "arm_render_examples.json").read_bytes() == b1
    assert hashlib.sha256((HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json").read_bytes()
                          ).hexdigest() == "8cf857891f95bb07e66a3048f7eabe4f1e5814777889abdf6dadb0d5d296d0b4"
    assert hashlib.sha256((HERE / "sanskrit_stage1_parser.py").read_bytes()).hexdigest() == \
        "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947"
