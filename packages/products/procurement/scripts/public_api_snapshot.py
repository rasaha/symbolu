"""Generate a deterministic snapshot of the curated public API.

The snapshot records, for every name exported by :mod:`ugence_procurement.api`
(``__all__``), a stable structural fingerprint: its kind (class / function / enum /
constant), and — for classes/enums — the sorted public member names, and — for
functions — the parameter names. It deliberately does NOT record docstrings, source
locations, or object ids, so it is a pure function of the *API shape*.

Written to ``artifacts/public_api.json`` and asserted by
``tests/packaging/test_public_api.py``. Regenerate intentionally when the public API
changes:

    python scripts/public_api_snapshot.py > artifacts/public_api.json
"""

from __future__ import annotations

import inspect
import json
from enum import Enum

import ugence_procurement.api as api


def _fingerprint(name: str, obj) -> dict:
    if isinstance(obj, type) and issubclass(obj, Enum):
        return {"kind": "enum",
                "members": sorted(m.name for m in obj),
                "values": sorted(m.value for m in obj)}
    if isinstance(obj, type):
        members = sorted(n for n in dir(obj) if not n.startswith("_"))
        return {"kind": "class", "members": members}
    if inspect.isfunction(obj) or inspect.isbuiltin(obj):
        try:
            params = list(inspect.signature(obj).parameters)
        except (TypeError, ValueError):
            params = []
        return {"kind": "function", "parameters": params}
    if isinstance(obj, (str, int, float, bool)):
        return {"kind": "constant", "type": type(obj).__name__}
    if isinstance(obj, dict):
        return {"kind": "mapping", "size": len(obj)}
    return {"kind": "object", "type": type(obj).__name__}


def snapshot() -> dict:
    names = sorted(api.__all__)
    return {
        "module": "ugence_procurement.api",
        "public_names": names,
        "count": len(names),
        "fingerprints": {n: _fingerprint(n, getattr(api, n)) for n in names},
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, sort_keys=True))
