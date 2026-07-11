"""Completeness + leakage-prevention + determinism tests for the word-specificity preregistration. NO network, NO model."""
import hashlib
import json
import pathlib

import b1_native_word_specificity_prereg as PR

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "native_word_specificity_prereg"
CONS = {"k", "kh", "g", "gh", "ṅ", "c", "ch", "j", "jh", "ñ", "ṭ", "ṭh", "ḍ", "ḍh", "ṇ", "t", "th", "d", "dh", "n",
        "p", "ph", "b", "bh", "m", "y", "r", "l", "v", "ś", "ṣ", "s", "h"}
REQUIRED = ["set_A_manifest.json", "set_B_manifest.json", "packet_rendering_spec.json", "leakage_controls.json",
            "arm_control_spec.json", "evaluator_prompt_spec.json", "randomization_manifest_schema.json",
            "analysis_plan.json", "outcome_taxonomy.json", "success_criteria.json", "freeze_index.json"]


def test_all_deliverables_present():
    PR.build()
    for f in REQUIRED:
        assert (OUT / f).exists()


def test_sets_frozen_and_disjoint_from_each_other():
    PR.build()
    a = json.load(open(OUT / "set_A_manifest.json", encoding="utf-8"))["words"]
    b = json.load(open(OUT / "set_B_manifest.json", encoding="utf-8"))["words"]
    assert a == ["aśva", "bala", "bhaya", "duḥkha", "gaja", "megha"]
    assert len(a) == 6 and len(b) == 6
    assert not (set(a) & set(b))                       # sets independent


def test_packets_contain_no_consonant_symbol():
    PR.build()
    for f in ("set_A_manifest.json", "set_B_manifest.json"):
        d = json.load(open(OUT / f, encoding="utf-8"))
        for w, p in d["packets"].items():
            for feat in p["packet_features"]:
                assert "unit" not in feat and "devanagari" not in feat
                assert set(feat.keys()) == {"feature_index", "binding", "liberating"}


def test_candidate_representation_hides_spelling():
    spec = json.load(open(OUT / "evaluator_prompt_spec.json", encoding="utf-8"))
    rep = spec["candidate_representation"].lower()
    assert "english" in rep and "gloss" in rep
    assert "no devanāgarī" in spec["candidate_representation_rationale"].lower() or \
           "no devanagari" in spec["candidate_representation_rationale"].lower()


def test_english_only_render_required():
    spec = json.load(open(OUT / "packet_rendering_spec.json", encoding="utf-8"))
    rules = " ".join(spec["rules"]).lower()
    assert "english-only" in rules and "vṛtti proper-name" in " ".join(spec["rules"])
    lk = json.load(open(OUT / "leakage_controls.json", encoding="utf-8"))
    assert "sanskrit_vritti_name_reverse_map" in lk["blocked_shortcuts"]


def test_primary_contrast_is_true_minus_max_control():
    ap = json.load(open(OUT / "analysis_plan.json", encoding="utf-8"))
    c = ap["primary_contrast"]
    assert "Accuracy(T)" in c and "max(" in c
    for arm in ("X", "R", "G", "F"):
        assert f"Accuracy({arm})" in c
    assert "1/6" in ap["primary_endpoint"]


def test_success_criteria_conjunctive_and_two_sets():
    sc = json.load(open(OUT / "success_criteria.json", encoding="utf-8"))["conjunctive_all_required"]
    blob = " ".join(sc)
    assert "Set A" in blob and "Set B" in blob
    assert any("above chance" in s for s in sc) and any("above ALL controls" in s or "above all controls" in s for s in sc)


def test_arms_present():
    arms = json.load(open(OUT / "arm_control_spec.json", encoding="utf-8"))["arms"]
    for a in ("T_true", "X_cross_word_mismatch", "S_scrambled_order", "R_random_varna_assignment",
              "G_generic_matched", "F_feature_only"):
        assert a in arms


def test_no_vowel_or_authored_provisional_in_packets():
    m = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
    dev = {r["canonical_parser_unit"] for r in m["rows"] if r["activation_scope"] == "DEVELOPMENT_ONLY"}
    for f in ("set_A_manifest.json", "set_B_manifest.json"):
        d = json.load(open(OUT / f, encoding="utf-8"))
        for w, p in d["packets"].items():
            # every feature's binding/liberating text must come from a CONFIRMATORY consonant row, never a dev vowel
            cb_bind = {v[0] for v in PR.CB.values()}
            for feat in p["packet_features"]:
                assert feat["binding"] in cb_bind


def test_deterministic_freeze():
    PR.build(); h1 = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in REQUIRED}
    PR.build(); h2 = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in REQUIRED}
    assert h1 == h2
    fi = json.load(open(OUT / "freeze_index.json", encoding="utf-8"))
    assert fi["readiness_verdict"] == "READY_FOR_PACKET_AUTHORING_AND_FREEZE"


def test_no_experiment_or_judge_in_source():
    src = (HERE / "b1_native_word_specificity_prereg.py").read_text()
    for banned in ("openai", "HfApi", "import torch", "transformers", "requests.post", "judge(", "run_real"):
        assert banned not in src
