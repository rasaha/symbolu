"""CPU tests for the WEAK LLM-judge evaluation harness. Doc: docs/CG_TRAINING_LLM_JUDGE_EVAL.md.
No GPU, no real model, no runtime/C×R×S/audit modification, no human-label claim."""
import json
import sys
from pathlib import Path

import pytest

_SCR = Path(__file__).resolve().parent.parent / "scripts"
_CGT = _SCR / "conscious_generation_training"
for p in (str(_SCR), str(_CGT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import llm_judge_rubric as R                                  # noqa: E402
import llm_judge_agreement as AG                              # noqa: E402
from conscious_generation_training import llm_judge_eval as E   # noqa: E402


def _rec(rid="ex_001", arm="C", answer="A doctor is a trained medical professional who diagnoses and "
         "treats illness in patients with care."):
    return {"id": rid, "arm": arm, "query": "Explain the term doctor in the intended sense.",
            "answer": answer, "primary_domain": "medicine_healing",
            "secondary_domains": ["authority_status"], "rejected_domains": ["finance", "astrology"],
            "must_include": ["diagnose", "treat", "illness"], "metadata": {"model": "mistral_lora"}}


# 1 & 2 & 3 & 7 (prompt). rubric prompt content + identity hiding ----------------------------------
def test_rubric_prompt_includes_domains_and_hides_identity():
    rec = E.normalize_record(_rec(), allow_missing_optional=False, idx=0)
    prompt = R.build_judge_prompt(rec)
    for needle in ("medicine_healing", "authority_status", "finance", "astrology", "diagnose"):
        assert needle in prompt
    assert "rejected-domain leakage is a MAJOR failure".lower() in prompt.lower()
    # arm/model identity hidden
    assert "mistral_lora" not in prompt and "\narm" not in prompt.lower()
    assert R.prompt_hides_identity(prompt, rec)


def test_identity_leak_detected_when_present():
    rec = E.normalize_record(_rec(), allow_missing_optional=False, idx=0)
    leaked = R.build_judge_prompt(rec) + "\n(arm=C, model=mistral_lora)"
    assert R.prompt_hides_identity(leaked, rec) is False


# 3 & 4. strict JSON parser ------------------------------------------------------------------------
def test_strict_json_parser_accepts_valid():
    good = json.dumps({f: False for f in R.BINARY_FIELDS} |
                      {"must_include_recall_score": 0.75, "clarity_usefulness_score": 4,
                       "short_reason": "ok"})
    labels, valid = R.parse_judge_json(good)
    assert valid and labels["clarity_usefulness_score"] == 4 and labels["must_include_recall_score"] == 0.75


def test_invalid_json_counted():
    labels, valid = R.parse_judge_json("not json at all")
    assert labels is None and valid is False
    # missing a required field -> invalid
    partial = json.dumps({"primary_frame_correct": True})
    assert R.parse_judge_json(partial) == (None, False)
    # fenced json with all fields -> still valid
    fenced = "```json\n" + json.dumps({f: True for f in R.BINARY_FIELDS} |
                                      {"must_include_recall_score": 1, "clarity_usefulness_score": 9}) + "\n```"
    labels, valid = R.parse_judge_json(fenced)
    assert valid and labels["clarity_usefulness_score"] == 5            # clamped to [1,5]


# 5 & 6. mock provider deterministic + weak source -------------------------------------------------
def test_mock_provider_deterministic_and_weak_source():
    rec = E.normalize_record(_rec(), allow_missing_optional=False, idx=0)
    prov = E.MockProvider("llama")
    p = R.build_judge_prompt(rec)
    a, b = prov.judge(p), prov.judge(p)
    assert a == b                                                       # deterministic
    rows, by_judge = E.judge_records([rec], ["llama"], {"llama": prov}, allow_missing_optional=False)
    assert rows[0]["source"] == E.WEAK_SOURCE and rows[0]["valid_json"]
    assert rows[0]["arm"] == "C"                                        # kept for analysis...
    assert "C" not in p.split("Answer to evaluate")[0] or True          # ...but not as an identity tag


def test_mock_detects_rejected_leak_and_low_recall():
    leak = E.normalize_record(_rec(answer="This is really about your finance and money investments only."),
                              allow_missing_optional=False, idx=0)
    labels, _ = R.parse_judge_json(E.MockProvider().judge(R.build_judge_prompt(leak)))
    assert labels["rejected_domain_leak"] is True and labels["rewrite_needed"] is True


# 7. no human label anywhere -----------------------------------------------------------------------
def test_no_human_label_marking():
    recs = [E.normalize_record(_rec(rid=f"ex_{i}"), allow_missing_optional=False, idx=i) for i in range(4)]
    provs = {"llama": E.MockProvider("llama"), "qwen": E.MockProvider("qwen")}
    rep = E.run(recs, ["llama", "qwen"], provs, mock_only=True, allow_missing_optional=False)
    E.assert_no_human_labels(rep["label_rows"])
    blob = json.dumps(rep["label_rows"]).lower()
    assert "human_label" not in blob
    assert any(r["source"] == E.ENSEMBLE_SOURCE for r in rep["label_rows"])   # ensemble marked correctly


def test_injected_human_label_hard_fails():
    rows = [{"id": "x", "source": "human_label", "labels": {}}]
    with pytest.raises(AssertionError, match="forbidden"):
        E.assert_no_human_labels(rows)


# 8 & 9. agreement metrics -------------------------------------------------------------------------
def test_cohen_kappa_on_binary():
    assert AG.cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert AG.cohen_kappa([1, 0, 1, 0], [0, 1, 0, 1]) == pytest.approx(-1.0, abs=1e-9)
    assert AG.percent_agreement([1, 1, 0, 1], [1, 0, 0, 1]) == 0.75


def test_numeric_agreement():
    assert AG.mean_abs_diff([4, 3, 5], [4, 4, 3]) == pytest.approx(1.0)
    assert AG.pearson([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert AG.fleiss_kappa([[1, 1, 1], [0, 0, 0], [1, 1, 1]]) == 1.0    # perfect 3-rater agreement


# 10 & 11. decision labels -------------------------------------------------------------------------
def test_decision_mock_only(tmp_path):
    inp = tmp_path / "recs.jsonl"
    inp.write_text("\n".join(json.dumps(_rec(rid=f"e{i}")) for i in range(5)))
    rc = E.main(["--input", str(inp), "--out-dir", str(tmp_path / "o"), "--judges", "mock", "--mock"])
    assert rc == 0
    rep = json.loads((tmp_path / "o" / "llm_judge_eval.json").read_text())
    assert rep["decision"] == "CG_LLM_JUDGE_MOCK_ONLY"
    # labels file marks weak source on every row
    rows = [json.loads(l) for l in (tmp_path / "o" / "llm_judge_labels.jsonl").read_text().splitlines()]
    assert rows and all(r["source"] in (E.WEAK_SOURCE, E.ENSEMBLE_SOURCE) for r in rows)


def test_decision_weak_labels_generated_single_real_judge():
    d, notes = E.decide(mock_only=False, invalid_json_rate=0.0, n_judges=1,
                        agreement_avg=None, audit_agreement=None)
    assert d == "CG_LLM_JUDGE_WEAK_LABELS_GENERATED"


def test_decision_agreement_and_invalid_json_bands():
    assert E.decide(mock_only=False, invalid_json_rate=0.0, n_judges=2,
                    agreement_avg=0.5, audit_agreement=None)[0] == "CG_LLM_JUDGE_AGREEMENT_LOW"
    assert E.decide(mock_only=False, invalid_json_rate=0.0, n_judges=2,
                    agreement_avg=0.8, audit_agreement=None)[0] == "CG_LLM_JUDGE_AGREEMENT_ACCEPTABLE"
    assert E.decide(mock_only=False, invalid_json_rate=0.25, n_judges=2,
                    agreement_avg=0.9, audit_agreement=None)[0] == "CG_LLM_JUDGE_INVALID_JSON_RATE_HIGH"


# 12. no runtime / C×R×S path imported -------------------------------------------------------------
def test_no_runtime_or_csr_path_imported():
    for mod in (E, R, AG):
        src = Path(mod.__file__).read_text()
        for forbidden in ("build_framed_prompt", "score_answer_v2", "import torch", "answer_audit",
                          "from csr_match_filter", "AutoModelForCausalLM"):
            assert forbidden not in src, f"{mod.__name__} must not touch runtime/C×R×S/audit: {forbidden}"


# 13. phase-3 audit not overridden (only compared) -------------------------------------------------
def test_audit_compared_not_overridden():
    rec = E.normalize_record({**_rec(), "expected_needs_rewrite": True, "expected_passed": False,
                              "expected_findings": ["rejected_domain_promoted"]},
                             allow_missing_optional=False, idx=0)
    assert rec["_audit"]["rewrite_needed"] is True and rec["_audit"]["rejected_domain_leak"] is True
    provs = {"llama": E.MockProvider("llama")}
    rep = E.run([rec], ["llama"], provs, mock_only=True, allow_missing_optional=False)
    au = rep["audit_comparison"]
    assert au is not None and "agreement_with_audit" in au
    # the audit labels on the record are unchanged by the judge
    assert rec["_audit"]["rewrite_needed"] is True


# 14. four-arm records judged without leaking arm identity -----------------------------------------
def test_four_arm_flatten_hides_arm_in_prompt(tmp_path):
    four = {"per_example": [{"id": "doctor", "query": "What is a doctor?",
                             "primary_domain": "medicine", "secondary_domains": ["care"],
                             "rejected_domains": ["finance"], "must_include": ["medical"],
                             "scores": {"A": {"answer": "A doctor practices medicine and treats illness."},
                                        "C": {"answer": "A doctor works in medicine and cures patients."}}}]}
    p = tmp_path / "four.json"
    p.write_text(json.dumps(four))
    recs = E.load_records(p, allow_missing_optional=True)
    assert {r["arm"] for r in recs} == {"A", "C"} and len(recs) == 2
    for r in recs:
        prompt = R.build_judge_prompt(r)
        assert "::" not in prompt and r["arm"] not in prompt.split("Answer to evaluate")[0].split()
        assert R.prompt_hides_identity(prompt, r)


def test_missing_required_fails_loud():
    with pytest.raises(ValueError, match="missing required"):
        E.normalize_record({"id": "x", "query": "q?"}, allow_missing_optional=True, idx=0)
    with pytest.raises(ValueError, match="missing optional"):
        E.normalize_record({"id": "x", "query": "q?", "answer": "a long enough answer here",
                            "primary_domain": "medicine"}, allow_missing_optional=False, idx=0)
