#!/usr/bin/env python3
"""Generate a minimal CycloneDX-style SBOM for the built wheel.

The core distribution declares NO runtime dependencies (Python standard library only),
so the SBOM's component list is the distribution itself plus its declared (empty) runtime
requirements. Emitting it explicitly documents that no third-party runtime component —
and in particular no provider SDK — is part of the distributed closure.

Usage: generate_sbom.py --wheel <path> --out <path>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import zipfile

PKG = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = PKG / "module_manifest.json"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wheel_requires(wheel: pathlib.Path):
    """Read Requires-Dist lines from the wheel METADATA (runtime deps, excl. extras)."""
    runtime, extras = [], []
    with zipfile.ZipFile(wheel) as z:
        meta_names = [n for n in z.namelist() if n.endswith(".dist-info/METADATA")]
        if not meta_names:
            return runtime, extras
        text = z.read(meta_names[0]).decode("utf-8", "ignore")
    for line in text.splitlines():
        if line.startswith("Requires-Dist:"):
            req = line.split(":", 1)[1].strip()
            (extras if "extra ==" in req else runtime).append(req)
    return runtime, extras


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    wheel = pathlib.Path(args.wheel)
    manifest = json.loads(MANIFEST.read_text())
    runtime, extras = _wheel_requires(wheel)

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "library",
                "name": manifest["distribution_name"],
                "version": manifest["version"],
                "purl": f"pkg:pypi/{manifest['distribution_name']}@{manifest['version']}",
                "properties": [
                    {"name": "authority_class", "value": manifest["authority_class"]},
                    {"name": "execution_capability", "value": manifest["execution_capability"]},
                    {"name": "provider_invocation_capability",
                     "value": manifest["provider_invocation_capability"]},
                    {"name": "credential_access", "value": manifest["credential_access"]},
                ],
            },
        },
        "components": [
            {"type": "library", "name": r, "scope": "optional"} for r in extras
        ],
        "runtime_dependencies": runtime,
        "runtime_dependency_count": len(runtime),
        "wheel": {"name": wheel.name, "sha256": _sha256(wheel)},
        "notes": [
            "Core distribution has zero third-party runtime dependencies (stdlib only).",
            "No provider SDK (openai/anthropic/boto3/google-cloud/...) is present in any "
            "runtime or optional component.",
        ],
        "evidence_class": "CI_GENERATED_BUILD_EVIDENCE",
    }
    pathlib.Path(args.out).write_text(json.dumps(sbom, indent=2, sort_keys=True))
    print(json.dumps(sbom, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
