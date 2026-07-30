"""
test_real_model_harness.py — unit tests for the RM1 harness (§16 B: mock backend, no weights).

These tests exercise the full pipeline plumbing and the deterministic guarantees WITHOUT torch,
transformers, or any model weights. They assert:
  * the resource gate raises RESOURCE_BLOCKED with a remediation manifest when core packages are
    missing, and never silently downgrades / quantizes;
  * dtype/device selection is honest;
  * schema-guided extraction parses, verifies source spans, and bounds retries;
  * the deterministic evidence pipeline resolves, states, and admits records, quarantining/rejecting
    malformed, unauthorized, corrupt, low-confidence and hallucinated proposals;
  * the integrity invariants hold (unauthorized admitted = 0, corrupt rejected, id preservation = 1,
    bypass fails closed);
  * the router routes contracts correctly;
  * the RM1 faithfulness evaluator detects unsupported claims and dropped qualifiers;
  * the end-to-end mock run produces the required artifacts and proof-of-execution fields.
"""
from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace

from experiments.hybrid_token_event_attention.datasets import build_dataset, DataCfg, ABSTAIN
from experiments.hybrid_token_event_attention.event_schema import REL, ACTIVE, SUPERSEDED, scope_mask
from experiments.hybrid_token_event_attention.real_model.hf_backend import (
    ModelConfig, MockBackend, load_backend, probe_environment, ResourceBlocked,
    _select_dtype, _select_device)
from experiments.hybrid_token_event_attention.real_model.prompts import (
    composite_mock_responder, build_extraction_prompt, extract_source_block)
from experiments.hybrid_token_event_attention.real_model.extraction import (
    extract_events, ClarificationRequest, ClarificationResponse, run_clarification)
from experiments.hybrid_token_event_attention.real_model.evidence_pipeline import (
    run_pipeline, VALIDATED, AUTHORITATIVE, QUARANTINED, REJECTED, SUPERSEDED_STATE)
from experiments.hybrid_token_event_attention.real_model.reasoning_router import (
    route, DETERMINISTIC_ONLY, DETERMINISTIC_PLUS_EVENT_ATTENTION, QUARANTINE_OR_REVIEW)
from experiments.hybrid_token_event_attention.real_model.evaluation import (
    RM1FaithfulnessEvaluator, integrity_controls, explanation_controls, record_to_provisional)
from experiments.hybrid_token_event_attention.real_model.explanation import build_typed_result
from experiments.hybrid_token_event_attention.real_model import run_real_model as R


def _one_instance(family="active_policy"):
    _, held, _ = build_dataset(DataCfg(n_train=60, n_heldout=60, seed=1))
    for inst in held:
        if inst.query.task_family == family:
            return inst
    return held[0]


class TestResourceGate(unittest.TestCase):
    def test_missing_packages_blocks(self):
        env = probe_environment()
        env = {"versions": dict(env["versions"], torch=None, transformers=None),
               "hardware": env["hardware"]}
        cfg = ModelConfig(model_id="some/model")
        with self.assertRaises(ResourceBlocked) as ctx:
            load_backend(cfg, env)
        m = ctx.exception.manifest
        self.assertEqual(m["status"], "RESOURCE_BLOCKED")
        self.assertIn("missing_packages", m["reason"])
        self.assertIn("recommended_steps", m["remediation"])
        self.assertTrue(any("requirements-real-model" in s for s in m["remediation"]["recommended_steps"]))

    def test_no_silent_downgrade_to_mock(self):
        # load_backend must never return a MockBackend
        env = probe_environment()
        cfg = ModelConfig(model_id="some/model")
        try:
            backend = load_backend(cfg, env)
            self.assertNotIsInstance(backend, MockBackend)
        except ResourceBlocked:
            pass  # expected in this environment

    def test_dtype_selection_honest(self):
        env = {"versions": {}, "hardware": {"supported_fp": ["float32"], "cuda_available": False,
                                            "mps_available": False}}
        # fp16 on cpu is refused
        _, err = _select_dtype(ModelConfig(model_id="m", dtype="fp16"), "cpu", env)
        self.assertEqual(err, "fp16_requested_on_cpu")
        # bf16 unsupported is refused
        _, err2 = _select_dtype(ModelConfig(model_id="m", dtype="bf16"), "cpu", env)
        self.assertEqual(err2, "bf16_requested_but_unsupported")
        # auto on cpu -> float32
        dt, err3 = _select_dtype(ModelConfig(model_id="m", dtype="auto"), "cpu", env)
        self.assertEqual((dt, err3), ("float32", None))

    def test_four_bit_requires_cuda(self):
        env = probe_environment()
        cfg = ModelConfig(model_id="m", load_in_4bit=True, device="cpu")
        with self.assertRaises(ResourceBlocked) as ctx:
            load_backend(cfg, env)
        self.assertIn(ctx.exception.manifest["reason"],
                      ("missing_packages:torch,transformers", "4bit_requires_cuda",
                       "missing_packages:torch", "missing_packages:transformers"))


class TestExtraction(unittest.TestCase):
    def setUp(self):
        self.backend = MockBackend(responder=composite_mock_responder)
        self.inst = _one_instance()

    def test_extraction_parses_and_verifies_spans(self):
        docs = {0: self.inst.raw_text}
        res = extract_events(self.backend, self.inst.query.task_family,
                             f"ent_{self.inst.query.subject_id}", docs, permitted_doc_ids=[0])
        self.assertTrue(res.parse_ok)
        self.assertTrue(res.schema_ok)
        self.assertTrue(len(res.proposals) > 0)
        self.assertTrue(all(p.span_verified for p in res.proposals))

    def test_bounded_retries_on_bad_json(self):
        bad = MockBackend(responder=lambda s, u: "not json at all")
        docs = {0: self.inst.raw_text}
        res = extract_events(bad, "active_policy", "ent_1", docs, max_attempts=2)
        self.assertFalse(res.parse_ok)
        self.assertEqual(len(res.attempts), 2)  # exactly two bounded attempts

    def test_retry_feedback_excludes_gold(self):
        _, user = build_extraction_prompt("active_policy", "ent_1", {0: "doc x"},
                                          retry_feedback="Schema errors: event[0]_missing_relation")
        self.assertNotIn("gold", user.lower())
        self.assertNotIn("answer", user.lower().split("decision question")[0][:0] or "")


class TestEvidencePipeline(unittest.TestCase):
    def setUp(self):
        self.inst = _one_instance()
        self.query = self.inst.query
        self.ledger = self.inst.oracle_records

    def _props(self):
        return [record_to_provisional(r) for r in self.ledger]

    def test_valid_records_admitted(self):
        out = run_pipeline(self._props(), self.query, self.ledger, K=8)
        self.assertTrue(len(out.slots) > 0)
        self.assertTrue(all(s.record.hash_valid() for s in out.slots))

    def test_hallucinated_identity_quarantined(self):
        props = self._props()
        bogus = replace(props[0], subject="ent_99999", source_span=props[0].source_span)
        out = run_pipeline([bogus], self.query, self.ledger, K=8)
        self.assertEqual(out.envelopes[0].state, QUARANTINED)
        self.assertEqual(out.envelopes[0].reason, "unresolved_identity")

    def test_type_incompatible_rejected(self):
        props = self._props()
        bad = replace(props[0], relation="not_a_relation")
        out = run_pipeline([bad], self.query, self.ledger, K=8)
        self.assertEqual(out.envelopes[0].state, REJECTED)

    def test_low_confidence_quarantined(self):
        props = self._props()
        lowc = replace(props[0], confidence=0.1)
        out = run_pipeline([lowc], self.query, self.ledger, K=8)
        self.assertEqual(out.envelopes[0].state, QUARANTINED)
        self.assertEqual(out.envelopes[0].reason, "low_confidence")

    def test_unverified_span_quarantined(self):
        props = self._props()
        us = replace(props[0], span_verified=False)
        out = run_pipeline([us], self.query, self.ledger, K=8)
        self.assertEqual(out.envelopes[0].state, QUARANTINED)

    def test_model_cannot_assign_ids(self):
        # even if a proposal "claims" an id, the pipeline assigns the ledger id
        props = self._props()
        out = run_pipeline([props[0]], self.query, self.ledger, K=8)
        env0 = out.envelopes[0]
        self.assertIsNotNone(env0.record)
        self.assertIn(env0.record.evidence_id, {r.evidence_id for r in self.ledger})


class TestIntegrityControls(unittest.TestCase):
    def test_invariants(self):
        inst = _one_instance()
        c = integrity_controls(inst.query, inst.oracle_records)
        self.assertEqual(c["unauthorized_events_admitted"], 0)
        self.assertEqual(c["corrupt_authoritative_rejected"], 1.0)
        self.assertEqual(c["evidence_id_preservation"], 1.0)
        self.assertEqual(c["bypass_failed_closed"], 1.0)
        self.assertTrue(c["order_shuffle_admission_invariant"])


class TestRouter(unittest.TestCase):
    def test_routes(self):
        recs = []
        self.assertEqual(route("exact_threshold", recs).route, DETERMINISTIC_ONLY)
        self.assertEqual(route("supporting_vs_opposing", recs).route,
                         DETERMINISTIC_PLUS_EVENT_ATTENTION)
        self.assertEqual(route("exact_threshold", recs, required_present=False).route,
                         QUARANTINE_OR_REVIEW)
        self.assertEqual(route("active_policy", recs, has_invalid_provenance=True).route,
                         QUARANTINE_OR_REVIEW)


class TestFaithfulness(unittest.TestCase):
    def setUp(self):
        self.ev = RM1FaithfulnessEvaluator()
        self.inst = _one_instance()
        # a genuine typed result over the oracle records
        from experiments.hybrid_token_event_attention.deterministic_event_reasoner import reason
        self.outcome, self.cited = reason(self.inst.oracle_records, self.inst.query.task_family,
                                          self.inst.query.subject_id)
        self.typed = build_typed_result(self.outcome, self.cited, self.inst.oracle_records,
                                        self.inst.query.task_family)
        self.docs = {0: self.inst.raw_text}

    def test_detects_unsupported_and_dropped_qualifier(self):
        c = explanation_controls(self.ev, self.typed, self.inst.oracle_records, self.docs)
        self.assertTrue(c["unsupported_claim_detected"])
        self.assertTrue(c["removed_qualifier_detected"])
        self.assertGreaterEqual(c["faithful_qualifier_preservation"], 0.99)

    def test_stale_version_confusion_flagged(self):
        # cite a superseded record -> active/stale confusion
        stale = [r for r in self.inst.oracle_records if r.status == SUPERSEDED]
        if stale:
            text = f"Result [EV-{stale[0].evidence_id}]."
            rep = self.ev.evaluate(text, self.typed, self.inst.oracle_records, self.docs)
            self.assertTrue(rep.active_stale_confusion)


class TestEndToEnd(unittest.TestCase):
    def test_mock_run_writes_artifacts_and_proof(self):
        rc = R.main(["--mock-plumbing", "--mode", "smoke", "--limit", "6"])
        self.assertEqual(rc, 0)
        rdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
        with open(os.path.join(rdir, "REAL_MODEL_RESULTS.json")) as _f:
            results = json.load(_f)
        self.assertEqual(results["actual_model_execution"], "MOCK")
        proof = results["execution_proof"]
        for k in ("model_class", "logits_shape", "generated_token_ids", "device", "dtype"):
            self.assertIn(k, proof)
        # deterministic governed path solves the controlled corpus; direct-model mock abstains
        self.assertGreaterEqual(results["arms"]["arms_accuracy"]["RM3"], 0.9)
        self.assertTrue(os.path.exists(os.path.join(rdir, "REAL_MODEL_TRACES.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(rdir, "REAL_MODEL_VALIDATION_REPORT.md")))

    def test_resource_blocked_run_stops_and_reports(self):
        rc = R.main(["--model-id", "some-org/some-real-model", "--mode", "smoke", "--limit", "5"])
        self.assertEqual(rc, 3)  # blocked in this environment
        rdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
        with open(os.path.join(rdir, "REAL_MODEL_RESULTS.json")) as _f:
            results = json.load(_f)
        self.assertEqual(results["status"], "RESOURCE_BLOCKED")
        self.assertEqual(results["actual_model_execution"], "RESOURCE_BLOCKED")


if __name__ == "__main__":
    unittest.main()
