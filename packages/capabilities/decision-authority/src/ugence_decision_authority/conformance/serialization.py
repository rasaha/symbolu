"""Serialization dimension — kernel records round-trip losslessly and stably."""
from __future__ import annotations

from .results import fail, ok


def check(fixture, platform, outcome):
    results = []
    for i, record in enumerate(outcome.records):
        name = type(record).__name__
        try:
            dumped = record.model_dump()
            restored = type(record)(**dumped)
            stable = restored == record and restored.model_dump() == dumped
            results.append(
                ok("serialization", f"round_trip:{name}") if stable
                else fail("serialization", f"round_trip:{name}", "round-trip not identical"))
        except Exception as exc:
            results.append(fail("serialization", f"round_trip:{name}", repr(exc)))
    return results
