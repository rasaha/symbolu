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

# Paths are repo-root-relative; the docs live under Project_documentation/ after
# the repository restructuring.
#
# The Agentic Proposer documents are included because the capability's enforcement
# documentation claims link coverage from this gate. A claim of coverage from a curated
# list is only true if the list actually names the documents, so they are named here
# rather than assumed. This gate checks link RESOLUTION only; it enforces no
# terminology, and the Agentic Proposer documents are deliberately NOT in
# scripts/validate_terminology.py's governed set, whose content rules are specific to
# the Decision Governance terminology ADR and do not apply to them.
DOCS = [
    "Project_documentation/repository/architecture/UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md",
    "Project_documentation/repository/restructuring/UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md",
    "Project_documentation/repository/architecture/UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md",
    "Project_documentation/repository/architecture/UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md",
    "Project_documentation/repository/ugence_platform/UGENCE_PLATFORM_OVERVIEW.md",
    "Project_documentation/repository/ugence_platform/UGENCE_PRODUCTIZATION_ROADMAP.md",
    "Project_documentation/model_selection/adr/ADR_MODEL_SELECTION_POLICY_PLACEMENT.md",
    "Project_documentation/repository/docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md",
    "Project_documentation/repository/docs/architecture/UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_UPDATE_REPORT.md",
    "docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md",
    "packages/capabilities/agentic-proposer/README.md",
    "packages/capabilities/agentic-proposer/docs/S1_ENFORCEMENT.md",
    "packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md",
    "packages/capabilities/agentic-proposer/docs/S0_SCOPE.md",
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
