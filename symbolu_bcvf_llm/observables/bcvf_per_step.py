"""Per-step BCVF observables.

The §11.4 aggregate BCVF observables score each (question, choice)
at a single commit-position lookahead. §11.8 showed those come back
UNCORRELATED on the V1 source ensemble — the per-choice aggregate
smooths out the per-token conditional that §10.V1.2 diagnosed as
V1's failure mechanism.

These observables walk the teacher-forced answer path, compute
BCVF at every step, and reduce via `max`. Two variants:

  BCVFPerStepMaxObservable            — max of total cost across steps.
  BCVFSourceZeroPerStepMaxObservable  — max of source 0's per-source
                                         cost across steps (directly
                                         targets "base voted off the
                                         island" on hallucination-prone
                                         tokens).

Both mutate source state via `commit()`, so both set
`requires_isolated_sources = True` and the probe harness gives
them fresh sources per (Q, choice).
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, BCVFLLMResult, compute_bcvf_cost
from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


def _bcvf_per_step(
    sources: Sequence[Source],
    cfg: BCVFLLMConfig,
    choice_tokens: Sequence[int],
) -> List[BCVFLLMResult]:
    """Walk the teacher-forced answer path, returning one BCVF result per step.

    At step t: read each source's current lookahead, run the kernel,
    then commit choice_tokens[t] to every source (except on the last
    step, where no further commit is needed).
    """
    results: List[BCVFLLMResult] = []
    n = len(choice_tokens)
    for t in range(n):
        probs_list = [s.lookahead()[0].astype(np.float64) for s in sources]
        masks_list = [s.lookahead()[1] for s in sources]
        results.append(
            compute_bcvf_cost(probs_list, cfg, valid_masks=masks_list)
        )
        if t < n - 1:
            token = int(choice_tokens[t])
            for s in sources:
                s.commit(token)
    return results


class BCVFPerStepMaxObservable:
    """Max total BCVF cost across steps of the teacher-forced answer path."""

    name: str = "bcvf_per_step_max"
    higher_means_more_suspicious: bool = True
    requires_isolated_sources: bool = True

    def __init__(self, bcvf_config: "BCVFLLMConfig | None" = None) -> None:
        self._cfg = bcvf_config or BCVFLLMConfig()

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        per_step = _bcvf_per_step(sources, self._cfg, choice_tokens)
        costs = [float(r.total_cost) for r in per_step]
        scalar = max(costs) if costs else 0.0
        return ObservableValue(
            scalar=scalar,
            metadata={
                "per_step_costs": costs,
                "n_steps": len(costs),
                "mean_cost": float(np.mean(costs)) if costs else 0.0,
                "argmax_step": int(np.argmax(costs)) if costs else -1,
            },
        )


class BCVFSourceZeroPerStepMaxObservable:
    """Max source-0 per-source BCVF cost across teacher-forced answer steps.

    Directly targets the §10.V1.2 hypothesis: if source 0 (the base
    decoder) gets penalized on specific hallucination-prone tokens
    where same-model paraphrases happen to align on a distractor,
    this observable's step-max should pick up those spikes even when
    the per-choice aggregate averages them out.
    """

    name: str = "bcvf_source_0_per_step_max"
    higher_means_more_suspicious: bool = True
    requires_isolated_sources: bool = True

    def __init__(self, bcvf_config: "BCVFLLMConfig | None" = None) -> None:
        self._cfg = bcvf_config or BCVFLLMConfig()

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        per_step = _bcvf_per_step(sources, self._cfg, choice_tokens)
        source_0_costs = [
            float(r.per_source_costs.get(0, 0.0)) for r in per_step
        ]
        total_costs = [float(r.total_cost) for r in per_step]
        scalar = max(source_0_costs) if source_0_costs else 0.0
        argmax = int(np.argmax(source_0_costs)) if source_0_costs else -1
        return ObservableValue(
            scalar=scalar,
            metadata={
                "per_step_source_0_costs": source_0_costs,
                "per_step_total_costs": total_costs,
                "n_steps": len(source_0_costs),
                "argmax_step": argmax,
            },
        )
