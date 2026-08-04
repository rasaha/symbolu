#!/usr/bin/env python3
"""Generate ``pack_control.json`` for the Ashtakoota rule pack.

Machine-readable control block for the DRAFT, NON-EXECUTABLE Guna rule pack
(Section 12 of the Guna-authority phase). Records the pack identity, component
maxima, honest counts derived from the traceability ledger, the domain-review /
source-freeze state, and a sha256 checksum of every other pack file. The
companion validator (``validate_rule_pack.py``) recomputes these and fails on
any drift.

This is pack *control metadata only*. It contains NO Guna scoring code and does
NOT make any rule executable. The ``executable`` flag is derived and MUST stay
``false`` while any rule is pending/blocked/conflicted, domain review is
pending, or no source edition is frozen.

Run from the product root:  python scripts/generate_pack_control.py
The generation date is read from DILCHAT_PACK_CONTROL_DATE (YYYY-MM-DD) so the
output is reproducible; it defaults to the acquisition-phase date.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACK_DIR = PRODUCT_ROOT / "rules" / "ashtakoota_muhurta_chintamani_raman_v1"
SOURCES = PRODUCT_ROOT / "rules" / "sources" / "GUNA_SOURCE_MANIFEST.json"
MANUAL = PRODUCT_ROOT / "rules" / "fixtures" / "guna_manual_cases.json"

# Every pack file whose integrity the control block pins (pack_control.json
# itself is excluded — a file cannot checksum itself).
CHECKSUMMED = [
    PACK_DIR / "manifest.json",
    PACK_DIR / "source_traceability.json",
    PACK_DIR / "parihara.json",
    PACK_DIR / "varna.json",
    PACK_DIR / "vashya.json",
    PACK_DIR / "tara.json",
    PACK_DIR / "yoni.json",
    PACK_DIR / "graha_maitri.json",
    PACK_DIR / "gana.json",
    PACK_DIR / "bhakoot.json",
    PACK_DIR / "nadi.json",
    SOURCES,
    MANUAL,
]

TOOL_VERSION = "generate_pack_control/1.0"
BLOCKING_RULE_STATUSES = {"PENDING_DOMAIN_REVIEW", "BLOCKED_DOMAIN_SOURCE", "SOURCE_CONFLICT"}


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: pathlib.Path) -> str:
    return str(path.relative_to(PRODUCT_ROOT))


def main() -> int:
    manifest = json.loads((PACK_DIR / "manifest.json").read_text())
    trace = json.loads((PACK_DIR / "source_traceability.json").read_text())
    parihara = json.loads((PACK_DIR / "parihara.json").read_text())
    sources = json.loads(SOURCES.read_text())
    manual = json.loads(MANUAL.read_text())

    rules = trace["rules"]
    approved = [r for r in rules if r.get("v1_inclusion_decision") == "DOMAIN_APPROVED"]
    excluded = [r for r in rules if r.get("v1_inclusion_decision") == "EXCLUDED_FROM_V1"]
    blocked = [r for r in rules if r.get("review_status") == "BLOCKED_DOMAIN_SOURCE"]
    conflicts = [r for r in rules if r.get("source_conflict_status") == "SOURCE_CONFLICT"]
    conflict_topics = sorted({r["koota"] for r in conflicts})
    pending = [r for r in rules if r.get("review_status") == "PENDING_DOMAIN_REVIEW"]

    any_source_frozen = any(
        s.get("review_status", "").startswith("FROZEN") for s in sources["sources"]
    )
    domain_review_pending = sources.get("domain_review") != "DOMAIN_REVIEW_COMPLETE"

    # Derived executable invariant. Executable is permitted ONLY when nothing blocks it.
    blockers = []
    if pending:
        blockers.append(f"{len(pending)} rule(s) PENDING_DOMAIN_REVIEW")
    if blocked:
        blockers.append(f"{len(blocked)} rule(s) BLOCKED_DOMAIN_SOURCE")
    if conflicts:
        blockers.append(f"{len(conflicts)} rule(s) SOURCE_CONFLICT")
    if not any_source_frozen:
        blockers.append("no source edition is FROZEN")
    if domain_review_pending:
        blockers.append("domain review pending")
    unresolved_manual = [
        c for c in manual["cases"] if c.get("reviewer_status") != "MANUAL_VERIFIED"
    ]
    if unresolved_manual:
        blockers.append(f"{len(unresolved_manual)} manual case(s) not MANUAL_VERIFIED")

    derived_executable = len(blockers) == 0

    control = {
        "pack_control_id": "ashtakoota_muhurta_chintamani_raman_v1_control",
        "rule_pack_id": manifest["id"],
        "semantic_version": manifest["version"],
        "tradition_scope": manifest["tradition"],
        "total_max": manifest["total_max"],
        "component_maxima": {c["name"]: c["max"] for c in manifest["components"]},
        "generated_at_utc_date": os.environ.get("DILCHAT_PACK_CONTROL_DATE", "2026-08-04"),
        "generation_tool_version": TOOL_VERSION,
        "counts": {
            "total_rules": len(rules),
            "approved_rules": len(approved),
            "excluded_rules": len(excluded),
            "blocked_rules": len(blocked),
            "pending_rules": len(pending),
            "unresolved_source_conflict_rule_entries": len(conflicts),
            "unresolved_source_conflict_topics": len(conflict_topics),
            "parihara_rules": len(parihara["rules"]),
            "parihara_enabled": sum(1 for r in parihara["rules"] if r.get("enabled")),
            "manual_cases": len(manual["cases"]),
            "manual_cases_verified": len(manual["cases"]) - len(unresolved_manual),
        },
        "source_conflict_topics": conflict_topics,
        "source_edition_state": {
            "any_source_frozen": any_source_frozen,
            "overall_status": sources["overall_status"],
            "domain_review": sources.get("domain_review"),
        },
        "executable_invariant": {
            "manifest_executable_flag": manifest["executable"],
            "derived_executable": derived_executable,
            "blockers": blockers,
            "rule": (
                "executable may be true ONLY when blockers is empty; "
                "manifest.executable must never exceed derived_executable."
            ),
        },
        "checksums_sha256": {rel(p): sha256_of(p) for p in CHECKSUMMED},
        "notes": [
            "DRAFT / NON-EXECUTABLE control block. No Guna scoring code exists.",
            "Counts are derived from source_traceability.json; approved_rules stays 0 pre-review.",
            "Any edit to a checksummed file changes its digest; the validator flags the "
            "drift until this file is regenerated and the change is reviewed.",
        ],
    }

    out = PACK_DIR / "pack_control.json"
    out.write_text(json.dumps(control, indent=2) + "\n")
    print(f"wrote {rel(out)}")
    print(f"  executable(derived)={derived_executable} blockers={len(blockers)}")
    print(f"  rules={len(rules)} approved={len(approved)} conflicts={len(conflicts)} "
          f"blocked={len(blocked)} manual_cases={len(manual['cases'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
