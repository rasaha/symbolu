"""The documented public API equals the actual package surface.

On the conformance distribution's precedent this distribution ships a
``public_api.json`` snapshot, asserted here — including dataclass field
**order** — so the curated surface cannot drift from the committed contract.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_agent_constitution_activation as activation

_PKG_ROOT = pathlib.Path(activation.__file__).resolve().parent
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
    for name in sorted(activation.__all__):
        if name == "__version__":
            continue
        obj = getattr(activation, name)
        entry: dict = {"kind": _kind(obj)}
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            # Field ORDER is part of the snapshot, not merely the field set.
            entry["fields"] = [f.name for f in dataclasses.fields(obj)]
        elif isinstance(obj, str):
            entry["kind"] = "str_constant"
            entry["value"] = obj
            constants[name] = obj
        symbols[name] = entry
    return symbols, constants


def _documented() -> dict:
    return json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))


def test_documented_public_api_matches_actual():
    documented = _documented()
    symbols, constants = actual_surface()
    assert documented["distribution"] == "ugence-agent-constitution-activation"
    assert documented["namespace"] == "ugence_agent_constitution_activation"
    assert documented["package_version"] == activation.__version__ == "0.1.0"
    assert documented["symbols"] == symbols
    assert documented["constants"] == constants


def test_curated_api_names_match_module_all():
    documented = _documented()
    expected = {n for n in activation.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_the_surface_is_the_ratified_delta_and_nothing_more():
    """`ACC-IA-1` with `ACC-IA-4`: the root and its builder, the two standalone
    seams, their shapes, the two receipts and the error family — thirteen names
    plus ``__version__``, no identity constant. Every identity value is the
    family package's or the authority's, imported never restated."""

    documented = _documented()
    assert documented["constants"] == {}
    assert len(documented["symbols"]) == 13
    assert documented["symbols"]["ActivationRoot"]["kind"] == "class"
    assert documented["symbols"]["build_activation_root"]["kind"] == "function"
    assert documented["symbols"]["populate_reference_map"]["kind"] == "function"
    assert documented["symbols"]["preflight_issuance"]["kind"] == "function"
    for shape in ("PreflightCheck", "PreflightReport", "IssuanceReceipt",
                  "ActivationReceipt"):
        assert documented["symbols"][shape]["kind"] == "dataclass"
    exceptions = [
        name
        for name, entry in documented["symbols"].items()
        if entry["kind"] == "exception"
    ]
    assert len(exceptions) == 5


def test_the_receipt_field_order_is_snapshotted_exactly():
    """`ACC-IA-4`: the ruled receipt content, pinned — and provably free of key
    material: no signature, no policy artifact, no key bytes field exists."""

    documented = _documented()
    assert documented["symbols"]["IssuanceReceipt"]["fields"] == [
        "record_id",
        "coordinate",
        "policy_body_digest",
        "issuing_authority_id",
        "key_id",
        "signature_alg",
        "approving_authority_id",
        "approval_ref",
        "approval_digest",
        "issued_at",
    ]
    assert documented["symbols"]["ActivationReceipt"]["fields"] == [
        "record_id",
        "coordinate",
        "activated_entries",
        "activated_at",
    ]
    for receipt in ("IssuanceReceipt", "ActivationReceipt"):
        fields = set(documented["symbols"][receipt]["fields"])
        assert "signature" not in fields
        assert "policy" not in fields
        assert not any("key" in f for f in fields - {"key_id"})


def test_the_snapshot_exports_no_verified_boolean():
    documented = _documented()
    for name in documented["symbols"]:
        assert "verified" not in name.lower()


def test_py_typed_present():
    assert (_PKG_ROOT / "py.typed").is_file()
