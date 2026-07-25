"""Maintenance gate — classify changes vs the freeze (Task 11).

    python -m platform_freeze.classify_change --base <freeze-commit> --head HEAD

Produces evidence and a *proposed* classification (PATCH / MINOR / MAJOR /
APPLICATION_LOCAL / UNCLASSIFIED). It does not replace human architectural review;
MAJOR and UNCLASSIFIED fail CI unless explicitly approved. API-breaking or
dependency-violating changes to a frozen core tree are forced to MAJOR.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from . import version as V
from .compat import classify as classify_diffs, compare_snapshots
from .api_snapshot import snapshot_all
from .dependencies import check_dependency_direction
from .manifest import load_stored_snapshots

_CORE = set(V.CORE_TREES)
_BEHAVIOUR = set(V.BEHAVIOUR_TREES)
_APP = {"ai_hiring", "domains", "applications"}
_SEVERITY = {"PATCH": 0, "APPLICATION_LOCAL": 1, "MINOR": 2, "UNCLASSIFIED": 3, "MAJOR": 4}


def _changed_paths(base: str, head: str) -> list:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}..{head}"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip())
    return [p for p in out.stdout.splitlines() if p.strip()]


def _classify_path(path: str) -> str:
    parts = path.split("/")
    root = parts[0]
    if root in _CORE:
        return "PATCH" if len(parts) > 1 and "tests" in parts else "CORE_SOURCE"
    if root in _BEHAVIOUR:
        return "PATCH" if "tests" in parts else "MINOR"
    if root in _APP:
        return "APPLICATION_LOCAL"
    if root in ("docs", "packaging", "platform", "platform_freeze", "reports"):
        return "PATCH"
    if path.endswith((".md", ".json")):
        return "PATCH"
    return "UNCLASSIFIED"


def classify_change(base: str, head: str = "HEAD") -> dict:
    paths = _changed_paths(base, head)
    per_path = {p: _classify_path(p) for p in paths}
    core_source_changed = any(c == "CORE_SOURCE" for c in per_path.values())

    # API compatibility of the frozen public surface (vs stored snapshots)
    stored = load_stored_snapshots()
    diffs = compare_snapshots(stored, snapshot_all(V.PUBLIC_API_MODULES)) if stored else []
    api_class = classify_diffs(diffs)                       # PATCH / MINOR / MAJOR
    breaking = [d.__dict__ for d in diffs if d.severity == "BREAKING"]
    dep_violations = [v.__dict__ for v in check_dependency_direction()]

    # resolve core-source changes by their API/dependency impact
    resolved = []
    for c in per_path.values():
        if c == "CORE_SOURCE":
            if breaking or dep_violations:
                resolved.append("MAJOR")
            elif api_class == "MINOR":
                resolved.append("MINOR")
            else:
                resolved.append("PATCH")   # semantic-preserving core edit (still needs review)
        else:
            resolved.append(c)
    if core_source_changed and (breaking or dep_violations):
        resolved.append("MAJOR")

    overall = max(resolved, key=lambda c: _SEVERITY[c]) if resolved else "PATCH"
    return {
        "base": base, "head": head, "changed_path_count": len(paths),
        "changed_paths": per_path,
        "core_source_changed": core_source_changed,
        "api_classification": api_class,
        "api_breaking_changes": breaking,
        "dependency_violations": dep_violations,
        "proposed_classification": overall,
        "requires_approval": overall in ("MAJOR", "UNCLASSIFIED"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Classify changes against the platform freeze")
    parser.add_argument("--base", default=V.FREEZE_COMMIT)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--approve", action="store_true",
                        help="acknowledge a MAJOR/UNCLASSIFIED change (human review done)")
    args = parser.parse_args(argv)

    result = classify_change(args.base, args.head)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["requires_approval"] and not args.approve:
        print(f"\nCLASSIFICATION {result['proposed_classification']} requires explicit approval "
              f"(--approve after architectural review).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
