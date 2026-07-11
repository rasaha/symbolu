"""Determinism + integrity tests for the Stage-1 parser→mapping integration audit. NO network, NO model.

Proves: deterministic (byte-identical regeneration), the identity bridge is injective (no varṇa collapse),
order/multiplicity preserved for every audited word, seed words round-trip, and the audit invents no meaning.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL.
"""
import hashlib
import json
import pathlib

import b1_stage1_mapping_integration_audit as A

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "stage1_mapping_integration"
FILES = ("identity_bridge.json", "word_resolution.json", "coverage_summary.json",
         "discrepancies.json", "trackg_decomposition_diff.json", "identity_bridge.csv")
ALLOWED = {"EXACT_ACTIVE", "EXACT_INACTIVE", "ALIASED_EXACT", "MISSING_TABLE_ENTRY", "CONTRADICTORY_ENTRY",
           "UNRESOLVED_IDENTITY", "UNSUPPORTED_ORTHOGRAPHIC_UNIT", "NON_SEMANTIC_MARKER"}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def test_deterministic_regeneration():
    A.build(); h1 = {f: _sha(OUT / f) for f in FILES}
    A.build(); h2 = {f: _sha(OUT / f) for f in FILES}
    assert h1 == h2


def test_bridge_injective_no_collapse():
    res = A.build()
    keys = [b["table_key"] for b in res["bridge"] if b["parser_type"] == "consonant" and b["table_key"]]
    assert len(keys) == len(set(keys)), "two consonants collapse to one key"
    assert len(set(keys)) == 33


def test_all_statuses_allowed():
    res = A.build()
    for b in res["bridge"]:
        assert b["mapping_status"] in ALLOWED
    for w in res["words"] + res["seed_words"]:
        for r in w["atomic_varnas"]:
            assert r["status"] in ALLOWED


def test_order_and_multiplicity_preserved_everywhere():
    res = A.build()
    for w in res["words"] + res["seed_words"]:
        assert w["order_preserved"] is True
        assert w["multiplicity_preserved"] is True


def test_seed_round_trips():
    res = A.build()
    assert all(w["round_trip_ok"] for w in res["seed_words"])


def test_no_fully_mappable_word_with_a_vowel():
    res = A.build()
    for w in res["words"] + res["seed_words"]:
        has_vowel = any(r["type"] == "vowel" for r in w["atomic_varnas"])
        if has_vowel:
            assert w["word_status"] != "FULLY_MAPPABLE"


def test_vowels_and_marks_all_missing():
    res = A.build()
    for b in res["bridge"]:
        if b["parser_type"] in ("vowel", "anusvara", "visarga", "nasalization"):
            assert b["mapping_status"] == "MISSING_TABLE_ENTRY"
            assert b["table_key"] is None


def test_audit_invents_no_meaning():
    # the audit must not emit binding/liberating/pole selections or scores
    blob = "".join((OUT / f).read_text() for f in FILES if f.endswith(".json"))
    for banned in ("GENUTILITY", "ONTOLOGICAL_SIGNAL"):
        assert banned not in blob
    # provenance status labels may appear (they are structural), but no polarity SELECTION or score is emitted
    res = A.build()
    for w in res["words"]:
        for r in w["atomic_varnas"]:
            assert "selected_pole" not in r and "score" not in r


def test_verdict_reflects_full_inventory():
    res = A.build()
    assert res["verdict"] == "BLOCKED_BY_MISSING_VOWEL_AND_MARKER_MAPPINGS"
    assert res["unit_cov"]["vowel_resolved"] == 0
