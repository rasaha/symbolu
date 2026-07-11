"""Validation for the development-only native word-mapping review. NO network, NO model.

Asserts: deterministic; word status from the allowed set; no word is called validated/confirmatory; missing
vocalic-ṛ words are flagged; order preserved; authored vowels are DEVELOPMENT_ONLY and consonants
CONFIRMATORY_BACKBONE; binding/liberating come verbatim from the merged lexicon (no new meaning).
"""
import hashlib
import json
import pathlib

import b1_native_word_mapping_review as R

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "b1_native_word_mapping_review"
MERGED = {r["canonical_parser_unit"]: r for r in
          json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))["rows"]}
ALLOWED_STATUS = {"FULLY_RESOLVED_DEVELOPMENT_GRADE", "PARTIALLY_RESOLVED", "CONFIRMATORY_BACKBONE_ONLY",
                  "CONTAINS_MISSING_UNIT", "CONTAINS_CONTRADICTORY_UNIT"}


def test_deterministic():
    R.build(); h1 = hashlib.sha256((OUT / "word_mappings.json").read_bytes()).hexdigest()
    R.build(); h2 = hashlib.sha256((OUT / "word_mappings.json").read_bytes()).hexdigest()
    assert h1 == h2


def test_status_allowed_and_grade_development_only():
    res = R.build()
    for w in res["words"]:
        assert w["word_status"] in ALLOWED_STATUS
    assert "DEVELOPMENT_ONLY" in res["summary"]["grade"]
    blob = (OUT / "summary.json").read_text() + (OUT / "word_mappings.json").read_text()
    for banned in ("VALIDATED", "SEMANTICALLY_CORRECT", "CONFIRMATORY_PASS", "GENUTILITY"):
        assert banned not in blob


def test_vocalic_r_words_flagged_missing():
    res = R.build()
    for w in res["words"]:
        if "ṛ" in w["atomic_varnas"]:
            assert w["word_status"] == "CONTAINS_MISSING_UNIT"
            assert "ṛ" in w["missing_units"]


def test_order_preserved():
    res = R.build()
    for w in res["words"]:
        assert [r["unit"] for r in w["mapping_rows"]] == w["atomic_varnas"]
        assert len(w["binding_sequence"]) == len(w["atomic_varnas"])


def test_scope_and_source_consistency():
    res = R.build()
    for w in res["words"]:
        for r in w["mapping_rows"]:
            if r["type"] == "consonant" and r["scope"] == "CONFIRMATORY_BACKBONE":
                assert r["source"] == "consonant_v3_1"
            if r["type"] == "vowel" and r["scope"] == "DEVELOPMENT_ONLY":
                assert r["source"] == "varna_lens_vowel"
                assert r["provenance"] == "AUTHORED_PROVISIONAL"


def test_no_new_meaning_authored():
    res = R.build()
    for w in res["words"]:
        for r in w["mapping_rows"]:
            if r["scope"] in ("MISSING", "UNRESOLVED", "OUT_OF_SCOPE"):
                continue
            src = MERGED[r["unit"]]
            assert r["binding"] == src["binding_vritti"]
            assert r["liberating"] == src["liberating_vritti"]


def test_structural_ge_confirmatory_per_word():
    res = R.build()
    for w in res["words"]:
        assert w["structural_coverage"] >= w["confirmatory_eligible_coverage"]
