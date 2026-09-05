#!/usr/bin/env python3
"""Regenerate ``public_api.json`` from the package's actual curated surface.

Run after any deliberate change to ``__all__``; ``tests/packaging/test_packaging.py``
asserts the file equals the live surface.
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
for _path in (PKG / "src",):  # the package imports nothing else
    if _path.exists() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import ugence_control_plane_root as pkg  # noqa: E402


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
    if isinstance(value, dict):
        return {"kind": "mapping", "keys": sorted(str(k) for k in value)}
    if isinstance(value, tuple):
        return {"kind": "tuple", "values": [str(v) for v in value]}
    if isinstance(value, bool):
        return {"kind": "constant", "value": value}
    if isinstance(value, str):
        return {"kind": "constant", "value": value}
    return {"kind": type(value).__name__}


def build() -> dict:
    return {
        "distribution": "ugence-control-plane-root",
        "namespace": "ugence_control_plane_root",
        "package_version": pkg.__version__,
        "curated_api_module": "ugence_control_plane_root",
        "note": (
            "Machine-readable snapshot of the curated public API "
            "(ugence_control_plane_root.__all__). tests/packaging/test_packaging.py asserts "
            "this file equals the live package surface. Regenerate with "
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
