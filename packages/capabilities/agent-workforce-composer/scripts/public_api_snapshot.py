"""Generate a deterministic snapshot of the curated public API.

Records, for every name exported by ``ugence_agent_workforce_composer.api``
(``__all__``), a stable structural fingerprint: its kind (class / function / enum
/ constant), and — for classes/enums — sorted public member names, and — for
functions — parameter names. No docstrings, source locations, or object ids, so
it is a pure function of the API *shape*.

Regenerate intentionally when the public API changes:

    PYTHONPATH=src python scripts/public_api_snapshot.py > artifacts/public_api.json
"""
from __future__ import annotations

import inspect
import json
from enum import Enum

import ugence_agent_workforce_composer.api as api


def _fingerprint(name: str, obj) -> dict:
    if isinstance(obj, type) and issubclass(obj, Enum):
        return {
            "kind": "enum",
            "members": sorted(m.name for m in obj),
            "values": sorted(str(m.value) for m in obj),
        }
    if isinstance(obj, type):
        members = sorted(n for n in dir(obj) if not n.startswith("_"))
        return {"kind": "class", "members": members}
    if inspect.isfunction(obj) or inspect.isbuiltin(obj):
        try:
            params = list(inspect.signature(obj).parameters)
        except (TypeError, ValueError):
            params = []
        return {"kind": "function", "parameters": params}
    if isinstance(obj, bool) or isinstance(obj, (str, int, float)):
        return {"kind": "constant", "type": type(obj).__name__}
    return {"kind": "object", "type": type(obj).__name__}


def snapshot() -> dict:
    names = sorted(api.__all__)
    return {
        "module": "ugence_agent_workforce_composer.api",
        "public_names": names,
        "count": len(names),
        "fingerprints": {n: _fingerprint(n, getattr(api, n)) for n in names},
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, sort_keys=True))
