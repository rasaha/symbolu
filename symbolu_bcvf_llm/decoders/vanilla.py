"""§4.6 / §1.10 VanillaDecoder — baseline `A0`, source-0 argmax only.

Uses only source 0 (the base decoder from §1.4.1). Emits
`argmax(p_0(t, l=0))` at every outer step. This is what a
conventional greedy decoder would produce — it ignores the other
M-1 sources entirely and has no trust-weighting. Serves as the
zero-blend baseline for the §6 three-way comparison.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from symbolu_bcvf_llm.sources.base import Source

from .loop import DecodeResult, Lookahead, run_decode


def _vanilla_next_token(lookaheads: Sequence[Lookahead], step: int) -> int:
    probs, _mask = lookaheads[0]
    return int(np.argmax(probs[0]))


def decode_vanilla(
    sources: Sequence[Source],
    max_tokens: int = 32,
    eos_token_id: Optional[int] = None,
) -> DecodeResult:
    """Run the vanilla (source-0-only) baseline decoder.

    The vanilla decoder never consults sources 1..M-1 even when they
    are provided, which matches §1.10's "vanilla" baseline. Other
    sources are still accepted in the argument to match the
    conventional-blend + trust-shaped decoder interfaces; the
    sources are *committed* into alongside source 0 so that all
    three decoders see the same committed-prefix state if they are
    later compared on identical traces.
    """
    if not sources:
        raise ValueError("decode_vanilla requires at least one source")
    return run_decode(
        sources=sources,
        next_token_fn=_vanilla_next_token,
        max_tokens=max_tokens,
        eos_token_id=eos_token_id,
    )
