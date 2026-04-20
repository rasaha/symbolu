"""§2.9.4 tests 45–47: cross-kernel parity checks against autonomy.

These tests verify that verbatim-carry-over stages (pseudo_huber,
_enumerate_pairs) behave identically to the autonomy reference, and
that the scalar-entry structural contract holds on a trivial input
both kernels agree on (identical sources ⇒ total_cost = 0).
"""

from __future__ import annotations

import numpy as np
import pytest


def test_pseudo_huber_matches_autonomy_bit_exact():
    from symbolu_bcvf_llm.core import pseudo_huber as huber_llm
    try:
        from symbolu_robotics.bcvf_autonomous.core import (
            pseudo_huber as huber_aut,
        )
    except Exception as exc:  # autonomy not importable in this env
        pytest.skip(f"autonomy kernel not importable: {exc}")
    rs = np.linspace(-5.0, 5.0, 37)
    for delta in (0.1, 0.5, 1.0, 2.5):
        out_llm = huber_llm(rs, delta=delta)
        out_aut = huber_aut(rs, delta=delta)
        np.testing.assert_array_equal(out_llm, out_aut)


def test_enumerate_pairs_matches_autonomy():
    from symbolu_bcvf_llm.core import _enumerate_pairs as enum_llm
    try:
        from symbolu_robotics.bcvf_autonomous.core import (
            _enumerate_pairs as enum_aut,
        )
    except Exception as exc:
        pytest.skip(f"autonomy kernel not importable: {exc}")
    for M in (2, 3, 4, 5):
        for use_anchor in (True, False):
            for anchor in range(M):
                assert enum_llm(M, use_anchor, anchor) == enum_aut(
                    M, use_anchor, anchor
                )


def test_compute_bcvf_cost_scalar_matches_autonomy_on_identical_shape_inputs():
    """Structural sanity check (not primary correctness).

    For identical trajectories both kernels return total_cost = 0
    regardless of domain metric — autonomy's body-frame error is
    trivially zero for traj_i == traj_j; LLM's p_i - p_j is trivially
    zero for p_i == p_j.
    """
    from symbolu_bcvf_llm.core import (
        BCVFLLMConfig,
        compute_bcvf_cost as cost_llm,
    )
    try:
        from symbolu_robotics.bcvf_autonomous.core import (
            BCVFConfig,
            compute_bcvf_cost as cost_aut,
        )
    except Exception as exc:
        pytest.skip(f"autonomy kernel not importable: {exc}")
    # L=5, V=3 with identical sources / trajectories across M=3.
    identical = np.zeros((5, 3), dtype=np.float64)
    identical[:, 0] = np.arange(5)  # any nonzero pattern; the point is parity
    sources = [identical.copy() for _ in range(3)]
    r_llm = cost_llm(sources, BCVFLLMConfig())
    total_aut = cost_aut(
        [identical.copy() for _ in range(3)], BCVFConfig()
    ).total_cost
    assert r_llm.total_cost == pytest.approx(0.0, abs=1e-10)
    assert total_aut == pytest.approx(0.0, abs=1e-10)
