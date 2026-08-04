#!/usr/bin/env python3
"""Minimal CycloneDX-style SBOM for the operations distribution (declared deps).

Not a substitute for a full dependency-tree SBOM; it records the distribution and its
declared core + optional dependencies from the manifest for supply-chain evidence.
"""

from __future__ import annotations

import argparse
import json
import pathlib

PKG = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = PKG / "module_manifest.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    m = json.loads(MANIFEST.read_text())
    components = []
    for dep in m.get("core_dependencies", []):
        components.append({"type": "library", "name": dep, "scope": "required"})
    for extra, deps in m.get("optional_dependencies", {}).items():
        for dep in deps:
            components.append({"type": "library", "name": dep, "scope": "optional",
                               "extra": extra})
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "metadata": {"component": {
            "type": "library",
            "name": m["distribution_name"],
            "version": m["version"],
        }},
        "components": components,
    }
    pathlib.Path(a.out).write_text(json.dumps(sbom, indent=2, sort_keys=True))
    print(f"wrote SBOM with {len(components)} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
