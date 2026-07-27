"""
test_parity.py — D1/D2 arm-parity check (resolves the D2>D1 anomaly).

Decisive question: is D2 (learned routing) materially above oracle-route D1 because of a hidden
code-path shortcut, or purely because of which events get routed? To isolate this we force the
SAME model to run both the D1 (oracle) and D2 (learned) code paths on the SAME routed indices.
If every non-routing code path (query update, binding, bounded attention, decoder, hop head) is
shared, the two runs must produce BIT-IDENTICAL answer logits. Divergence ⇒ an arm mismatch.
"""
from __future__ import annotations

import torch

from experiments.phase_iterative_quadratic.multihop_dataset import build_vocab, generate
from experiments.phase_iterative_quadratic.hybrid_model import IterativeHybrid
from experiments.phase_iterative_quadratic.train import collate_iter


def _one_model_two_paths(routing_mode):
    torch.manual_seed(0)
    vocab = build_vocab()
    m = IterativeHybrid(vocab.size, vocab.n_id, hops=2, routing_mode=routing_mode, W=32, K=8)
    m.eval()
    data = generate(vocab, 32, 2, 24, 99001)
    ids, ep, pp, vl, ans, reqf, reqe, hoptgt = collate_iter(data, vocab)
    return m, (ids, ep, pp, vl, reqf, reqe)


@torch.no_grad()
def test_forced_routing_makes_arms_identical():
    """Learned-route run and oracle-route run, forced onto the learned run's own routed indices,
    must yield identical answer logits — proving only the routing SELECTION differs across arms."""
    m, (ids, ep, pp, vl, reqf, reqe) = _one_model_two_paths("learned")

    # D2 code path (learned routing selects the events).
    out_learned = m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
    routed = out_learned["routed"]                      # list[H] of [B, 2K] token positions

    # D1 code path (oracle routing) but FORCED onto exactly the events D2 selected.
    m.routing_mode = "oracle"
    out_oracle = m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe, forced_routed=routed)

    assert torch.allclose(out_learned["answer_logits"], out_oracle["answer_logits"], atol=1e-6), (
        "arm mismatch: identical routed indices produced different answer logits — a non-routing "
        "code path differs between the oracle (D1) and learned (D2) arms")


@torch.no_grad()
def test_oracle_forced_equals_oracle_selfroute_when_indices_match():
    """Sanity: forcing the oracle arm onto the indices it would itself pick reproduces its own
    output (the forced_routed plumbing does not alter the shared path)."""
    m, (ids, ep, pp, vl, reqf, reqe) = _one_model_two_paths("oracle")
    a = m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
    b = m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe, forced_routed=a["routed"])
    assert torch.allclose(a["answer_logits"], b["answer_logits"], atol=1e-6)


if __name__ == "__main__":
    test_forced_routing_makes_arms_identical()
    test_oracle_forced_equals_oracle_selfroute_when_indices_match()
    print("PARITY OK")
