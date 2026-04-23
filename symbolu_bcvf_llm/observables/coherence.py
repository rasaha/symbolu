"""Coherence-anchored BCVF observables.

§11.11 hypothesis test: V1-V3 probes showed pure BCVF is sign-free
and direction-free — it detects disagreement but can't tell truth
from consensus hallucination. Adding a truth-direction anchor (per
the SCC `C' = C × S` pattern) should surface signal that neither
factor alone carries.

Two variants:

  CoherenceAnchoredBCVFObservable
    scalar = 1/(1+bcvf_total_cost) × P(first_token | prompt)
    Aggregate stability × first-token alignment. Cheap; no state
    mutation; shared sources.

  CoherenceAnchoredBCVFPerStepObservable
    scalar = 1/(1+max_step_bcvf_cost) × geo_mean(P(t_i | prefix))
    Per-step stability × per-step geometric-mean alignment. Walks
    the teacher-forced answer path, commits between steps;
    requires_isolated_sources = True.

Both match the SCC `C' = C × S` pattern with a minimum-knob
instance (no α,β,γ,δ — just the two factors) to stay §0.8-compliant.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, compute_bcvf_cost
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


class CoherenceAnchoredBCVFPerStepObservable:
    """scalar = 1/(1 + max_step_bcvf) × geo_mean(P(t_i | prefix)).

    Per-step SCC instance: walks the teacher-forced answer path,
    computes BCVF at every step (matching BCVFPerStepMaxObservable's
    reduction), and teacher-forces source 0 through the answer to
    get a per-step probability trajectory for the alignment factor.

    Stability factor: `1 / (1 + max_t bcvf_total_cost(step_t))`.
    Max over steps — matches the reduction that surfaced signal on
    HaluEval at §11.11 (AUC 0.673).

    Alignment factor: `exp(mean_t log P(token_t | prompt, tokens_0..t-1))`
    — geometric mean of teacher-forced per-step probabilities on
    source 0. Geometric mean is the correct combiner for
    multi-token answer-likelihood: robust to answer length, reflects
    the per-step plausibility trajectory rather than one surprising
    token or one confident token.

    Polarity: trust (higher = more trusted).
    Opt-in to isolated sources because commit() mutates source state.
    """

    name: str = "coherence_anchored_bcvf_per_step"
    higher_means_more_suspicious: bool = False
    requires_isolated_sources: bool = True

    def __init__(self, bcvf_config: "BCVFLLMConfig | None" = None) -> None:
        self._cfg = bcvf_config or BCVFLLMConfig()

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        n = len(choice_tokens)
        if n == 0:
            # Degenerate fallback: pure aggregate stability, alignment=1
            result, per_source = _run_bcvf(sources, self._cfg)
            stability = 1.0 / (1.0 + float(result.total_cost))
            return ObservableValue(
                scalar=stability,
                per_source=per_source,
                metadata={
                    "stability": stability,
                    "alignment": 1.0,
                    "max_step_bcvf": float(result.total_cost),
                    "geo_mean_log_prob": 0.0,
                    "n_steps": 0,
                    "per_step_costs": [],
                    "per_step_source_0_costs": [],
                },
            )

        step_bcvf_costs: list = []
        step_source_0_costs: list = []
        step_log_probs: list = []

        for t in range(n):
            probs_list = [s.lookahead()[0].astype(np.float64) for s in sources]
            masks_list = [s.lookahead()[1] for s in sources]
            result = compute_bcvf_cost(
                probs_list, self._cfg, valid_masks=masks_list,
            )
            step_bcvf_costs.append(float(result.total_cost))
            step_source_0_costs.append(
                float(result.per_source_costs.get(0, 0.0))
            )

            token = int(choice_tokens[t])
            # Source 0's next-token probability at lookahead position 0
            p_token = float(probs_list[0][0, token])
            step_log_probs.append(float(np.log(max(p_token, 1e-30))))

            if t < n - 1:
                for s in sources:
                    s.commit(token)

        max_bcvf = max(step_bcvf_costs)
        stability = 1.0 / (1.0 + max_bcvf)

        geo_mean_log_prob = float(np.mean(step_log_probs))
        alignment = float(np.exp(geo_mean_log_prob))

        scalar = stability * alignment

        return ObservableValue(
            scalar=scalar,
            metadata={
                "stability": stability,
                "alignment": alignment,
                "max_step_bcvf": max_bcvf,
                "geo_mean_log_prob": geo_mean_log_prob,
                "n_steps": n,
                "per_step_costs": step_bcvf_costs,
                "per_step_source_0_costs": step_source_0_costs,
            },
        )
