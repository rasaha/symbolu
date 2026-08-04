#!/usr/bin/env python3
"""Generate build_provenance.json for ugence-cloud-scaling-operations, bound to the
ACTUAL build revision (GITHUB_SHA or ``git rev-parse HEAD``)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys

VERIFIER_VERSION = "0.1.0"
PKG = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = PKG / "module_manifest.json"


def _sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(*a, default=""):
    try:
        return subprocess.check_output(["git", "-C", str(PKG), *a],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return default


def _dirty() -> bool:
    s = _git("status", "--porcelain", default="__err__")
    return s == "__err__" or bool(s.strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--sdist", required=True)
    ap.add_argument("--sbom", default=None)
    ap.add_argument("--authority-inventory", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timestamp", default=None)
    a = ap.parse_args(argv)

    manifest = json.loads(MANIFEST.read_text())
    ts = a.timestamp
    if ts is None:
        import datetime
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    prov = {
        "repository": _git("config", "--get", "remote.origin.url",
                           default=os.environ.get("GITHUB_REPOSITORY", "")),
        "branch": os.environ.get("GITHUB_REF_NAME") or _git("rev-parse", "--abbrev-ref", "HEAD"),
        "source_commit": os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD"),
        "build_revision_source": "GITHUB_SHA" if os.environ.get("GITHUB_SHA") else "git rev-parse HEAD",
        "package_version": manifest.get("version"),
        "advisory_dependency_version": manifest.get("advisory_dependency_range"),
        "wheel": {"name": pathlib.Path(a.wheel).name, "sha256": _sha256(pathlib.Path(a.wheel))},
        "sdist": {"name": pathlib.Path(a.sdist).name, "sha256": _sha256(pathlib.Path(a.sdist))},
        "manifest_sha256": _sha256(MANIFEST),
        "sbom_sha256": (_sha256(pathlib.Path(a.sbom)) if a.sbom and pathlib.Path(a.sbom).exists() else None),
        "authority_inventory_sha256": (_sha256(pathlib.Path(a.authority_inventory))
                                       if a.authority_inventory and pathlib.Path(a.authority_inventory).exists() else None),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "ci_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "dirty_tree": _dirty(),
        "verifier_version": VERIFIER_VERSION,
        "build_timestamp": ts,
        "evidence_class": "CI_GENERATED_BUILD_EVIDENCE",
    }
    pathlib.Path(a.out).write_text(json.dumps(prov, indent=2, sort_keys=True))
    print(json.dumps(prov, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
