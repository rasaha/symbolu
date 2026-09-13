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
if str(PKG / "src") not in sys.path:
    sys.path.insert(0, str(PKG / "src"))

import ugence_workflow_drafts as pkg  # noqa: E402

#: Public methods every exception inherits from ``BaseException``; excluded so the
#: manifest describes only what the class itself contributes and reproduces on every
#: supported interpreter (``add_note`` exists from 3.11 and not before).
_INHERITED_EXCEPTION_METHODS = frozenset(
    name for name, _ in inspect.getmembers(BaseException, callable)
    if not name.startswith("_")
)


def own_methods(value: type) -> list:
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
        return {"kind": "dataclass",
                "fields": [f.name for f in dataclasses.fields(value) if f.init]}
    if isinstance(value, type):
        return {"kind": "class", "methods": own_methods(value)}
    if inspect.isfunction(value):
        return {"kind": "function", "parameters": list(inspect.signature(value).parameters)}
    if isinstance(value, dict):
        return {"kind": "mapping", "keys": sorted(str(k) for k in value)}
    if isinstance(value, tuple):
        return {"kind": "tuple", "values": [str(v) for v in value]}
    if isinstance(value, (bool, str)):
        return {"kind": "constant", "value": value}
    return {"kind": type(value).__name__}


def build() -> dict:
    return {
        "distribution": "ugence-workflow-drafts",
        "namespace": "ugence_workflow_drafts",
        "package_version": pkg.__version__,
        "curated_api_module": "ugence_workflow_drafts",
        "note": (
            "Machine-readable snapshot of the curated public API "
            "(ugence_workflow_drafts.__all__). tests/packaging/test_packaging.py asserts "
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
