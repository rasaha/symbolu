"""Uncertainty-gated per-step BCVF observable.

§11.14 diagnosis: the existing TrustShaper applies BCVF-weighted
softmin trust-shaping at every commit step, including steps where
the base model is confidently producing (possibly wrong) tokens.
On adversarial-by-common-misconception benchmarks (TruthfulQA) the
model's confidence is high AND wrong, so always-on trust-shaping
reacts to misleading local BCVF signal. On LLM-generated
hallucinations (HaluEval) the signal exists at per-token level but
the decoder's softmin reduction doesn't match the per-step-max
reduction that actually carries truth information.

The uncertainty-gating hypothesis: per-step BCVF is only
discriminative when the base model is genuinely uncertain. On
confident steps, the model's prior is either right (correct answer
is high-probability) or confidently wrong (adversarial
misconception) — neither case benefits from trust-shaping. On
uncertain steps, the model is hedging, and BCVF disagreement
across paraphrase sources becomes informative.

  UncertaintyGatedBCVFPerStepMaxObservable
    scalar = max over steps where entropy(source_0) > tau of
             bcvf_total_cost(step)
    tau = 1.0 nat (pre-committed per §0.8 — not tuned post-hoc)

Uses max-reduction to match the §11.11-passing `bcvf_per_step_max`
shape, adding the entropy gate as a filter. If the gate produces
an equally-strong or stronger signal, it's evidence that filtering
confident steps amplifies the truth-correlated per-token dynamics.
If it produces a weaker signal, confident steps were contributing
usable information after all.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, compute_bcvf_cost
from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


# Pre-committed threshold in nats. Rationale: ln(e) = 1 nat is "the
# model's next-token distribution is roughly as uncertain as a
# uniform distribution over e ≈ 2.7 tokens." A natural split
# between "confident on a single next token" and "hedging across
# a small set." Not tuned on the probe split.
_DEFAULT_ENTROPY_THRESHOLD = 1.0


class UncertaintyGatedBCVFPerStepMaxObservable:
    """Max per-step BCVF cost, restricted to steps where source-0
    entropy exceeds a pre-committed threshold (default 1.0 nat)."""

    name: str = "uncertainty_gated_bcvf_per_step_max"
    higher_means_more_suspicious: bool = True
    requires_isolated_sources: bool = True

    def __init__(
        self,
        bcvf_config: "BCVFLLMConfig | None" = None,
        entropy_threshold: float = _DEFAULT_ENTROPY_THRESHOLD,
    ) -> None:
        self._cfg = bcvf_config or BCVFLLMConfig()
        self._tau = float(entropy_threshold)

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        n = len(choice_tokens)
        if n == 0:
            return ObservableValue(
                scalar=0.0,
                metadata={
                    "entropy_threshold": self._tau,
                    "n_steps": 0,
                    "n_uncertain_steps": 0,
                    "per_step_costs": [],
                    "per_step_entropies": [],
                    "max_step_cost_all": 0.0,
                    "max_step_cost_gated": 0.0,
                },
            )

        step_costs: List[float] = []
        step_entropies: List[float] = []
        gated_costs: List[float] = []

        for t in range(n):
            probs_list = [s.lookahead()[0].astype(np.float64) for s in sources]
            masks_list = [s.lookahead()[1] for s in sources]
            result = compute_bcvf_cost(
                probs_list, self._cfg, valid_masks=masks_list,
            )
            cost = float(result.total_cost)
            step_costs.append(cost)

            p0 = probs_list[0][0]
            p0_safe = np.clip(p0, 1e-30, None)
            entropy = float(-np.sum(p0 * np.log(p0_safe)))
            step_entropies.append(entropy)

            if entropy > self._tau:
                gated_costs.append(cost)

            if t < n - 1:
                token = int(choice_tokens[t])
                for s in sources:
                    s.commit(token)

        scalar = max(gated_costs) if gated_costs else 0.0
        return ObservableValue(
            scalar=scalar,
            metadata={
                "entropy_threshold": self._tau,
                "n_steps": n,
                "n_uncertain_steps": len(gated_costs),
                "per_step_costs": step_costs,
                "per_step_entropies": step_entropies,
                "max_step_cost_all": max(step_costs) if step_costs else 0.0,
                "max_step_cost_gated": scalar,
            },
        )
