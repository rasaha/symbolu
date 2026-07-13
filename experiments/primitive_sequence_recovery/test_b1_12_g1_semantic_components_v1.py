"""Deterministic tests for B1.12 Gate-G1 V1.2 ordered component-descriptor instrument. No judges, no run.

Covers: inventory extraction; 100% source-backed coverage; verbatim source fidelity; firewall (descriptors keyed
only by (type,unit), no selected-word meaning present); descriptor length/tier leakage detection; affliction-
domain / neutrality failure; A/B/D render-spec parity fields; verdict; and that G0/pool/lexicon are untouched.
"""
import hashlib
import json
import pathlib

import b1_12_g1_semantic_components_v1 as S

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "b1_12_g1_semantic_components_v1"

# regenerate deterministically
S.stage1_inventory()
S.stage2_descriptors()
_RES = S.stage3_audit()


def _j(name):
    return json.loads((OUT / name).read_text())


def test_inventory_18_identities():
    inv = _j("required_varna_inventory.json")
    assert inv["n_distinct_identities"] == 18
    assert set(inv["vowels"]) == {"a", "ā", "i", "ī", "e", "ū"}
    assert len(inv["consonants"]) == 12


def test_coverage_complete_source_backed():
    cov = _j("coverage_report.json")
    assert cov["selected_set_coverage_pct"] == 100.0
    assert cov["coverage_outcome"] == "G1_COMPONENT_COVERAGE_COMPLETE"
    assert cov["n_developmental_gap"] == 0


def test_descriptors_verbatim_from_frozen_binding_pole():
    lex = {r["canonical_parser_unit"]: r for r in
           json.loads((HERE / "frozen" / "varna_native_stage1_merged_v1.json").read_text())["rows"]}
    for e in _j("component_descriptor_map_draft.json")["entries"]:
        u = e["atomic_identity"].split(":")[1]
        assert e["original_frozen_gloss"] == lex[u]["binding_vritti"]      # exact verbatim, fixed pole
        assert e["source_tier"] == "A_SOURCE_BACKED"


def test_firewall_no_selected_word_meaning_in_descriptor_map():
    # descriptors are authored per (type,unit) only; assert no selected word's IAST or ordinary gloss appears as
    # a standalone token in the descriptor content (word-boundary match; incidental substrings like
    # 'bone' within 'CONFIRMATORY_BACKBONE' are not leaks).
    import re
    pool = json.loads((HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json").read_text())["words"]
    sel = {"W03", "W15", "W20", "W23", "W30", "W35"}
    words = [w for w in pool if w["id"] in sel]
    # inspect only the authored descriptor text, not provenance/scope metadata
    descs = " ".join(e["original_frozen_gloss"] + " " + e["normalized_component_descriptor"]
                     for e in _j("component_descriptor_map_draft.json")["entries"]).lower()
    for w in words:
        for token in (w["iast"].lower(), w["gloss"].lower()):
            assert not re.search(r"\b" + re.escape(token) + r"\b", descs), (w["id"], token)


def test_length_and_tier_leakage_detected():
    q = _j("descriptor_quality_audit.json")
    assert q["vowel_length_range"][1] < q["consonant_length_range"][0]     # disjoint -> C/V leak
    assert q["length_leakage_vowel_vs_consonant_disjoint"] is True
    assert q["source_tier_leakage_dev_vs_conf_disjoint"] is True
    assert "DESCRIPTOR_LENGTH_LEAKAGE" in q["quality_outcomes"]
    assert "DESCRIPTOR_SOURCE_TIER_LEAKAGE" in q["quality_outcomes"]


def test_affliction_domain_neutrality_failure():
    q = _j("descriptor_quality_audit.json")
    assert q["n_affliction_tendency"] >= 11
    assert q["domain_match"] is False
    assert q["candidate_meaning_domain"] == "ordinary_concrete_referent"
    assert "DESCRIPTOR_NEUTRALITY_FAILURE" in q["quality_outcomes"]


def test_render_spec_parity_fields():
    rs = _j("arm_render_spec.json")
    assert rs["arm_B_scramble"]["same_multiset"] and rs["arm_B_scramble"]["must_differ_from_A"]
    assert rs["arm_B_scramble"]["no_resample_after_output"] is True
    assert rs["arm_D_unordered_inventory"]["no_pronunciation_order_semantics"] is True
    for banned in ("progression/causal language", "connectives between positions"):
        assert banned in rs["prohibited"]


def test_verdict_blocked_descriptor_quality():
    v = _j("g1_v1_2_verdict.json")
    assert v["verdict"] == "G1_BLOCKED_DESCRIPTOR_QUALITY"
    assert v["coverage_complete"] is True and v["descriptor_ready"] is False and v["domain_match"] is False


def test_g0_pool_lexicon_untouched():
    assert hashlib.sha256((HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json").read_bytes()
                          ).hexdigest() == "8cf857891f95bb07e66a3048f7eabe4f1e5814777889abdf6dadb0d5d296d0b4"
    assert hashlib.sha256((HERE / "sanskrit_stage1_parser.py").read_bytes()).hexdigest() == \
        "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947"
