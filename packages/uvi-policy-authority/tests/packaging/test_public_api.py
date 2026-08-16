"""The documented public API equals the actual package surface (GV-2C-b §15)."""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_uvi_policy_authority as g
from ugence_uvi_policy_authority import api

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
        symbols[name] = entry
    return {
        "distribution": "ugence-uvi-policy-authority",
        "namespace": "ugence_uvi_policy_authority",
        "package_version": g.__version__,
        "curated_api_module": "ugence_uvi_policy_authority.api",
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


def test_top_level_and_curated_surfaces_agree():
    assert set(g.__all__) == set(api.__all__)
    for name in api.__all__:
        assert getattr(g, name) is getattr(api, name)


def test_py_typed_present():
    assert (_PKG_ROOT / "py.typed").is_file()


def test_package_version_is_the_new_leaf_version():
    assert g.__version__ == "0.1.0"


def test_no_existing_package_version_was_bumped():
    """This milestone adds a package; it changes none of the merged ones."""

    import ugence_governance_contracts
    import ugence_uvi_policy_contracts

    assert ugence_governance_contracts.__version__ == "0.2.0"
    assert ugence_uvi_policy_contracts.__version__ == "0.1.0"


def test_no_symbol_shadows_a_contract_symbol():
    """The authority re-exports no contract shape under its own name."""

    from ugence_uvi_policy_contracts import api as contracts_api

    overlap = set(api.__all__) & set(contracts_api.__all__)
    assert overlap == {"__version__"}
