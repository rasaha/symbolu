#!/usr/bin/env python3
"""Ugence Decision Governance terminology validation.

Documentation-only guard. Enforces the canonical vocabulary decided in
`docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`
over the *current, canonical* architecture documents only. Historical evidence,
frozen reports, and investor documents are intentionally NOT enforced.

Rules (per the ADR / terminology audit):
  * "Ugence Decision Governance" is the umbrella; each governed doc must say so.
  * "Decision Authority" is the bounded capability; must be named.
  * The AI Control Plane must be described as optional and never as the
    universal authority.
  * The orchestrator must be described as optional / bypassable.
  * "Model Selection" must appear (distinct capability, tenth).
  * "Decision Governance Platform" is legacy — a new use is allowed only when
    marked legacy or when quoting a frozen artifact (a version / quoted name).
  * "Digital Governance" must never be used as the canonical umbrella.
  * A governed doc that uses the bare phrase "Decision Governance" must
    distinguish the umbrella (Ugence Decision Governance) from the capability
    (Decision Authority).
  * Each amended current-architecture doc must carry the terminology note that
    links the ADR.

Exit code 0 = all checks pass; 1 = one or more violations.

Usage:  python scripts/validate_terminology.py [--repo-root PATH]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ADR_REF = "ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES"

# Canonical / new architecture documents whose *content* is enforced.
GOVERNED_DOCS = [
    "UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md",
    "docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md",
    "docs/architecture/UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_UPDATE_REPORT.md",
]

# Current-architecture documents amended with a terminology note; each must
# reference the ADR so the note is present and discoverable.
AMENDED_DOCS = [
    "UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md",
    "UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md",
    "UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md",
    "UGENCE_PLATFORM_OVERVIEW.md",
    "UGENCE_PRODUCTIZATION_ROADMAP.md",
]

NEGATIONS = ("not", "never", "neither", "nor", "no ")
_LEGACY_OK = ("legacy", "frozen", "v1.0.0", '"decision governance platform')


def _has_negation(line: str) -> bool:
    low = line.lower()
    return any(tok in low for tok in NEGATIONS)


def check_governed(path: Path, text: str) -> list[str]:
    errs: list[str] = []
    low = text.lower()

    if "ugence decision governance" not in low or "umbrella" not in low:
        errs.append('must present "Ugence Decision Governance" as the umbrella')
    if "decision authority" not in low:
        errs.append('must name the "Decision Authority" capability')
    if "model selection" not in low:
        errs.append('must mention "Model Selection" (distinct tenth capability)')

    if "ai control plane" in low and "optional" not in low:
        errs.append('mentions "AI Control Plane" but never describes it as optional')
    if "orchestrator" in low and "optional" not in low:
        errs.append('mentions the orchestrator but never describes it as optional')

    for i, line in enumerate(text.splitlines(), 1):
        ll = line.lower()
        # "Digital Governance" may only appear to forbid it (negation/prohibition).
        if "digital governance" in ll and not _has_negation(line):
            errs.append(f'line {i}: "Digital Governance" used without prohibition')
        # AI Control Plane must never be asserted as the universal authority.
        if "universal authority" in ll and not _has_negation(line):
            errs.append(f'line {i}: "universal authority" asserted without negation')
        # New "Decision Governance Platform" use must be marked legacy / a quote.
        if "decision governance platform" in ll and not any(t in ll for t in _LEGACY_OK):
            errs.append(
                f'line {i}: "Decision Governance Platform" used without a legacy/frozen marker'
            )

    # Bare "Decision Governance" must be disambiguated in the doc.
    bare = re.search(r"(?<!ugence )decision governance(?! platform)(?! kernel)", low)
    if bare and not ("ugence decision governance" in low and "decision authority" in low):
        errs.append(
            'uses bare "Decision Governance" without distinguishing umbrella vs. capability'
        )
    return errs


def check_amended(path: Path, text: str) -> list[str]:
    if ADR_REF not in text:
        return [f"missing terminology note linking the ADR ({ADR_REF})"]
    return []


# Documents where "AI Control Plane" must denote ONLY the optional component and the
# governance layer must be named the Governance Services Layer.
SINGLE_MEANING_DOCS = ["UGENCE_PLATFORM_OVERVIEW.md"]


def check_single_meaning(path: Path, text: str) -> list[str]:
    errs: list[str] = []
    low = text.lower()
    if "governance services layer" not in low:
        errs.append('must name the governance layer "Governance Services Layer"')
    if "ai control plane" in low.replace("autonomous control plane", ""):
        for i, line in enumerate(text.splitlines(), 1):
            ll = line.lower().replace("autonomous control plane", "")
            if "ai control plane" not in ll:
                continue
            # Allowed only where it discusses the reserved optional meaning or the rename.
            if "optional" not in ll and "governance services layer" not in ll:
                errs.append(
                    f'line {i}: "AI Control Plane" used as a layer label '
                    "(reserve it for the optional component)"
                )
    return errs


def run(repo_root: Path) -> int:
    failures = 0
    print(f"Ugence Decision Governance terminology validation @ {repo_root}")
    print("-" * 72)

    for rel in GOVERNED_DOCS:
        p = repo_root / rel
        if not p.is_file():
            print(f"FAIL  {rel}: file not found")
            failures += 1
            continue
        errs = check_governed(p, p.read_text(encoding="utf-8"))
        if errs:
            failures += 1
            print(f"FAIL  {rel}")
            for e in errs:
                print(f"        - {e}")
        else:
            print(f"ok    {rel}")

    for rel in AMENDED_DOCS:
        p = repo_root / rel
        if not p.is_file():
            print(f"FAIL  {rel}: file not found")
            failures += 1
            continue
        text = p.read_text(encoding="utf-8")
        errs = check_amended(p, text)
        if rel in SINGLE_MEANING_DOCS:
            errs = errs + check_single_meaning(p, text)
        if errs:
            failures += 1
            print(f"FAIL  {rel}")
            for e in errs:
                print(f"        - {e}")
        else:
            print(f"ok    {rel} (terminology note present)")

    print("-" * 72)
    print("PASS" if failures == 0 else f"{failures} document(s) FAILED")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Ugence terminology in current docs.")
    ap.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="repository root (default: parent of scripts/)",
    )
    args = ap.parse_args()
    return run(Path(args.repo_root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
