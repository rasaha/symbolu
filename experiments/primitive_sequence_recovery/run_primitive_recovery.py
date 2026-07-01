"""Guarded runner — NOT_RUN on real data.

The scaffold has no frozen, approved lexicon or realization set, so this computes no real
result and writes no result artifacts. Stage A is not imported. No semantic claim.
"""
from __future__ import annotations


def run(config: dict | None = None) -> dict:
    return {"status": "NOT_RUN",
            "reason": "no frozen approved assignment + realizations (synthetic scaffold only)",
            "computed": False, "result": None}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
