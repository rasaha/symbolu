"""The documented public API equals the actual package surface.

On the `S2B-PF-H` precedent this distribution ships a ``public_api.json``
snapshot. The snapshot is only worth shipping if something asserts it, so this
asserts it — including dataclass field **order** and the exact value of every
string constant, on the Policy Authority's own precedent. A snapshot nothing
compares against is documentation that drifts.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_agent_constitution_policy as family

_PKG_ROOT = pathlib.Path(family.__file__).resolve().parent
_DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
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
    if callable(obj):
        return "function"
    return type(obj).__name__


def actual_surface() -> tuple:
    symbols: dict = {}
    constants: dict = {}
    for name in sorted(family.__all__):
        if name == "__version__":
            continue
        obj = getattr(family, name)
        entry: dict = {"kind": _kind(obj)}
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            # Field ORDER is part of the snapshot, not merely the field set.
            entry["fields"] = [f.name for f in dataclasses.fields(obj)]
        elif isinstance(obj, str):
            entry["kind"] = "str_constant"
            entry["value"] = obj
            constants[name] = obj
        elif isinstance(obj, frozenset):
            entry["kind"] = "frozenset_constant"
            entry["values"] = sorted(obj)
        symbols[name] = entry
    return symbols, constants


def _documented() -> dict:
    return json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))


def test_documented_public_api_matches_actual():
    documented = _documented()
    symbols, constants = actual_surface()
    assert documented["distribution"] == "ugence-agent-constitution-policy"
    assert documented["namespace"] == "ugence_agent_constitution_policy"
    assert documented["package_version"] == family.__version__ == "0.2.0"
    assert documented["symbols"] == symbols
    assert documented["constants"] == constants


def test_curated_api_names_match_module_all():
    documented = _documented()
    expected = {n for n in family.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_the_identity_constants_are_snapshotted_exactly():
    """Each is bound into a digest, a coordinate, or both — so each is pinned.

    The four values are the `ACC-S1-Q1` table, ratified whole; each equality
    below is against the ratified spelling, not against the module, so a drift
    in either direction fails.
    """

    documented = _documented()
    for name in (
        "AGENT_CONSTITUTION_ADAPTER_ID",
        "AGENT_CONSTITUTION_POLICY_FAMILY",
        "AGENT_CONSTITUTION_POLICY_TYPE",
        "CONSTITUTION_VOCABULARY_VERSION",
    ):
        assert documented["constants"][name] == getattr(family, name)
    assert (
        documented["constants"]["AGENT_CONSTITUTION_ADAPTER_ID"]
        == "ugence.agent-constitution/v1"
    )
    assert (
        documented["constants"]["AGENT_CONSTITUTION_POLICY_FAMILY"]
        == "agent_governance.agent_constitution"
    )
    assert (
        documented["constants"]["AGENT_CONSTITUTION_POLICY_TYPE"]
        == "AgentConstitutionPolicy"
    )
    assert (
        documented["constants"]["CONSTITUTION_VOCABULARY_VERSION"]
        == "ugence.agent-constitution/clauses/v1"
    )


def test_the_snapshot_exports_no_verified_boolean_and_no_resolver():
    """`[R]` No ``verified`` boolean is ratified anywhere in this work, and
    resolution belongs to the separate `ACC-S1-Q2` conformance distribution."""

    documented = _documented()
    for name in documented["symbols"]:
        assert "verified" not in name.lower()
        assert "resolver" not in name.lower()


def test_py_typed_present():
    assert (_PKG_ROOT / "py.typed").is_file()
