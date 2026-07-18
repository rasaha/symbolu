"""CPU tests for the T1 C×R×S-LoRA training scaffold (docs/CG_TRAINING_CRS_MISTRAL_PREREG.md).
No GPU, no model load, no embeddings. Validates dataset schema, leakage controls, four-arm config,
disabled symbolic/Bhava/Guna/Vritti/Kosha losses, and the pre-registered decision-label set.
"""
import sys
from pathlib import Path

import pytest

_CGT = Path(__file__).resolve().parent.parent / "scripts" / "conscious_generation_training"
if str(_CGT.parent) not in sys.path:
    sys.path.insert(0, str(_CGT.parent))

from conscious_generation_training import build_crs_sft_dataset as DS    # noqa: E402
from conscious_generation_training import train_mistral_lora_crs as TR   # noqa: E402
from conscious_generation_training import eval_crs_trained_model as EVAL # noqa: E402


# ---- 1+2. dataset examples carry domains and C/R/S/MATCH ------------------------------------------
def test_examples_have_domains_and_crs_fields():
    exs = DS.build_dry_run()
    assert len(exs) >= 4
    for ex in exs:
        assert ex["primary_domain"] and "secondary_domains" in ex and "rejected_domains" in ex
        assert set(("C", "R", "S", "MATCH", "match_available")) <= set(ex["match_trace"])
        assert "prompt" in ex and "target_answer" in ex
        assert "Primary frame:" in ex["prompt"] and "Rejected frames:" in ex["prompt"]


# ---- 6. no Bhava/Guna/Vritti/Kosha fields in examples --------------------------------------------
def test_no_forbidden_fields_in_examples():
    for ex in DS.build_dry_run():
        for k in ex:
            assert not any(b in k.lower() for b in DS.FORBIDDEN_FIELDS)


# ---- 3+4. split leakage controls: unseen terms separated, no target leakage ----------------------
def test_splits_separate_terms_and_no_target_leakage():
    exs = []
    for t in range(12):
        exs.append(DS.make_example(
            {"id": f"e{t}", "term": f"term{t}", "query": "q?",
             "primary_domain": "medicine", "secondary_domains": ["care"], "rejected_domains": ["finance"]},
            f"answer {t}", {"C": None, "R": None, "S": None, "MATCH": None, "match_available": False},
            {"primary_frame_correct": True}, "high_conf_primary"))
    sp = DS.split_examples(exs, seed=1)
    DS.assert_no_leakage(sp)                                  # raises on any term/target leakage
    tr = {e["term"] for e in sp["train"]}
    te = {e["term"] for e in sp["test"]}
    assert tr.isdisjoint(te) and sp["test"]                  # disjoint, non-empty test
    assert any(e["slice"] == "unseen_term" for e in sp["test"])


def test_unseen_domain_forced_into_test_only():
    exs = []
    for t in range(8):
        dom = "astronomy" if t < 2 else "medicine"
        exs.append(DS.make_example(
            {"id": f"e{t}", "term": f"term{t}", "query": "q?", "primary_domain": dom,
             "secondary_domains": [], "rejected_domains": ["finance"]},
            f"answer {t}", {"C": None, "R": None, "S": None, "MATCH": None, "match_available": False},
            {"primary_frame_correct": True}, "high_conf_primary"))
    sp = DS.split_examples(exs, seed=0, unseen_domains=["astronomy"])
    train_terms = {e["term"] for e in sp["train"]}
    astro_terms = {f"term{t}" for t in range(2)}
    assert train_terms.isdisjoint(astro_terms)               # unseen-domain examples never train
    assert sp["_holdout"]["unseen_domains"] == ["astronomy"]


def test_leakage_detector_catches_shared_target():
    sp = {"train": [{"term": "a", "target_answer": "X"}],
          "val": [], "test": [{"term": "b", "target_answer": "X"}]}
    with pytest.raises(AssertionError, match="target_answer leakage"):
        DS.assert_no_leakage(sp)


# ---- 5. four-arm config present ------------------------------------------------------------------
def test_four_arms_present():
    assert set(EVAL.ARMS) == {"A", "B", "C", "D"}
    assert EVAL.ARMS["B"]["wrapper"] is True and EVAL.ARMS["C"]["model"] == "crs_lora"
    assert EVAL.ARMS["A"] == {"model": "base", "wrapper": False}


# ---- 6. T1 boundaries: symbolic head + Bhava/Guna/Vritti/Kosha losses disabled -------------------
def test_t1_config_boundaries_enforced():
    cfg = TR.t1_config()
    assert cfg.enable_symbolic_head_32d is False
    assert cfg.lambda_bhava == cfg.lambda_guna == cfg.lambda_vritti == cfg.lambda_kosha == 0.0
    cfg.assert_t1_boundaries()                               # no raise
    with pytest.raises(AssertionError, match="32-D symbolic head"):
        TR.t1_config(enable_symbolic_head_32d=True)
    with pytest.raises(AssertionError, match="Guna/Vritti/Kosha"):
        TR.t1_config(lambda_guna=0.1)


# ---- 7. decision labels are exactly the pre-registered set ---------------------------------------
def test_decision_label_set_and_used():
    expected = {"CG_TRAINING_CRS_ADDS_VALUE", "CG_TRAINING_CRS_NO_INCREMENTAL_VALUE",
                "CG_TRAINING_WRAPPER_STILL_BEST", "CG_TRAINING_DEGRADES_FACTUALITY",
                "CG_TRAINING_OVERFITS_FRAMES", "CG_TRAINING_INSUFFICIENT_DATA",
                "CG_TRAINING_ENV_UNAVAILABLE"}
    assert set(EVAL.DECISIONS) == expected
    # the four-arm gate returns only pre-registered labels
    base = {"primary_frame_correct": 0.6, "rejected_domain_avoidance": 0.85, "factuality_preserved": 0.95,
            "clarity_usefulness": 0.9, "generalization_to_unseen_terms": 0.5,
            "generalization_to_unseen_domains": 0.5}
    arms = {"A": base,
            "B": {**base, "primary_frame_correct": 0.74, "rejected_domain_avoidance": 0.91},
            "C": {**base, "primary_frame_correct": 0.70, "rejected_domain_avoidance": 0.88,
                  "generalization_to_unseen_terms": 0.62},
            "D": {**base, "primary_frame_correct": 0.75, "rejected_domain_avoidance": 0.92}}
    label, _ = EVAL.decide(arms)
    assert label in expected


def test_gate_flags_factuality_degradation():
    base = {"primary_frame_correct": 0.6, "rejected_domain_avoidance": 0.85, "factuality_preserved": 0.95,
            "clarity_usefulness": 0.9, "generalization_to_unseen_terms": 0.5,
            "generalization_to_unseen_domains": 0.5}
    arms = {"A": base, "B": base,
            "C": {**base, "primary_frame_correct": 0.7, "rejected_domain_avoidance": 0.9,
                  "factuality_preserved": 0.80},                # factuality dropped
            "D": base}
    label, _ = EVAL.decide(arms)
    assert label == "CG_TRAINING_DEGRADES_FACTUALITY"


def test_gate_wrapper_still_best():
    base = {"primary_frame_correct": 0.6, "rejected_domain_avoidance": 0.85, "factuality_preserved": 0.95,
            "clarity_usefulness": 0.9, "generalization_to_unseen_terms": 0.5,
            "generalization_to_unseen_domains": 0.5}
    arms = {"A": base,
            "B": {**base, "primary_frame_correct": 0.80, "rejected_domain_avoidance": 0.93},
            "C": {**base, "primary_frame_correct": 0.66, "rejected_domain_avoidance": 0.87,
                  "generalization_to_unseen_terms": 0.55},
            "D": {**base, "primary_frame_correct": 0.79, "rejected_domain_avoidance": 0.92}}
    label, _ = EVAL.decide(arms)
    assert label in ("CG_TRAINING_WRAPPER_STILL_BEST", "CG_TRAINING_CRS_NO_INCREMENTAL_VALUE")


# ---- aggregate() maps the validated rubric to the gate metrics (pure, CPU) -----------------------
def _rub(pfc, rda, fact=1.0, clar=1.0, promo=0.0, mir=1.0):
    return {"primary_frame_correct": pfc, "rejected_domain_avoidance": rda, "factuality_preserved": fact,
            "answer_clarity_proxy": clar, "rejected_domain_promotion": promo, "must_include_recall": mir}


def test_aggregate_maps_rubric_to_gate_metrics():
    per = []
    for i in range(6):
        sl = "unseen_term" if i >= 4 else "high_conf_primary"
        per.append({"id": f"e{i}", "slice": sl, "primary_domain": "medicine",
                    "scores": {"A": _rub(0.0, 0.5), "B": _rub(1.0, 1.0),
                               "C": _rub(1.0, 1.0), "D": _rub(1.0, 1.0)},
                    "answer_len": {"A": 20, "B": 25, "C": 25, "D": 25}})
    m = EVAL.aggregate(per)
    assert m["A"]["primary_frame_correct"] == 0.0 and m["C"]["primary_frame_correct"] == 1.0
    assert m["C"]["rejected_domain_leak_rate"] == 0.0          # 1 - avoidance(1.0)
    assert m["C"]["generalization_to_unseen_terms"] == 1.0     # unseen-term slice mean
    assert m["C"]["n"] == 6
    # end-to-end: C beats A, generalizes, approaches B -> ADDS_VALUE
    label, _ = EVAL.decide(m)
    assert label == "CG_TRAINING_CRS_ADDS_VALUE"


def test_bootstrap_delta_shape():
    per = [{"scores": {"C": _rub(1.0, 1.0), "B": _rub(0.0, 0.0)}} for _ in range(10)]
    d = EVAL.bootstrap_delta(per, "primary_frame_correct", "C", "B", n_boot=300, seed=0)
    assert set(d) == {"delta", "ci_low", "ci_high", "excludes_zero"}
    assert d["delta"] == 1.0 and d["excludes_zero"] is True
