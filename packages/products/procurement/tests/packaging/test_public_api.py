"""The curated public API must exactly match the frozen snapshot.

Adding or removing a public name in ``ugence_procurement.api`` is a deliberate,
reviewed API change and requires regenerating ``artifacts/public_api.json``
(``python scripts/public_api_snapshot.py``).
"""

from __future__ import annotations

import inspect
import json
import pathlib
from enum import Enum

import ugence_procurement.api as api

_ARTIFACT = pathlib.Path(__file__).resolve().parents[2] / "artifacts" / "public_api.json"


def _fingerprint(name, obj):
    if isinstance(obj, type) and issubclass(obj, Enum):
        return {"kind": "enum",
                "members": sorted(m.name for m in obj),
                "values": sorted(m.value for m in obj)}
    if isinstance(obj, type):
        return {"kind": "class", "members": sorted(n for n in dir(obj) if not n.startswith("_"))}
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


def _live_snapshot():
    names = sorted(api.__all__)
    return {"module": "ugence_procurement.api", "public_names": names, "count": len(names),
            "fingerprints": {n: _fingerprint(n, getattr(api, n)) for n in names}}


def test_public_api_matches_frozen_snapshot():
    frozen = json.loads(_ARTIFACT.read_text())
    assert _live_snapshot() == frozen, (
        "ugence_procurement.api drifted from artifacts/public_api.json; "
        "regenerate intentionally with scripts/public_api_snapshot.py")


def test_every_public_name_is_importable_and_resolves():
    for name in api.__all__:
        assert hasattr(api, name), name


def test_no_private_names_leak_into_all():
    assert all(not n.startswith("_") for n in api.__all__)
