#!/usr/bin/env python3
"""Regenerate ``public_api.json`` from the package's actual curated surface.

Run after any deliberate change to ``__all__``; ``tests/packaging/test_packaging.py`` asserts
the file equals the live surface.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import json
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]
_P = REPO / "packages"
for _path in (
    PKG / "src",
    _P / "risk_authority" / "src",
    _P / "trusted-evidence-authority" / "src",
    _P / "policy-authority" / "src",
    _P / "uvi-policy-contracts" / "src",
    _P / "governance-contracts" / "src",
    _P / "capabilities" / "cloud-scaling-controller" / "src",
    _P / "integration" / "cloud-scaling-risk-integration" / "src",
    _P / "integration" / "cloud-scaling-authorization-contracts" / "src",
    _P / "integration" / "cloud-scaling-policy-authenticity" / "src",
    _P / "integration" / "cloud-scaling-producer-attestation" / "src",
):
    if _path.exists() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import ugence_cloud_scaling_envelope_issuance as pkg  # noqa: E402


#: Public methods every exception inherits from ``BaseException``. They are not this
#: package's API, and they are not even stable across interpreters: ``add_note`` exists
#: from Python 3.11 and not before. Recording them made ``public_api.json`` a statement
#: about the interpreter that generated the file, so a 3.10 run could never reproduce a
#: manifest generated on 3.11 whatever the package itself declared. Excluded here rather
#: than normalised at the comparison, so the committed artifact describes only what the
#: class itself contributes and stays reproducible on every supported interpreter. The
#: set is derived from ``BaseException`` rather than hard-coded, so a method a future
#: interpreter adds is excluded on both sides of the comparison too.
_INHERITED_EXCEPTION_METHODS = frozenset(
    name for name, _ in inspect.getmembers(BaseException, callable)
    if not name.startswith("_")
)


def own_methods(value: type) -> list:
    """The class's own public callables, minus what every exception inherits."""

    inherited = (
        _INHERITED_EXCEPTION_METHODS if issubclass(value, BaseException) else frozenset()
    )
    return sorted(
        name for name, _ in inspect.getmembers(value, callable)
        if not name.startswith("_") and name not in inherited
    )


def describe(name: str) -> dict:
    value = getattr(pkg, name)
    if isinstance(value, type) and issubclass(value, enum.Enum):
        return {"kind": "enum", "values": [member.value for member in value]}
    if dataclasses.is_dataclass(value) and isinstance(value, type):
        return {"kind": "dataclass", "fields": [f.name for f in dataclasses.fields(value)]}
    if isinstance(value, type):
        return {"kind": "class", "methods": own_methods(value)}
    if inspect.isfunction(value):
        return {"kind": "function", "parameters": list(inspect.signature(value).parameters)}
    if isinstance(value, frozenset):
        return {"kind": "frozenset", "values": sorted(str(v) for v in value)}
    if isinstance(value, tuple):
        return {"kind": "tuple", "values": [str(v) for v in value]}
    if isinstance(value, str):
        return {"kind": "constant", "value": value}
    return {"kind": type(value).__name__}


def build() -> dict:
    return {
        "distribution": "ugence-cloud-scaling-envelope-issuance",
        "namespace": "ugence_cloud_scaling_envelope_issuance",
        "package_version": pkg.__version__,
        "curated_api_module": "ugence_cloud_scaling_envelope_issuance",
        "note": (
            "Machine-readable snapshot of the curated public API "
            "(ugence_cloud_scaling_envelope_issuance.__all__). tests/packaging/test_packaging.py "
            "asserts this file equals the live package surface. Regenerate with "
            "scripts/generate_public_api.py when the curated API changes deliberately."
        ),
        "symbols": {name: describe(name) for name in sorted(pkg.__all__)},
    }


def main() -> int:
    target = PKG / "public_api.json"
    target.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target} ({len(pkg.__all__)} symbols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
