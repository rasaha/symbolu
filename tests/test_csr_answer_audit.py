"""CPU tests for Phase 3 — the C×R×S answer-audit / post-check layer.

Covers the finding taxonomy + dataclasses, the deterministic (negation- and term-aware) audit engine
on every finding type, the conservative rewrite policy, the rewrite-prompt builder, the eval metrics
+ PHASE3_* decision labels, the fixture dataset (every row reproduces its gold labels and the eval
returns PHASE3_ANSWER_AUDIT_PASS), and the opt-in Phase 2 runner integration. No LLM, no network.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import answer_audit as AA            # noqa: E402
from csr_match_filter import eval_answer_audit as EAA       # noqa: E402

_DATA = _ABL / "csr_match_filter" / "eval_data" / "answer_audit_eval.jsonl"

DOCTOR = {"primary_domains": ["medicine"], "secondary_domains": ["care", "authority"],
          "rejected_domains": ["commerce", "fruit"]}
PYTHON = {"primary_domains": ["programming"], "secondary_domains": [], "rejected_domains": ["fruit"]}


def _types(res):
    return set(res.finding_types)


# --- dataclasses / taxonomy -----------------------------------------------------------------------

def test_finding_confidence_from_severity():
    f = AA.AnswerAuditFinding("primary_frame_missing", "error", "medicine", "ev", "why")
    assert f.confidence == 0.8
    assert AA.AnswerAuditFinding("x", "critical", None, "", "").confidence == 0.9
    assert AA.AnswerAuditFinding("x", "info", None, "", "").confidence == 0.2


def test_result_to_dict_roundtrip():
    res = AA.audit_answer("What is a doctor?",
                          "A doctor primarily involves medicine, clinical, and cure here.", DOCTOR)
    d = res.to_dict()
    assert d["passed"] is True and "findings" in d and d["status"] == "audit_pass"


# --- the audit engine, one assertion per finding type ---------------------------------------------

def test_frame_compliant():
    res = AA.audit_answer("What is a doctor?",
                          "A doctor primarily involves medicine, clinical, and cure here.", DOCTOR)
    assert _types(res) == {"frame_compliant"} and res.passed and not res.needs_rewrite


def test_primary_frame_missing_triggers_rewrite():
    res = AA.audit_answer("What is a doctor?",
                          "A doctor is a familiar everyday subject folks chat about casually.", DOCTOR)
    assert "primary_frame_missing" in _types(res)
    assert not res.passed and res.needs_rewrite


def test_rejected_domain_promoted_is_critical_when_primary_absent():
    res = AA.audit_answer("What is a doctor?",
                          "A doctor is basically about business, market, and trade above all.", DOCTOR)
    assert "rejected_domain_promoted" in _types(res) and res.needs_rewrite
    crit = [f for f in res.findings if f.finding_type == "rejected_domain_promoted"]
    assert crit[0].severity == "critical"


def test_rejected_leak_with_primary_present_is_error_not_rewrite():
    res = AA.audit_answer(
        "What is a doctor?",
        "A doctor is a physician who provides treatment, but it is also fundamentally about "
        "business and market.", DOCTOR)
    assert "rejected_domain_promoted" in _types(res)
    leak = [f for f in res.findings if f.finding_type == "rejected_domain_promoted"][0]
    assert leak.severity == "error" and not res.passed and not res.needs_rewrite


def test_refutation_is_not_a_leak():
    res = AA.audit_answer(
        "Is a doctor a fruit?",
        "A doctor is not about fruit; a doctor primarily involves medicine and clinical care.", DOCTOR)
    assert "rejected_domain_mentioned_as_refutation" in _types(res)
    assert "rejected_domain_promoted" not in _types(res) and res.passed


def test_alternate_true_sense_allowed_when_primary_present():
    res = AA.audit_answer(
        "What is python?",
        "In this context python mainly involves code and software; it can also refer to a snake "
        "in biology.", PYTHON, alternate_true_senses=["biology"])
    assert "alternate_true_sense_allowed" in _types(res)
    assert "frame_compliant" in _types(res) and res.passed and not res.needs_rewrite


def test_alternate_sense_promoted_is_a_frame_error():
    res = AA.audit_answer(
        "What is python?",
        "Python is mainly an animal and organism, primarily studied within biology.",
        PYTHON, alternate_true_senses=["biology"])
    assert {"secondary_promoted_to_primary", "primary_frame_missing"} <= _types(res)
    assert not res.passed and res.needs_rewrite


def test_phoneme_overreach_is_critical():
    res = AA.audit_answer(
        "What is a doctor?",
        "Because the sound of the word 'doctor' proves it means healing, a doctor involves "
        "clinical treatment.", DOCTOR)
    assert "phoneme_overreach_claim" in _types(res) and res.needs_rewrite and not res.passed


def test_factuality_suspected_independent_of_frame():
    res = AA.audit_answer(
        "What is mercury?",
        "Mercury is a leafy vegetable, just as it is plainly described in ordinary terms.",
        {"primary_domains": ["chemistry"], "secondary_domains": ["nature"],
         "rejected_domains": ["fruit"]}, false_claims=["mercury is a leafy vegetable"])
    assert "factuality_suspected" in _types(res) and not res.passed


def test_answer_too_generic_short_circuits():
    res = AA.audit_answer("What is a doctor?", "It really depends on many other factors entirely.",
                          DOCTOR)
    assert _types(res) == {"answer_too_generic"} and res.passed and not res.needs_rewrite


def test_term_awareness_bare_polysemous_term_does_not_assert_a_sense():
    # 'virus' is literally a biology keyword; a bare mention must NOT count as asserting biology
    res = AA.audit_answer(
        "What is a virus?",
        "A virus is mainly about hackers, malware, and intrusion, primarily studied within security.",
        {"primary_domains": ["biology"], "secondary_domains": ["medicine"],
         "rejected_domains": ["fruit"]}, alternate_true_senses=["security"])
    assert "primary_frame_missing" in _types(res)        # biology NOT asserted by the bare term


# --- conservative rewrite policy ------------------------------------------------------------------

def test_should_rewrite_is_conservative():
    # factuality alone (no pfm) must NOT trigger a frame rewrite
    res = AA.AnswerAuditResult("x", passed=False, needs_rewrite=False, confidence=0.8,
                               findings=[AA.AnswerAuditFinding("factuality_suspected", "error",
                                                               None, "", "")])
    assert AA.should_rewrite(res) is False
    res2 = AA.AnswerAuditResult("x", passed=False, needs_rewrite=False, confidence=0.9,
                                findings=[AA.AnswerAuditFinding("rejected_domain_promoted",
                                                                "critical", "commerce", "", "")])
    assert AA.should_rewrite(res2) is True


def test_build_rewrite_prompt_names_problems_and_frame():
    res = AA.audit_answer("What is a doctor?",
                          "A doctor is basically about business, market, and trade above all.", DOCTOR)
    prompt = AA.build_rewrite_prompt("What is a doctor?",
                                     "A doctor is basically about business, market, and trade.",
                                     DOCTOR, res)
    assert "medicine" in prompt and "commerce" in prompt and "rejected_domain_promoted" in prompt


# --- eval metrics + decision labels ---------------------------------------------------------------

def test_decide_phase3_label_precedence():
    base = {"finding_f1": 1.0, "rewrite_precision": 1.0, "rewrite_recall": 1.0,
            "false_rewrite_rate": 0.0, "missed_critical_failure_rate": 0.0}
    assert EAA.decide_phase3(base) == "PHASE3_ANSWER_AUDIT_PASS"
    assert EAA.decide_phase3(dict(base, missed_critical_failure_rate=0.1)) == \
        "PHASE3_AUDIT_MISSES_CRITICAL_FAILURES"
    assert EAA.decide_phase3(dict(base, false_rewrite_rate=0.5)) == \
        "PHASE3_AUDIT_WEAK_REWRITE_TOO_AGGRESSIVE"
    assert EAA.decide_phase3(dict(base, finding_f1=0.3)) == "PHASE3_AUDIT_NO_VALUE"
    assert EAA.decide_phase3(dict(base, rewrite_precision=0.7)) == "PHASE3_AUDIT_NEEDS_HUMAN_REVIEW"


def test_missed_critical_dominates_over_aggressive():
    m = {"finding_f1": 1.0, "rewrite_precision": 1.0, "rewrite_recall": 1.0,
         "false_rewrite_rate": 0.9, "missed_critical_failure_rate": 0.2}
    assert EAA.decide_phase3(m) == "PHASE3_AUDIT_MISSES_CRITICAL_FAILURES"


# --- the fixture dataset reproduces gold + the eval passes ----------------------------------------

def test_dataset_schema_and_size():
    rows = [json.loads(l) for l in _DATA.read_text().splitlines() if l.strip()]
    assert len(rows) >= 64
    for r in rows:
        assert {"id", "query", "csr_trace_fixture", "answer", "expected_findings",
                "expected_passed", "expected_needs_rewrite"} <= set(r)
        for ft in r["expected_findings"]:
            assert ft in AA.FINDING_TYPES


def test_every_row_reproduces_gold_and_eval_passes():
    rows = EAA.load_data(_DATA)
    per = EAA.run(rows)
    for p in per:
        assert set(p["res"].finding_types) == set(p["ex"]["expected_findings"]), p["ex"]["id"]
        assert p["res"].passed == p["ex"]["expected_passed"], p["ex"]["id"]
        assert p["res"].needs_rewrite == p["ex"]["expected_needs_rewrite"], p["ex"]["id"]
    m = EAA.metrics(per)
    assert m["finding_f1"] == 1.0 and m["missed_critical_failure_rate"] == 0.0
    assert m["false_rewrite_rate"] == 0.0
    assert EAA.decide_phase3(m) == "PHASE3_ANSWER_AUDIT_PASS"


# --- opt-in Phase 2 runner integration ------------------------------------------------------------

def test_runner_audit_aggregation_shape():
    from csr_match_filter import eval_framed_answers as EF
    trace = type("T", (), {"primary_domains": ["medicine"], "secondary_domains": ["care"],
                           "rejected_domains": ["commerce"]})()
    ex = {"id": "x", "query": "What is a doctor?"}
    rec = EF.audit_arm(ex, trace,
                       "A doctor primarily involves medicine, clinical, and cure here.",
                       llm=None, rewrite_mode="off")
    assert rec["passed"] is True and "rewrite_prompt" not in rec
    per = [{"audit": {"framed": rec}}]
    agg = EF.aggregate_audit(per, "framed")
    assert set(agg) == {"audit_pass_rate", "rewrite_recommended_rate", "critical_findings_rate"}
    assert agg["audit_pass_rate"] == 1.0
