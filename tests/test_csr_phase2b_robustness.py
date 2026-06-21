"""CPU tests for Phase 2B robustness validation (rubric YAML, v2 dataset, judge, runner).

No torch/network; deterministic + stub only. Validates that the pre-registered rubric is locked, the
held-out dataset is well-formed, the judge output schema is stable and negation-aware, the runner's
metrics/deltas/stratification are correct, and Phase 1 thresholds are untouched.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import CSRThresholds, DOMAIN_TEMPLATES  # noqa: E402
from csr_match_filter import judge_adapter as JU  # noqa: E402
from csr_match_filter import eval_framed_answers_robustness as R  # noqa: E402

RUBRIC = R.load_rubric(R._RUBRIC)
DATA = R.load_data(R._DATA)
JUDGE_KEYS = {"primary_frame_correct", "secondary_handling_correct", "rejected_domain_avoidance",
              "phoneme_overreach", "factuality_preserved", "clarity_score", "must_include_recall",
              "must_not_violation_rate", "reasons"}


# --- rubric pre-registration ----------------------------------------------------------------------

def test_rubric_is_versioned_and_locked():
    assert RUBRIC.get("version") == "framed_answer_rubric_v1"
    assert RUBRIC.get("locked") is True


def test_rubric_yaml_encodes_the_five_rules_and_metrics():
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load(R._RUBRIC.read_text())
    rule_names = {r["name"] for r in cfg["rules"]}
    assert {"overreach_requires_assertion", "refutation_is_not_a_leak",
            "secondary_promotion_is_framing_error", "factuality_independent_of_frame"} <= rule_names
    for m in ("primary_frame_correct", "rejected_domain_avoidance", "phoneme_overreach",
              "factuality_preserved", "trace_completeness"):
        assert m in cfg["metrics"]


# --- dataset v2 schema ----------------------------------------------------------------------------

def test_dataset_v2_size_and_schema():
    assert len(DATA) >= 105
    req = ("id", "query", "candidate_domains", "expected_primary", "expected_secondary",
           "expected_rejected", "must_include", "may_include", "must_not_include", "answer_type",
           "ambiguity_type", "unknown_terms", "notes")
    ids = set()
    for r in DATA:
        for k in req:
            assert k in r, f"{r.get('id')}: missing {k}"
        assert r["id"] not in ids
        ids.add(r["id"])
        cand = set(r["candidate_domains"])
        assert all(d in DOMAIN_TEMPLATES for d in cand)
        assert set(r["expected_primary"]) <= cand and set(r["expected_rejected"]) <= cand
        assert not (set(r["expected_primary"]) & set(r["expected_rejected"]))


def test_dataset_v2_covers_categories():
    cats = {r.get("category") for r in DATA}
    for c in ("ordinary", "polysemy", "unknown", "rejected_avoidance", "secondary", "adversarial",
              "factual"):
        assert c in cats


# --- judge output schema + negation-awareness -----------------------------------------------------

def test_deterministic_judge_output_schema():
    j = JU.DeterministicRubricJudge(RUBRIC)
    ex = {"expected_primary": ["medicine"], "expected_secondary": [], "expected_rejected": ["fruit"],
          "must_include": ["doctor medicine"], "must_not_include": ["doctor is a fruit"],
          "dominant_terms": ["doctor"]}
    out = j.score("q", "A doctor practices medicine and medical healing.", ex, ["doctor"])
    assert JUDGE_KEYS <= set(out)
    assert isinstance(out["primary_frame_correct"], bool) and isinstance(out["clarity_score"], float)


def test_stub_judge_schema():
    out = JU.StubJudge().score("q", "some answer text here", {}, [])
    assert JUDGE_KEYS <= set(out) and out["primary_frame_correct"] is True


def test_judge_refutation_not_a_leak_and_overreach_is_assertion():
    j = JU.DeterministicRubricJudge(RUBRIC)
    ex = {"expected_primary": ["medicine"], "expected_secondary": [], "expected_rejected": ["fruit"],
          "must_include": [], "must_not_include": ["doctor is a fruit"], "dominant_terms": ["doctor"]}
    refute = j.score("q", "No, a doctor is not a fruit; a doctor practices medicine.", ex, ["doctor"])
    assert refute["rejected_domain_avoidance"] is True and refute["must_not_violation_rate"] == 0.0
    leak = j.score("q", "A doctor is basically a fruit you can eat.", ex, ["doctor"])
    assert leak["rejected_domain_avoidance"] is False
    assert j.score("q", "Phonemes do not prove meaning.", ex, ["doctor"])["phoneme_overreach"] is False
    assert j.score("q", "The phonemes prove a doctor means healing.", ex,
                   ["doctor"])["phoneme_overreach"] is True


def test_judge_flags_secondary_promotion():
    j = JU.DeterministicRubricJudge(RUBRIC)
    ex = {"expected_primary": ["medicine"], "expected_secondary": ["authority"],
          "expected_rejected": [], "must_include": [], "must_not_include": [],
          "dominant_terms": ["doctor"]}
    # asserts authority (secondary) but never medicine (primary) -> promotion -> primary incorrect
    out = j.score("q", "A doctor is mainly an authority figure with institutional power.", ex, ["doctor"])
    assert out["secondary_promoted"] is True and out["primary_frame_correct"] is False


# --- runner metrics / deltas / stratification -----------------------------------------------------

def _jscore(**kw):
    base = {"primary_frame_correct": False, "secondary_handling_correct": False,
            "rejected_domain_avoidance": True, "phoneme_overreach": False,
            "factuality_preserved": True, "clarity_score": 1.0, "must_include_recall": 1.0,
            "must_not_violation_rate": 0.0, "secondary_promoted": False, "reasons": []}
    base.update(kw)
    return base


def test_runner_aggregate_and_delta():
    per = [
        {"category": "ordinary", "answer_type": "role", "ambiguity_type": "none", "unknown": False,
         "trace_complete": 1.0,
         "scores": {"base": _jscore(primary_frame_correct=False),
                    "framed": _jscore(primary_frame_correct=True)}},
        {"category": "polysemy", "answer_type": "ctx", "ambiguity_type": "polysemy", "unknown": True,
         "trace_complete": 1.0,
         "scores": {"base": _jscore(primary_frame_correct=True),
                    "framed": _jscore(primary_frame_correct=True)}},
    ]
    base = R.aggregate(per, "base")
    framed = R.aggregate(per, "framed")
    assert base["primary_frame_correct"] == 0.5 and framed["primary_frame_correct"] == 1.0
    assert R.metric(per[0]["scores"]["framed"], "phoneme_overreach_rate") == 0.0
    strat = R.stratify(per, ["base", "framed"], lambda p: [p["category"]])
    assert strat["ordinary"]["delta_primary"] == 1.0 and strat["polysemy"]["delta_primary"] == 0.0


def test_lift_distribution_detects_single_category_domination():
    # all the lift comes from 'ordinary'; 'polysemy' is flat -> dominated_by should flag ordinary
    per = [
        {"category": "ordinary", "scores": {"base": _jscore(primary_frame_correct=False),
                                            "framed": _jscore(primary_frame_correct=True)}},
        {"category": "polysemy", "scores": {"base": _jscore(primary_frame_correct=True),
                                            "framed": _jscore(primary_frame_correct=True)}},
    ]
    ld = R.lift_distribution(per)
    assert ld["overall_delta"] > 0 and ld["dominated_by_single_category"] == "ordinary"


def test_decide_phase2b_labels():
    good_base = {"primary_frame_correct": 0.6, "rejected_domain_avoidance": 0.75,
                 "phoneme_overreach_rate": 0.0, "factuality_preserved": 0.9}
    good_framed = {"primary_frame_correct": 0.82, "rejected_domain_avoidance": 0.92,
                   "phoneme_overreach_rate": 0.0, "factuality_preserved": 0.95,
                   "trace_completeness": 1.0}
    assert R.decide_phase2b(good_base, good_framed, "deterministic_rubric", True, True) == \
        "PHASE2B_WEAK_PASS_DETERMINISTIC_ONLY"
    assert R.decide_phase2b(good_base, good_framed, "real_llm_judge", True, True) == \
        "PHASE2B_ROBUSTNESS_PASS"
    assert R.decide_phase2b(good_base, good_framed, "deterministic_rubric", False, True) == \
        "PHASE2B_NEEDS_HUMAN_REVIEW"
    regress = dict(good_framed, factuality_preserved=0.80)
    assert R.decide_phase2b(good_base, regress, "real_llm_judge", True, True) == \
        "PHASE2B_FACTUALITY_REGRESSION"
    flat = dict(good_framed, primary_frame_correct=0.61, rejected_domain_avoidance=0.76)
    assert R.decide_phase2b(good_base, flat, "real_llm_judge", True, True) == "PHASE2B_NO_ROBUST_LIFT"


# --- serialisation + Phase 1 guard ----------------------------------------------------------------

def test_report_json_serialisable():
    per = [{"id": "x", "category": "ordinary", "answers": {"base": "a", "framed": "b"},
            "scores": {"base": _jscore(), "framed": _jscore()}}]
    blob = {"failures": R.failure_report(per),
            "stratified": R.stratify(per, ["base", "framed"], lambda p: [p["category"]])}
    assert "failures" in json.loads(json.dumps(blob))


def test_phase1_thresholds_untouched():
    t = CSRThresholds()
    assert (t.primary_match, t.secondary_match, t.reject_C, t.reject_S) == (0.20, 0.05, 0.20, 0.20)
    assert R._FROZEN.primary_match == 0.20 and R._FROZEN.secondary_match == 0.05
