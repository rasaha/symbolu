"""Entropy-based observable.

Confidence proxy: scalar = entropy of source 0's next-token
distribution at lookahead position l=0. Higher entropy → lower
confidence → candidate "suspicion" signal.

Independent of `choice_tokens` — same value across all choices of
a given question.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


class Source0EntropyObservable:
    name: str = "source_0_entropy"
    higher_means_more_suspicious: bool = True

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        probs, _mask = sources[0].lookahead()
        p0 = probs[0].astype(np.float64)
        p0_safe = np.clip(p0, 1e-30, None)
        entropy = float(-np.sum(p0 * np.log(p0_safe)))
        return ObservableValue(
            scalar=entropy,
            metadata={
                "top1_prob": float(p0.max()),
                "top1_token": int(np.argmax(p0)),
                "vocab_size": int(p0.shape[0]),
            },
        )
