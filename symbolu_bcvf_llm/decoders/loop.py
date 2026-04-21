"""§4.6 generic greedy outer-decoding loop.

Shared by both baseline decoders (vanilla, conventional-blend) from
§1.10 and by §5's trust-shaped decoder. The loop does three things
per outer step:

  1. Pull lookaheads from every source (one call per source).
  2. Ask the strategy callback to pick the next token.
  3. Commit the token into every source; stop at EOS or max_tokens.

The strategy is a `NextTokenFn`: `(lookaheads, step) -> token_id`.
All state beyond the committed token lives inside the strategy — the
loop is deliberately thin so different decoders can share it without
coupling their strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

from symbolu_bcvf_llm.sources.base import Source


Lookahead = Tuple[np.ndarray, np.ndarray]       # (probs (L,V), mask (L,))
NextTokenFn = Callable[[Sequence[Lookahead], int], int]


@dataclass
class DecodeResult:
    """Output of a generic outer-decoding run."""

    emitted_tokens: List[int] = field(default_factory=list)
    stopped_on_eos: bool = False
    num_steps: int = 0


def run_decode(
    sources: Sequence[Source],
    next_token_fn: NextTokenFn,
    max_tokens: int,
    eos_token_id: Optional[int] = None,
) -> DecodeResult:
    """Greedy outer decoding.

    Args:
        sources: M >= 1 Source objects. The loop calls `lookahead()`
            once per outer step per source, and `commit()` once per
            outer step per source after the next-token decision.
        next_token_fn: Strategy callback; receives the list of
            lookaheads (same order as `sources`) and the current
            outer-step index, returns a token_id in [0, V).
        max_tokens: Upper bound on emitted tokens.
        eos_token_id: If the strategy returns this token, the loop
            stops after emitting it.

    Returns:
        DecodeResult with the emitted token stream, an EOS flag, and
        the number of outer steps actually run.

    Raises:
        ValueError on empty sources or non-matching vocab sizes.
    """
    if len(sources) < 1:
        raise ValueError("run_decode requires at least one source")
    V = sources[0].vocab_size
    if any(s.vocab_size != V for s in sources):
        raise ValueError(
            f"sources must share vocab_size; got "
            f"{[s.vocab_size for s in sources]}"
        )

    emitted: List[int] = []
    stopped_on_eos = False
    for t in range(max_tokens):
        lookaheads = [src.lookahead() for src in sources]
        token = int(next_token_fn(lookaheads, t))
        if not (0 <= token < V):
            raise ValueError(f"next_token_fn returned {token}; out of range")
        emitted.append(token)
        if eos_token_id is not None and token == eos_token_id:
            stopped_on_eos = True
            break
        for src in sources:
            src.commit(token)

    return DecodeResult(
        emitted_tokens=emitted,
        stopped_on_eos=stopped_on_eos,
        num_steps=len(emitted),
    )
