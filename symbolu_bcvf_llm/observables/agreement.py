"""Source-agreement observable.

Cheapest disagreement proxy: scalar = 1 - fraction of lookahead
positions where every source's argmax token matches. 0.0 = unanimous
across all positions, 1.0 = no position has full agreement.

Polarity matches BCVF's: higher = more suspicious.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


class SourceAgreementObservable:
    name: str = "source_disagreement_fraction"
    higher_means_more_suspicious: bool = True

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        argmaxes = [np.argmax(s.lookahead()[0], axis=-1) for s in sources]
        stacked = np.stack(argmaxes, axis=0)  # (M, L)
        L = stacked.shape[1]
        unanimous = np.all(stacked == stacked[0:1, :], axis=0)
        agreement_fraction = float(unanimous.mean()) if L > 0 else 1.0
        return ObservableValue(
            scalar=1.0 - agreement_fraction,
            metadata={
                "agreement_fraction": agreement_fraction,
                "L": int(L),
                "M": int(stacked.shape[0]),
                "argmax_first_position": stacked[:, 0].tolist() if L > 0 else [],
            },
        )
