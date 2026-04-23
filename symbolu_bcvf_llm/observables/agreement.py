"""§11 Source-agreement observable.

Cheapest possible disagreement proxy: fraction of lookahead positions
where all M sources' argmax token matches. 1.0 = unanimous, 0.0 =
all different.

Contrast with BCVF: BCVF looks at the full vector distributions and
their 2nd derivative. Agreement looks only at argmax. If BCVF and
Agreement give similar AUC on the probe, BCVF's sophisticated math
isn't adding information over a cheap proxy — useful diagnostic.

Inverted polarity compared to BCVF: agreement ≈ 1 is MORE trusted
(cheap consensus), so the observable reports scalar = 1 - agreement
so that higher = more suspicious (matches BCVF's direction). That
keeps the probe's AUC interpretation uniform across observables.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from symbolu_bcvf_llm.sources.base import Source

from .base import ObservableValue


class SourceAgreementObservable:
    """Fraction of lookahead positions where all sources disagree on
    argmax, expressed as scalar = 1 - fraction-of-positions-where-
    all-argmax-match.

    Range: [0.0, 1.0]. Higher = more positions with argmax divergence.
    """

    name: str = "source_disagreement_fraction"
    higher_means_more_suspicious: bool = True

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        argmaxes = []
        for s in sources:
            probs, _mask = s.lookahead()  # (L, V)
            argmaxes.append(np.argmax(probs, axis=-1))  # (L,)
        stacked = np.stack(argmaxes, axis=0)  # (M, L)
        L = stacked.shape[1]
        # Unanimous agreement at position l iff all sources' argmax matches.
        unanimous = np.all(stacked == stacked[0:1, :], axis=0)  # (L,)
        agreement_fraction = float(unanimous.mean()) if L > 0 else 1.0
        disagreement = 1.0 - agreement_fraction
        return ObservableValue(
            scalar=disagreement,
            per_source=None,
            metadata={
                "agreement_fraction": agreement_fraction,
                "L": int(L),
                "M": int(stacked.shape[0]),
                "argmax_first_position": stacked[:, 0].tolist() if L > 0 else [],
            },
        )
