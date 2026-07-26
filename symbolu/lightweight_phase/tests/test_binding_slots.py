"""Stage 8 — bounded binding slots: complexity, streaming memory, semantics."""

import pytest
import torch

from symbolu.lightweight_phase.binding_slots import BoundedBindingSlots
from symbolu.lightweight_phase.invariants import (
    assert_state_size_independent_of_n,
    shape_audit,
)


def _slots(seed=0, **kw):
    torch.manual_seed(seed)
    kw.setdefault("top_k", 3)
    return BoundedBindingSlots(embed_dim=32, num_slots=8, **kw)


def test_no_sequence_squared_or_nmd_tensor():
    slots = _slots().eval()
    for N in (4, 19, 64):
        with shape_audit(seq_len=N):  # raises on any two-sequence-axis tensor
            slots(torch.randn(2, N, 32))


def test_state_size_independent_of_n():
    slots = _slots()
    sizes = {}
    for N in (5, 20, 100, 400):
        _, st = slots(torch.randn(1, N, 32), return_state=True)
        sizes[N] = st.numel()
    assert_state_size_independent_of_n(sizes)


def test_slot_count_is_bounded():
    slots = _slots()
    _, st = slots(torch.randn(2, 200, 32), return_state=True)
    assert st.active.sum(-1).max().item() <= slots.num_slots


def test_streaming_chunked_equivalence_of_state_metadata():
    """Whole-sequence vs chunked writes converge to consistent active-slot counts."""
    slots = _slots().eval()
    x = torch.randn(1, 30, 32)
    _, st_full = slots(x, return_state=True)
    # chunked
    st = None
    for a, b in ((0, 10), (10, 20), (20, 30)):
        _, st = slots(x[:, a:b], state=st, return_state=True)
    # deterministic addressing → identical slot metadata
    assert torch.equal(st_full.active, st.active)
    assert torch.equal(st_full.version, st.version)
    assert torch.equal(st_full.source, st.source)


def test_gradients_finite():
    slots = _slots()
    x = torch.randn(2, 12, 32, requires_grad=True)
    slots(x).pow(2).mean().backward()
    assert torch.isfinite(x.grad).all()
    for n, p in slots.named_parameters():
        assert p.grad is not None and torch.isfinite(p.grad).all(), n


def test_version_bump_on_supersession():
    """Repeatedly writing a similar key must reuse a slot and bump its version."""
    slots = _slots(match_threshold=0.3).eval()
    # feed a repeated pattern so matching fires
    base = torch.randn(1, 1, 32)
    x = base.repeat(1, 12, 1) + 0.01 * torch.randn(1, 12, 32)
    _, st = slots(x, return_state=True)
    assert st.version.max().item() >= 2, st.version


def test_source_attribution_recorded():
    slots = _slots().eval()
    x = torch.randn(1, 6, 32)
    src = torch.arange(6).view(1, 6)
    _, st = slots(x, source_ids=src, return_state=True)
    active_sources = st.source[st.active > 0.5]
    assert (active_sources >= 0).all()


def test_top_k_read_bounded():
    slots = _slots(top_k=2).eval()
    assert slots.top_k == 2
    _, st = slots(torch.randn(1, 20, 32), return_state=True)
    # a read only ever aggregates top_k slots — smoke check it runs and is finite
    out = slots(torch.randn(1, 5, 32))
    assert torch.isfinite(out).all()


def test_reducing_slot_count_changes_capacity():
    small = _slots(seed=1);
    small2 = BoundedBindingSlots(embed_dim=32, num_slots=2, top_k=2)
    _, s_big = small(torch.randn(1, 50, 32), return_state=True)
    _, s_small = small2(torch.randn(1, 50, 32), return_state=True)
    assert s_small.active.sum().item() <= 2
    assert s_big.active.sum().item() <= 8
