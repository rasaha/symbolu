"""CPU tests for Phase 2B-v2 (rubric_v2: factuality decoupled from frame compliance).

Verifies the pre-registered v2 rules, that rubric_v1 behaviour is unchanged (reproducible), the
corrected dataset schema, the version-aware judge, and trace serialisation records rubric_version.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import rubric as RB  # noqa: E402
from csr_match_filter import judge_adapter as JU  # noqa: E402
from csr_match_filter import eval_framed_answers_robustness as R  # noqa: E402

_RV2 = _ABL / "csr_match_filter" / "eval_data" / "framed_answer_rubric_v2.yaml"
_DV2 = _ABL / "csr_match_filter" / "eval_data" / "framed_answer_eval_v2_rubricv2.jsonl"

PY = {"expected_primary": ["programming"], "expected_secondary": [],
      "expected_secondary_true_senses": ["biology"], "expected_rejected": ["fruit"],
      "must_include": [], "must_not_include": [], "false_claims": [], "dominant_terms": ["python"]}


# --- v2 rubric behaviour --------------------------------------------------------------------------

def test_alternate_true_sense_mention_is_not_factuality_or_leak():
    a = "Python is primarily a programming language, though it is also a snake in biology."
    s = RB.score_answer_v2(a, PY, ["python"])
    assert s["factuality_preserved"] == 1.0           # no false claim
    assert s["rejected_domain_avoidance"] == 1.0       # biology is a true secondary sense, not rejected
    assert s["alternate_true_sense_mention"] == 1.0
    assert s["primary_frame_correct"] == 1.0           # programming leads


def test_alternate_sense_promoted_as_primary_is_frame_error():
    a = "Python is a snake, a reptile studied in biology."     # biology asserted, programming absent
    s = RB.score_answer_v2(a, PY, ["python"])
    assert s["rejected_domain_promotion"] == 1.0 and s["primary_frame_correct"] == 0.0


def test_rejected_refutation_is_not_leak_v2():
    ex = {"expected_primary": ["medicine"], "expected_secondary_true_senses": [],
          "expected_rejected": ["fruit"], "false_claims": ["doctor is a fruit"],
          "must_include": [], "must_not_include": [], "dominant_terms": ["doctor"]}
    s = RB.score_answer_v2("A doctor is not a fruit; a doctor practices medicine.", ex, ["doctor"])
    assert s["rejected_domain_avoidance"] == 1.0 and s["factuality_preserved"] == 1.0


def test_factuality_is_independent_of_must_not_violation():
    # must_not is violated (frame) but there is NO false_claim -> factuality must still be preserved
    ex = {"expected_primary": ["medicine"], "expected_secondary_true_senses": [],
          "expected_rejected": ["commerce"], "false_claims": [],
          "must_not_include": ["doctor commerce trade"], "must_include": [], "dominant_terms": ["doctor"]}
    s = RB.score_answer_v2("A doctor works in commerce trade as a business.", ex, ["doctor"])
    assert s["must_not_violation_rate"] > 0.0          # frame violated
    assert s["factuality_preserved"] == 1.0            # but factuality independent (no false claim)


def test_factuality_fails_on_false_claim():
    ex = dict(PY, false_claims=["python is a finance instrument"])
    s = RB.score_answer_v2("Python is a finance instrument used in markets and money.", ex, ["python"])
    assert s["factuality_preserved"] == 0.0


def test_overreach_requires_assertion_v2():
    ex = dict(PY)
    assert RB.score_answer_v2("Phonemes do not prove meaning; python is programming.", ex,
                              ["python"])["phoneme_overreach_rate"] == 0.0
    assert RB.score_answer_v2("The phonemes prove python means a snake.", ex,
                              ["python"])["phoneme_overreach_rate"] == 1.0


# --- rubric_v1 reproducibility (must NOT change) --------------------------------------------------

def test_rubric_v1_behaviour_reproducible():
    ex = {"expected_primary": ["medicine"], "expected_secondary": [], "expected_rejected": ["fruit"],
          "must_include": [], "must_not_include": ["doctor is a fruit"], "dominant_terms": ["doctor"]}
    s = RB.score_answer("A doctor is not a fruit; a doctor practices medicine.", ex, ["doctor"])
    assert s["rejected_domain_avoidance"] == 1.0 and s["must_not_violation_rate"] == 0.0
    assert "alternate_true_sense_mention" not in s    # v1 schema unchanged


# --- version-aware judge + schema -----------------------------------------------------------------

def test_judge_is_version_aware_and_records_version():
    jv2 = JU.DeterministicRubricJudge({"version": "framed_answer_rubric_v2"})
    out = jv2.score("q", "Python is mainly programming, also a snake in biology.", PY, ["python"])
    assert out["rubric_version"] == "framed_answer_rubric_v2"
    assert out["alternate_true_sense_mention"] is True and out["factuality_preserved"] is True
    jv1 = JU.DeterministicRubricJudge({"version": "framed_answer_rubric_v1"})
    assert jv1.score("q", "x doctor medicine", {"expected_primary": ["medicine"],
                     "expected_rejected": [], "expected_secondary": [], "dominant_terms": ["doctor"]},
                     ["doctor"])["rubric_version"] == "framed_answer_rubric_v1"


def test_rubric_v2_yaml_schema():
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load(_RV2.read_text())
    assert cfg["version"] == "framed_answer_rubric_v2" and cfg["locked"] is True
    names = {r["name"] for r in cfg["rules"]}
    assert {"factuality_is_no_false_claim", "alternate_true_sense_is_secondary_allowed",
            "promotion_is_a_frame_error", "refutation_is_not_a_leak"} <= names
    assert cfg["params"]["factuality_source"] == "false_claims"
    assert cfg["metrics"]["factuality_preserved"]["independent_of"]


def test_corrected_dataset_schema():
    rows = [json.loads(l) for l in _DV2.read_text().splitlines() if l.strip()]
    assert len(rows) >= 105
    for r in rows:
        assert "expected_secondary_true_senses" in r and "false_claims" in r
        assert r.get("rubric_target") == "framed_answer_rubric_v2"
        # alternate true sense and rejected are disjoint
        assert not (set(r["expected_secondary_true_senses"]) & set(r["expected_rejected"]))
    # polysemy rows actually gained alternate true senses
    poly = [r for r in rows if r.get("category") == "polysemy"]
    assert sum(1 for r in poly if r["expected_secondary_true_senses"]) >= 8


def test_decide_phase2b_v2_labels():
    base = {"primary_frame_correct": 0.55, "rejected_domain_avoidance": 0.80,
            "phoneme_overreach_rate": 0.0, "factuality_preserved": 0.9}
    framed = {"primary_frame_correct": 0.72, "rejected_domain_avoidance": 0.95,
              "phoneme_overreach_rate": 0.0, "factuality_preserved": 0.92, "trace_completeness": 1.0}
    assert R.decide_phase2b_v2(base, framed, "real_llm_judge", True, True) == "PHASE2B_V2_ROBUSTNESS_PASS"
    assert R.decide_phase2b_v2(base, framed, "deterministic_rubric", True, True) == \
        "PHASE2B_V2_NEEDS_HUMAN_REVIEW"
    only = dict(framed, rejected_domain_avoidance=0.81)
    assert R.decide_phase2b_v2(base, only, "real_llm_judge", True, True) == "PHASE2B_V2_PRIMARY_LIFT_ONLY"
    flat = dict(framed, primary_frame_correct=0.56)
    assert R.decide_phase2b_v2(base, flat, "real_llm_judge", True, True) == "PHASE2B_V2_NO_ROBUST_LIFT"
    reg = dict(framed, factuality_preserved=0.80)
    assert R.decide_phase2b_v2(base, reg, "real_llm_judge", True, True) == "PHASE2B_V2_FACTUALITY_REGRESSION"
