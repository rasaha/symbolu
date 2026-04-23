"""Coherence-anchored BCVF observables.

§11.11 hypothesis test: pure BCVF is scale-free and direction-free —
it detects disagreement but not truth. When same-model paraphrases
confidently agree on a hallucinated distractor, BCVF reports "low
cost = high trust" in the wrong direction.

The SCC-style fix couples BCVF to a semantic-alignment anchor:

    scalar = stability × alignment
    stability = 1 / (1 + bcvf_total_cost)          ∈ (0, 1]
    alignment = P(first_token_of_choice | prompt)   ∈ [0, 1]

High scalar requires BOTH high cross-source stability AND the base
model finding the candidate plausible. Mirrors the autonomy pattern
of pairing a fault detector with a direction sensor — BCVF supplies
stability, the teacher-forced answer-probability supplies direction.

Matches the SCC `C' = C × S` pattern with a minimum-knob instance
(no α,β,γ,δ — just the two factors) to stay §0.8-compliant.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig
from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue
from .bcvf import _run_bcvf


class CoherenceAnchoredBCVFObservable:
    """scalar = 1/(1 + bcvf_total_cost) × P(first_token | prompt).

    Combines a cross-source stability signal (inverted BCVF cost)
    with a semantic-alignment anchor (the base model's predicted
    probability of the candidate's first answer token at the
    commit-position lookahead).

    Higher = more trusted. `higher_means_more_suspicious = False`
    because the factors are trust-polarity.

    Notes:
      - The alignment factor reads `source_0.lookahead()[0, token]`
        which is P(token | prompt) under teacher-forced position 0.
      - Zero cost to run — no extra forward passes vs the existing
        aggregate BCVF observables. `requires_isolated_sources`
        stays False (no state mutation).
      - If choice_tokens is empty, alignment defaults to 1.0 so the
        scalar reduces to pure stability (degenerate case).
    """

    name: str = "coherence_anchored_bcvf"
    higher_means_more_suspicious: bool = False

    def __init__(self, bcvf_config: "BCVFLLMConfig | None" = None) -> None:
        self._cfg = bcvf_config or BCVFLLMConfig()

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        result, per_source = _run_bcvf(sources, self._cfg)
        stability = 1.0 / (1.0 + float(result.total_cost))

        if not choice_tokens:
            alignment = 1.0
            first_token = -1
        else:
            source_0 = sources[0]
            probs, _mask = source_0.lookahead()
            first_token = int(choice_tokens[0])
            alignment = float(probs[0, first_token])

        scalar = stability * alignment

        return ObservableValue(
            scalar=scalar,
            per_source=per_source,
            metadata={
                "stability": stability,
                "alignment": alignment,
                "bcvf_total_cost": float(result.total_cost),
                "first_token": first_token,
            },
        )
