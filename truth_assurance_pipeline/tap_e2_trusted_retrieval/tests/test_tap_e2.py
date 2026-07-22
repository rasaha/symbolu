"""
TAP-E2 behavioral tests.

Verify the retrieval pipeline, evidence-unit provenance, gap detection, ranking
interpretability, the E1->E2 interface, leakage controls, reproducibility, and that
the layer stays a RETRIEVAL layer (no truth/claim judgments). TAP-E1 is imported only
through its public interface.
"""

import json

import pytest

from truth_assurance_pipeline.tap_e1_intent import IntentUnderstandingLayer, config as e1_config
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e2_trusted_retrieval import (
    BASELINES, RetrievalIndex, TrustedRetrievalLayer, config, validate_record,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval import harness, loader, metrics
from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus import documents, queries
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import GapType

_INDEX = RetrievalIndex.build(documents.units())
_E1 = IntentUnderstandingLayer(e1_config("V4"))


def _intent(text):
    return _E1.interpret(RawUserRequest("t", text))


def _retrieve(cfg_name, text):
    return TrustedRetrievalLayer(config(cfg_name), _INDEX).retrieve(_intent(text))


# --- interface & schema -----------------------------------------------------

def test_consumes_e1_intentrecord():
    rec = _retrieve("F", "How long do we retain customer data?")
    assert rec.intent_objective
    ok, problems = validate_record(rec)
    assert ok, problems


def test_all_baselines_valid_records():
    for cfg in BASELINES:
        rec = TrustedRetrievalLayer(cfg, _INDEX).retrieve(
            _intent("What is the API rate limit?"))
        ok, problems = validate_record(rec)
        assert ok, (cfg.name, problems)


# --- evidence units & provenance --------------------------------------------

def test_every_candidate_has_complete_provenance_in_full_pipeline():
    rec = _retrieve("F", "How long do we retain customer data?")
    assert rec.candidates
    for c in rec.candidates:
        assert c.provenance.is_complete()
        assert c.provenance.source_id and c.provenance.source_location
        assert c.provenance.retrieval_path and c.provenance.retrieval_score is not None


def test_provenance_filter_drops_unsourced_evidence():
    # scratch-notes units have empty location -> incomplete provenance
    q = "How long do we retain customer data?"
    c_hits = {u for u in _retrieve("C", q).unit_ids}    # no provenance filter
    d_hits = {u for u in _retrieve("D", q).unit_ids}    # provenance filter
    assert any(u.startswith("SCRATCH-NOTES") for u in c_hits)
    assert not any(u.startswith("SCRATCH-NOTES") for u in d_hits)


def test_evidence_units_are_sub_document():
    # a retrieved unit is a sentence-level fragment, not a whole document
    rec = _retrieve("F", "How is data at rest protected?")
    assert rec.candidates
    top = rec.candidates[0].unit
    assert "#u" in top.unit_id and len(top.text) < 300


# --- ranking interpretability -----------------------------------------------

def test_ranking_signals_are_exposed():
    rec = _retrieve("F", "How long are audit logs retained?")
    s = rec.candidates[0].signals
    for v in (s.lexical, s.semantic, s.authority, s.freshness,
              s.provenance_completeness, s.specificity):
        assert 0.0 <= v <= 1.0


def test_confidence_is_multidimensional():
    rec = _retrieve("F", "How long are audit logs retained?")
    d = rec.confidence.to_dict()
    assert set(d) == {"entity_match", "semantic_relevance", "temporal_relevance",
                      "source_completeness", "provenance_quality", "retrieval_coverage"}


# --- gap detection ----------------------------------------------------------

def test_conflict_gap_detected_and_not_hidden():
    rec = _retrieve("E", "What is the minimum password length we require?")
    kinds = {g.gap_type for g in rec.gaps}
    assert GapType.CONFLICTING_SOURCES in kinds


def test_missing_evidence_gap_detected():
    rec = _retrieve("E", "What is our policy on cryptocurrency payments?")
    kinds = {g.gap_type for g in rec.gaps}
    assert GapType.INSUFFICIENT_EVIDENCE in kinds


def test_no_authoritative_source_gap():
    rec = _retrieve("E", "What does our official policy say the approved production deployment strategy is?")
    kinds = {g.gap_type for g in rec.gaps}
    assert GapType.NO_AUTHORITATIVE_SOURCE in kinds


def test_baselines_without_gap_detection_report_no_gaps():
    for name in ("A", "B", "C", "D"):
        rec = _retrieve(name, "What is the minimum password length we require?")
        assert rec.gaps == ()


# --- no hallucinated identifiers (structural) -------------------------------

def test_no_hallucinated_evidence_ids():
    ids = set(documents.unit_ids())
    for name in ("A", "F"):
        rec = _retrieve(name, "How much notice to terminate the vendor agreement?")
        assert all(uid in ids for uid in rec.unit_ids)


# --- leakage controls -------------------------------------------------------

def test_public_loader_hides_query_gold():
    for pub in loader.public_queries("eval"):
        assert set(pub.keys()) == {"query_id", "split", "request_text"}


def test_eval_lock_stable_and_no_dev_eval_overlap():
    assert loader.verify_eval_lock()
    dev = {q.request_text.strip().lower() for q in queries.queries_for_split("dev")}
    ev = {q.request_text.strip().lower() for q in queries.queries_for_split("eval")}
    assert not (dev & ev)


def test_no_duplicate_queries():
    seen = {}
    for q in queries.ALL_QUERIES:
        k = q.request_text.strip().lower()
        assert k not in seen, f"dup {q.query_id}"
        seen[k] = q.query_id


# --- reproducibility & gates ------------------------------------------------

def test_metrics_reproducible():
    def strip(r):
        r = dict(r); r.pop("latency_ms_mean", None); return r
    a = json.dumps(strip(harness.run_all()), sort_keys=True, default=str)
    b = json.dumps(strip(harness.run_all()), sort_keys=True, default=str)
    assert a == b


def test_hybrid_beats_or_matches_single_signal_on_recall():
    r = harness.run_all()
    ev = r["metrics"]["eval_locked"]
    assert ev["C"]["recall_at_k"] >= ev["A"]["recall_at_k"]
    assert ev["C"]["recall_at_k"] >= ev["B"]["recall_at_k"]


def test_provenance_filter_improves_completeness():
    r = harness.run_all()
    ev = r["metrics"]["eval_locked"]
    assert ev["D"]["provenance_completeness"] == 1.0
    assert ev["C"]["provenance_completeness"] < 1.0


def test_gap_detection_adds_gap_accuracy():
    r = harness.run_all()
    ev = r["metrics"]["eval_locked"]
    assert ev["E"]["gap_detection_accuracy"] > ev["D"]["gap_detection_accuracy"]


def test_gates_pass_and_verdict():
    r = harness.run_all()
    assert r["gates"]["all_pass"]
    assert r["verdict"] == "PASS_WITH_LIMITED_CLAIM"
    assert r["selection"]["selected_config"] in {c.name for c in BASELINES}


def test_severe_criticals_zero_on_selected():
    r = harness.run_all()
    sel = r["selection"]["selected_config"]
    crit = r["metrics"]["eval_locked"][sel]["critical_failures"]
    for k in ("authoritative_evidence_omitted", "provenance_missing",
              "conflicting_evidence_hidden", "hallucinated_evidence_identifiers"):
        assert crit[k] == 0
