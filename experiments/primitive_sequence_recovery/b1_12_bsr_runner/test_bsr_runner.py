#!/usr/bin/env python3
"""Deterministic tests for the B1.12 BSR runner — no models required. Run: python -m pytest test_bsr_runner.py -q"""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bsr_rubric as R
import verify_inputs
from mappings import word_occurrences
from run_crossover import extract_json

# ---- aggregation & verdict thresholds (frozen) ----
def test_aggregate_and_verdict():
    a = R.aggregate([100, 75, 50]); assert a["mean"] == 75.0 and a["min"] == 50
    assert R.word_verdict(75.0, 50) == "STRONG_RESONANCE"
    assert R.word_verdict(75.0, 25) == "MODERATE_RESONANCE"   # min<50 blocks STRONG
    assert R.word_verdict(50.0, 50) == "MODERATE_RESONANCE"
    assert R.word_verdict(49.9, 25) == "WEAK_RESONANCE"
    assert R.word_verdict(29.9, 0) == "MINIMAL_RESONANCE"
    assert R.word_verdict(14.9, 0) == "NO_RESONANCE"

def test_holistic_only_flag():
    assert R.holistic_only(80, 40) is True
    assert R.holistic_only(80, 55) is False   # mean not weak
    assert R.holistic_only(50, 40) is False

def test_bsr_scale_enforced():
    try:
        R.aggregate([100, 60]); assert False
    except AssertionError:
        pass

# ---- validation reject reasons (never for unfavorable score) ----
def test_validate_author():
    occ = [0, 1]
    good = {"profile": "peace", "components": [
        {"occurrence_index": 0, "supporting_evidence": "x", "opposing_evidence": "y", "proposed_relationship": "embodiment"},
        {"occurrence_index": 1, "supporting_evidence": "x", "opposing_evidence": "y", "proposed_relationship": "opposition"}]}
    assert R.validate_author(good, occ) == (True, "")
    bad = json.loads(json.dumps(good)); bad["components"][0]["proposed_relationship"] = "vibes"
    assert R.validate_author(bad, occ)[1] == "invented_relationship"
    bad2 = json.loads(json.dumps(good)); bad2["components"][0]["supporting_evidence"] = "  "
    assert R.validate_author(bad2, occ)[1] == "missing_evidence:supporting"

def test_validate_scorer():
    occ = [0]; glosses = {0: "GLOSS"}
    good = {"components": [{"occurrence_index": 0, "final_relationship": "implication", "bsr_score": 75,
                           "adjudication": "ok"}], "combined_reconciliation": 60}
    assert R.validate_scorer(good, occ, glosses) == (True, "")
    bad = json.loads(json.dumps(good)); bad["components"][0]["bsr_score"] = 60
    assert R.validate_scorer(bad, occ, glosses)[1] == "invalid_score"
    bad2 = json.loads(json.dumps(good)); bad2["components"][0]["mapping_gloss"] = "CHANGED"
    assert R.validate_scorer(bad2, occ, glosses)[1] == "modified_mapping_gloss"

# ---- agreement + role rule ----
def test_relationship_and_score_agreement():
    assert R.relationship_agreement("embodiment", "embodiment") == "exact"
    assert R.relationship_agreement("embodiment", "constitutive_property") == "compatible"
    assert R.relationship_agreement("embodiment", "opposition") == "incompatible"
    assert R.score_step_agreement(75, 50) == {"exact": False, "within_one_step": True, "abs_diff": 25, "ge50": False}
    assert R.score_step_agreement(100, 25)["ge50"] is True

def test_canonicalize_relationship():
    # exact match: no coercion
    assert R.canonicalize_relationship("embodiment") == ("embodiment", False)
    # the observed Mistral typo (extra 'i') -> unique nearest within edit distance 2
    assert R.canonicalize_relationship("constituitive_property") == ("constitutive_property", True)
    # case / separator normalization
    assert R.canonicalize_relationship("Natural-Consequence") == ("natural_consequence", True)
    # semantically distinct / non-vocab token -> rejected (no coercion), caller flags invented_relationship
    assert R.canonicalize_relationship("vibes") == (None, False)
    assert R.canonicalize_relationship("causation") == (None, False)
    assert R.canonicalize_relationship(None) == (None, False)

def test_role_dependence_bands():
    assert R.role_dependence(0.9, 0.9, 0, 3) == "ROLE_STABLE"
    assert R.role_dependence(0.9, 0.9, 0, 20) == "SIGNIFICANT_ROLE_DEPENDENCE"   # systematic
    assert R.role_dependence(0.7, 0.7, 1, 3) == "MINOR_ROLE_DEPENDENCE"
    assert R.role_dependence(0.5, 0.9, 0, 3) == "SIGNIFICANT_ROLE_DEPENDENCE"
    assert R.role_dependence(0, 0, 0, 0, invalid=True) == "RUN_INVALID"

def test_cross_run_indeterminate():
    assert R.cross_run_word_indeterminate("STRONG_RESONANCE", "WEAK_RESONANCE", 80, 40) is True   # 2 bands
    assert R.cross_run_word_indeterminate("STRONG_RESONANCE", "MODERATE_RESONANCE", 80, 70) is False

def test_extract_json():
    assert extract_json('```json\n{"a": 1}\n```')["a"] == 1
    assert extract_json('sure!\n{"a": {"b": 2}} done')["a"]["b"] == 2
    assert extract_json("no json here") is None

# ---- integration: frozen inputs verify OK; parser+glosses available ----
def test_verify_inputs_ok():
    status, det = verify_inputs.verify()
    assert status == "OK", det
    assert det["n_words"] == 20
    assert det["wordlist_sha256"] == verify_inputs.EXPECT_WORDLIST_SHA

def test_word_occurrences_glosses_present():
    wo = word_occurrences("कपट")   # kapaṭa
    mapped = [o for o in wo["occurrences"] if o["is_mapped"]]
    assert len(mapped) == 3 and all(o["mapping_gloss"] for o in mapped)
