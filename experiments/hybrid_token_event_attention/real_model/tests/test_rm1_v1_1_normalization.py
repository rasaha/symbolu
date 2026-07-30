"""
test_rm1_v1_1_normalization.py — negative controls for the RM1-v1.1 deterministic normalization layer.

These tests prove that the two bounded parser fixes (source-document binding + strict ent_<N> entity
parsing) tolerate normal model phrasing WITHOUT increasing false admission. Every case that must NOT
be admitted is asserted to be quarantined/rejected; every case that legitimately resolves is asserted
to resolve to an AUTHORIZED document/identity only. No acceptance threshold, prompt, reasoner, router,
or evaluator is touched.
"""
from __future__ import annotations

import unittest
from dataclasses import replace

from ...datasets import build_dataset, DataCfg
from ...event_schema import Query
from ..extraction import (resolve_document, RES_EXACT_ID, RES_SINGLE_PERMITTED, RES_UNIQUE_SPAN,
                          RES_AMBIGUOUS, RES_UNRESOLVED)
from ..evidence_pipeline import (run_pipeline, VALIDATED, AUTHORITATIVE, SUPERSEDED_STATE,
                                QUARANTINED, REJECTED)
from ..evaluation import record_to_provisional


def _instance(family="active_policy"):
    _, held, _ = build_dataset(DataCfg(n_train=60, n_heldout=60, seed=1))
    for inst in held:
        if inst.query.task_family == family:
            return inst
    return held[0]


def _admitted_ids(out):
    return {s.record.evidence_id for s in out.slots}


class TestDocumentBindingControls(unittest.TestCase):
    def setUp(self):
        self.inst = _instance()
        self.doc0 = self.inst.raw_text
        # take a real line from the single permitted document as a valid span
        self.valid_span = self.doc0.split(" . ")[0]

    def test_invented_doc_id_plus_correct_unique_span_binds_to_authorized_doc(self):
        # single permitted document (id 0); model invents id 920 but the span IS in doc 0
        rdoc, method, ok = resolve_document(
            {"source_document_id": 920, "source_span": self.valid_span}, {0: self.doc0})
        self.assertTrue(ok)
        self.assertEqual(rdoc, 0)                        # bound to the AUTHORIZED doc, not 920
        self.assertEqual(method, RES_SINGLE_PERMITTED)

    def test_invented_doc_id_plus_absent_span_quarantines(self):
        rdoc, method, ok = resolve_document(
            {"source_document_id": 920, "source_span": "this text is nowhere in the source"},
            {0: self.doc0})
        self.assertFalse(ok)
        self.assertIsNone(rdoc)
        self.assertEqual(method, RES_UNRESOLVED)

    def test_same_span_in_two_documents_is_ambiguous(self):
        rdoc, method, ok = resolve_document(
            {"source_document_id": 7, "source_span": "shared clause"},
            {0: "alpha shared clause beta", 1: "gamma shared clause delta"})
        self.assertFalse(ok)
        self.assertEqual(method, RES_AMBIGUOUS)

    def test_unique_span_across_docs_resolves_to_that_doc(self):
        rdoc, method, ok = resolve_document(
            {"source_document_id": 7, "source_span": "beta"},
            {0: "alpha shared clause beta", 1: "gamma shared clause delta"})
        self.assertTrue(ok)
        self.assertEqual((rdoc, method), (0, RES_UNIQUE_SPAN))

    def test_correct_span_from_unauthorized_document_not_resolved(self):
        # the span lives in a document that is NOT in the permitted set -> unresolved (quarantine)
        rdoc, method, ok = resolve_document(
            {"source_document_id": 1, "source_span": "secret clause"},
            {0: "only authorized text here"})           # permitted excludes the doc with the span
        self.assertFalse(ok)
        self.assertEqual(method, RES_UNRESOLVED)

    def test_exact_id_still_works(self):
        rdoc, method, ok = resolve_document(
            {"source_document_id": 0, "source_span": self.valid_span}, {0: self.doc0})
        self.assertEqual((rdoc, method, ok), (0, RES_EXACT_ID, True))


class TestEntityParsingControls(unittest.TestCase):
    def setUp(self):
        self.inst = _instance()
        self.query = self.inst.query
        self.ledger = self.inst.oracle_records

    def _valid_prop(self):
        # a provisional that resolves to a real ledger record (span already verified)
        return record_to_provisional(self.ledger[0], span_verified=True)

    def test_ent_token_resolves(self):
        out = run_pipeline([self._valid_prop()], self.query, self.ledger, K=8)
        self.assertTrue(len(out.slots) >= 1)
        self.assertTrue(all(s.record.hash_valid() for s in out.slots))

    def test_ent_phrasing_resolves(self):
        p = replace(self._valid_prop(), subject=f"the subject is {self._valid_prop().subject}")
        out = run_pipeline([p], self.query, self.ledger, K=8)
        self.assertEqual(len(out.slots), 1)             # tolerant of normal phrasing

    def test_bare_number_not_silently_resolved(self):
        p = replace(self._valid_prop(), subject="532")   # no ent_ token
        out = run_pipeline([p], self.query, self.ledger, K=8)
        self.assertEqual(_admitted_ids(out), set())
        self.assertEqual(out.envelopes[0].reason, "unresolved_subject")

    def test_ent_outside_ledger_not_admitted(self):
        p = replace(self._valid_prop(), subject="ent_999999")
        out = run_pipeline([p], self.query, self.ledger, K=8)
        self.assertEqual(_admitted_ids(out), set())      # no false admission
        self.assertEqual(out.envelopes[0].state, QUARANTINED)

    def test_cross_tenant_rejected(self):
        # resolve a real record but issue the query as a DIFFERENT tenant -> rejected, never admitted
        other = Query(task_family=self.query.task_family, subject_id=self.query.subject_id,
                      reader_role=self.query.reader_role, tenant_id=self.query.tenant_id + 1)
        out = run_pipeline([self._valid_prop()], other, self.ledger, K=8)
        self.assertEqual(_admitted_ids(out), set())
        self.assertEqual(out.envelopes[0].state, REJECTED)
        self.assertEqual(out.envelopes[0].reason, "cross_tenant")


if __name__ == "__main__":
    unittest.main()
