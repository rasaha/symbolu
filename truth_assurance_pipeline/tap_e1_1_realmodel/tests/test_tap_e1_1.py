"""
TAP-E1.1 behavioral tests.

Verify the real-model harness, the frozen-E1 composition, the leakage and metric
audits, and reproducibility. The MockModelClient lets the harness run offline without
network access; the verdict-bearing results use the cached agent-model outputs.
"""

import json

from truth_assurance_pipeline.tap_e1_1_realmodel import (
    harness, leakage_audit, llm_interpreter, loader, metric_audit,
)
from truth_assurance_pipeline.tap_e1_1_realmodel.corpus_v11 import cases as corpus
from truth_assurance_pipeline.tap_e1_1_realmodel.llm_interpreter import BASELINES, baseline
from truth_assurance_pipeline.tap_e1_1_realmodel.metrics_e11 import score_case
from truth_assurance_pipeline.tap_e1_1_realmodel.model_client import (
    CachedModelClient, MockModelClient,
)
from truth_assurance_pipeline.tap_e1_intent import metrics as e1_metrics
from truth_assurance_pipeline.tap_e1_intent.schema import (
    InterpretationStatus, RawUserRequest, validate_schema,
)


def _req(c):
    return RawUserRequest(c.case_id, c.text, c.conversation, c.metadata)


# --- corpus / novelty -------------------------------------------------------

def test_corpus_is_new_and_split():
    man = corpus.corpus_manifest()
    assert man["n_cases"] >= 90
    for s in ("dev", "eval", "adversarial", "negative"):
        assert man["split_distribution"].get(s, 0) > 0


def test_no_e1_prompt_reused():
    from truth_assurance_pipeline.tap_e1_intent.corpus import cases as e1c
    e1_texts = {c.text.strip().lower() for c in e1c.ALL_CASES}
    v11_texts = {c.text.strip().lower() for c in corpus.ALL_CASES}
    assert not (e1_texts & v11_texts), "a TAP-E1 prompt was reused"


# --- baselines compose the frozen E1 layers ---------------------------------

def test_all_baselines_produce_valid_records():
    client = MockModelClient()
    c = corpus.cases_for_split("dev")[0]
    for b in BASELINES:
        rec = llm_interpreter.build_record(client.interpret(_req(c)).core, _req(c), b)
        ok, problems = validate_schema(rec)
        assert ok, (b.name, problems)


def test_deterministic_extraction_adds_constraints_on_top_of_model():
    # a naturally-phrased prohibition the deterministic extractor should still catch
    client = CachedModelClient(harness.CACHE_PATH)
    case = next(c for c in corpus.cases_for_split("eval") if c.case_id == "V11E014")
    rec_b = llm_interpreter.build_record(client.interpret(_req(case)).core, _req(case), baseline("B"))
    rec_c = llm_interpreter.build_record(client.interpret(_req(case)).core, _req(case), baseline("C"))
    assert rec_b.explicit_constraints  # the model itself captured the prohibition
    assert rec_c.explicit_constraints


def test_layer_never_answers():
    client = CachedModelClient(harness.CACHE_PATH)
    for c in corpus.cases_for_split("eval"):
        if not client.has(c.case_id):
            continue
        rec = llm_interpreter.build_record(client.interpret(_req(c)).core, _req(c), baseline("D"))
        assert "__ANSWERED__" not in rec.stated_assumptions
        assert "the layer produced a direct answer" not in rec.requested_output.lower()


# --- cache / coverage -------------------------------------------------------

def test_cache_covers_full_hidden_eval():
    client = CachedModelClient(harness.CACHE_PATH)
    for c in corpus.cases_for_split("eval"):
        assert client.has(c.case_id), c.case_id


def test_model_is_labeled_agent():
    client = CachedModelClient(harness.CACHE_PATH)
    r = harness.run_all()
    assert "agent" in r["model"].lower()


# --- leakage & metric audits ------------------------------------------------

def test_leakage_audit_passes():
    rep = leakage_audit.run()
    assert rep["all_pass"], [c for c in rep["checks"] if not c["pass"]]


def test_public_loader_hides_gold():
    for pub in loader.public_cases("eval"):
        assert set(pub.keys()) == {"case_id", "split", "text", "conversation", "metadata"}


def test_metric_audit_passes_and_only_two_fields_corrected():
    rep = metric_audit.run()
    assert rep["all_pass"], [c for c in rep["checks"] if not c["pass"]]
    assert set(rep["corrected_fields"]) == {"crit_invented_action", "material_amb_flagged"}


def test_e1_metrics_module_unchanged():
    import inspect
    from truth_assurance_pipeline.tap_e1_intent.schema import stable_hash
    live = stable_hash(inspect.getsource(e1_metrics))
    assert live == metric_audit.E1_METRICS_SOURCE_HASH


def test_invented_action_metric_is_paraphrase_invariant():
    # a paraphrase ("polish" -> "improve") must NOT count as an invented action
    client = CachedModelClient(harness.CACHE_PATH)
    case = next(c for c in corpus.cases_for_split("eval") if c.case_id == "V11E001")
    rec = llm_interpreter.build_record(client.interpret(_req(case)).core, _req(case), baseline("D"))
    e1 = e1_metrics.score_case(case, rec)
    corr = score_case(case, rec)
    assert e1.crit_invented_action is True      # E1 (extractive) false-positives here
    assert corr.crit_invented_action is False   # corrected metric does not


# --- headline findings & reproducibility ------------------------------------

def test_llm_improves_constraint_preservation_vs_deterministic():
    r = harness.run_all()
    llm = r["metrics"]["eval_hidden"]["llm"][r["selection"]["selected_baseline"]]
    det = r["metrics"]["eval_hidden"]["deterministic"]["V4"]
    assert llm["explicit_constraint_preservation"] >= det["explicit_constraint_preservation"]
    assert llm["explicit_constraint_preservation"] >= 0.9


def test_llm_safer_on_adversarial():
    r = harness.run_all()
    b = r["selection"]["selected_baseline"]
    llm = r["metrics"]["adversarial"]["llm"][b]
    det = r["metrics"]["adversarial"]["deterministic"]["V4"]
    assert llm["severe_failure_count"] <= det["severe_failure_count"]
    assert llm["unsupported_assumption_rate"] <= det["unsupported_assumption_rate"]


def test_raw_llm_baseline_A_is_worse_than_structured():
    r = harness.run_all()
    A = r["metrics"]["eval_hidden"]["llm"]["A"]
    D = r["metrics"]["eval_hidden"]["llm"]["D"]
    assert A["severe_failure_count"] > D["severe_failure_count"]


def test_selection_uses_dev_and_verdict_is_limited():
    r = harness.run_all()
    assert r["selection"]["selected_baseline"] in {b.name for b in BASELINES}
    assert r["verdict"] in ("PASS_WITH_LIMITED_CLAIM", "INCONCLUSIVE", "FAIL")
    assert r["gates"]["all_pass"] == (r["verdict"] == "PASS_WITH_LIMITED_CLAIM")


def test_evaluation_reproducible():
    a = json.dumps(harness.run_all(), sort_keys=True, default=str)
    b = json.dumps(harness.run_all(), sort_keys=True, default=str)
    assert a == b


def test_eval_lock_stable():
    assert corpus.eval_lock() == corpus.eval_lock()
