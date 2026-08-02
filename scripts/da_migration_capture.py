#!/usr/bin/env python3
"""Decision Authority migration — namespace-parameterized equivalence fingerprint.

Runs against a governance-kernel namespace (``decision_governance`` before the
move, ``ugence_decision_authority`` after) and emits a deterministic JSON
fingerprint of:

  * version + public-API surface (top-level and ``.api`` ``__all__``);
  * every pydantic model reachable in the namespace — qualified name, ordered
    field names, required/optional, defaults, and a hash of ``model_json_schema``
    (captures serialization shape, field order, types, defaults, constraints);
  * every Enum — members and values.

Diffing two runs (before vs after) proves zero semantic change to the public
surface, serialization shapes, and enum values without instantiating records.

Usage:  python scripts/da_migration_capture.py <namespace> [out.json]
"""
from __future__ import annotations

import enum
import hashlib
import importlib
import inspect
import json
import pkgutil
import sys


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _iter_classes(ns_name: str):
    ns = importlib.import_module(ns_name)
    seen = set()
    for _f, modname, _p in pkgutil.walk_packages(ns.__path__, ns.__name__ + "."):
        if ".tests" in modname or modname.endswith(".tests"):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for name, obj in vars(mod).items():
            if not inspect.isclass(obj):
                continue
            if getattr(obj, "__module__", "") != modname:
                continue  # only classes defined in this namespace module
            key = obj.__module__ + "." + obj.__qualname__
            if key in seen:
                continue
            seen.add(key)
            yield modname, name, obj


def _rel(qual: str, ns_name: str) -> str:
    # Normalize the namespace prefix so before/after are comparable.
    return qual.replace(ns_name, "<ns>", 1)


def capture(ns_name: str) -> dict:
    ns = importlib.import_module(ns_name)
    api = importlib.import_module(ns_name + ".api")

    out: dict = {"namespace": ns_name, "version": ns.__version__}
    out["top_all"] = sorted(getattr(ns, "__all__", []))
    out["api_all"] = sorted(getattr(api, "__all__", []))
    out["api_manifest"] = {
        "module": "<ns>.api",
        "symbols": sorted(
            [{"name": n, "kind": type(getattr(api, n)).__name__}
             for n in getattr(api, "__all__", [])],
            key=lambda d: d["name"],
        ),
    }
    out["api_manifest_sha256"] = _sha(out["api_manifest"])

    # Pydantic 2 BaseModel detection without importing pydantic by name.
    models: dict = {}
    enums: dict = {}
    for modname, name, obj in _iter_classes(ns_name):
        rmod = _rel(modname, ns_name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            enums[_rel(obj.__module__ + "." + obj.__qualname__, ns_name)] = {
                m.name: (m.value if not isinstance(m.value, enum.Enum) else m.value.name)
                for m in obj
            }
            continue
        if hasattr(obj, "model_fields") and hasattr(obj, "model_json_schema"):
            try:
                schema = obj.model_json_schema()
            except Exception as e:
                schema = {"_schema_error": repr(e)}
            fields = {}
            for fname, finfo in obj.model_fields.items():
                fields[fname] = {
                    "required": bool(getattr(finfo, "is_required", lambda: False)()),
                    # Normalize the namespace out of repr/annotation strings so the
                    # fingerprint is comparable across the package rename (these
                    # strings embed the defining module path).
                    "default": _rel(repr(getattr(finfo, "default", None)), ns_name),
                    "annotation": _rel(str(getattr(finfo, "annotation", "")), ns_name),
                }
            models[_rel(obj.__module__ + "." + obj.__qualname__, ns_name)] = {
                "fields": fields,
                "field_order": list(obj.model_fields.keys()),
                "schema_sha256": _sha(schema),
            }
    out["models"] = models
    out["models_count"] = len(models)
    out["enums"] = enums
    out["enums_count"] = len(enums)
    out["models_digest"] = _sha(models)
    out["enums_digest"] = _sha(enums)
    return out


def main() -> int:
    ns_name = sys.argv[1] if len(sys.argv) > 1 else "decision_governance"
    data = capture(ns_name)
    text = json.dumps(data, indent=2, sort_keys=True)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as f:
            f.write(text + "\n")
        print(f"wrote {sys.argv[2]}")
    print(f"ns={ns_name} version={data['version']} "
          f"api_sha={data['api_manifest_sha256'][:16]} "
          f"models={data['models_count']} models_digest={data['models_digest'][:16]} "
          f"enums={data['enums_count']} enums_digest={data['enums_digest'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
