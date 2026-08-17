"""The documented public API agrees with the actual package surface.

Rebuilds the public-API description from the imported
``ugence_trusted_evidence_authority.api`` module and asserts it equals the
committed ``public_api.json``. Catches an accidental export addition or removal,
an enum-value drift, a dataclass-field change, a field **reordering**, or a
changed pinned constant that the machine-readable snapshot does not reflect.

The same builder is used by the distribution verifier against the *installed*
wheel, so the source tree, the manifest, the wheel and an isolated installed
runtime are all held to one description.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_trusted_evidence_authority as pkg
from ugence_trusted_evidence_authority import api

_PKG_ROOT = pathlib.Path(pkg.__file__).resolve().parent
# tests/packaging/ -> tests/ -> packages/trusted-evidence-authority/
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
    if callable(obj):
        return "function"
    return "constant"


def _constant_value(obj):
    """A JSON-representable, order-preserving rendering of a pinned constant."""

    if isinstance(obj, str):
        return obj
    if isinstance(obj, (tuple, list)):
        return [getattr(v, "value", v) for v in obj]
    if isinstance(obj, frozenset):
        return sorted(getattr(v, "value", v) for v in obj)
    if hasattr(obj, "items"):  # the lifecycle transition mapping
        return {
            getattr(k, "value", k): sorted(getattr(v, "value", v) for v in value)
            for k, value in obj.items()
        }
    return repr(obj)


def actual_surface(module=api, version=None) -> dict:
    symbols: dict = {}
    for name in sorted(module.__all__):
        if name == "__version__":
            continue
        obj = getattr(module, name)
        entry: dict = {"kind": _kind(obj)}
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            entry["values"] = [m.value for m in obj]
        elif isinstance(obj, type) and dataclasses.is_dataclass(obj):
            entry["fields"] = [f.name for f in dataclasses.fields(obj)]
        elif entry["kind"] == "constant":
            entry["value"] = _constant_value(obj)
        symbols[name] = entry
    return {
        "distribution": "ugence-trusted-evidence-authority",
        "namespace": "ugence_trusted_evidence_authority",
        "package_version": version or pkg.__version__,
        "curated_api_module": "ugence_trusted_evidence_authority.api",
        "symbols": symbols,
    }


def test_documented_public_api_matches_actual():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    documented.pop("note", None)
    actual = actual_surface()
    for key in ("distribution", "namespace", "package_version", "curated_api_module"):
        assert documented[key] == actual[key], key
    assert documented["symbols"] == actual["symbols"]


def test_curated_api_names_match_module_all():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    expected = {n for n in api.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_top_level_reexports_match_the_curated_api():
    """The package root and ``api`` export the same names (plus ``api`` itself)."""

    assert set(pkg.__all__) - {"api"} == set(api.__all__)
    for name in api.__all__:
        if name == "__version__":
            continue
        assert getattr(pkg, name) is getattr(api, name), name


def test_all_is_explicit_and_free_of_duplicates():
    for module in (pkg, api):
        assert isinstance(module.__all__, list)
        assert len(set(module.__all__)) == len(module.__all__)


def test_no_private_name_is_exported():
    for name in api.__all__:
        assert name == "__version__" or not name.startswith("_"), name


def test_py_typed_marker_present():
    assert (_PKG_ROOT / "py.typed").is_file(), "PEP 561 py.typed marker missing"


def test_the_manifest_records_the_package_version():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    assert documented["package_version"] == pkg.__version__ == "0.1.0"


def test_pinned_constants_are_snapshotted_with_their_values():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    constants = {
        name: entry
        for name, entry in documented["symbols"].items()
        if entry["kind"] == "constant"
    }
    assert set(constants) == {
        "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
        "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
        "EVIDENCE_TRUST_STAGE_ORDER",
        "EVIDENCE_LIFECYCLE_TRANSITIONS",
        "TRUSTED_EVIDENCE_REFUSAL_REASONS",
    }
    for entry in constants.values():
        assert "value" in entry


def test_enum_member_order_is_snapshotted_not_just_the_member_set():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    values = documented["symbols"]["TrustedEvidenceRefusalReason"]["values"]
    assert values == [m.value for m in api.TrustedEvidenceRefusalReason]
    assert values[0] == "TRUSTED_EVIDENCE_MISSING"
    assert values[-1] == "TRUSTED_EVIDENCE_INDETERMINATE"
