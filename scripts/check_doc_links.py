#!/usr/bin/env python3
"""Documentation-link validation for the Ugence Decision Governance terminology docs.

Checks that relative Markdown links in the terminology phase's documents resolve to
existing files in the tree. External (http/https) links and pure in-page anchors are
skipped. Exit 0 = all resolve; 1 = one or more broken.

Usage:  python scripts/check_doc_links.py [--repo-root PATH]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

DOCS = [
    "UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md",
    "UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md",
    "UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md",
    "UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md",
    "UGENCE_PLATFORM_OVERVIEW.md",
    "UGENCE_PRODUCTIZATION_ROADMAP.md",
    "ADR_MODEL_SELECTION_POLICY_PLACEMENT.md",
    "docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md",
    "docs/architecture/UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_UPDATE_REPORT.md",
]

LINK = re.compile(r"\[[^\]]*\]\((?!https?://)([^)#]+)(?:#[^)]*)?\)")


def run(repo_root: Path) -> int:
    broken = 0
    checked = 0
    print(f"Documentation-link validation @ {repo_root}")
    print("-" * 72)
    for rel in DOCS:
        p = repo_root / rel
        if not p.is_file():
            print(f"FAIL  {rel}: file not found")
            broken += 1
            continue
        base = p.parent
        doc_broken = 0
        for m in LINK.finditer(p.read_text(encoding="utf-8")):
            target = m.group(1).strip()
            checked += 1
            if not (base / target).resolve().exists():
                print(f"FAIL  {rel} -> {target}")
                doc_broken += 1
        broken += doc_broken
        if doc_broken == 0:
            print(f"ok    {rel}")
    print("-" * 72)
    print(f"{checked} link(s) checked; " + ("PASS" if broken == 0 else f"{broken} broken"))
    return 1 if broken else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate relative doc links.")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()
    return run(Path(args.repo_root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
