"""§5 V1 consumer architecture — **logit blending**.

The three consumer architectures §5 offers (hidden-state shaping,
logit blending, routing/gating) differ in where the trust weights
enter the generation pipeline. V1 picks **logit blending** because:

  - It requires no model internals; works with any `Source` that
    exposes the §4.2 protocol. Hidden-state shaping needs access
    to `h_t`, which HuggingFaceSource does not expose today.
  - It's a clean drop-in at §4.6's `next_token_fn` hook — the
    outer loop, EOS handling, paraphrase logic all stay unchanged.
  - It generalizes the §1.10 conventional-blend baseline
    (equal-weight blend → trust-weight blend), making the §6
    three-way decoder comparison maximally apples-to-apples.

Consensus formula (per outer step t, emitting token at position
l=0 of the lookahead, §2.3.2):

    per_source_costs = BCVFLLMResult(compute_bcvf_cost(sources, ...))
    weights          = TrustShaper.step(per_source_costs)       # §5.1
    consensus        = Σ_i weights[i] · p_i(t, l=0)             # (V,)
    emitted_token    = argmax_v consensus[v]

Rejected V1 alternatives, recorded for §9:
  - Hidden-state shaping: needs Source to expose hidden states.
    V2 once HuggingFaceSource grows that API.
  - Routing/gating: hard-switch to a single source per step.
    Loses the smooth trust distribution §5.1 produces; the
    autonomy caveat in §5.2 makes hard switches risky on the
    borderline-seed rotation pattern.

`decode_trust_shaped` returns a `TrustShapedDecodeResult` that
wraps the §4 `DecodeResult` with per-step trust diagnostics —
useful both for §6 benchmark reporting and for §3-style alignment
sweeps over realistic decoding traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, compute_bcvf_cost
from symbolu_bcvf_llm.decoders.loop import DecodeResult, Lookahead, run_decode
from symbolu_bcvf_llm.sources.base import Source

from .shaper import TrustShaper, TrustShaperConfig


@dataclass
class TrustShapedDecodeResult:
    """Decoder result + per-step trust diagnostics (§6 wants these)."""

    decode_result: DecodeResult
    per_step_weights: np.ndarray          # (T, M)
    per_step_costs: np.ndarray            # (T, M)
    per_step_residuals: np.ndarray        # (T, M)
    per_step_bcvf_total: np.ndarray       # (T,)
    per_step_bcvf_activations: np.ndarray # (T,) int
    shaper: TrustShaper = field(repr=False)


def decode_trust_shaped(
    sources: Sequence[Source],
    bcvf_config: Optional[BCVFLLMConfig] = None,
    trust_config: Optional[TrustShaperConfig] = None,
    max_tokens: int = 32,
    eos_token_id: Optional[int] = None,
) -> TrustShapedDecodeResult:
    """Run the §5 V1 trust-shaped decoder (logit blending).

    Args:
        sources: M >= 2 Source objects. M = 3 is the V1 target;
            M = 2 is accepted for degenerate-case testing but the
            §2.4.5 2:1 attribution ratio collapses.
        bcvf_config: defaults to `BCVFLLMConfig()` (§2.8.4 V1
            defaults, including `use_anchor_pairing = False` which
            §5.1 stage 3 requires).
        trust_config: defaults to `TrustShaperConfig()` (§5.1 V1
            defaults: `ema_alpha = 0.05`, `deadband_k_sigma = 2.0`,
            `trust_temperature = 1.0`).
        max_tokens, eos_token_id: as in §4 `run_decode`.

    Returns:
        TrustShapedDecodeResult with decoder output + per-step
        weights, costs, residuals, and BCVF diagnostics.
    """
    if len(sources) < 2:
        raise ValueError(
            "decode_trust_shaped requires M >= 2 sources (V1 target M=3)"
        )
    cfg = bcvf_config or BCVFLLMConfig()
    if cfg.use_anchor_pairing:
        raise ValueError(
            "§5.1 stage 3 requires non-anchor pairing; got "
            "BCVFLLMConfig.use_anchor_pairing = True"
        )
    t_cfg = trust_config or TrustShaperConfig()
    M = len(sources)
    shaper = TrustShaper(M=M, config=t_cfg)

    # Per-step diagnostics accumulated inside next_token_fn's closure.
    costs_log: List[np.ndarray] = []
    weights_log: List[np.ndarray] = []
    residuals_log: List[np.ndarray] = []
    bcvf_total_log: List[float] = []
    bcvf_act_log: List[int] = []

    def next_token_fn(lookaheads: Sequence[Lookahead], step: int) -> int:
        # §2.7.2 fp32→fp64 upcast at the BCVF boundary.
        probs_list = [la[0].astype(np.float64) for la in lookaheads]
        masks_list = [la[1] for la in lookaheads]
        result = compute_bcvf_cost(probs_list, cfg, valid_masks=masks_list)
        per_source = np.array(
            [result.per_source_costs[i] for i in range(M)], dtype=np.float64
        )
        weights = shaper.step(per_source)

        # Weighted consensus at l=0 (the emitted position — §2.3.2).
        p0 = np.stack(
            [la[0][0].astype(np.float64) for la in lookaheads], axis=0
        )  # (M, V)
        consensus = (weights.reshape(-1, 1) * p0).sum(axis=0)

        # Diagnostics.
        costs_log.append(per_source)
        weights_log.append(weights)
        # Compute residual from the matching history entry (shaper
        # just appended it).
        residuals_log.append(shaper.history[-1].residual.copy())
        bcvf_total_log.append(float(result.total_cost))
        bcvf_act_log.append(int(result.gate_activation_count))

        return int(np.argmax(consensus))

    decode_result = run_decode(
        sources=sources,
        next_token_fn=next_token_fn,
        max_tokens=max_tokens,
        eos_token_id=eos_token_id,
    )

    T = len(costs_log)
    return TrustShapedDecodeResult(
        decode_result=decode_result,
        per_step_weights=(
            np.stack(weights_log, axis=0) if T else np.zeros((0, M))
        ),
        per_step_costs=(
            np.stack(costs_log, axis=0) if T else np.zeros((0, M))
        ),
        per_step_residuals=(
            np.stack(residuals_log, axis=0) if T else np.zeros((0, M))
        ),
        per_step_bcvf_total=np.array(bcvf_total_log, dtype=np.float64),
        per_step_bcvf_activations=np.array(bcvf_act_log, dtype=np.int64),
        shaper=shaper,
    )
