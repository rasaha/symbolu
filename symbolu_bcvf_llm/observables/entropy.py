"""§11 Entropy-based observable.

Not a disagreement-derived Ketu — instead, a confidence-derived one.
Measures how uncertain the base decoder is at the emission position.

Intuition: if the base decoder's next-token distribution has high
entropy, it's hedging. High-entropy next-token distributions on an
MC scoring event are a candidate Ketu for "the decoder is unsure
here" — and if the decoder is unsure, its argmax is less likely
to be correct.

Whether this actually correlates with truth on a specific benchmark
is what the probe harness measures. Running probe_observable on
this alongside BCVFTotalCostObservable lets you compare two
semantically different Ketu candidates directly.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


class Source0EntropyObservable:
    """Entropy of source 0's next-token distribution at emission position l=0.

    Output: scalar entropy in nats (natural log). Higher entropy →
    lower confidence → candidate "suspicion" signal.

    Properties:
      - Independent of `choice_tokens` (reads only the base decoder's
        commit-position distribution). Same value for all choices of
        a given question.
      - O(V) per observation — very fast.
      - No dependence on the kernel or other sources — probes the
        "is the base model alone informative?" question.
    """

    name: str = "source_0_entropy"
    higher_means_more_suspicious: bool = True

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        probs, _mask = sources[0].lookahead()
        p0 = probs[0].astype(np.float64)  # (V,)
        p0_safe = np.clip(p0, 1e-30, None)
        entropy = float(-np.sum(p0 * np.log(p0_safe)))
        top_token = int(np.argmax(p0))
        return ObservableValue(
            scalar=entropy,
            per_source=None,
            metadata={
                "top1_prob": float(p0.max()),
                "top1_token": top_token,
                "vocab_size": int(p0.shape[0]),
            },
        )
