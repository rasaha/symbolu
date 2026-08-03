"""Three-way bundled-fixture drift protection (P3B packaging protection P2).

Proves, for every bundled fixture:

    canonical source hash  ==  backend-packaged hash  ==  recorded manifest hash

covering all bundled scenario manifests, workflows, registries, policies,
expected outputs, replay records and v2 conformance artifacts.

    python scripts/verify_fixture_bundle.py            # verify (fails on drift)
    python scripts/verify_fixture_bundle.py --write     # (re)generate the recorded manifest

Sources:
  * demo_data/**        <- apps/ugence-governance-studio/demo_data
  * expected_outputs/** <- apps/ugence-governance-studio/expected_outputs
  * conformance_v2/**   <- packages/capabilities/agent-workforce-composer/conformance/governance_studio_v2

Recorded manifests tied into the check:
  * BUNDLED_FIXTURE_MANIFEST.json  (this script's committed record; every file)
  * expected_outputs/MANIFEST.json (canonical P3A record; demo_data + expected_outputs)
  * conformance_v2/EQUIVALENCE_MANIFEST.json (AWC v1_input_digests; where present)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
_APP = os.path.dirname(_BACKEND)
_REPO = os.path.dirname(os.path.dirname(_APP))

_DATA = os.path.join(_BACKEND, "src", "ugence_governance_studio_api", "data")
_MANIFEST_NAME = "BUNDLED_FIXTURE_MANIFEST.json"
_MANIFEST_PATH = os.path.join(_DATA, _MANIFEST_NAME)

_CONFORMANCE_SRC = os.path.join(
    _REPO, "packages", "capabilities", "agent-workforce-composer",
    "conformance", "governance_studio_v2")

_CATEGORIES = ("scenario manifests", "workflows", "registries", "policies",
               "expected outputs", "replay records", "v2 conformance artifacts")


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _collect_bundled() -> dict:
    """rel-path -> sha256 for every bundled .json fixture (excludes the manifest)."""
    out = {}
    for dirpath, _dirs, files in os.walk(_DATA):
        for fname in sorted(files):
            if fname == _MANIFEST_NAME or not fname.endswith(".json"):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, _DATA).replace(os.sep, "/")
            out[rel] = _sha256(full)
    return dict(sorted(out.items()))


def _source_path(rel: str) -> str:
    if rel.startswith("conformance_v2/"):
        return os.path.join(_CONFORMANCE_SRC, rel[len("conformance_v2/"):])
    # demo_data/** and expected_outputs/** live under the P3A app root
    return os.path.join(_APP, rel)


def _p3a_recorded() -> dict:
    manifest = os.path.join(_APP, "expected_outputs", "MANIFEST.json")
    with open(manifest, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    recorded = {}
    recorded.update(data.get("inputs", {}))    # demo_data/...
    recorded.update(data.get("outputs", {}))   # expected_outputs/...
    return recorded


def _v2_recorded() -> dict:
    """AWC EQUIVALENCE_MANIFEST v1_input_digests -> {conformance_v2/<sid>/<f>: hash}."""
    path = os.path.join(_CONFORMANCE_SRC, "EQUIVALENCE_MANIFEST.json")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    recorded = {}
    for sid, entry in data.get("scenarios", {}).items():
        for fname, digest in entry.get("v1_input_digests", {}).items():
            recorded[f"conformance_v2/{sid}/{fname}"] = digest
    return recorded


def _canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _build_manifest(bundled: dict) -> dict:
    digest = hashlib.sha256(json.dumps(bundled, sort_keys=True).encode()).hexdigest()
    return {
        "schema": "governance_studio.bundled_fixture_manifest.v1",
        "covers": list(_CATEGORIES),
        "count": len(bundled),
        "files": bundled,
        "manifest_digest": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="three-way bundled-fixture drift check")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    bundled = _collect_bundled()
    problems: list[str] = []

    # leg 1: packaged == canonical source
    for rel, packaged_hash in bundled.items():
        src = _source_path(rel)
        if not os.path.isfile(src):
            problems.append(f"source missing for bundled {rel} ({src})")
            continue
        if _sha256(src) != packaged_hash:
            problems.append(f"source != packaged: {rel}")

    if args.write:
        if problems:
            print("REFUSING TO WRITE — source/packaged drift:", file=sys.stderr)
            print("\n".join(problems), file=sys.stderr)
            return 1
        with open(_MANIFEST_PATH, "wb") as fh:
            fh.write(_canonical(_build_manifest(bundled)))
        print(f"wrote {_MANIFEST_PATH} ({len(bundled)} files)")
        return 0

    # leg 2: packaged == recorded (this script's committed manifest)
    if not os.path.isfile(_MANIFEST_PATH):
        print(f"FIXTURE DRIFT: missing {_MANIFEST_PATH}", file=sys.stderr)
        return 1
    with open(_MANIFEST_PATH, "rb") as fh:
        committed = fh.read()
    if committed != _canonical(_build_manifest(bundled)):
        problems.append("BUNDLED_FIXTURE_MANIFEST.json out of date (packaged != recorded)")

    # leg 3: packaged == canonical P3A recorded manifest (demo_data + expected_outputs)
    p3a = _p3a_recorded()
    covered_by_p3a = 0
    for rel, packaged_hash in bundled.items():
        if rel in p3a:
            covered_by_p3a += 1
            if p3a[rel] != packaged_hash:
                problems.append(f"P3A-manifest != packaged: {rel}")

    # leg 4: packaged == AWC v2 recorded digests (where the equivalence manifest records them)
    v2 = _v2_recorded()
    covered_by_v2 = 0
    for rel, digest in v2.items():
        if rel in bundled:
            covered_by_v2 += 1
            if bundled[rel] != digest:
                problems.append(f"v2 equivalence-manifest != packaged: {rel}")

    if problems:
        print("FIXTURE DRIFT DETECTED:", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        return 1

    print(f"fixture bundle in sync: {len(bundled)} files "
          f"(P3A-manifest-tied {covered_by_p3a}, v2-digest-tied {covered_by_v2}); "
          f"three-way source==packaged==recorded OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
