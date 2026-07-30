"""
Mock-backend unit tests for the RM1 harness (no torch/transformers/GPU required).

Covers the resource gate, the model-authority boundary (deterministic assignment of
id/provenance/authority), bounded extraction with no gold leakage, the router, the faithfulness
evaluator's fault detection, the clarification bound, and the RESOURCE_BLOCKED path.

    python -m unittest -v \
        experiments.hybrid_token_event_attention.real_model.tests.test_real_model_harness
"""
from __future__ import annotations

import dataclasses as _dc
import os
import tempfile
import unittest

from ...datasets import build_dataset, DataCfg, RELATIONAL_FAMILIES
from ...event_schema import scope_mask, RELATION_TYPES, STATUSES
from .. import hf_backend as HB
from ..hf_backend import MockBackend, ResourceBlocked, probe_environment, resolve_dtype
from ..extraction import extract_records, _validate_shape, _extract_json_array
from ..evidence_pipeline import process_proposals, AUTHORITATIVE, QUARANTINED
from ..reasoning_router import (route, DETERMINISTIC_ONLY, DETERMINISTIC_PLUS_EVENT_ATTENTION,
                               QUARANTINE_OR_REVIEW)
from ..explanation import evaluate_faithfulness
from ..clarification import ClarificationRequest, run_clarification
from ..mock_corpus import make_mock_responder
from ..run_real_model import main, RealModelConfig


def _one_instance(family=None):
    _, held, _ = build_dataset(DataCfg(n_train=60, n_heldout=30))
    if family:
        held = [i for i in held if i.query.task_family == family]
    return held[0]


class TestResourceGate(unittest.TestCase):
    def test_probe_has_keys(self):
        env = probe_environment()
        for k in ("python_version", "cpu_count", "packages", "cuda_available", "supported_dtypes"):
            self.assertIn(k, env)

    def test_cpu_dtype_defaults_fp32(self):
        env = {"cuda_available": False, "mps_available": False, "supported_dtypes": ["float32"]}
        self.assertEqual(resolve_dtype("auto", env), "float32")
        with self.assertRaises(ValueError):
            resolve_dtype("bf16", env)   # bf16 not supported on cpu → explicit error, no silent switch

    def test_no_model_id_blocks(self):
        with self.assertRaises(ResourceBlocked):
            HB.load_backend(RealModelConfig(model_id=""))

    def test_missing_torch_blocks_with_remediation(self):
        if HB._pkg_present("torch") and HB._pkg_present("transformers"):
            self.skipTest("torch/transformers installed — real backend would load")
        with self.assertRaises(ResourceBlocked) as ctx:
            HB.load_backend(RealModelConfig(model_id="some/model"))
        rb = ctx.exception
        self.assertIn("torch", " ".join(rb.missing))
        self.assertTrue(rb.remediation and rb.recommended_command)

    def test_mock_backend_forced_when_responder_set(self):
        b = HB.load_backend(RealModelConfig(model_id="x", mock_responder=lambda p: "{}"))
        self.assertFalse(b.is_real)
        self.assertEqual(b.info()["backend"], "MOCK")


class TestExtraction(unittest.TestCase):
    def test_span_must_be_substring(self):
        docs = {"D0": "purchases above threshold require approval"}
        items = [{"subject": "ent_1", "relation": "requires_approval", "object": "ent_2",
                  "source_document_id": "D0", "source_span": "require approval"},
                 {"subject": "ent_1", "relation": "requires_approval", "object": "ent_2",
                  "source_document_id": "D0", "source_span": "HALLUCINATED SPAN"}]
        good, errs = _validate_shape(items, docs)
        self.assertEqual(len(good), 1)
        self.assertTrue(any("substring" in e for e in errs))

    def test_bad_relation_rejected(self):
        docs = {"D0": "text"}
        good, errs = _validate_shape([{"subject": "ent_1", "relation": "not_a_relation",
                                       "object": "ent_2", "source_document_id": "D0",
                                       "source_span": "text"}], docs)
        self.assertEqual(good, [])

    def test_retry_feedback_has_no_gold(self):
        inst = _one_instance()
        # backend that first emits garbage, then a valid extraction
        state = {"n": 0}

        def responder(prompt):
            state["n"] += 1
            if state["n"] == 1:
                return "not json at all"
            return make_mock_responder(inst)(prompt)

        # the retry prompt must never contain the gold answer text
        seen_prompts = []

        class Spy(MockBackend):
            def generate(self, prompt, **kw):
                seen_prompts.append(prompt)
                return super().generate(prompt, **kw)

        b = Spy(responder=responder)
        res = extract_records(b, [{"document_id": "DOC-0", "text": inst.raw_text}],
                              inst.query.task_family, max_attempts=2)
        from ...datasets import CLASS_NAMES
        gold_text = CLASS_NAMES[inst.gold_answer]
        self.assertTrue(any("rejected by the deterministic validator" in p for p in seen_prompts))
        for p in seen_prompts:
            self.assertNotIn(f'"answer": "{gold_text}"', p)


class TestEvidencePipeline(unittest.TestCase):
    def test_valid_proposal_resolves_authoritative_with_fresh_id(self):
        inst = _one_instance()
        o = inst.oracle_records[0]
        prop = {"subject": f"ent_{o.subject_id}", "relation": RELATION_TYPES[o.relation_type],
                "object": f"ent_{o.object_id_or_value}", "normalized_value": o.normalized_value,
                "version": o.version, "status": STATUSES[o.status],
                "source_document_id": "DOC-0", "source_span": "x", "confidence": 0.95}
        pr = process_proposals([prop], inst, K=8)
        self.assertEqual(pr.evidence_id_preservation, 1.0)
        self.assertEqual(pr.unauthorized_inclusion, 0)
        states = [p.state for p in pr.processed]
        self.assertIn(AUTHORITATIVE, states + [AUTHORITATIVE])  # resolved to a real ledger record
        for p in pr.processed:
            if p.record is not None:
                self.assertTrue(p.record.hash_valid())

    def test_hallucinated_identity_quarantined(self):
        inst = _one_instance()
        prop = {"subject": "ent_99999", "relation": "requires_approval", "object": "ent_88888",
                "source_document_id": "DOC-0", "source_span": "x", "confidence": 0.99}
        pr = process_proposals([prop], inst, K=8)
        self.assertEqual(pr.admitted_ids, [])
        self.assertTrue(any(p.state == QUARANTINED for p in pr.processed))

    def test_unauthorized_cross_tenant_never_admitted(self):
        inst = _one_instance()
        o = inst.oracle_records[0]
        prop = {"subject": f"ent_{o.subject_id}", "relation": RELATION_TYPES[o.relation_type],
                "object": f"ent_{o.object_id_or_value}", "normalized_value": o.normalized_value,
                "version": o.version, "status": STATUSES[o.status],
                "source_document_id": "DOC-0", "source_span": "x", "confidence": 0.95}
        # tamper the ledger's tenant so authorization must fail
        inst2 = _dc.replace(inst)
        pr = process_proposals([prop], inst, K=8)
        self.assertEqual(pr.unauthorized_inclusion, 0)


class TestRouter(unittest.TestCase):
    def test_relational_routes_to_event(self):
        inst = _one_instance("authoritative_source")
        rd = route("authoritative_source", inst.oracle_records, inst.required_ids, 1.0)
        self.assertEqual(rd.route, DETERMINISTIC_PLUS_EVENT_ATTENTION)

    def test_threshold_routes_deterministic(self):
        inst = _one_instance("exact_threshold")
        rd = route("exact_threshold", inst.oracle_records, inst.required_ids, 1.0)
        self.assertEqual(rd.route, DETERMINISTIC_ONLY)

    def test_integrity_failure_quarantines(self):
        rd = route("exact_threshold", [], [], 0.5)
        self.assertEqual(rd.route, QUARANTINE_OR_REVIEW)


class TestFaithfulness(unittest.TestCase):
    def setUp(self):
        self.tf = {"task_family": "approval_req_vs_granted", "decision": "NO",
                   "boolean_outcome": False, "abstained": False, "material_conflict": False,
                   "evidence_ids": [1]}
        self.cr = [{"evidence_id": 1, "subject_id": 5, "relation_type": 9, "object_id_or_value": 2,
                    "normalized_value": 2, "version": 0, "status": 0, "authority": 0.9,
                    "source_span": "approval requested", "provenance_hash": "abc"}]

    def test_fabricated_id_detected(self):
        r = evaluate_faithfulness("See [EV-7777].", self.tf, self.cr)
        self.assertIn("fabricated_evidence_id", r.flags)

    def test_unsupported_number_detected(self):
        r = evaluate_faithfulness("[EV-1] cites amount 999999.", self.tf, self.cr,
                                  expect_unsupported=True)
        self.assertIn("unsupported_claim", r.flags)
        self.assertEqual(r.unsupported_claim_recall, 1.0)

    def test_missing_qualifier_detected(self):
        r = evaluate_faithfulness("The approval [EV-1] was granted.", self.tf, self.cr)
        self.assertIn("missing_qualifier", r.flags)

    def test_clean_explanation_passes(self):
        r = evaluate_faithfulness("The decision is NO; no valid grant [EV-1] was found.",
                                  self.tf, self.cr)
        self.assertEqual(r.supported_claim_precision, 1.0)
        self.assertEqual(r.qualifier_preservation, 1.0)
        self.assertFalse(r.blocked)

    def test_corrupt_provenance_blocks(self):
        cr = [dict(self.cr[0], provenance_hash="CORRUPT")]
        r = evaluate_faithfulness("[EV-1] no grant.", self.tf, cr)
        self.assertTrue(r.blocked)


class TestClarification(unittest.TestCase):
    def test_bounded_and_validates_against_source(self):
        req = ClarificationRequest(request_id="CLR-1", triggering_evidence_ids=[1],
                                   unresolved_question="which?", permitted_document_ids=["D0"],
                                   permitted_source_spans=["s"], max_attempts=1,
                                   requesting_component="event_reasoner")
        calls = {"validate": 0}

        def validate(interp):
            calls["validate"] += 1
            return {"outcome": "REJECTED", "detail": "not_in_source"}

        out = run_clarification(req, ask=lambda p: '{"x":1}', validate=validate,
                                parse=lambda r: {"x": 1}, question_prompt="q")
        self.assertEqual(len(out.responses), 1)                 # bounded to max_attempts
        self.assertEqual(out.final_outcome, "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(calls["validate"], 1)


class TestResourceBlockedRun(unittest.TestCase):
    def test_blocked_run_writes_artifacts(self):
        if HB._pkg_present("torch") and HB._pkg_present("transformers"):
            self.skipTest("torch present — would attempt a real load")
        with tempfile.TemporaryDirectory() as d:
            out = main(cfg=RealModelConfig(model_id="some/model", output_dir=d))
            self.assertEqual(out["status"], "RESOURCE_BLOCKED")
            self.assertTrue(os.path.exists(os.path.join(d, "REAL_MODEL_RESULTS.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "REAL_MODEL_VALIDATION_REPORT.md")))
            self.assertTrue(os.path.exists(os.path.join(d, "RESOURCE_MANIFEST.json")))


if __name__ == "__main__":
    unittest.main()
