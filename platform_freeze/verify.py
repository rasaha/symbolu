"""Deterministic freeze-verification command (Task 10).

    python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json

Verifies component versions, public API snapshots, tree hashes, dependency
direction, package ownership, conformance suites, frozen invariants, packaging
integrity, benchmark artifact identity, and documentation presence. Writes the
report set under build/platform-freeze/ and prints a stable substantive digest.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import version as V
from .dependencies import dependency_report
from .hashing import REPO, canonical_hash
from .invariants import invariants_ok, verify_invariants
from .manifest import MANIFEST_PATH, build_manifest, load_manifest, verify_manifest

_PLATFORM_DOCS = ("PLATFORM_OVERVIEW.md", "ARCHITECTURE_INVARIANTS.md", "PUBLIC_API_POLICY.md",
                  "VERSIONING_POLICY.md", "COMPATIBILITY_POLICY.md", "PROVIDER_DEVELOPMENT_GUIDE.md",
                  "MAINTENANCE_POLICY.md", "SECURITY_BOUNDARIES.md", "MIGRATION_POLICY.md",
                  "AI_HIRING_INTEGRATION_GUIDE.md")
_HIRING_DOCS = ("AI_HIRING_REENTRY_BASELINE.md", "PLATFORM_BOUNDARY.md",
                "AI_HIRING_COMPLETION_ROADMAP.md")


def _packaging_integrity() -> dict:
    """Symlinked distributions resolve to the canonical source; no drift."""
    pkgs = {
        "dgm-actiongate-provider": "actiongate_provider",
        "dgm-tap-provider": "tap_provider",
        "dgm-provider-framework": "governance_providers",
        "decision-governance": "decision_governance",
    }
    problems = []
    for dist, pkg in pkgs.items():
        link = REPO / "packaging" / dist / pkg
        if not link.exists():
            problems.append(f"{dist}: missing {pkg}")
        elif link.is_symlink() and link.resolve() != (REPO / pkg).resolve():
            problems.append(f"{dist}: symlink drift -> {link.resolve()}")
    return {"passed": not problems, "problems": problems}


def _benchmark_identity() -> dict:
    from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
    ds = load_frozen_dataset()
    ok = ds.content_hash.startswith("4d6de429") and len(ds.scenarios) == 90
    return {"passed": ok, "dataset_version": ds.version, "hash": ds.content_hash[:16],
            "scenarios": len(ds.scenarios)}


def _docs_presence() -> dict:
    # Documentation locations after the repository restructuring moved these
    # governance docs under Project_documentation/. Paths are repo-root-relative.
    _PLATFORM_DOCS_DIR = pathlib.Path("Project_documentation") / "repository" / "docs" / "platform-v1"
    _HIRING_DOCS_DIR = pathlib.Path("Project_documentation") / "ai_hiring" / "docs" / "ai-hiring"
    _CHANGELOG_PLATFORM_V1 = (
        pathlib.Path("Project_documentation") / "governance" / "decision_platform" / "CHANGELOG_PLATFORM_V1.md"
    )
    missing = []
    for d in _PLATFORM_DOCS:
        rel = _PLATFORM_DOCS_DIR / d
        if not (REPO / rel).exists():
            missing.append(str(rel))
    for d in _HIRING_DOCS:
        rel = _HIRING_DOCS_DIR / d
        if not (REPO / rel).exists():
            missing.append(str(rel))
    for extra in (_CHANGELOG_PLATFORM_V1,):
        if not (REPO / extra).exists():
            missing.append(str(extra))
    return {"passed": not missing, "missing": missing}


def run_verification(manifest_path=MANIFEST_PATH) -> dict:
    manifest = load_manifest(manifest_path)
    manifest_check = verify_manifest(manifest)
    dep = dependency_report()
    invariants = verify_invariants()
    packaging = _packaging_integrity()
    benchmark = _benchmark_identity()
    docs = _docs_presence()

    checks = {
        "component_versions": {"passed": manifest["components"] == V.COMPONENT_VERSIONS},
        "public_api_snapshots": manifest_check["checks"]["public_api_manifests"],
        "api_compatibility": manifest_check["checks"]["api_compatibility"],
        "core_tree_hashes": manifest_check["checks"]["core_tree_hashes"],
        "conformance_hashes": manifest_check["checks"]["conformance_hashes"],
        "dependency_direction": {"passed": dep["passed"], **dep},
        "package_ownership": {"passed": not dep["ownership_problems"],
                              "problems": dep["ownership_problems"]},
        "frozen_invariants": {"passed": invariants_ok(invariants), "results": invariants},
        "packaging_integrity": packaging,
        "benchmark_identity": benchmark,
        "documentation_presence": docs,
    }
    passed = all(c.get("passed", True) for c in checks.values()) and manifest_check["passed"]
    substantive = {k: {kk: vv for kk, vv in v.items() if kk not in ("results",)}
                   for k, v in checks.items()}
    return {"platform_version": V.PLATFORM_VERSION, "freeze_commit": V.FREEZE_COMMIT,
            "manifest_digest": manifest.get("manifest_digest"), "passed": passed,
            "checks": checks,
            "substantive_digest": canonical_hash(substantive)}


def write_reports(result: dict, out_dir: pathlib.Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    def dump(name, obj):
        p = out_dir / name
        p.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")
        written.append(p)

    dump("verification.json", result)
    dump("api-diff.json", result["checks"]["api_compatibility"])
    dump("dependency-report.json", result["checks"]["dependency_direction"])
    dump("invariant-report.json", result["checks"]["frozen_invariants"])
    dump("package-ownership-report.json", result["checks"]["package_ownership"])

    lines = [f"# Platform v{result['platform_version']} Freeze Verification", "",
             f"- **Result:** {'PASS' if result['passed'] else 'FAIL'}",
             f"- **Freeze commit:** `{result['freeze_commit']}`",
             f"- **Manifest digest:** `{result['manifest_digest'][:16]}…`",
             f"- **Substantive digest:** `{result['substantive_digest'][:16]}…`", "", "## Checks", ""]
    for name, c in result["checks"].items():
        lines.append(f"- `{name}`: {'PASS' if c.get('passed', True) else 'FAIL'}")
    summary = out_dir / "verification-summary.md"
    summary.write_text("\n".join(lines) + "\n")
    written.append(summary)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Platform v1.0 freeze")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    parser.add_argument("--output", default="build/platform-freeze")
    args = parser.parse_args(argv)

    result = run_verification(pathlib.Path(args.manifest))
    written = write_reports(result, pathlib.Path(args.output))
    print(f"Platform v{result['platform_version']} freeze verification: "
          f"{'PASS' if result['passed'] else 'FAIL'}")
    for name, c in result["checks"].items():
        print(f"  {'ok ' if c.get('passed', True) else 'FAIL'} {name}")
    print(f"substantive digest: {result['substantive_digest']}")
    print(f"reports: {len(written)} -> {args.output}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
