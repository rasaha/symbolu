"""Generate a deterministic snapshot of the curated public API.

Records, for every name exported by ``ugence_policy_workflow_compiler.api``
(``__all__``), a stable structural fingerprint: its kind (class / function / enum /
constant), and — for classes/enums — sorted public member names, and — for
functions — parameter names. It records no docstrings, source locations, or object
ids, so it is a pure function of the API *shape*.

Written to ``artifacts/public_api.json`` and asserted by the packaging tests.
Regenerate intentionally when the public API changes:

    python scripts/public_api_snapshot.py > artifacts/public_api.json
"""

from __future__ import annotations

import inspect
import json
from enum import Enum

import ugence_policy_workflow_compiler.api as api


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
    if isinstance(obj, dict):
        return {"kind": "mapping", "size": len(obj)}
    return {"kind": "object", "type": type(obj).__name__}


def snapshot() -> dict:
    names = sorted(api.__all__)
    return {
        "module": "ugence_policy_workflow_compiler.api",
        "public_names": names,
        "count": len(names),
        "fingerprints": {n: _fingerprint(n, getattr(api, n)) for n in names},
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, sort_keys=True))
