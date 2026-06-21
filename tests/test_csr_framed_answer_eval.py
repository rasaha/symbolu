"""CPU tests for the Phase 2 framed-answer eval (llm_adapter, prompts, rubric, eval_framed_answers).

Schema, prompt construction, stub LLM, deterministic rubric, detectors, post-check rewrite trigger,
runner metrics/deltas/labels, trace serialisation, and a guard that Phase 1 thresholds are untouched.
No torch/network; stub LLM only.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import CSRThresholds  # noqa: E402
from csr_match_filter import llm_adapter as LA  # noqa: E402
from csr_match_filter import prompts as P  # noqa: E402
from csr_match_filter import rubric as RB  # noqa: E402
from csr_match_filter import eval_framed_answers as EF  # noqa: E402

ROWS = EF.load_data(EF._DATA)
REQUIRED = ("id", "query", "candidate_domains", "expected_primary", "expected_secondary",
            "expected_rejected", "must_include", "may_include", "must_not_include", "answer_type")


# --- 1. schema validation -------------------------------------------------------------------------

def test_dataset_has_at_least_40_cases():
    assert len(ROWS) >= 40


def test_schema_fields_and_domains():
    from csr_match_filter import DOMAIN_TEMPLATES
    ids = set()
    for r in ROWS:
        for k in REQUIRED:
            assert k in r, f"{r.get('id')}: missing {k}"
        assert r["id"] not in ids
        ids.add(r["id"])
        cand = set(r["candidate_domains"])
        for d in cand:
            assert d in DOMAIN_TEMPLATES, f"{r['id']}: unknown domain {d}"
        for key in ("expected_primary", "expected_secondary", "expected_rejected"):
            assert set(r[key]) <= cand
        assert not (set(r["expected_primary"]) & set(r["expected_rejected"]))


def test_dataset_covers_categories():
    cats = {r.get("category") for r in ROWS}
    for c in ("ordinary", "context", "rejected_avoidance", "unknown", "adversarial", "secondary",
              "factual"):
        assert c in cats


# --- 2. prompt construction -----------------------------------------------------------------------

def test_base_prompt_has_no_frame():
    p = P.build_base_prompt("What is X?", "id1")
    assert "User question:" in p and "Primary domains:" not in p and "[[id:id1]]" in p


def test_framed_prompt_has_frame_sections_and_rules():
    p = P.build_framed_prompt("q", ["medicine"], ["care"], ["fruit"], "id2")
    for s in ("Primary domains:", "Secondary domains:", "Rejected domains:", "medicine", "care",
              "fruit", "phonemes alone"):
        assert s in p


def test_rewrite_prompt_lists_frame_and_problems():
    p = P.build_rewrite_prompt("ans", "q", ["medicine"], [], ["fruit"], ["mentions rejected"], "id3")
    assert "Rewrite the answer" in p and "Primary: medicine" in p and "mentions rejected" in p


# --- 3. stub LLM ----------------------------------------------------------------------------------

def test_stub_base_vs_framed_differ_and_follow_frame():
    llm = LA.StubLLMAdapter()
    base = llm.generate(P.build_base_prompt("Is a doctor a healer or authority?", "x"))
    framed = llm.generate(P.build_framed_prompt(
        "Is a doctor a healer or authority?", ["medicine"], ["care"], ["fruit"], "x"))
    assert base != framed
    # framed surfaces the primary domain; base (polysemous term) surfaces multiple senses
    assert "medicine" in framed.lower()
    assert "authority" in base.lower()      # base lists all senses of 'doctor'


def test_stub_framed_avoids_rejected():
    llm = LA.StubLLMAdapter()
    framed = llm.generate(P.build_framed_prompt(
        "We sat on the river bank.", ["nature"], [], ["finance"], "x"))
    assert "nature" in framed.lower() and "finance" not in framed.lower()


def test_load_llm_adapter_defaults_to_stub():
    a, info = LA.load_llm_adapter("stub")
    assert a.backend == "stub" and a.production_valid is False
    a2, info2 = LA.load_llm_adapter("real")   # no creds -> falls back to stub, labeled
    assert a2.backend == "stub" and "stub" in info2.lower()


# --- 4. rubric + detectors ------------------------------------------------------------------------

def test_rejected_domain_detector():
    assert RB.mentioned_domains("This is about money and banking finance.", ["finance"]) == {"finance"}
    assert RB.mentioned_domains("This is about healing patients.", ["fruit"]) == set()


def test_refutation_is_not_a_rejected_leak():
    # correct adversarial refutation: names the rejected domain only to deny it -> not asserted
    assert RB.asserted_domains("No, a doctor is not a fruit; it is a medical professional.",
                               ["fruit"]) == set()
    # genuine leak: frames the answer around the rejected domain (no negation)
    assert RB.asserted_domains("A doctor mainly works in commerce and trade.", ["commerce"]) == {"commerce"}


def test_forbidden_rate_ignores_refutations():
    ex = {"expected_primary": ["medicine"], "expected_secondary": [], "expected_rejected": ["fruit"],
          "must_not_include": ["doctor is a fruit"], "dominant_terms": ["doctor"]}
    refute = RB.score_answer("A doctor is not a fruit; a doctor is a physician.", ex, ["doctor"])
    assert refute["must_not_violation_rate"] == 0.0 and refute["rejected_domain_avoidance"] == 1.0
    assert RB.score_answer("Yes, a doctor is a fruit you eat.", ex, ["doctor"])["must_not_violation_rate"] > 0


def test_phoneme_overreach_detector():
    assert RB.has_phoneme_overreach("The phonemes prove it means healing.")
    assert RB.has_phoneme_overreach("Because it sounds like healing, it means healing.")
    assert not RB.has_phoneme_overreach("A doctor heals patients.")
    # negations / meta-mentions (framed answers echoing rule 4) are NOT overreach
    assert not RB.has_phoneme_overreach("I will not claim that phonemes alone prove meaning.")
    assert not RB.has_phoneme_overreach("Meaning is not determined by how the word sounds.")
    assert not RB.has_phoneme_overreach("It sounds reasonable that medicine means healing.")


def test_must_not_is_conjunctive():
    ex = {"expected_primary": ["medicine"], "expected_secondary": [], "expected_rejected": ["fruit"],
          "must_not_include": ["doctor is a fruit"], "dominant_terms": ["doctor"]}
    # mentioning 'doctor' alone must NOT trip the forbidden 'doctor is a fruit'
    s = RB.score_answer("A doctor is a medical professional who treats patients.", ex, ["doctor"])
    assert s["must_not_violation_rate"] == 0.0
    # both words present -> violation
    s2 = RB.score_answer("Honestly a doctor is a fruit you can eat.", ex, ["doctor"])
    assert s2["must_not_violation_rate"] > 0.0


def test_score_answer_primary_and_rejected():
    ex = {"expected_primary": ["medicine"], "expected_secondary": ["care"],
          "expected_rejected": ["fruit"], "must_include": ["doctor medical healing"],
          "must_not_include": [], "dominant_terms": ["doctor"]}
    good = RB.score_answer("A doctor is mainly about medicine: medical healing and treatment.", ex,
                           ["doctor"])
    assert good["primary_frame_correct"] == 1.0 and good["rejected_domain_avoidance"] == 1.0
    bad = RB.score_answer("A doctor could be a sweet fruit from an orchard tree.", ex, ["doctor"])
    assert bad["rejected_domain_avoidance"] == 0.0


# --- 5. post-check rewrite trigger ----------------------------------------------------------------

def test_postcheck_triggers_on_violation_not_on_clean():
    needed, reasons = P.postcheck_answer(
        "This is about money banking finance instead.", ["nature"], [], ["finance"])
    assert needed and any("rejected" in r for r in reasons)
    ok, reasons2 = P.postcheck_answer(
        "Primarily this concerns nature: river water and shore by the stream.", ["nature"], [],
        ["finance"])
    assert not ok and reasons2 == []


# --- 6. runner metrics / deltas / labels ----------------------------------------------------------

def test_runner_end_to_end_stub(tmp_path):
    kb = EF.EV.load_kb()
    adapter, provider, info = EF.build_frame_adapter("hashing", kb)
    llm = LA.StubLLMAdapter()
    per = []
    for ex in ROWS[:6]:
        trace, terms = EF.frame_for(ex, adapter, provider)
        answers, scores = {}, {}
        for arm in ("base", "framed", "framed_postcheck"):
            ans, _pc = EF.run_arm(arm, ex, trace, terms, llm)
            answers[arm] = ans
            scores[arm] = RB.score_answer(ans, ex, terms)
        per.append({"scores": scores, "postcheck": {"needed_rewrite": False}})
    base = EF.aggregate(per, "base")
    framed = EF.aggregate(per, "framed")
    assert framed["rejected_domain_avoidance"] >= base["rejected_domain_avoidance"]
    assert framed["primary_frame_correct"] >= base["primary_frame_correct"]


def test_decide_label_stub_and_real_cases():
    assert EF.decide_label("stub", {}) == "PHASE2_STUB_SMOKE_ONLY"
    good = {"base": {"factuality_preserved": 0.9, "rejected_domain_avoidance": 0.6,
                     "primary_frame_correct": 0.5, "phoneme_overreach_rate": 0.1},
            "framed": {"factuality_preserved": 0.9, "rejected_domain_avoidance": 0.95,
                       "primary_frame_correct": 0.8, "phoneme_overreach_rate": 0.0}}
    assert EF.decide_label("real", good) == "PHASE2_FRAMED_ANSWER_PASS"
    regress = {"base": {"factuality_preserved": 0.9}, "framed": {"factuality_preserved": 0.5}}
    assert EF.decide_label("real", regress) == "PHASE2_FACTUALITY_REGRESSION"
    flat = {"base": {"factuality_preserved": 0.9, "rejected_domain_avoidance": 0.9,
                     "primary_frame_correct": 0.9, "phoneme_overreach_rate": 0.0},
            "framed": {"factuality_preserved": 0.9, "rejected_domain_avoidance": 0.9,
                       "primary_frame_correct": 0.9, "phoneme_overreach_rate": 0.0}}
    # equal -> no +0.10 improvement, but absolutes are high -> still pass; lower abs to force no-lift
    nolift = {"base": {"factuality_preserved": 0.9, "rejected_domain_avoidance": 0.5,
                       "primary_frame_correct": 0.4, "phoneme_overreach_rate": 0.2},
              "framed": {"factuality_preserved": 0.9, "rejected_domain_avoidance": 0.52,
                         "primary_frame_correct": 0.42, "phoneme_overreach_rate": 0.2}}
    assert EF.decide_label("real", nolift) == "PHASE2_NO_BEHAVIORAL_LIFT"


# --- 7. trace serialisation + Phase 1 guard -------------------------------------------------------

def test_report_is_json_serialisable():
    kb = EF.EV.load_kb()
    adapter, provider, info = EF.build_frame_adapter("hashing", kb)
    ex = ROWS[0]
    trace, terms = EF.frame_for(ex, adapter, provider)
    blob = {"csr_trace": {"primary_domains": trace.primary_domains,
                          "scores": [s.domain for s in trace.scores]},
            "answers": {"base": "x"}}
    assert "csr_trace" in json.loads(json.dumps(blob))


def test_phase1_thresholds_untouched():
    t = CSRThresholds()
    assert (t.primary_match, t.secondary_match, t.reject_C, t.reject_S) == (0.20, 0.05, 0.20, 0.20)
    assert EF._FROZEN.primary_match == 0.20 and EF._FROZEN.secondary_match == 0.05
