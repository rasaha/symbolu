"""Hashes dimension — kernel record hashing is deterministic and stable."""
from __future__ import annotations

from ..common import canonical_hash
from .results import fail, ok


def check(fixture, platform, outcome):
    results = []
    for i, record in enumerate(outcome.records):
        name = type(record).__name__
        try:
            h1 = canonical_hash(record.model_dump(mode="json"))
            h2 = canonical_hash(record.model_dump(mode="json"))
            results.append(
                ok("hashes", f"deterministic:{name}") if h1 == h2
                else fail("hashes", f"deterministic:{name}", "canonical hash not deterministic"))
        except Exception as exc:
            results.append(fail("hashes", f"deterministic:{name}", repr(exc)))
    return results
