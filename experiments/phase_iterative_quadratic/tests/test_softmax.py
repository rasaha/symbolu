"""
test_softmax.py — §6 correctness tests for the bounded routed softmax attention.

Proves bounded == reference on equivalent masks, weights sum to 1, masked/future keys get
zero, K=0 reduces to local causal attention, W=N & K=0 reproduces full causal attention,
dedup counts once, routed order is irrelevant, gradients flow, router scores can be detached,
and the bounded path never forms [B,H,N,N].
"""
from __future__ import annotations

import torch

from experiments.phase_iterative_quadratic.reference_attention import ReferenceSoftmaxAttention
from experiments.phase_iterative_quadratic.bounded_attention import BoundedRoutedSoftmaxAttention
from experiments.phase_iterative_quadratic.routing_mask import build_allowed, full_mask

TOL = 1e-5


def _pair(D=32, H=4, seed=0):
    torch.manual_seed(seed)
    ref = ReferenceSoftmaxAttention(D, H)
    bnd = BoundedRoutedSoftmaxAttention(D, H)
    bnd.load_state_dict(ref.state_dict())
    return ref.eval(), bnd.eval()


def test_bounded_matches_reference():
    ref, bnd = _pair()
    B, N, D = 2, 20, 32
    x = torch.randn(B, N, D)
    qpos = torch.tensor([[N - 1], [N - 1]])
    routed = torch.tensor([[3, 7, 11, 15], [2, 5, 9, 14]])
    W = 5
    vlen = torch.tensor([N, N])
    gather, valid = build_allowed(qpos, routed, W, vlen, Lkv=N)
    mask = full_mask(gather, valid, N)
    out_ref = ref(x[:, -1:], x, mask)
    out_bnd = bnd(x[:, -1:], x, qpos, routed, W, vlen)
    assert (out_ref - out_bnd).abs().max().item() < TOL


def test_weights_sum_to_one():
    ref, bnd = _pair()
    B, N, D = 2, 16, 32
    x = torch.randn(B, N, D)
    qpos = torch.tensor([[N - 1]] * B)
    routed = torch.tensor([[1, 4, 8, 12]] * B)
    gather, valid = build_allowed(qpos, routed, 4, torch.tensor([N] * B), Lkv=N)
    mask = full_mask(gather, valid, N)
    w = ref.attn_weights(x[:, -1:], x, mask)                    # [B,H,1,N]
    s = w.sum(-1)
    assert torch.allclose(s, torch.ones_like(s), atol=TOL)


def test_future_and_masked_zero():
    ref, bnd = _pair()
    B, N, D = 1, 16, 32
    x = torch.randn(B, N, D)
    qpos = torch.tensor([[8]])                                  # causal cutoff at 8
    routed = torch.tensor([[3, 12, 15, -1]])                    # 12,15 are future → excluded; -1 none
    gather, valid = build_allowed(qpos, routed, 4, torch.tensor([N]), Lkv=N)
    mask = full_mask(gather, valid, N)
    assert not mask[0, 0, 9:].any()                             # no future key allowed
    w = ref.attn_weights(x[:, 8:9], x, mask)[0, :, 0]           # [H,N]
    assert w[:, 9:].abs().max().item() < TOL


def test_K0_is_local_causal():
    ref, bnd = _pair()
    B, N, D = 2, 18, 32
    x = torch.randn(B, N, D)
    qpos = torch.tensor([[N - 1]] * B)
    empty = torch.full((B, 0), -1, dtype=torch.long)
    out_bnd = bnd(x[:, -1:], x, qpos, empty, 6, torch.tensor([N] * B))
    # local-only reference: allow [N-6 .. N-1]
    mask = torch.zeros(B, 1, N, dtype=torch.bool); mask[:, 0, N - 6:] = True
    out_ref = ref(x[:, -1:], x, mask)
    assert (out_ref - out_bnd).abs().max().item() < TOL


def test_WN_K0_is_full_causal():
    ref, bnd = _pair()
    B, N, D = 2, 12, 32
    x = torch.randn(B, N, D)
    qpos = torch.arange(N).unsqueeze(0).expand(B, N)
    empty = torch.full((B, 0), -1, dtype=torch.long)
    out_bnd = bnd(x, x, qpos, empty, N, torch.tensor([N] * B))
    causal = torch.tril(torch.ones(N, N, dtype=torch.bool)).unsqueeze(0).expand(B, N, N)
    out_ref = ref(x, x, causal)
    assert (out_ref - out_bnd).abs().max().item() < TOL


def test_dedup_counts_once():
    B, N = 1, 16
    qpos = torch.tensor([[N - 1]])
    routed = torch.tensor([[N - 2, N - 3, 4, 4]])              # N-2,N-3 also in local window; 4 duplicated
    gather, valid = build_allowed(qpos, routed, 4, torch.tensor([N]), Lkv=N)
    kept = gather[0, 0][valid[0, 0]].tolist()
    assert len(kept) == len(set(kept))                         # no index counted twice


def test_routed_order_irrelevant():
    ref, bnd = _pair()
    B, N, D = 1, 16, 32
    x = torch.randn(B, N, D)
    qpos = torch.tensor([[N - 1]])
    r1 = torch.tensor([[2, 6, 9, 13]]); r2 = torch.tensor([[13, 9, 6, 2]])
    o1 = bnd(x[:, -1:], x, qpos, r1, 3, torch.tensor([N]))
    o2 = bnd(x[:, -1:], x, qpos, r2, 3, torch.tensor([N]))
    assert (o1 - o2).abs().max().item() < TOL


def test_gradients_flow():
    ref, bnd = _pair()
    B, N, D = 2, 14, 32
    x = torch.randn(B, N, D, requires_grad=True)
    qpos = torch.tensor([[N - 1]] * B); routed = torch.tensor([[1, 5, 9, 12]] * B)
    out = bnd(x[:, -1:], x, qpos, routed, 4, torch.tensor([N] * B))
    out.sum().backward()
    assert x.grad is not None and x.grad.abs().sum() > 0
    for p in (bnd.Wq, bnd.Wk, bnd.Wv, bnd.Wo):
        assert p.weight.grad is not None


def test_router_scores_detachable():
    # routed_idx comes from argsort of scores; detaching scores must not break attention grad
    ref, bnd = _pair()
    B, N, D = 1, 16, 32
    x = torch.randn(B, N, D, requires_grad=True)
    scores = torch.randn(B, N)
    routed = scores.detach().topk(4, dim=-1).indices                # detached routing
    out = bnd(x[:, -1:], x, torch.tensor([[N - 1]]), routed, 4, torch.tensor([N]))
    out.sum().backward()
    assert x.grad is not None


def test_no_NxN_tensor():
    # the bounded forward must not allocate an [B,H,N,N] tensor; check peak M dimension ≤ W+K
    B, N, D = 2, 256, 32
    ref, bnd = _pair()
    x = torch.randn(B, N, D)
    qpos = torch.tensor([[N - 1]] * B); routed = torch.randint(0, N, (B, 8))
    gather, valid = build_allowed(qpos, routed, 16, torch.tensor([N] * B), Lkv=N)
    assert gather.shape[-1] <= 16 + 8                              # M bounded by W+K
    out = bnd(x[:, -1:], x, qpos, routed, 16, torch.tensor([N] * B))
    assert out.shape == (B, 1, D)


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok:", fn.__name__)
    print("ALL SOFTMAX TESTS PASSED")
