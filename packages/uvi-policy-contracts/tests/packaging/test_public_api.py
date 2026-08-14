"""The documented public API agrees with the actual package surface.

Rebuilds the public-API description from the installed
``ugence_uvi_policy_contracts.api`` module and asserts it is equal (after
normalization) to the committed ``public_api.json``. Catches an accidental
export addition/removal, an enum-value drift, or a dataclass-field change not
reflected in the machine-readable snapshot. Also asserts the PEP 561 ``py.typed``
marker is present.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_uvi_policy_contracts as g
from ugence_uvi_policy_contracts import api

_PKG_ROOT = pathlib.Path(g.__file__).resolve().parent
# tests/packaging/ -> tests/ -> packages/uvi-policy-contracts/
_DIST_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PUBLIC_API_JSON = _DIST_ROOT / "public_api.json"


def _kind(obj) -> str:
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return "enum"
        if issubclass(obj, Exception):
            return "exception"
        if dataclasses.is_dataclass(obj):
            return "dataclass"
        return "class"
    return type(obj).__name__


def _actual_surface() -> dict:
    symbols: dict[str, dict] = {}
    for name in sorted(api.__all__):
        if name == "__version__":
            continue
        obj = getattr(api, name)
        entry: dict = {"kind": _kind(obj)}
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            entry["values"] = [m.value for m in obj]
        elif isinstance(obj, type) and dataclasses.is_dataclass(obj):
            entry["fields"] = [f.name for f in dataclasses.fields(obj)]
        symbols[name] = entry
    return {
        "distribution": "ugence-uvi-policy-contracts",
        "namespace": "ugence_uvi_policy_contracts",
        "package_version": g.__version__,
        "curated_api_module": "ugence_uvi_policy_contracts.api",
        "symbols": symbols,
    }


def test_documented_public_api_matches_actual():
    documented = json.loads(_PUBLIC_API_JSON.read_text())
    documented.pop("note", None)
    actual = _actual_surface()
    for key in ("distribution", "namespace", "package_version", "curated_api_module"):
        assert documented[key] == actual[key], key
    assert documented["symbols"] == actual["symbols"]


def test_curated_api_names_match_module_all():
    documented = json.loads(_PUBLIC_API_JSON.read_text())
    expected = {n for n in api.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_py_typed_marker_present():
    assert (_PKG_ROOT / "py.typed").is_file(), "PEP 561 py.typed marker missing"
