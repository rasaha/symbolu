"""The documented public API equals the actual package surface (GV-3R-a)."""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_agent_value_readiness as g
from ugence_agent_value_readiness import api

_PKG_ROOT = pathlib.Path(g.__file__).resolve().parent
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
        elif isinstance(obj, str):
            # Exported string constants are identities consumers pin, so the
            # snapshot records the exact value, not merely the type.
            entry["value"] = obj
        symbols[name] = entry
    return {
        "distribution": "ugence-agent-value-readiness",
        "namespace": "ugence_agent_value_readiness",
        "package_version": g.__version__,
        "curated_api_module": "ugence_agent_value_readiness.api",
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


def test_py_typed_present():
    assert (_PKG_ROOT / "py.typed").is_file()
