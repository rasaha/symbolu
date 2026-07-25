"""Canonical public-API snapshotting (Task 7).

Introspects a public API module (e.g. ``decision_governance.api``) into a
deterministic, JSON-serialisable snapshot: exported symbols and their kind,
function/method signatures, enum values, dataclass/pydantic fields (with
required/optional), protocol methods, exception base classes, and version values.
Snapshots are stable across runs (sorted keys) so their hash is reproducible.
"""
from __future__ import annotations

import enum
import inspect
from typing import Any


def _signature(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "(...)"


def _params(obj) -> list:
    """Structured parameters so compat can tell additive from breaking changes."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return []
    out = []
    for name, p in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        out.append({"name": name, "kind": p.kind.name,
                    "has_default": p.default is not inspect.Parameter.empty})
    return out


def _fn(obj) -> dict:
    return {"signature": _signature(obj), "params": _params(obj)}


def _fields(cls) -> dict:
    """Return {field_name: {'required': bool, 'annotation': str}} for a model/dataclass."""
    out: dict = {}
    # pydantic v2
    mf = getattr(cls, "model_fields", None)
    if isinstance(mf, dict) and mf:
        for name, f in mf.items():
            required = bool(getattr(f, "is_required", lambda: True)()) if hasattr(f, "is_required") \
                else getattr(f, "required", True)
            out[name] = {"required": bool(required),
                         "annotation": _ann(getattr(f, "annotation", None))}
        return out
    # dataclass
    dfields = getattr(cls, "__dataclass_fields__", None)
    if dfields:
        import dataclasses
        for name, f in dfields.items():
            has_default = (f.default is not dataclasses.MISSING
                           or f.default_factory is not dataclasses.MISSING)  # type: ignore[misc]
            out[name] = {"required": not has_default, "annotation": _ann(f.type)}
        return out
    return out


def _ann(a) -> str:
    if a is None:
        return ""
    if isinstance(a, str):
        return a
    return getattr(a, "__name__", str(a)).replace("typing.", "")


def _protocol_methods(cls) -> dict:
    methods = {}
    for name, member in inspect.getmembers(cls):
        if name.startswith("_"):
            continue
        if inspect.isfunction(member) or inspect.ismethod(member):
            methods[name] = _fn(member)
    return methods


def _describe(name: str, obj: Any) -> dict:
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return {"kind": "enum",
                    "values": {m.name: str(m.value) for m in obj}}
        if issubclass(obj, BaseException):
            return {"kind": "exception",
                    "bases": [b.__name__ for b in obj.__mro__[1:] if b is not object]}
        is_protocol = bool(getattr(obj, "_is_protocol", False))
        fields = _fields(obj)
        result: dict = {"kind": "protocol" if is_protocol else "class"}
        if is_protocol:
            result["methods"] = _protocol_methods(obj)
        if fields:
            result["fields"] = fields
        # public methods for regular classes (signatures)
        if not is_protocol:
            result["methods"] = {
                n: _fn(m) for n, m in inspect.getmembers(obj)
                if not n.startswith("_") and (inspect.isfunction(m) or inspect.ismethod(m))}
        return result
    if inspect.isfunction(obj):
        return {"kind": "function", **_fn(obj)}
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return {"kind": "constant", "value": str(obj)}
    if isinstance(obj, (frozenset, set, tuple, list)):
        return {"kind": "constant", "value": str(sorted(obj) if isinstance(obj, (set, frozenset))
                                                else list(obj))}
    return {"kind": "object", "type": type(obj).__name__}


def snapshot_module(module_name: str) -> dict:
    import importlib
    mod = importlib.import_module(module_name)
    exported = getattr(mod, "__all__", None)
    if exported is None:
        exported = [n for n in dir(mod) if not n.startswith("_")]
    symbols: dict = {}
    for name in sorted(exported):
        try:
            obj = getattr(mod, name)
        except AttributeError:
            continue
        symbols[name] = _describe(name, obj)
    return {"module": module_name, "symbols": symbols}


def snapshot_all(module_names) -> dict:
    return {m: snapshot_module(m) for m in module_names}
