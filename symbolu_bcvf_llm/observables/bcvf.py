"""BCVF-based observables.

Two variants of the V1 Ketu witness:

  BCVFTotalCostObservable       — total BCVF cost across all source pairs.
  BCVFSourceZeroCostObservable  — per-source BCVF cost for source 0
                                  (the base decoder).

Both feed the §4 Source protocol's `lookahead()` returns into the §2
kernel unchanged.
"""

from __future__ import annotations

from typing import Sequence, Tuple

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, BCVFLLMResult, compute_bcvf_cost
from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


def _run_bcvf(
    sources: Sequence[Source], cfg: BCVFLLMConfig
) -> Tuple[BCVFLLMResult, np.ndarray]:
    """Pull lookahead from each source, run the kernel, return (result, per_source)."""
    probs_list = [s.lookahead()[0].astype(np.float64) for s in sources]
    masks_list = [s.lookahead()[1] for s in sources]
    result = compute_bcvf_cost(probs_list, cfg, valid_masks=masks_list)
    per_source = np.array(
        [float(result.per_source_costs[i]) for i in range(len(sources))],
        dtype=np.float64,
    )
    return result, per_source


class BCVFTotalCostObservable:
    """Sum of per-pair BCVF costs for a (question, choice) scoring event.

    Scalar = total cost. Higher = more accelerating disagreement.
    """

    name: str = "bcvf_total_cost"
    higher_means_more_suspicious: bool = True

    def __init__(self, bcvf_config: "BCVFLLMConfig | None" = None) -> None:
        self._cfg = bcvf_config or BCVFLLMConfig()

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        result, per_source = _run_bcvf(sources, self._cfg)
        return ObservableValue(
            scalar=float(result.total_cost),
            per_source=per_source,
            metadata={
                "max_acceleration_norm": float(result.max_acceleration_norm),
                "gate_activation_count": int(result.gate_activation_count),
                "per_pair_costs": {
                    f"{i},{j}": float(v)
                    for (i, j), v in result.per_pair_costs.items()
                },
            },
        )


class BCVFSourceZeroCostObservable:
    """Per-source BCVF cost of source 0 (the base decoder).

    Scalar = per_source_costs[0]. Higher = source 0 is the largest
    contributor to total disagreement.
    """

    name: str = "bcvf_source_0_cost"
    higher_means_more_suspicious: bool = True

    def __init__(self, bcvf_config: "BCVFLLMConfig | None" = None) -> None:
        self._cfg = bcvf_config or BCVFLLMConfig()

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        result, per_source = _run_bcvf(sources, self._cfg)
        source_0_cost = float(result.per_source_costs.get(0, 0.0))
        return ObservableValue(
            scalar=source_0_cost,
            per_source=per_source,
            metadata={
                "total_cost": float(result.total_cost),
                "relative_to_total": (
                    source_0_cost / result.total_cost
                    if result.total_cost > 0 else 0.0
                ),
            },
        )
