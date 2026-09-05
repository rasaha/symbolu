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
    _P / "integration" / "cloud-scaling-envelope-issuance" / "src",
    _P / "integration" / "cloud-scaling-action-admission" / "src",
    _P / "integration" / "execution-reservation" / "src",
    _P / "capabilities" / "action-clearance" / "src",
    _P / "capabilities" / "decision-authority" / "src",
    _P / "capabilities" / "cloud-scaling-operations" / "src",
    _P / "integration" / "cloud-scaling-credential-broker" / "src",
    _P / "integration" / "risk-authority-execution-assurance" / "src",
):
    if _path.exists() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import ugence_cloud_scaling_bounded_execution as pkg  # noqa: E402


def describe(name: str) -> dict:
    value = getattr(pkg, name)
    if isinstance(value, type) and issubclass(value, enum.Enum):
        return {"kind": "enum", "values": [member.value for member in value]}
    if dataclasses.is_dataclass(value) and isinstance(value, type):
        return {"kind": "dataclass", "fields": [f.name for f in dataclasses.fields(value)]}
    if isinstance(value, type):
        return {"kind": "class", "methods": sorted(
            n for n, _ in inspect.getmembers(value, callable) if not n.startswith("_"))}
    if inspect.isfunction(value):
        return {"kind": "function", "parameters": list(inspect.signature(value).parameters)}
    if isinstance(value, frozenset):
        return {"kind": "frozenset", "values": sorted(str(v) for v in value)}
    if isinstance(value, tuple):
        return {"kind": "tuple", "values": [str(v) for v in value]}
    if isinstance(value, str):
        return {"kind": "constant", "value": value}
    if type(value).__name__ == "timedelta":
        return {"kind": "timedelta", "seconds": value.total_seconds()}
    return {"kind": type(value).__name__}


def build() -> dict:
    return {
        "distribution": "ugence-cloud-scaling-bounded-execution",
        "namespace": "ugence_cloud_scaling_bounded_execution",
        "package_version": pkg.__version__,
        "curated_api_module": "ugence_cloud_scaling_bounded_execution",
        "note": (
            "Machine-readable snapshot of the curated public API "
            "(ugence_cloud_scaling_bounded_execution.__all__). tests/packaging/test_packaging.py "
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
