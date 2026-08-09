"""Deterministic replay checks. Torch-free.

Regenerating an episode from the same (split, seed, index, role) must yield a byte-identical serialization
and identical fact_hash. This underpins the protocol-step-0 deterministic-replay integrity check.
"""
from __future__ import annotations

from .generator import generate_episode
from .serializer import serialize_input


def replay_matches(split: str, seed: int, index: int, role: str = "unit") -> bool:
    a = generate_episode(split, seed, index, role)
    b = generate_episode(split, seed, index, role)
    return (serialize_input(a) == serialize_input(b)
            and a.fact_hash() == b.fact_hash()
            and a.authoritative_output.payload() == b.authoritative_output.payload())


def replay_report(splits, seed: int, n: int, role: str = "unit") -> dict:
    return {s: all(replay_matches(s, seed, i, role) for i in range(n)) for s in splits}
