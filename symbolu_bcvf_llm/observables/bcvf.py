"""§11 BCVF-based observables.

Two variants of V1's Ketu witness:

  BCVFTotalCostObservable       — total BCVF cost across all pairs for
                                  the (Q, choice) pair. Higher = more
                                  disagreement. V1's implicit observable.

  BCVFSourceZeroCostObservable  — per-source BCVF cost for source 0
                                  specifically. Probes the §10.V1.2
                                  mechanism ("2:1 attribution votes
                                  source 0 off the island"): if this
                                  observable is anti-correlated with
                                  correctness, it confirms the hypothesis.

Both consume the §4 Source protocol's `lookahead()` returns and feed
into the §2 kernel unchanged.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, compute_bcvf_cost
from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


class BCVFTotalCostObservable:
    """Sum of per-pair BCVF costs for a (question, choice) scoring event.

    V1's implicit Ketu. Observed at the commit-time lookahead window
    per §2.3.2. Higher total cost = more accelerating disagreement
    among sources = "something is off" in V1's intended semantics.

    §10.V1.8 shows this observable is likely ANTI_CORRELATED on same-
    model paraphrase sources for TruthfulQA-MC; running the probe on
    a v1-configured MockBenchmark or real TruthfulQA set should
    reproduce that finding cheaply.
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
        probs_list: List[np.ndarray] = []
        masks_list: List[np.ndarray] = []
        for s in sources:
            p, m = s.lookahead()
            probs_list.append(p.astype(np.float64))
            masks_list.append(m)
        result = compute_bcvf_cost(
            probs_list, self._cfg, valid_masks=masks_list
        )
        per_source = np.array(
            [float(result.per_source_costs[i]) for i in range(len(sources))],
            dtype=np.float64,
        )
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

    Probes the §10.V1.2 hypothesis directly: if source 0 is getting
    systematically high per-source cost on questions where it's
    right, the observable will be ANTI_CORRELATED. That would confirm
    the "base voted off the island" mechanism without needing to run
    a full Rahu attractor.
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
        probs_list: List[np.ndarray] = []
        masks_list: List[np.ndarray] = []
        for s in sources:
            p, m = s.lookahead()
            probs_list.append(p.astype(np.float64))
            masks_list.append(m)
        result = compute_bcvf_cost(
            probs_list, self._cfg, valid_masks=masks_list
        )
        source_0_cost = float(result.per_source_costs.get(0, 0.0))
        per_source = np.array(
            [float(result.per_source_costs[i]) for i in range(len(sources))],
            dtype=np.float64,
        )
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
