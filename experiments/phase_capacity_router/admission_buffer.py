"""
admission_buffer.py — streaming bounded top-K admission (§6).

Maintains a capacity-K buffer of the highest-scoring candidates seen so far. When a new
candidate outranks the current lowest admitted, it replaces it. Produces the same admitted
set as full-ranking top-K (admission-replacement by total candidate ranking), but in O(N)
streaming with O(K) state — demonstrating the router is deployable online. Counts replacements.
"""
from __future__ import annotations

from typing import List, Tuple


def stream_admit(scores: List[float], K: int) -> Tuple[set, int]:
    """Returns (admitted indices, replacement count). Bounded O(K) state, O(N) pass."""
    buf = []          # list of (score, idx), kept as the current top-K
    replacements = 0
    for i, s in enumerate(scores):
        if len(buf) < K:
            buf.append((s, i))
            if len(buf) == K:
                buf.sort()               # ascending; buf[0] is the lowest admitted
        else:
            if s > buf[0][0]:
                buf[0] = (s, i)
                buf.sort()
                replacements += 1
    return {i for _, i in buf}, replacements
