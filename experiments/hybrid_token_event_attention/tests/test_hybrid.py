"""
Stdlib-unittest suite for the hybrid token/event attention experiment (no pytest/torch/numpy).

Covers the structural invariants the acceptance criteria hinge on plus the autograd correctness
and the softmax-axis requirement of §4. Run: python -m unittest -v
    experiments.hybrid_token_event_attention.tests.test_hybrid
"""
from __future__ import annotations

import math
import unittest

from experiments.hybrid_token_event_attention import autograd as ag
from experiments.hybrid_token_event_attention.autograd import Tensor
from experiments.hybrid_token_event_attention._common import RNG
from experiments.hybrid_token_event_attention.datasets import build_dataset, DataCfg
from experiments.hybrid_token_event_attention.event_schema import scope_mask
from experiments.hybrid_token_event_attention.normalization_bridge import (
    build_working_set, evidence_id_preservation, provenance_valid)
from experiments.hybrid_token_event_attention.event_encoder import EventEncoder
from experiments.hybrid_token_event_attention.event_attention import EventSelfAttention
from experiments.hybrid_token_event_attention.deterministic_event_reasoner import reason
import dataclasses as _dc


class TestAutograd(unittest.TestCase):
    def test_gradcheck_matmul_softmax_ce(self):
        rng = RNG(0)
        E = Tensor([[rng.normal() * .4 for _ in range(4)] for _ in range(4)], True)
        W = Tensor([[rng.normal() * .4 for _ in range(4)] for _ in range(4)], True)
        Wo = Tensor([[rng.normal() * .4 for _ in range(5)] for _ in range(4)], True)

        def build():
            A = ag.row_softmax(ag.matmul(E, W))
            H = ag.matmul(A, E)
            pooled = ag.row_mean(ag.tanh(H))
            return ag.cross_entropy(ag.matmul(pooled, Wo), 2)

        loss = build()
        loss.backward()
        eps, maxerr = 1e-5, 0.0
        for i in range(4):
            for j in range(4):
                W.data[i][j] += eps
                lp = build().data[0][0]
                W.data[i][j] -= 2 * eps
                lm = build().data[0][0]
                W.data[i][j] += eps
                maxerr = max(maxerr, abs((lp - lm) / (2 * eps) - W.grad[i][j]))
        self.assertLess(maxerr, 1e-4)


class TestEventAttention(unittest.TestCase):
    def test_softmax_axis_is_slots_and_matrix_is_KxK(self):
        rng = RNG(1)
        enc = EventEncoder(16, rng)
        attn = EventSelfAttention(16, rng)
        _, ho, _ = build_dataset(DataCfg(n_train=40, n_heldout=8))
        inst = ho[0]
        recs = inst.oracle_records[:8]
        E = enc.encode(recs, inst.query)
        _, A = attn.readout(E)
        self.assertEqual(len(A), len(recs))
        for row in A:
            self.assertEqual(len(row), len(recs))       # K x K
            self.assertAlmostEqual(sum(row), 1.0, places=6)  # softmax over slots


class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.train, self.held, self.vocab = build_dataset(DataCfg(n_train=120, n_heldout=60))

    def test_evidence_id_preservation_is_one(self):
        for inst in self.held:
            slots, _ = build_working_set(inst.predicted_records, inst.query, 8)
            self.assertEqual(evidence_id_preservation(slots), 1.0)

    def test_unauthorized_cross_tenant_never_admitted(self):
        for inst in self.held:
            bad = _dc.replace(inst.oracle_records[0])
            bad.evidence_id = 99999
            bad.tenant_id = inst.query.tenant_id + 1
            bad.access_scope = scope_mask([0, 1, 2, 3, 4])
            bad.seal()
            slots, rep = build_working_set(inst.oracle_records + [bad], inst.query, 8)
            self.assertNotIn(99999, [s.evidence_id for s in slots])

    def test_tampered_record_rejected_by_provenance(self):
        inst = self.held[0]
        r = _dc.replace(inst.oracle_records[0])
        r.normalized_value += 5           # mutate an exact field WITHOUT re-sealing
        self.assertFalse(provenance_valid(r))

    def test_admitted_records_all_resolve(self):
        for inst in self.held:
            slots, _ = build_working_set(inst.predicted_records, inst.query, 8)
            for s in slots:
                self.assertTrue(s.record.hash_valid())


class TestDeterministicReasoner(unittest.TestCase):
    def test_oracle_reasoning_is_exact(self):
        train, _, _ = build_dataset(DataCfg(n_train=200, n_heldout=20))
        ok = sum(reason(i.oracle_records, i.query.task_family, i.query.subject_id)[0]
                 == i.gold_answer for i in train)
        self.assertEqual(ok, len(train))    # rules reproduce the ground truth exactly on oracle

    def test_predicted_reasoning_degrades(self):
        train, _, _ = build_dataset(DataCfg(n_train=200, n_heldout=20))
        ok = sum(reason(i.predicted_records, i.query.task_family, i.query.subject_id)[0]
                 == i.gold_answer for i in train)
        self.assertLess(ok / len(train), 1.0)   # extraction noise creates the H5-H6 gap


if __name__ == "__main__":
    unittest.main()
