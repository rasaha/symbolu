"""Guarded entrypoint for the vṛtti-operator scaffold.

Emits NOT_RUN unless a real, approved varṇa→operator table + task is supplied. The
scaffold supplies none, so it computes NO real representation and makes NO semantic claim.
Stage A is not imported or modified.
"""
from __future__ import annotations


def run(config: dict | None = None) -> dict:
    if not config:
        return {"status": "NOT_RUN",
                "reason": "no real varṇa→operator table supplied (synthetic scaffold only)",
                "computed": False, "result": None}
    # A real table/task would gate the run; the scaffold deliberately does not implement it.
    return {"status": "NOT_RUN",
            "reason": "real-run path is gated pending approval",
            "computed": False, "result": None}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
