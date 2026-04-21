"""§5 V1 TrustShapedDecoder end-to-end tests via MockSource.

Scenarios:
  - All sources agree → same emission as §4 conventional-blend.
  - One source diverges (accelerates away) → down-weighted; emission
    follows the majority of healthy sources.
  - Reproducibility: same seeds yield identical token stream.
  - Diagnostics: per-step arrays have expected shapes and properties.
  - §5.1 stage 3 enforcement: anchor pairing rejected at call time.
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.core import BCVFLLMConfig
from symbolu_bcvf_llm.decoders.blend import decode_conventional_blend
from symbolu_bcvf_llm.sources.mock import MockSource
from symbolu_bcvf_llm.trust.decoder import decode_trust_shaped
from symbolu_bcvf_llm.trust.shaper import TrustShaperConfig


def _logits_from_prob(prob: np.ndarray, L: int, floor: float = -10.0) -> np.ndarray:
    """Tile a (V,) probability vector across L lookahead positions as logits."""
    V = prob.shape[0]
    z = np.full((L, V), floor, dtype=np.float32)
    for v in range(V):
        if prob[v] > 0:
            z[:, v] = float(np.log(prob[v] + 1e-12))
    return z


def _concentrated(V: int, top: int, mass: float = 0.9) -> np.ndarray:
    """Return a (V,) distribution with `mass` on token `top`, rest uniform."""
    p = np.full(V, (1.0 - mass) / (V - 1), dtype=np.float64)
    p[top] = mass
    return p


def _peaked_logits(L: int, V: int, top: int, peak: float = 10.0) -> np.ndarray:
    z = np.full((L, V), -peak, dtype=np.float32)
    z[:, top] = peak
    return z


def test_trust_shaped_agrees_with_blend_when_all_sources_agree():
    """If every source emits identical logits, trust weighting reduces to blend."""
    V = 8

    def fn(prefix):
        return _peaked_logits(L=5, V=V, top=3)

    sources = [MockSource(fn, L=5, V=V) for _ in range(3)]
    blend_result = decode_conventional_blend(sources, max_tokens=6)

    sources_trust = [MockSource(fn, L=5, V=V) for _ in range(3)]
    trust_result = decode_trust_shaped(
        sources_trust,
        bcvf_config=BCVFLLMConfig(),
        trust_config=TrustShaperConfig(),
        max_tokens=6,
    )
    assert trust_result.decode_result.emitted_tokens == blend_result.emitted_tokens


def test_trust_shaped_downweights_accelerating_outlier():
    """Source 0 accelerates away from sources 1, 2; trust shaper down-weights it
    on the step the divergence first appears (before the EMA catches up).

    §5.1's pattern is designed for spike-like outliers — sustained
    monotonic growth drives the EMA up alongside, so the residual
    shrinks over time. This test checks the step where the
    divergence first crosses into BCVF's gate-open regime, which
    is where trust shaping is most effective.
    """
    V = 16

    def fn_base(prefix):
        return _peaked_logits(L=5, V=V, top=2)

    def fn_outlier(prefix):
        t = len(prefix)
        if t < 3:
            return _peaked_logits(L=5, V=V, top=2)
        # First divergent step (t=3): accelerating peak shift along l.
        logits = np.full((5, V), -10.0, dtype=np.float32)
        for l in range(5):
            shift = min(5, int(0.5 * (l + (t - 3)) ** 2))
            idx = (2 + shift) % V
            logits[l, idx] = 10.0
        return logits

    sources_trust = [
        MockSource(fn_outlier, L=5, V=V),
        MockSource(fn_base, L=5, V=V),
        MockSource(fn_base, L=5, V=V),
    ]
    result = decode_trust_shaped(
        sources_trust,
        bcvf_config=BCVFLLMConfig(),
        trust_config=TrustShaperConfig(ema_alpha=0.05),
        max_tokens=5,
    )
    # Step 3 is the first step where source 0 diverges. EMA from
    # steps 0-2 is ≈ 0, so residual ≈ BCVF per_source_cost (≈ 4 for
    # outlier, ≈ 2 for healthy — 2:1 by §2.4.5). Deadband with low
    # α has tiny σ → threshold ≈ 0, gate passes, softmin kicks in.
    w_at_first_drift = result.per_step_weights[3]
    assert w_at_first_drift[0] < 0.3, (
        f"source 0 should be clearly down-weighted at first divergent "
        f"step; got {w_at_first_drift}"
    )
    # The two healthy sources should share the freed weight roughly equally.
    assert abs(w_at_first_drift[1] - w_at_first_drift[2]) < 0.01
    assert w_at_first_drift[1] > 0.35
    assert w_at_first_drift[2] > 0.35


def test_trust_shaped_reproducible_across_runs():
    """Two runs with identical mock state and seeds produce identical output."""
    V = 8
    rng_seed = 0

    def make_fn(seed_offset):
        def fn(prefix):
            rng = np.random.default_rng(seed=rng_seed + seed_offset + len(prefix))
            return rng.normal(size=(5, V)).astype(np.float32)
        return fn

    def run():
        srcs = [MockSource(make_fn(k), L=5, V=V) for k in range(3)]
        return decode_trust_shaped(srcs, max_tokens=10)

    a = run()
    b = run()
    assert a.decode_result.emitted_tokens == b.decode_result.emitted_tokens
    np.testing.assert_array_equal(a.per_step_weights, b.per_step_weights)
    np.testing.assert_array_equal(a.per_step_costs, b.per_step_costs)


def test_diagnostics_shapes_and_properties():
    V = 8

    def fn(prefix):
        return _peaked_logits(L=5, V=V, top=len(prefix) % V)

    sources = [MockSource(fn, L=5, V=V) for _ in range(3)]
    result = decode_trust_shaped(sources, max_tokens=7)

    T = len(result.decode_result.emitted_tokens)
    M = 3
    assert result.per_step_weights.shape == (T, M)
    assert result.per_step_costs.shape == (T, M)
    assert result.per_step_residuals.shape == (T, M)
    assert result.per_step_bcvf_total.shape == (T,)
    assert result.per_step_bcvf_activations.shape == (T,)

    # Weights per step sum to 1.
    row_sums = result.per_step_weights.sum(axis=1)
    np.testing.assert_allclose(row_sums, 1.0, rtol=0, atol=1e-10)
    # Weights are non-negative.
    assert (result.per_step_weights >= 0).all()
    # Costs are finite.
    assert np.isfinite(result.per_step_costs).all()


def test_rejects_anchor_pairing_config():
    """§5.1 stage 3 — non-anchor pairing required."""
    V = 4

    def fn(prefix):
        return _peaked_logits(L=5, V=V, top=1)

    sources = [MockSource(fn, L=5, V=V) for _ in range(3)]
    bad_cfg = BCVFLLMConfig(use_anchor_pairing=True)
    with pytest.raises(ValueError, match="non-anchor"):
        decode_trust_shaped(sources, bcvf_config=bad_cfg, max_tokens=3)


def test_rejects_m_lt_2():
    V = 4

    def fn(prefix):
        return _peaked_logits(L=5, V=V, top=1)

    sources = [MockSource(fn, L=5, V=V)]
    with pytest.raises(ValueError, match="M >= 2"):
        decode_trust_shaped(sources, max_tokens=3)


def test_stops_on_eos():
    V = 5
    EOS = 3

    def fn(prefix):
        # Emit EOS after 2 committed tokens.
        top = EOS if len(prefix) >= 2 else 0
        return _peaked_logits(L=5, V=V, top=top)

    sources = [MockSource(fn, L=5, V=V, eos_token_id=EOS) for _ in range(3)]
    result = decode_trust_shaped(sources, max_tokens=10, eos_token_id=EOS)
    assert result.decode_result.stopped_on_eos
    assert result.decode_result.emitted_tokens[-1] == EOS


def test_history_matches_diagnostics_array():
    """shaper.history length matches per_step_costs rows."""
    V = 8

    def fn(prefix):
        return _peaked_logits(L=5, V=V, top=2)

    sources = [MockSource(fn, L=5, V=V) for _ in range(3)]
    result = decode_trust_shaped(sources, max_tokens=5)
    assert len(result.shaper.history) == result.per_step_weights.shape[0]
    # First history entry should have residual = 0 (cold-start).
    np.testing.assert_allclose(
        result.shaper.history[0].residual, np.zeros(3), atol=1e-12
    )
