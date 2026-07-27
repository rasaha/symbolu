"""
test_audit.py — §17 audit tests (fast, no training) proving the system is a bounded evidence
engine, not a generative LM, with autonomous (non-teacher-forced) evaluation.
"""
from __future__ import annotations

import copy
import torch

from experiments.phase_iterative_quadratic.multihop_dataset import build_vocab, generate
from experiments.phase_iterative_quadratic.hybrid_model import IterativeHybrid
from experiments.phase_iterative_quadratic.train import collate_iter
from experiments.phase_iterative_quadratic.serializer import serialize


def _model(vocab, mode="learned", **kw):
    torch.manual_seed(0)
    return IterativeHybrid(vocab.size, vocab.n_id, hops=2, routing_mode=mode, W=32, K=8, **kw).eval()


def test_no_lm_head():
    v = build_vocab(); m = _model(v)
    # answer/hop heads classify over n_id identities, NOT the token vocabulary
    assert m.answer_head.out_features == v.n_id and v.n_id < v.size
    assert m.hop_head.out_features == v.n_id
    assert not any("lm_head" in n for n, _ in m.named_modules())


def test_learned_arm_ignores_labels():
    """Decisive no-leak proof: a LEARNED arm's output is invariant to the required-hop labels."""
    v = build_vocab(); m = _model(v, "learned")
    data = generate(v, 24, 2, 16, 5)
    ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(data, v)
    with torch.no_grad():
        o1 = m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)["answer_logits"]
        bad = torch.randint_like(reqf, 1, 40); bad_e = torch.randint_like(reqe, 0, 20)
        o2 = m(ids, ep, pp, vl, required_hops=bad, req_evidx=bad_e)["answer_logits"]
    assert torch.allclose(o1, o2, atol=1e-6)           # learned routing never reads the labels


def test_oracle_arm_uses_labels():
    """Sanity: the ORACLE arm DOES use labels (so the invariance above is meaningful)."""
    v = build_vocab(); m = _model(v, "oracle")
    data = generate(v, 24, 2, 16, 5)
    ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(data, v)
    with torch.no_grad():
        o1 = m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)["answer_logits"]
        o2 = m(ids, ep, pp, vl, required_hops=reqf.flip(0), req_evidx=reqe.flip(0))["answer_logits"]
    assert not torch.allclose(o1, o2, atol=1e-4)


def test_no_weight_update_at_inference():
    v = build_vocab(); m = _model(v)
    before = copy.deepcopy(m.state_dict())
    data = generate(v, 24, 2, 16, 5)
    ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(data, v)
    with torch.no_grad():
        m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
    after = m.state_dict()
    for k in before:
        assert torch.equal(before[k], after[k])        # inference never mutates weights


def test_serialization_contract():
    v = build_vocab(); m = _model(v)
    ex = generate(v, 24, 2, 1, 5)[0]
    pkt = serialize(m, ex, v)
    for key in ("query", "answer_candidate", "selected_evidence_ids", "evidence_chain",
                "hop_order", "confidence", "chain_complete"):
        assert key in pkt
    assert len(pkt["evidence_chain"]) == ex["n_required"]
    for link in pkt["evidence_chain"]:
        for f in ("evidence_id", "source_ref", "entity", "relation", "value"):
            assert f in link
    # selected evidence IDs refer back to real records
    real = {e["evidence_id"] for e in ex["events"]}
    assert all(eid in real for eid in pkt["selected_evidence_ids"])


def test_key_value_representation_present():
    """The earlier defect (event without value) is fixed: each event emits KEY and VAL tokens."""
    v = build_vocab(); ex = generate(v, 16, 2, 1, 5)[0]
    for ev in ex["events"]:
        kp = ex["key_pos"][ex["events"].index(ev)]
        assert ex["tokens"][kp] == v.key(ev["entity"], ev["relation"])
        assert ex["tokens"][kp + 1] == v.val(ev["value"])     # value is readable from the sequence
        assert "evidence_id" in ev and "source_pos" in ev


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok:", fn.__name__)
    print("ALL AUDIT TESTS PASSED")
