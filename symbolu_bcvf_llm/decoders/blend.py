"""§4.6 / §1.10 ConventionalBlendDecoder — equal-weight blend of M sources.

Computes `p̄(l=0) = (1/M) · Σ_s p_s(l=0)` and emits
`argmax_v p̄_v`. No trust-weighting, no BCVF — this is the
conventional blended-verifier baseline (`conventional-blend`) that
§6 compares BCVF-trust against.

§5's TrustShapedDecoder will replace the equal weights with
softmin-trust weights derived from §2.8.12's per-source costs.
Keeping the same outer-loop shape here means that plugging §5 in
is a single-function change to `next_token_fn`.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from symbolu_bcvf_llm.sources.base import Source

from .loop import DecodeResult, Lookahead, run_decode


def _blend_next_token(lookaheads: Sequence[Lookahead], step: int) -> int:
    # Stack the l=0 probability vector from each source and average.
    p0 = np.stack([la[0][0] for la in lookaheads], axis=0)  # (M, V)
    avg = p0.mean(axis=0)
    return int(np.argmax(avg))


def decode_conventional_blend(
    sources: Sequence[Source],
    max_tokens: int = 32,
    eos_token_id: Optional[int] = None,
) -> DecodeResult:
    """Run the conventional-blend (equal-weight) baseline decoder.

    Args:
        sources: M >= 1 Source objects; the loop averages their
            position-0 probabilities at every outer step.
        max_tokens, eos_token_id: as in `run_decode`.
    """
    if not sources:
        raise ValueError("decode_conventional_blend requires at least one source")
    return run_decode(
        sources=sources,
        next_token_fn=_blend_next_token,
        max_tokens=max_tokens,
        eos_token_id=eos_token_id,
    )
