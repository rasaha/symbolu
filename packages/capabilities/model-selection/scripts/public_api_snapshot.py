"""Generate a deterministic snapshot of the curated public API.

Records, for every name exported by ``ugence_model_selection.api`` (``__all__``), a
stable structural fingerprint: its kind (class / function / enum / constant), and — for
classes/enums — sorted public member names, and — for functions — parameter names. No
docstrings, source locations, or object ids, so it is a pure function of the API *shape*.

Inherited exception methods are excluded deliberately: ``BaseException.add_note`` arrived
in 3.11, and recording it would make the artifact a statement about the interpreter that
generated it rather than about the API.

Regenerate intentionally when the public API changes:

    PYTHONPATH=src python scripts/public_api_snapshot.py > artifacts/public_api.json
"""
from __future__ import annotations

import inspect
import json
from enum import Enum

import ugence_model_selection.api as api

#: Methods Python adds to every exception, which differ by interpreter version.
_INHERITED_EXCEPTION_METHODS = frozenset(dir(BaseException)) - {"args"}


def _fingerprint(name: str, obj) -> dict:
    if isinstance(obj, type) and issubclass(obj, Enum):
        return {
            "kind": "enum",
            "members": sorted(m.name for m in obj),
            "values": sorted(str(m.value) for m in obj),
        }
    if isinstance(obj, type):
        members = sorted(n for n in dir(obj) if not n.startswith("_"))
        if issubclass(obj, BaseException):
            members = sorted(set(members) - _INHERITED_EXCEPTION_METHODS)
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
        "count": len(names),
        "fingerprints": {name: _fingerprint(name, getattr(api, name)) for name in names},
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, sort_keys=True))
