#!/usr/bin/env python3
"""Regenerate ``public_api.json`` from the package's actual curated surface.

Run after any deliberate change to ``__all__``. ``tests/packaging/test_public_api.py``
asserts the file equals the live surface, and the isolated-install verifier asserts the
same for the built wheel and the installed runtime, so a drift between the three is a
failure rather than a discrepancy nobody noticed.
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
for _path in (
    PKG / "src",
    REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts" / "src",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "integration" / "cloud-scaling-risk-integration" / "src",
    REPO / "packages" / "trusted-evidence-authority" / "src",
):
    if _path.exists():
        sys.path.insert(0, str(_path))

import ugence_cloud_scaling_producer_attestation as pkg  # noqa: E402


def describe(name: str) -> dict:
    value = getattr(pkg, name)
    if isinstance(value, type) and issubclass(value, enum.Enum):
        return {"kind": "enum", "values": [member.value for member in value]}
    if dataclasses.is_dataclass(value) and isinstance(value, type):
        return {
            "kind": "dataclass",
            "fields": [f.name for f in dataclasses.fields(value)],
        }
    if isinstance(value, type):
        return {
            "kind": "class",
            "methods": sorted(
                n for n, _ in inspect.getmembers(value, callable) if not n.startswith("_")
            ),
        }
    if inspect.isfunction(value):
        return {
            "kind": "function",
            "parameters": list(inspect.signature(value).parameters),
        }
    if isinstance(value, frozenset):
        return {"kind": "frozenset", "values": sorted(str(v) for v in value)}
    if isinstance(value, str):
        return {"kind": "constant", "value": value}
    return {"kind": type(value).__name__}


def build() -> dict:
    return {
        "distribution": "ugence-cloud-scaling-producer-attestation",
        "namespace": "ugence_cloud_scaling_producer_attestation",
        "package_version": pkg.__version__,
        "curated_api_module": "ugence_cloud_scaling_producer_attestation",
        "note": (
            "Machine-readable snapshot of the curated public API "
            "(ugence_cloud_scaling_producer_attestation.__all__). "
            "tests/packaging/test_public_api.py asserts this file equals the live package "
            "surface; scripts/verify_isolated_install.py asserts the same for the built "
            "wheel and for a genuinely offline isolated install. Regenerate with "
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
