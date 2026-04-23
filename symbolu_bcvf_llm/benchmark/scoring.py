"""§6.3 MC scoring via teacher-forcing.

Scores each candidate answer by summing the log-probability of its
tokens under the decoder's distribution, advancing sources via
teacher-forced commits (the correct choice's tokens, not the
decoder's own argmax). Pick `argmax_k score_k` as the MC prediction.

Three scoring functions mirror the three §1.10 decoders:

    score_choice_vanilla    — baseline A0: use source 0's p(l=0)
    score_choice_blend      — conventional-blend: equal-weight
                              average of p_s(l=0)
    score_choice_trust      — §5 trust-shaped: BCVF-based softmin
                              trust weights, weighted consensus

All three iterate the same teacher-forcing loop; only the per-
position probability distribution differs. The common loop is
factored into `_score_with_prob_fn`.

§2.7.2 fp32 → fp64 upcast happens at the BCVF boundary inside
`score_choice_trust`, matching the §5 decoder.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Sequence

import numpy as np

from symbolu_bcvf_llm.core import BCVFLLMConfig, compute_bcvf_cost
from symbolu_bcvf_llm.sources.base import Source
from symbolu_bcvf_llm.trust.shaper import TrustShaper, TrustShaperConfig


Lookahead = tuple  # (probs (L,V), mask (L,))
ProbFn = Callable[[Sequence[Lookahead]], np.ndarray]  # → (V,)


def _score_with_prob_fn(
    sources: Sequence[Source],
    choice_tokens: Sequence[int],
    prob_fn: ProbFn,
    log_floor: float = 1e-30,
) -> float:
    """Common teacher-forced scoring loop.

    For each target token in `choice_tokens`:
      1. Pull lookaheads from every source.
      2. Compute the per-position probability distribution under
         this decoder via `prob_fn`.
      3. Accumulate log-prob of the target token.
      4. Commit the target token into every source.

    Returns the summed log-probability (higher = better).
    """
    total = 0.0
    for target in choice_tokens:
        lookaheads = [s.lookahead() for s in sources]
        p = prob_fn(lookaheads)  # shape (V,)
        prob = float(p[int(target)])
        total += math.log(max(prob, log_floor))
        for s in sources:
            s.commit(int(target))
    return total


# --------------------------------------------------------------------------- #
# Per-decoder prob_fn factories
# --------------------------------------------------------------------------- #


def _vanilla_prob_fn(lookaheads: Sequence[Lookahead]) -> np.ndarray:
    return lookaheads[0][0][0].astype(np.float64)


def _blend_prob_fn(lookaheads: Sequence[Lookahead]) -> np.ndarray:
    stacked = np.stack(
        [la[0][0].astype(np.float64) for la in lookaheads], axis=0
    )
    return stacked.mean(axis=0)


def _make_trust_prob_fn(
    M: int,
    bcvf_config: BCVFLLMConfig,
    trust_config: TrustShaperConfig,
    shaper_out: Optional[List[TrustShaper]] = None,
) -> ProbFn:
    """Returns a `prob_fn` closure that maintains a fresh TrustShaper.

    `shaper_out`, if provided as a 1-element list, is populated with
    the shaper instance so the caller can inspect trust history
    after scoring.
    """
    shaper = TrustShaper(M=M, config=trust_config)
    if shaper_out is not None:
        shaper_out.append(shaper)

    def fn(lookaheads: Sequence[Lookahead]) -> np.ndarray:
        probs_list = [la[0].astype(np.float64) for la in lookaheads]
        masks_list = [la[1] for la in lookaheads]
        result = compute_bcvf_cost(
            probs_list, bcvf_config, valid_masks=masks_list
        )
        per_source = np.array(
            [result.per_source_costs[i] for i in range(M)], dtype=np.float64
        )
        weights = shaper.step(per_source)
        p0 = np.stack(
            [la[0][0].astype(np.float64) for la in lookaheads], axis=0
        )
        return (weights.reshape(-1, 1) * p0).sum(axis=0)

    return fn


# --------------------------------------------------------------------------- #
# Public scoring API
# --------------------------------------------------------------------------- #


def score_choice_vanilla(
    sources: Sequence[Source],
    choice_tokens: Sequence[int],
) -> float:
    """§1.10 A0 baseline — source 0's greedy distribution only."""
    return _score_with_prob_fn(sources, choice_tokens, _vanilla_prob_fn)


def score_choice_blend(
    sources: Sequence[Source],
    choice_tokens: Sequence[int],
) -> float:
    """§1.10 conventional-blend baseline — equal-weight average."""
    return _score_with_prob_fn(sources, choice_tokens, _blend_prob_fn)


def score_choice_trust(
    sources: Sequence[Source],
    choice_tokens: Sequence[int],
    bcvf_config: Optional[BCVFLLMConfig] = None,
    trust_config: Optional[TrustShaperConfig] = None,
) -> float:
    """§5 trust-shaped — BCVF softmin trust weights + weighted consensus."""
    cfg = bcvf_config or BCVFLLMConfig()
    if cfg.use_anchor_pairing:
        raise ValueError(
            "§5.1 stage 3 requires non-anchor pairing; got "
            "BCVFLLMConfig.use_anchor_pairing = True"
        )
    t_cfg = trust_config or TrustShaperConfig()
    prob_fn = _make_trust_prob_fn(len(sources), cfg, t_cfg)
    return _score_with_prob_fn(sources, choice_tokens, prob_fn)


# --------------------------------------------------------------------------- #
# §6.2 Phase 2 fast scoring paths — single forward-pass per source
# --------------------------------------------------------------------------- #

def _has_batched_scoring(source: Source) -> bool:
    """True if the source implements ``score_teacher_forced``."""
    return callable(getattr(source, "score_teacher_forced", None))


def score_choice_vanilla_batched(
    sources: Sequence[Source],
    choice_tokens: Sequence[int],
    log_floor: float = 1e-30,
) -> float:
    """Fast §1.10 A0 baseline: single forward pass on source 0 via
    ``score_teacher_forced``. Sums log-prob of the target tokens.

    Assumes ``sources[0]`` implements `BatchedScoringSource`. Caller
    verifies via `_has_batched_scoring` before invoking.
    """
    if not _has_batched_scoring(sources[0]):
        raise TypeError(
            "score_choice_vanilla_batched requires source 0 to implement "
            "score_teacher_forced; use score_choice_vanilla for fallback."
        )
    tgt = list(int(t) for t in choice_tokens)
    probs = sources[0].score_teacher_forced(tgt)  # (K, V) fp64
    total = 0.0
    for k, target in enumerate(tgt):
        p = float(probs[k, target])
        total += math.log(max(p, log_floor))
    return total


def score_choice_blend_batched(
    sources: Sequence[Source],
    choice_tokens: Sequence[int],
    log_floor: float = 1e-30,
) -> float:
    """Fast §1.10 conventional-blend baseline: one forward pass per
    source (M passes total, not M × K). Equal-weight average of per-
    position probabilities, then log-prob of target.

    All sources must implement `BatchedScoringSource`. Caller checks.
    """
    if not all(_has_batched_scoring(s) for s in sources):
        raise TypeError(
            "score_choice_blend_batched requires every source to implement "
            "score_teacher_forced; use score_choice_blend for fallback."
        )
    tgt = list(int(t) for t in choice_tokens)
    # Stack per-source per-position probabilities.
    per_source = [s.score_teacher_forced(tgt) for s in sources]  # each (K, V)
    stacked = np.stack(per_source, axis=0)  # (M, K, V)
    avg = stacked.mean(axis=0)              # (K, V)
    total = 0.0
    for k, target in enumerate(tgt):
        p = float(avg[k, target])
        total += math.log(max(p, log_floor))
    return total
