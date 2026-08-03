#!/usr/bin/env python3
"""Deterministic public-API snapshot for the TAP provider (any namespace).

Snapshots the TAP public surface through a chosen import namespace
(``tap_provider`` or ``ugence_tap_provider``) so the pre-migration API baseline can
be compared against the post-migration canonical and legacy surfaces. Reuses the
platform-freeze introspection (which deliberately records symbol names, kinds,
signatures, enum values, dataclass fields, and exception bases — but NOT
``__module__``) so a facade that re-exports identical objects snapshots identically.

    python scripts/tap_api_snapshot.py <namespace> <output.json>

Also records the ``__all__`` of each deep-import submodule and the resolvable deep
import paths, so relocation of the implementation cannot silently drop a path.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from platform_freeze.api_snapshot import snapshot_module  # noqa: E402

# Deep-import submodules external consumers rely on.
DEEP_MODULES = (
    "api", "core", "client", "configuration", "conformance", "errors",
    "health", "mapping", "mapping.controls", "mapping.request", "mapping.result",
    "observability", "provider", "version",
)


def snapshot(ns: str) -> dict:
    top = importlib.import_module(ns)
    api_snap = snapshot_module(ns + ".api")
    # Normalise the recorded module name so the snapshot is namespace-independent
    # (the whole point: the facade must snapshot identically to canonical).
    api_snap["module"] = "<tap>.api"

    deep = {}
    for sub in DEEP_MODULES:
        name = ns + "." + sub
        try:
            mod = importlib.import_module(name)
            deep[sub] = {
                "importable": True,
                "all": sorted(getattr(mod, "__all__", []) or []),
            }
        except Exception as exc:  # noqa: BLE001
            deep[sub] = {"importable": False, "error": type(exc).__name__}

    return {
        "top_level_all": sorted(getattr(top, "__all__", []) or []),
        "top_level_version": getattr(top, "__version__", None),
        "api": api_snap,
        "deep_modules": deep,
    }


def main(argv: list[str]) -> int:
    ns = argv[1] if len(argv) > 1 else "tap_provider"
    default_out = (pathlib.Path("docs/audits/tap_packaging/artifacts")
                   / f"tap_public_api_{ns}.json")
    out_path = pathlib.Path(argv[2]) if len(argv) > 2 else default_out
    data = snapshot(ns)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    export_count = len(data["api"]["symbols"])
    print(f"snapshot {ns} -> {out_path}")
    print(f"api_export_count: {export_count}")
    print(f"snapshot_sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
