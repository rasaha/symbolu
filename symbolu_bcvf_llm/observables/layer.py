"""§12.5 Cross-layer BCVF-style observables.

Motivation (from §11.12 + §12 pivot).

§11.12 showed that `coherence_anchored_bcvf_per_step` collapsed
(AUC 0.431, ANTI) on HaluEval because the alignment factor was
**adversarially anti-correlated**: LLM-generated hallucinations were
specifically optimized against the target's teacher-forced log-prob,
so alignment pushed in the wrong direction.

The §12 spec-dec pivot revealed a second compatibility problem:
same-family draft-target pairs have small cross-source disagreement
most of the time, so BCVF's stability factor saturates near 1 and
contributes little independent signal.

Both problems share a root cause: the stability factor was not
structurally independent of the alignment factor. On adversarial
benchmarks the alignment is anti-signal, on same-family pairs the
stability is near-constant.

§12.5 proposes a genuinely-independent stability factor: the
target model's **cross-layer representation stability**. Each
transformer layer produces a hidden state; applying the logit
lens gives an ``(N_layers, V)`` per-position probability matrix.
The 2nd-order difference norm across layers quantifies how
"jittery" the representation is as it traverses depth. High layer
instability ↔ the model is "arguing with itself" across layers ↔
plausibly correlated with hallucination or rejection.

This factor is structurally independent of:
- paraphrase-source agreement (doesn't use other sources).
- teacher-forced probability (reads hidden states, not logits
  directly, though the logit lens projects them).
- cross-family disagreement (single model, no ensemble).

Two observables shipped:

  LayerInstabilityObservable
    Max across answer-path steps of the 2nd-order difference norm
    of source 0's per-layer next-token distributions.

  CoherenceAnchoredLayerBCVFObservable
    Layer-stability × alignment. The SCC `C × S` pattern with a
    structurally-independent stability factor — the proper test
    of the coherence hypothesis on spec-dec and on any other
    problem where source-side factors saturate or invert.

Both require source 0 to implement ``layer_lookahead()``
(HuggingFaceSource and MockLayerSource do).

Both opt into ``requires_isolated_sources = True`` because they
walk the teacher-forced answer path via ``commit()``.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


def _layer_2nd_diff_norm(probs_per_layer: np.ndarray) -> float:
    """L2 norm of 2nd-order layer-axis difference, summed over middle layers.

    Input shape: ``(N_layers, V)``. At least 3 layers required.
    Output: non-negative scalar.

    For each interior layer l ∈ [1, N-2]:
      d_l = p_{l-1} - 2 * p_l + p_{l+1}
    Return Σ_l ||d_l||_2.
    """
    if probs_per_layer.ndim != 2:
        raise ValueError(
            f"expected (N_layers, V), got shape {probs_per_layer.shape}"
        )
    n = probs_per_layer.shape[0]
    if n < 3:
        return 0.0
    d2 = probs_per_layer[:-2] - 2.0 * probs_per_layer[1:-1] + probs_per_layer[2:]
    return float(np.linalg.norm(d2, axis=-1).sum())


class LayerInstabilityObservable:
    """Max across answer-path steps of the 2nd-order difference norm of
    source 0's per-layer next-token distributions (logit-lens).

    Higher = more cross-layer thrashing = less stable representation.
    Structurally independent of the other observables in the family
    because it reads only source 0's internal state.

    Walks the teacher-forced answer path via ``commit()`` — sets
    ``requires_isolated_sources = True`` so the probe harness
    supplies a fresh source triple per (Q, choice).

    Requires source 0 to expose ``layer_lookahead() -> (N_layers, V)``.
    """

    name: str = "layer_instability_max"
    higher_means_more_suspicious: bool = True
    requires_isolated_sources: bool = True

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        source_0 = sources[0]
        if not hasattr(source_0, "layer_lookahead"):
            # Graceful degradation: emit zero scalar so the probe run
            # completes on benchmarks whose sources lack layer_lookahead.
            # The probe will report UNCORRELATED (AUC 0.5) and the
            # `unsupported` flag in metadata signals the skip.
            return ObservableValue(
                scalar=0.0,
                metadata={
                    "unsupported": True,
                    "reason": (
                        f"source 0 ({type(source_0).__name__}) lacks "
                        "layer_lookahead(); use HuggingFaceSource or "
                        "MockLayerSource to exercise this observable."
                    ),
                    "per_step_instabilities": [],
                    "n_steps": 0,
                    "n_layers": 0,
                },
            )

        n = len(choice_tokens)
        if n == 0:
            return ObservableValue(
                scalar=0.0,
                metadata={
                    "per_step_instabilities": [],
                    "n_steps": 0,
                    "n_layers": 0,
                },
            )

        step_instabilities: List[float] = []
        n_layers = 0
        for t in range(n):
            probs_per_layer = source_0.layer_lookahead()
            n_layers = probs_per_layer.shape[0]
            step_instabilities.append(_layer_2nd_diff_norm(probs_per_layer))
            if t < n - 1:
                source_0.commit(int(choice_tokens[t]))

        scalar = max(step_instabilities) if step_instabilities else 0.0
        return ObservableValue(
            scalar=scalar,
            metadata={
                "per_step_instabilities": step_instabilities,
                "mean_instability": float(np.mean(step_instabilities)),
                "argmax_step": int(np.argmax(step_instabilities))
                if step_instabilities else -1,
                "n_steps": n,
                "n_layers": n_layers,
            },
        )


class CoherenceAnchoredLayerBCVFObservable:
    """scalar = 1/(1 + max_layer_instability) × exp(mean log p_target(token)).

    The `C × S` SCC pattern with a structurally-independent stability
    factor: cross-layer representation stability (from the target's
    hidden-state trajectory) paired with teacher-forced alignment
    (target's next-token probability on the candidate). Neither
    factor can trivially collapse the other because they read
    orthogonal internal signals.

    Polarity: trust (higher = more trusted). Walks the answer path
    via ``commit()``.
    """

    name: str = "coherence_anchored_layer_bcvf_per_step"
    higher_means_more_suspicious: bool = False
    requires_isolated_sources: bool = True

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        source_0 = sources[0]
        if not hasattr(source_0, "layer_lookahead"):
            return ObservableValue(
                scalar=0.0,
                metadata={
                    "unsupported": True,
                    "reason": (
                        f"source 0 ({type(source_0).__name__}) lacks "
                        "layer_lookahead(); use HuggingFaceSource or "
                        "MockLayerSource to exercise this observable."
                    ),
                    "stability": 0.0,
                    "alignment": 0.0,
                    "n_steps": 0,
                },
            )

        n = len(choice_tokens)
        if n == 0:
            return ObservableValue(
                scalar=1.0,
                metadata={
                    "stability": 1.0,
                    "alignment": 1.0,
                    "max_layer_instability": 0.0,
                    "per_step_instabilities": [],
                    "n_steps": 0,
                },
            )

        step_instabilities: List[float] = []
        step_log_probs: List[float] = []
        for t in range(n):
            # Layer-stability component on source 0.
            probs_per_layer = source_0.layer_lookahead()
            step_instabilities.append(_layer_2nd_diff_norm(probs_per_layer))

            # Alignment component: source 0's P(token_t | prefix).
            probs, _mask = source_0.lookahead()
            p_token = float(probs[0, int(choice_tokens[t])])
            step_log_probs.append(float(np.log(max(p_token, 1e-30))))

            if t < n - 1:
                source_0.commit(int(choice_tokens[t]))

        max_instability = max(step_instabilities)
        stability = 1.0 / (1.0 + max_instability)
        geo_mean_log_prob = float(np.mean(step_log_probs))
        alignment = float(np.exp(geo_mean_log_prob))
        scalar = stability * alignment
        return ObservableValue(
            scalar=scalar,
            metadata={
                "stability": stability,
                "alignment": alignment,
                "max_layer_instability": max_instability,
                "mean_layer_instability": float(np.mean(step_instabilities)),
                "per_step_instabilities": step_instabilities,
                "geo_mean_log_prob": geo_mean_log_prob,
                "n_steps": n,
            },
        )
