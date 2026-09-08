"""The documented public API equals the actual package surface.

The kernel shipped a curated ``governed_value.api.__all__`` that nothing pinned:
a symbol could be added, removed or reshaped and every test still passed, because
the suite exercised behaviour and never the surface. Its peers at the same tier
(``governance-contracts``, ``policy-authority``, ``uvi-policy-contracts``,
``benchmark-registry``, ``trusted-evidence-authority``, ``agent-value-readiness``)
all committed a ``public_api.json`` and asserted equality against it; this closes
the same gap here.

Regenerate the manifest with ``scripts/generate_public_api.py`` when the curated
API changes deliberately.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import json
import pathlib

import governed_value as gv
from governed_value import api

_PKG_ROOT = pathlib.Path(gv.__file__).resolve().parent
_DIST_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PUBLIC_API_JSON = _DIST_ROOT / "public_api.json"

#: Excluded for the same reason the generator excludes them: ``BaseException``'s
#: public methods are not this package's API and are not stable across
#: interpreters (``add_note`` is a 3.11 addition), so recording them would make
#: the committed artifact unreproducible on 3.10.
_INHERITED_EXCEPTION_METHODS = frozenset(
    name for name, _ in inspect.getmembers(BaseException, callable)
    if not name.startswith("_")
)


def _own_methods(value: type) -> list:
    inherited = (
        _INHERITED_EXCEPTION_METHODS if issubclass(value, BaseException) else frozenset()
    )
    return sorted(
        name for name, _ in inspect.getmembers(value, callable)
        if not name.startswith("_") and name not in inherited
    )


def _describe(name: str) -> dict:
    value = getattr(api, name)
    if isinstance(value, type) and issubclass(value, enum.Enum):
        return {"kind": "enum", "values": [member.value for member in value]}
    if isinstance(value, type) and dataclasses.is_dataclass(value):
        return {"kind": "dataclass", "fields": [f.name for f in dataclasses.fields(value)]}
    if isinstance(value, type) and issubclass(value, Exception):
        return {"kind": "exception", "methods": _own_methods(value)}
    if isinstance(value, type):
        return {"kind": "class", "methods": _own_methods(value)}
    if inspect.isfunction(value):
        return {"kind": "function", "parameters": list(inspect.signature(value).parameters)}
    if isinstance(value, str):
        return {"kind": "constant", "value": value}
    return {"kind": type(value).__name__}


def _actual_surface() -> dict:
    return {
        "distribution": "ugence-governed-value",
        "namespace": "governed_value",
        "package_version": gv.__version__,
        "curated_api_module": "governed_value.api",
        "symbols": {
            name: _describe(name) for name in sorted(api.__all__) if name != "__version__"
        },
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


def test_manifest_version_matches_the_distribution():
    """The manifest is a snapshot of a release, so it must name that release."""

    documented = json.loads(_PUBLIC_API_JSON.read_text())
    assert documented["package_version"] == gv.__version__


def test_py_typed_present():
    assert (_PKG_ROOT / "py.typed").is_file()


def test_the_surface_exports_no_observation_constructor():
    """GV-PRODUCER: this kernel constructs no observation and attests none.

    ``MetricObservation`` is owned by ``ugence-governance-contracts`` and reaches
    the kernel only as a caller-supplied value. Re-exporting it here would make
    the kernel look like a producer of the very evidence it must not mint, so the
    curated surface carries ``ObservedMetric`` — the record of what was admitted —
    and never the observation type itself.
    """

    assert "MetricObservation" not in api.__all__
    assert "ObservedMetric" in api.__all__
