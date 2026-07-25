"""Platform freeze manifest — build, persist, verify (Task 5).

Reproducibly generates the machine-readable freeze manifest with complete hashes
of public API snapshots, package trees, conformance suites, dependency rules, and
the invariant register, and verifies the current repository against it.
"""
from __future__ import annotations

import json
import pathlib

from . import version as V
from .api_snapshot import snapshot_all
from .compat import classify, compare_snapshots
from .dependencies import FORBIDDEN_IMPORTS
from .hashing import canonical_hash, conformance_hash, tree_hash
from .invariants import REGISTER

REPO = pathlib.Path(__file__).resolve().parents[1]
PLATFORM_DIR = REPO / "platform"
MANIFEST_PATH = PLATFORM_DIR / "PLATFORM_FREEZE_V1.json"
API_SNAPSHOT_DIR = PLATFORM_DIR / "api-snapshots"

_PROVIDERS_WITH_CONFORMANCE = ("actiongate_provider", "tap_provider")


def _dependency_rules() -> dict:
    return {pkg: sorted(forbidden) for pkg, forbidden in FORBIDDEN_IMPORTS.items()}


def _compatibility_rules() -> dict:
    return {
        "PATCH": "correctness/security/docs/tests/packaging/perf; no API or semantic change",
        "MINOR": "additive optional fields, additive public APIs, new capabilities, "
                 "new conformance assertions, backward-compatible observability",
        "MAJOR": "breaking API, provider-contract redesign, authority/lifecycle/dependency-"
                 "direction/fail-safe changes, new provider families, execution-boundary changes",
        "APPLICATION_LOCAL": "AI Hiring workflows/ontology/evidence/policies/composition/UI/APIs",
    }


def build_manifest() -> dict:
    snapshots = snapshot_all(V.PUBLIC_API_MODULES)
    api_hashes = {m: canonical_hash(snapshots[m]) for m in V.PUBLIC_API_MODULES}
    tree_hashes = {t: tree_hash(t) for t in V.CORE_TREES}
    behaviour_hashes = {t: tree_hash(t) for t in V.BEHAVIOUR_TREES}
    conformance_hashes = {p: conformance_hash(p) for p in _PROVIDERS_WITH_CONFORMANCE}
    invariants = [{"id": i.id, "statement": i.statement,
                   "authoritative_test": i.authoritative_test} for i in REGISTER]

    manifest = {
        "platform_name": "Decision Governance Platform",
        "platform_version": V.PLATFORM_VERSION,
        "freeze_commit": V.FREEZE_COMMIT,
        "baseline_tests": V.BASELINE_TESTS,
        "components": dict(V.COMPONENT_VERSIONS),
        "core_trees": list(V.CORE_TREES),
        "behaviour_trees": list(V.BEHAVIOUR_TREES),
        "frozen_invariants": invariants,
        "public_api_manifests": api_hashes,
        "core_tree_hashes": tree_hashes,
        "behaviour_tree_hashes": behaviour_hashes,
        "conformance_hashes": conformance_hashes,
        "dependency_rules": _dependency_rules(),
        "compatibility_rules": _compatibility_rules(),
        "approved_change_classes": ["PATCH", "MINOR", "MAJOR", "APPLICATION_LOCAL"],
    }
    manifest["manifest_digest"] = canonical_hash(
        {k: v for k, v in manifest.items() if k != "manifest_digest"})
    return manifest


def write_manifest() -> dict:
    PLATFORM_DIR.mkdir(exist_ok=True)
    API_SNAPSHOT_DIR.mkdir(exist_ok=True)
    snapshots = snapshot_all(V.PUBLIC_API_MODULES)
    for module, snap in snapshots.items():
        (API_SNAPSHOT_DIR / f"{module}.json").write_text(
            json.dumps(snap, indent=2, sort_keys=True) + "\n")
    manifest = build_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_manifest(path=MANIFEST_PATH) -> dict:
    return json.loads(pathlib.Path(path).read_text())


def load_stored_snapshots() -> dict:
    out = {}
    for module in V.PUBLIC_API_MODULES:
        p = API_SNAPSHOT_DIR / f"{module}.json"
        if p.exists():
            out[module] = json.loads(p.read_text())
    return out


def verify_manifest(manifest: dict) -> dict:
    """Compare the current repo state against a stored manifest; report deltas."""
    current = build_manifest()
    checks = {}

    def cmp(key):
        return {"ok": manifest.get(key) == current.get(key),
                "expected": manifest.get(key), "actual": current.get(key)}

    checks["components"] = cmp("components")
    checks["core_tree_hashes"] = cmp("core_tree_hashes")
    checks["conformance_hashes"] = cmp("conformance_hashes")
    checks["public_api_manifests"] = cmp("public_api_manifests")
    checks["dependency_rules"] = cmp("dependency_rules")

    # API compatibility vs stored snapshots (breaking changes fail)
    stored = load_stored_snapshots()
    diffs = compare_snapshots(stored, snapshot_all(V.PUBLIC_API_MODULES)) if stored else []
    checks["api_compatibility"] = {
        "ok": not any(d.severity == "BREAKING" for d in diffs),
        "classification": classify(diffs),
        "diffs": [d.__dict__ for d in diffs]}

    passed = all(c["ok"] for c in checks.values())
    return {"passed": passed, "checks": checks,
            "manifest_digest_match": manifest.get("manifest_digest") == current.get("manifest_digest")}
