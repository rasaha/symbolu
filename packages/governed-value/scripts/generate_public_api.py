#!/usr/bin/env python3
"""Regenerate ``public_api.json`` from the package's actual curated surface.

Run after any deliberate change to ``governed_value.api.__all__``;
``tests/packaging/test_public_api.py`` asserts the file equals the live surface.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import json
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = PKG.parent
for _path in (PKG / "src", PACKAGES / "governance-contracts" / "src"):
    if _path.exists() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import governed_value as gv  # noqa: E402
from governed_value import api  # noqa: E402


#: Public methods every exception inherits from ``BaseException``. They are not this
#: package's API and are not stable across interpreters — ``add_note`` exists from
#: 3.11 and not before — so recording them would make the committed artifact a
#: statement about the interpreter that generated it. Derived rather than
#: hard-coded, so a method a future interpreter adds is excluded on both sides.
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
    value = getattr(api, name)
    if isinstance(value, type) and issubclass(value, enum.Enum):
        return {"kind": "enum", "values": [member.value for member in value]}
    if isinstance(value, type) and dataclasses.is_dataclass(value):
        return {"kind": "dataclass", "fields": [f.name for f in dataclasses.fields(value)]}
    if isinstance(value, type) and issubclass(value, Exception):
        return {"kind": "exception", "methods": own_methods(value)}
    if isinstance(value, type):
        return {"kind": "class", "methods": own_methods(value)}
    if inspect.isfunction(value):
        return {"kind": "function", "parameters": list(inspect.signature(value).parameters)}
    if isinstance(value, str):
        return {"kind": "constant", "value": value}
    return {"kind": type(value).__name__}


NOTE = (
    "Machine-readable snapshot of the curated public API "
    "(governed_value.api.__all__). tests/packaging/test_public_api.py asserts this "
    "file equals the live package surface; regenerate with "
    "scripts/generate_public_api.py when the curated API changes deliberately. "
    "This surface is the POST_DEPLOYMENT_VALUE reported-value calculation only. "
    "It operates on caller-reported, unverified inputs: every result is "
    "EvidenceStatus.REPORTED and AuthorityStatus.UNVERIFIED, and no symbol here "
    "can lift either axis. MetricObservation is NOT exported — it is owned by "
    "ugence-governance-contracts and consumed through admit_observations; what "
    "this package owns is ObservedMetric, the record of what was admitted, "
    "carried outside every monetary term and outside the scorability verdict."
)


def build() -> dict:
    return {
        "distribution": "ugence-governed-value",
        "namespace": "governed_value",
        "package_version": gv.__version__,
        "curated_api_module": "governed_value.api",
        "note": NOTE,
        "symbols": {
            name: describe(name) for name in sorted(api.__all__) if name != "__version__"
        },
    }


def main() -> int:
    target = PKG / "public_api.json"
    target.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target} ({len(build()['symbols'])} symbols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
