"""Stage 1 — complexity/memory invariants.

Enforces:
  * INV-NO-NN   : the Phase core never materializes an [.., N, N] tensor.
  * INV-STATE-O : recurrent state size is independent of N.
  * O(N) scaling: peak intermediate elements grow linearly, not quadratically.
"""

import torch

from symbolu.lightweight_phase import LightweightPhaseAttention, PhaseConfig
from symbolu.lightweight_phase.invariants import (
    InvariantViolation,
    assert_state_size_independent_of_n,
    shape_audit,
    register_shape,
)


def test_no_n_by_n_tensor_is_created():
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=32, num_heads=4)).eval()
    # The forward already runs under an internal shape_audit; a violation would raise.
    for N in (4, 17, 64):
        layer(torch.randn(2, N, 32))  # must not raise


def test_audit_catches_forbidden_shape():
    with shape_audit(seq_len=8):
        try:
            # A score matrix has two sequence axes (query position × key position).
            register_shape("bad_scores", (2, 4, 8, 8), n_seq_axes=2)  # [B, H, N, N]
        except InvariantViolation:
            pass
        else:
            raise AssertionError("shape_audit failed to catch a two-sequence-axis tensor")


def test_audit_allows_value_collisions():
    """[B, N, H, Dh] must be allowed even when N coincides with B or H."""
    with shape_audit(seq_len=2):
        register_shape("kv", (2, 2, 2, 8), n_seq_axes=1)  # B==N==H==2, still fine


def test_state_size_independent_of_n():
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=32, num_heads=4))
    sizes = {}
    for N in (2, 10, 100, 500):
        out = layer(torch.randn(1, N, 32), return_state=True)
        sizes[N] = out.state.numel()
    assert_state_size_independent_of_n(sizes)


def test_peak_intermediate_scales_linearly():
    """Track the largest intermediate tensor; it must grow ~O(N), not O(N^2)."""
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=32, num_heads=4)).eval()

    def peak_elems(N):
        with shape_audit(seq_len=N) as audit:
            layer(torch.randn(1, N, 32))
        return audit.peak_numel()

    p_small = peak_elems(16)
    p_large = peak_elems(160)  # 10x N
    ratio = p_large / p_small
    # Linear would be ~10x; quadratic ~100x. Require well below quadratic.
    assert ratio < 20, f"peak grew {ratio:.1f}x for 10x N (looks superlinear)"
