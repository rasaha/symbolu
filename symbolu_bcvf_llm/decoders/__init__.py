"""§4.6 baseline decoders + generic outer-decoding loop.

`decode_vanilla`, `decode_conventional_blend` are §1.10's two
baselines. `run_decode` is the shared outer loop that both — and
§5's future trust-shaped decoder — invoke.
"""

from __future__ import annotations

from .blend import decode_conventional_blend
from .loop import DecodeResult, Lookahead, NextTokenFn, run_decode
from .vanilla import decode_vanilla

__all__ = [
    "DecodeResult",
    "Lookahead",
    "NextTokenFn",
    "decode_conventional_blend",
    "decode_vanilla",
    "run_decode",
]
