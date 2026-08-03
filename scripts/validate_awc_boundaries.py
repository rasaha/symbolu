#!/usr/bin/env python3
"""Documentation-consistency guard for Agent Workforce Composer Phase 0.

This is a *documentation validation* script — it asserts that the frozen AWC
architecture contract and the seven AWC design documents agree with the Phase 0
reconciliation ADR. It implements **no product behavior**; it only reads
committed docs/JSON and returns non-zero on drift.

Checks:
  1. every required AWC owner appears exactly once in the boundaries contract;
  2. no prohibited ownership is assigned to AWC;
  3. all five downstream boundaries are documented;
  4. no active AWC document still calls the compiler "spec-only";
  5. no active AWC document says compiler integration happens "when it ships";
  6. package name and namespace remain consistent across the contract + ADR.

Run: python scripts/validate_awc_boundaries.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
BOUNDARIES = REPO / "docs" / "architecture" / "agent_workforce_composer_boundaries.json"
ADR = REPO / "docs" / "architecture" / "ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md"

AWC_DOCS = (
    "AGENT_WORKFORCE_COMPOSER_DESIGN_SPEC.md",
    "AGENT_WORKFORCE_COMPOSER_ARCHITECTURE.md",
    "AGENT_WORKFORCE_COMPOSER_OBJECT_MODEL.md",
    "AGENT_WORKFORCE_COMPOSER_AUTHORITY_BOUNDARY.md",
    "AGENT_WORKFORCE_COMPOSER_SELECTION_POLICY.md",
    "AGENT_WORKFORCE_COMPOSER_ASSURANCE_PLAN.md",
    "AGENT_WORKFORCE_COMPOSER_IMPLEMENTATION_ROADMAP.md",
)

REQUIRED_OWNS = {
    "WORKFLOW_ROLE_EXTRACTION",
    "AGENT_ELIGIBILITY",
    "AGENT_RANKING",
    "TEAM_COMPOSITION",
    "PLAN_EXPLANATION",
    "PLAN_REPLAY",
}
PROHIBITED_OWNS = {
    "AGENT_EXECUTION",
    "MODEL_SELECTION",
    "WORKFLOW_SCHEDULING",
    "BINDING_BUSINESS_DECISION",
    "EXACT_ACTION_AUTHORIZATION",
    "OPERATIONAL_CLEARANCE",
}
REQUIRED_BOUNDARIES = {
    "AWC_TO_COMPILER",
    "AWC_TO_H16",
    "AWC_TO_MODEL_SELECTION",
    "AWC_TO_AGENT_RUNTIME",
    "AWC_TO_H22",
}
EXPECTED_DISTRIBUTION = "ugence-agent-workforce-composer"
EXPECTED_NAMESPACE = "ugence_agent_workforce_composer"

# Stale-terminology patterns. These must not appear as *active* claims about the
# compiler. The correction notes intentionally quote the old phrasing, so lines
# that are clearly historical (quoted / struck / labelled "was"/"originally"/
# "correction") are exempted.
STALE_SPEC_ONLY = re.compile(r"spec[-\s]?only", re.IGNORECASE)
STALE_WHEN_SHIPS = re.compile(r"when it ships", re.IGNORECASE)
HISTORICAL_HINT = re.compile(
    r"(~~|originally|original assumption|previously|former|formerly|was described|"
    r"stale|corrected|correction|no longer|superseded|historical|\bwas\b)",
    re.IGNORECASE,
)


def _fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def main() -> int:
    problems: list[str] = []

    if not BOUNDARIES.exists():
        print(f"FAIL: missing contract file {BOUNDARIES.relative_to(REPO)}")
        return 1
    contract = json.loads(BOUNDARIES.read_text(encoding="utf-8"))

    # 1) every required owner appears exactly once.
    owns = contract.get("owns", [])
    for req in sorted(REQUIRED_OWNS):
        n = owns.count(req)
        if n != 1:
            _fail(problems, f"required AWC owner {req!r} appears {n} times (expected exactly 1)")
    for extra in owns:
        if extra not in REQUIRED_OWNS:
            _fail(problems, f"unexpected owner in contract 'owns': {extra!r}")

    # 2) no prohibited ownership assigned to AWC.
    for bad in sorted(PROHIBITED_OWNS):
        if bad in owns:
            _fail(problems, f"prohibited concern assigned to AWC 'owns': {bad!r}")
    declared_mustnot = set(contract.get("must_not_own", []))
    missing_mustnot = PROHIBITED_OWNS - declared_mustnot
    if missing_mustnot:
        _fail(problems, f"contract 'must_not_own' missing: {sorted(missing_mustnot)}")

    # 3) all five boundaries documented.
    boundaries = set(contract.get("boundaries", {}).keys())
    missing_boundaries = REQUIRED_BOUNDARIES - boundaries
    if missing_boundaries:
        _fail(problems, f"missing documented boundaries: {sorted(missing_boundaries)}")

    # 6) package name + namespace consistent (contract + ADR).
    tgt = contract.get("frozen_target_package", {})
    if tgt.get("distribution") != EXPECTED_DISTRIBUTION:
        _fail(problems, f"contract distribution {tgt.get('distribution')!r} != {EXPECTED_DISTRIBUTION!r}")
    if tgt.get("namespace") != EXPECTED_NAMESPACE:
        _fail(problems, f"contract namespace {tgt.get('namespace')!r} != {EXPECTED_NAMESPACE!r}")
    if ADR.exists():
        adr_text = ADR.read_text(encoding="utf-8")
        if EXPECTED_NAMESPACE not in adr_text:
            _fail(problems, f"ADR does not mention namespace {EXPECTED_NAMESPACE!r}")
    else:
        _fail(problems, f"missing ADR {ADR.relative_to(REPO)}")

    # 4) + 5) stale-terminology scan across the seven active AWC docs.
    # The dated "Implementation-Status Correction" blockquote intentionally quotes
    # the old phrasing; skip that whole block, then scan the live body.
    for name in AWC_DOCS:
        path = REPO / name
        if not path.exists():
            _fail(problems, f"AWC document not found: {name}")
            continue
        in_correction_note = False
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if "Implementation-Status Correction" in line:
                in_correction_note = True
                continue
            if in_correction_note:
                # the note is a contiguous blockquote; blank lines inside it stay in-note
                if stripped.startswith(">") or stripped == "":
                    continue
                in_correction_note = False
            if HISTORICAL_HINT.search(line):
                continue  # historical context is allowed to quote old phrasing
            if STALE_SPEC_ONLY.search(line):
                _fail(problems, f"{name}:{i} active 'spec-only' compiler claim: {line.strip()!r}")
            if STALE_WHEN_SHIPS.search(line):
                _fail(problems, f"{name}:{i} active 'when it ships' compiler claim: {line.strip()!r}")

    if problems:
        print("AWC boundary/terminology validation: FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("AWC boundary/terminology validation: PASS")
    print(f"  owns={len(owns)} boundaries={len(boundaries)} docs={len(AWC_DOCS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
