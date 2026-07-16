#!/usr/bin/env python3
"""Deterministic tests for the V2 independent-judge runner — no models required.
Run: python -m pytest test_v2_runner.py -q"""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bsr_rubric as R
import verify_inputs
from mappings import word_occurrences
from phase_worker import extract_json
from run_v2_independent import aggregate

def test_validate_judge():
    occ = [0, 1]
    good = {"profile": "fortitude", "components": [
        {"occurrence_index": 0, "relationship": "opposition", "supporting_evidence": "x", "opposing_evidence": "y",
         "dbr_score": 75, "adjudication": "z"},
        {"occurrence_index": 1, "relationship": "implication", "supporting_evidence": "x", "opposing_evidence": "y",
         "dbr_score": 50, "adjudication": "z"}]}
    assert R.validate_judge(good, occ) == (True, "")
    bad = json.loads(json.dumps(good)); bad["components"][0]["relationship"] = "vibes"
    assert R.validate_judge(bad, occ)[1] == "invented_relationship"
    bad2 = json.loads(json.dumps(good)); bad2["components"][0]["dbr_score"] = 60
    assert R.validate_judge(bad2, occ)[1] == "invalid_score"
    bad3 = json.loads(json.dumps(good)); bad3["components"][0]["supporting_evidence"] = "  "
    assert R.validate_judge(bad3, occ)[1] == "missing_evidence:supporting"

def test_no_relationship_valid_only_at_zero():
    # V2.1 amendment: no_relationship valid IFF dbr_score == 0
    occ = [0]
    ok0 = {"profile": "shank", "components": [
        {"occurrence_index": 0, "relationship": "no_relationship", "supporting_evidence": "x", "opposing_evidence": "y",
         "dbr_score": 0, "adjudication": "no defensible relationship"}]}
    assert R.validate_judge(ok0, occ) == (True, "")
    bad = json.loads(json.dumps(ok0)); bad["components"][0]["dbr_score"] = 25
    assert R.validate_judge(bad, occ)[1] == "no_relationship_requires_zero"
    # honest synonyms canonicalize to no_relationship
    assert R.canonicalize_relationship("none") == ("no_relationship", True)
    assert R.canonicalize_relationship("N/A") == ("no_relationship", True)
    # positive types still fine at score 0
    pos0 = json.loads(json.dumps(ok0)); pos0["components"][0]["relationship"] = "opposition"
    assert R.validate_judge(pos0, occ) == (True, "")

def test_opposition_full_range_allowed():
    # the v2 correction: opposition is a legitimate, full-range relationship (no polarity cap in validation)
    occ = [0]
    o = {"profile": "love", "components": [
        {"occurrence_index": 0, "relationship": "opposition", "supporting_evidence": "x", "opposing_evidence": "y",
         "dbr_score": 100, "adjudication": "clean conventional opposition"}]}
    assert R.validate_judge(o, occ) == (True, "")

def test_canonicalize_typo():
    assert R.canonicalize_relationship("constituitive_property") == ("constitutive_property", True)
    assert R.canonicalize_relationship("opposition") == ("opposition", False)

def test_extract_json():
    assert extract_json('```json\n{"a": 1}\n```')["a"] == 1
    assert extract_json("no json") is None

def test_verify_inputs_ok():
    status, det = verify_inputs.verify()
    assert status == "OK", det
    assert det["n_words"] == 20
    assert det["wordlist_sha256"] == verify_inputs.EXPECT_WORDLIST_SHA

def test_word_occurrences_v2_words():
    wo = word_occurrences("पवन")   # pavana
    mapped = [o for o in wo["occurrences"] if o["is_mapped"]]
    assert len(mapped) >= 2 and all(o["mapping_gloss"] for o in mapped)

def _mk(model, rows):
    # rows: {word: [(occ, rel, score), ...]}
    scores, profiles = [], []
    for w, comps in rows.items():
        cs = [s for _, _, s in comps]
        agg = R.aggregate(cs)
        profiles.append({"word": w, "gloss": w, "judge_model": model, "profile": f"{w}-meaning"})
        scores.append({"word": w, "gloss": w, "category": "afflictive", "judge_model": model,
                       "components": [{"word": w, "occurrence_index": o, "varna": "k", "frozen_mapping": "g",
                                       "relationship": r, "dbr_score": s, "supporting_evidence": "s",
                                       "opposing_evidence": "o", "adjudication": "a", "judge_model": model}
                                      for o, r, s in comps],
                       "mean_dbr": agg["mean"], "min_dbr": agg["min"], "counts": agg["counts"],
                       "weak_components_le_25": agg["weak_components_le_25"],
                       "verdict": R.word_verdict(agg["mean"], agg["min"])})
    return {"judge_model": model, "profiles": profiles, "scores": scores}

def test_aggregate_mechanical():
    qwen = _mk("Q", {"aa": [(0, "opposition", 75), (1, "implication", 50)], "bb": [(0, "implication", 25)]})
    mistral = _mk("M", {"aa": [(0, "opposition", 75), (1, "implication", 25)], "bb": [(0, "opposition", 25)]})
    ag = aggregate(qwen, mistral)
    c = ag["component_agreement"]
    assert c["n_components"] == 3
    assert c["exact_agreement"] == round(2/3, 4)               # aa#0 and bb#0 scores equal
    assert c["within_one_step_agreement"] == 1.0               # only aa#1 differs, by one step (25)
    assert c["signed_mean_diff_Qwen_minus_Mistral"] == round((0+25+0)/3, 2)
    assert ag["relationship_agreement"]["exact"] == 2 and ag["relationship_agreement"]["incompatible"] == 1
    assert ag["word_verdict_agreement"]["n_words"] == 2
    assert ag["model_identity_dependence"] in ("ROLE_STABLE", "MINOR_ROLE_DEPENDENCE", "SIGNIFICANT_ROLE_DEPENDENCE")
