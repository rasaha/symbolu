"""The documented public API equals the actual package surface.

On the `S2B-PF-H` precedent this distribution ships a ``public_api.json``
snapshot. The snapshot is only worth shipping if something asserts it, so this
asserts it — including dataclass field **order** — on the Policy Authority's own
precedent. A snapshot nothing compares against is documentation that drifts.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_agent_constitution_conformance as conformance

_PKG_ROOT = pathlib.Path(conformance.__file__).resolve().parent
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
    for name in sorted(conformance.__all__):
        if name == "__version__":
            continue
        obj = getattr(conformance, name)
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
    assert documented["distribution"] == "ugence-agent-constitution-conformance"
    assert documented["namespace"] == "ugence_agent_constitution_conformance"
    assert documented["package_version"] == conformance.__version__ == "0.1.0"
    assert documented["symbols"] == symbols
    assert documented["constants"] == constants


def test_curated_api_names_match_module_all():
    documented = _documented()
    expected = {n for n in conformance.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_the_surface_is_the_ratified_delta_and_nothing_more():
    """§8: resolver, conformance verifier, role-facts input type, error family,
    one composition helper. No identity constant lives here — every identity
    value is the family package's, imported never restated."""

    documented = _documented()
    assert documented["constants"] == {}
    assert documented["symbols"]["PolicyAuthorityConstitutionResolver"]["kind"] == "class"
    assert documented["symbols"]["role_facts_conform"]["kind"] == "function"
    assert documented["symbols"]["build_constitution_resolver"]["kind"] == "function"
    assert documented["symbols"]["GovernedRoleFacts"]["kind"] == "dataclass"
    exceptions = [
        name
        for name, entry in documented["symbols"].items()
        if entry["kind"] == "exception"
    ]
    assert len(exceptions) == 9


def test_the_facts_field_order_is_snapshotted_exactly():
    documented = _documented()
    assert documented["symbols"]["GovernedRoleFacts"]["fields"] == [
        "tenant_id",
        "role_contract_ref",
        "declared_candidate_dispositions",
        "declared_review_actions",
        "declared_tool_scopes",
    ]


def test_the_snapshot_exports_no_verified_boolean():
    documented = _documented()
    for name in documented["symbols"]:
        assert "verified" not in name.lower()


def test_py_typed_present():
    assert (_PKG_ROOT / "py.typed").is_file()
