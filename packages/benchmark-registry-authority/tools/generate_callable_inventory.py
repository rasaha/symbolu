#!/usr/bin/env python3
"""Freeze every callable reachable under ``src/``, with its resolved signature.

Run:
    PYTHONPATH=packages/benchmark-registry-authority/src:\
packages/benchmark-registry/src \
        python packages/benchmark-registry-authority/tools/generate_callable_inventory.py

Why a frozen set rather than a rule
------------------------------------
Three audits found seven defects in the gates asserting BR-2B's central
boundary, and **none** in the boundary itself. Every one of them was a
*classification* defect: a substring rule an alias walked past, a ``None``
annotation that was skipped rather than failed, a PEP 563 string read as one
opaque name, an ownership test keyed on attacker-supplied ``co_filename``, a
module walk scoped to ``contracts/``, and then — in the third round — a
dunder-named lambda, a reassigned ``__module__``, a base class whose
``__module__`` was reassigned to make a method look generated, and a reserved
name bound by ``NewType`` rather than ``class``.

Each fix answered the attack in front of it and added machinery whose exemptions
became the next attack. That is what proving a **negative over an open-ended
surface** costs: the rule must anticipate every spelling, and the attacker only
needs one it did not.

This file inverts the property. There is no rule to walk past, because there is
nothing to classify: the inventory lists every callable this package reaches,
with the types its annotations resolve to, and a test asserts the live set
equals the frozen set **exactly**. A callable the inventory does not list is a
failure whether it is a lambda, a synthesized method, an ``exec``-compiled
function, or a plain ``def`` in a module nobody thought to walk. A listed
callable whose resolved signature moved is a failure too.

That is the discipline this package already uses for ``public_api.json``, the
eighteen pinned vectors and the digest domains — none of which any audit has
bypassed, because none of them decides anything. They compare.

No exemptions, and that includes the ugly ones
------------------------------------------------
Imported stdlib functions, ``@dataclass``-synthesized ``__eq__``,
``EnumType``-copied ``_generate_next_value_`` and ``typing.Protocol``'s injected
``__init__`` are all **inventory entries**, not exclusions. They make the file
larger and tie it to the interpreter version — a Python upgrade that changes
``Enum``'s methods will fail this test.

That cost is deliberate and the failure is the point: "the set of callables
reachable in this package changed" is exactly what this must notice, and a
loud, specific diff is the right way to be told. Every exclusion written to
avoid that noise is the shape of all seven previous defects.

Resolution, then rendering
---------------------------
Types are resolved by :mod:`tests._boundary` — ``typing.get_type_hints`` for
PEP 563 strings, ``typing.get_args`` walked to the leaves — and compared by
**class identity**. Only after resolution is a class rendered as
``module.qualname`` for storage. The identity work happens in the check; the
file records its result.
"""

from __future__ import annotations

import importlib
import inspect
import json
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parent.parent
SRC = PKG / "src" / "ugence_benchmark_registry_authority"
NAMESPACE = "ugence_benchmark_registry_authority"

sys.path.insert(0, str(PKG / "tests"))

from _boundary import (  # noqa: E402
    resolved_parameter_types,
    resolved_return_types,
)

#: What a parameter with no resolvable annotation records. Distinct from an
#: empty list so "unannotated" and "annotated with nothing" cannot be confused.
UNRESOLVED = "<unresolved>"


def package_modules():
    """Every module whose source lives under ``src/``, imported."""

    modules = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).with_suffix("")
        parts = [part for part in relative.parts if part != "__init__"]
        modules.append(importlib.import_module(".".join([NAMESPACE, *parts])))
    return modules


def _render(types) -> list:
    return sorted(f"{cls.__module__}.{cls.__qualname__}" for cls in types)


def _unwrap(member):
    """The underlying function of a classmethod, staticmethod or property."""

    if isinstance(member, (classmethod, staticmethod)):
        return getattr(member, "__func__", None)
    if isinstance(member, property):
        return member.fget
    return member


def _signature(func) -> dict:
    try:
        parameters = {
            name: _render(types)
            for name, types in resolved_parameter_types(func).items()
        }
    except Exception:  # pragma: no cover - recorded, never skipped
        parameters = {UNRESOLVED: []}
    try:
        returns = _render(resolved_return_types(func))
    except Exception:  # pragma: no cover - recorded, never skipped
        returns = [UNRESOLVED]
    return {"parameters": parameters, "returns": returns}


def build_inventory() -> dict:
    """``{label: signature}`` for every callable reachable under ``src/``.

    The label is built from the **module being walked** and the attribute path,
    never from the callable's own ``__module__`` or ``__qualname__``. Both are
    writable, and the third audit used exactly that: a method whose
    ``__module__`` was reassigned to ``"builtins"``. Where a thing is *bound*
    is a fact about this package; what it claims about itself is not.
    """

    entries = {}
    for module in package_modules():
        for name, value in vars(module).items():
            func = _unwrap(value)
            if inspect.isfunction(func):
                entries[f"{module.__name__}::{name}"] = _signature(func)
            elif inspect.isclass(value):
                for attribute, member in vars(value).items():
                    inner = _unwrap(member)
                    if inspect.isfunction(inner):
                        label = f"{module.__name__}::{name}.{attribute}"
                        entries[label] = _signature(inner)
    return entries


def main() -> int:
    inventory = build_inventory()
    (PKG / "public_callable_inventory.json").write_text(
        json.dumps(
            {
                "distribution": "ugence-benchmark-registry-authority",
                "namespace": NAMESPACE,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "note": (
                    "Every callable reachable under src/, with its resolved "
                    "parameter and return types. The live set must equal this "
                    "set EXACTLY: an unlisted callable is a failure, and so is "
                    "a listed one whose signature moved. No classification, no "
                    "exemption, no ownership test — imported, synthesized and "
                    "injected callables are entries, not exclusions. Ties to "
                    "the interpreter version by design; regenerate with "
                    "tools/generate_callable_inventory.py."
                ),
                "callables_inventoried": len(inventory),
                "callables": dict(sorted(inventory.items())),
            },
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
    print(f"public_callable_inventory.json  {len(inventory)} callables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
