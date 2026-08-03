"""Shared test bootstrap: put the lab root on sys.path and provide tiny stdlib helpers.

No pytest/numpy required. Tests import from ``src.*`` after calling nothing — importing this
module performs the path insertion as a side effect.
"""
from __future__ import annotations

import pathlib
import sys
from typing import List

_LAB_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))


def basis(i: int, d: int) -> List[float]:
    """Unit basis vector e_i in R^d (deterministic, no randomness)."""
    v = [0.0] * d
    v[i] = 1.0
    return v


def argmax(xs) -> int:
    return max(range(len(xs)), key=lambda i: xs[i])
