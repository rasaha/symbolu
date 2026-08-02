#!/usr/bin/env python3
"""Public-API snapshot for the Model Selection consumer surface.

Introspects the ``execution_gate`` product-core submodules — the surface established
consumers import — and records, per module, every public symbol with its kind and (for
callables/classes) signature or field layout. Runs in both the pre-migration tree (real
modules) and the post-migration tree (compatibility surface over the canonical package);
a byte-identical result is the PATCH-equivalence proof for established consumers.

Usage:  python scripts/model_selection_api_snapshot.py <out.json>
"""
from __future__ import annotations

import dataclasses
import enum
import inspect
import json
import sys

MODULES = ("execution_gate.reason_codes", "execution_gate.states", "execution_gate.model",
           "execution_gate.gate", "execution_gate.policy", "execution_gate.registry")


def _describe(obj):
    if isinstance(obj, type) and issubclass(obj, enum.Enum):
        return {"kind": "enum", "members": {m.name: m.value for m in obj}}
    if dataclasses.is_dataclass(obj):
        fields = {}
        for f in dataclasses.fields(obj):
            default = "<required>"
            if f.default is not dataclasses.MISSING:
                default = repr(f.default)
            elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                default = f"factory:{getattr(f.default_factory, '__name__', 'lambda')}"
            fields[f.name] = {"type": str(f.type), "default": default}
        return {"kind": "dataclass", "fields": fields}
    if isinstance(obj, type):
        methods = {}
        for n, m in inspect.getmembers(obj, predicate=inspect.isfunction):
            if not n.startswith("_") or n in ("__init__",):
                try:
                    methods[n] = str(inspect.signature(m))
                except (ValueError, TypeError):
                    methods[n] = "<no-signature>"
        return {"kind": "class", "methods": methods}
    if inspect.isfunction(obj):
        try:
            return {"kind": "function", "signature": str(inspect.signature(obj))}
        except (ValueError, TypeError):
            return {"kind": "function", "signature": "<no-signature>"}
    return {"kind": type(obj).__name__, "repr": repr(obj)}


def main() -> int:
    out_path = sys.argv[1]
    snap = {}
    import importlib
    for modname in MODULES:
        mod = importlib.import_module(modname)
        exported = getattr(mod, "__all__", None)
        names = exported if exported else [n for n in dir(mod) if not n.startswith("_")]
        # Only Model-Selection-owned symbols: drop stdlib helpers re-exported into the
        # namespace (dataclasses.field/dataclass, typing, enum, …), whose reprs are
        # process-dependent and are not part of the capability's public API.
        _STDLIB = {"dataclasses", "typing", "typing_extensions", "enum", "builtins",
                   "abc", "collections", "collections.abc", "functools"}
        entry = {}
        for n in sorted(names):
            obj = getattr(mod, n, None)
            if obj is None or inspect.ismodule(obj):
                continue
            if getattr(obj, "__module__", None) in _STDLIB:
                continue
            entry[n] = _describe(obj)
        snap[modname] = entry
    blob = json.dumps(snap, sort_keys=True, indent=2, default=str)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(blob)
    import hashlib
    print(f"wrote {out_path}: {sum(len(v) for v in snap.values())} symbols; "
          f"sha256 {hashlib.sha256(blob.encode()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
