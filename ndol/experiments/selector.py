"""KV block selection by policy — the `--selector` core (CPU-testable, GPU-ready).

Pure index logic on score lists; the same function works on torch by passing
`.tolist()` scores (selection is over a few-thousand blocks — cheap on CPU).
Mirrors the sink+recent pinning + top-budget shape of
`CTM_plus/.../readskip_select.select_retained_blocks`, but lets the *score
source* be swapped (attention / coherence / blend / random / oracle).
"""
from __future__ import annotations

import random as _random
from typing import Iterable, Optional, Sequence

POLICIES = ("full", "attention", "semantic", "scc", "random", "oracle")


def blend(attention: Sequence[float], coherence: Sequence[float],
          alpha: float = 0.5, beta: float = 0.5) -> list[float]:
    """SCC C_b = α·attn + β·coh."""
    return [alpha * a + beta * c for a, c in zip(attention, coherence)]


def select_blocks(scores: Sequence[float], pinned: Iterable[int], budget: int) -> set[int]:
    """Keep `pinned` (sinks + recent) plus the top of `scores` up to `budget`."""
    n = len(scores)
    keep = set(pinned)
    cand = sorted((i for i in range(n) if i not in keep), key=lambda i: scores[i], reverse=True)
    keep.update(cand[: max(0, budget - len(keep))])
    return keep


def select_by_policy(
    policy: str,
    n_blocks: int,
    budget: int,
    pinned: Iterable[int] = (),
    *,
    attention: Optional[Sequence[float]] = None,
    coherence: Optional[Sequence[float]] = None,
    true_importance: Optional[Sequence[float]] = None,
    alpha: float = 0.5,
    beta: float = 0.5,
    seed: int = 0,
) -> set[int]:
    """Return the retained block-id set under `policy`.

    full     — all blocks (quality reference / no-skip)
    attention— top-budget by attention magnitude (read-skip baseline)
    semantic — top-budget by coherence score
    scc      — top-budget by α·attn + β·coh
    random   — pinned + random fill (lower bound, reproducible via seed)
    oracle   — top-budget by true_importance (upper bound; needs ground truth)
    """
    pinned = set(pinned)
    if policy == "full":
        return set(range(n_blocks))
    if policy == "random":
        rng = _random.Random(seed)
        scores = [rng.random() for _ in range(n_blocks)]
    elif policy == "attention":
        if attention is None:
            raise ValueError("attention scores required for policy 'attention'")
        scores = list(attention)
    elif policy == "semantic":
        if coherence is None:
            raise ValueError("coherence scores required for policy 'semantic'")
        scores = list(coherence)
    elif policy == "scc":
        if attention is None or coherence is None:
            raise ValueError("attention and coherence required for policy 'scc'")
        scores = blend(attention, coherence, alpha, beta)
    elif policy == "oracle":
        if true_importance is None:
            raise ValueError("true_importance required for policy 'oracle'")
        scores = list(true_importance)
    else:
        raise ValueError(f"unknown policy {policy!r} (one of {POLICIES})")
    return select_blocks(scores, pinned, budget)
