#!/usr/bin/env python3
"""Generate build_provenance.json binding the built artifacts to the ACTUAL build
revision (never a static self-referential SHA).

Build revision source, in order: ``GITHUB_SHA`` env, else ``git rev-parse HEAD``.
Baseline commit is a stable reference read from module_manifest.json
(``source_baseline_commit``) — it is the pre-packaging frozen-baseline commit and
MUST differ from the build revision.

Usage:
    generate_build_provenance.py --wheel <path> --sdist <path> --out <path> \
        [--timestamp <iso8601>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys

VERIFIER_VERSION = "0.1.1"
PKG = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = PKG / "module_manifest.json"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args, default=""):
    try:
        return subprocess.check_output(["git", "-C", str(PKG), *args],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return default


def build_revision() -> str:
    return os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD")


def dirty_tree() -> bool:
    status = _git("status", "--porcelain", default="__error__")
    if status == "__error__":
        return True  # cannot determine -> treat as dirty (fail closed)
    return bool(status.strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--sdist", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timestamp", default=None,
                    help="ISO-8601 build timestamp (else UTC now; pass in for determinism)")
    args = ap.parse_args(argv)

    manifest = json.loads(MANIFEST.read_text())
    baseline = manifest.get("source_baseline_commit", "")
    version = manifest.get("version", "")

    ts = args.timestamp
    if ts is None:
        import datetime
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    prov = {
        "repository": _git("config", "--get", "remote.origin.url",
                           default=os.environ.get("GITHUB_REPOSITORY", "")),
        "branch": os.environ.get("GITHUB_REF_NAME") or _git("rev-parse", "--abbrev-ref", "HEAD"),
        "build_commit": build_revision(),
        "build_revision_source": "GITHUB_SHA" if os.environ.get("GITHUB_SHA") else "git rev-parse HEAD",
        "baseline_commit": baseline,
        "package_version": version,
        "wheel": {"name": pathlib.Path(args.wheel).name, "sha256": _sha256(pathlib.Path(args.wheel))},
        "sdist": {"name": pathlib.Path(args.sdist).name, "sha256": _sha256(pathlib.Path(args.sdist))},
        "module_manifest_sha256": _sha256(MANIFEST),
        "build_timestamp": ts,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "ci_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "dirty_tree": dirty_tree(),
        "verifier_version": VERIFIER_VERSION,
        "evidence_class": "CI_GENERATED_BUILD_EVIDENCE",
    }
    pathlib.Path(args.out).write_text(json.dumps(prov, indent=2, sort_keys=True))
    print(json.dumps(prov, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
