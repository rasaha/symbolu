#!/usr/bin/env python3
"""Structural + integrity validator for the DRAFT Ashtakoota rule pack.

Implements the Section-12 machine-readable pack controls for the Guna-authority
phase. This validator is deliberately NON-EXECUTABLE with respect to Guna
scoring: it never computes a compatibility score. It only checks that the
rule-pack DATA is internally consistent, that no blocked/pending/conflicted rule
has been silently promoted to executable, that the parihara rules stay disabled,
that the manual-case coverage is complete, and that the recorded checksums and
counts in ``pack_control.json`` match the files on disk.

Usage (from the product root):  python scripts/validate_rule_pack.py
Exit code 0 = all checks pass; 1 = one or more violations (printed).

The same ``validate()`` function is imported by tests/unit/test_rule_pack_controls.py.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACK_DIR = PRODUCT_ROOT / "rules" / "ashtakoota_muhurta_chintamani_raman_v1"
SOURCES = PRODUCT_ROOT / "rules" / "sources" / "GUNA_SOURCE_MANIFEST.json"
MANUAL = PRODUCT_ROOT / "rules" / "fixtures" / "guna_manual_cases.json"

KOOTA_MAX = {
    "varna": 1, "vashya": 2, "tara": 3, "yoni": 4,
    "graha_maitri": 5, "gana": 6, "bhakoot": 7, "nadi": 8,
}
KNOWN_KOOTAS = set(KOOTA_MAX) | {"external_mangal"}
CONFLICT_SENTINEL = "CONFLICT"


def _no_dupes(pairs: list[tuple[str, object]]) -> dict:
    """object_pairs_hook that rejects duplicate keys."""
    seen: dict = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate key: {k!r}")
        seen[k] = v
    return seen


def _load(path: pathlib.Path, errors: list[str]) -> dict | None:
    try:
        return json.loads(path.read_text(), object_pairs_hook=_no_dupes)
    except ValueError as exc:  # json errors are ValueError subclasses
        errors.append(f"{path.name}: invalid JSON / duplicate key: {exc}")
        return None


def _check_matrix(name: str, matrix: dict, keys: list[str], kmax: int,
                  errors: list[str], allow_conflict: bool = False) -> None:
    """Assert a square matrix over ``keys`` with values in [0, kmax].

    Keys beginning with ``_`` are metadata (e.g. ``_comment``) and are ignored.
    """
    rows = {k: v for k, v in matrix.items() if not k.startswith("_")}
    if sorted(rows.keys()) != sorted(keys):
        errors.append(f"{name}: row keys {sorted(rows.keys())} != expected {sorted(keys)}")
        return
    for r, row in rows.items():
        cols = {k: v for k, v in row.items() if not k.startswith("_")}
        if sorted(cols.keys()) != sorted(keys):
            errors.append(f"{name}[{r}]: column keys mismatch")
            continue
        for c, val in cols.items():
            if allow_conflict and val == CONFLICT_SENTINEL:
                continue
            if not isinstance(val, (int, float)):
                errors.append(f"{name}[{r}][{c}]: non-numeric value {val!r}")
            elif not (0 <= val <= kmax):
                errors.append(f"{name}[{r}][{c}]: value {val} out of range [0,{kmax}]")


def validate() -> list[str]:  # noqa: C901 - a linear checklist is clearest here
    errors: list[str] = []

    manifest = _load(PACK_DIR / "manifest.json", errors)
    trace = _load(PACK_DIR / "source_traceability.json", errors)
    parihara = _load(PACK_DIR / "parihara.json", errors)
    sources = _load(SOURCES, errors)
    manual = _load(MANUAL, errors)
    control = _load(PACK_DIR / "pack_control.json", errors)
    koota_files = {k: _load(PACK_DIR / f"{k}.json", errors) for k in KOOTA_MAX}
    if errors:  # a load/JSON failure invalidates everything downstream
        return errors
    assert manifest and trace and parihara and sources and manual and control

    # 1. Component maxima sum to 36 and match each koota file.
    comp_max = {c["name"]: c["max"] for c in manifest["components"]}
    if comp_max != KOOTA_MAX:
        errors.append(f"manifest component maxima {comp_max} != canonical {KOOTA_MAX}")
    if manifest["total_max"] != 36 or sum(comp_max.values()) != 36:
        errors.append("total_max is not 36 / component maxima do not sum to 36")
    for k, doc in koota_files.items():
        if doc.get("max") != KOOTA_MAX[k]:
            errors.append(f"{k}.json max {doc.get('max')} != {KOOTA_MAX[k]}")

    # 2. Matrix dimensions + value ranges.
    yoni = koota_files["yoni"]
    yoni_keys = [str(i) for i in range(14)]
    _check_matrix("yoni.score_matrix", yoni["scoring"]["yoni_score_matrix"], yoni_keys, 4, errors)
    gana = koota_files["gana"]
    _check_matrix("gana.score_matrix", gana["scoring"]["gana_score_matrix"],
                  ["Deva", "Manushya", "Rakshasa"], 6, errors, allow_conflict=True)
    vashya = koota_files["vashya"]
    vgroups = list(vashya["vashya_groups"].keys())
    _check_matrix("vashya.group_score_matrix", vashya["scoring"]["group_score_matrix"],
                  vgroups, 2, errors)
    gm = koota_files["graha_maitri"]
    planets = [k for k in gm["naisargika_relationships"] if not k.startswith("_")]
    if len(planets) != 7:
        errors.append(f"graha_maitri: expected 7 planets, got {len(planets)}")

    # 3. Traceability: unique rule IDs; valid koota + source references.
    rule_ids = [r["rule_id"] for r in trace["rules"]]
    if len(rule_ids) != len(set(rule_ids)):
        dupes = {rid for rid in rule_ids if rule_ids.count(rid) > 1}
        errors.append(f"traceability: duplicate rule_id(s): {sorted(dupes)}")
    valid_sources = set(manifest["source_hierarchy"])
    for r in trace["rules"]:
        if r["koota"] not in KNOWN_KOOTAS:
            errors.append(f"traceability {r['rule_id']}: unknown koota {r['koota']!r}")
        if r["source_work"] not in valid_sources:
            errors.append(f"traceability {r['rule_id']}: source_work {r['source_work']!r} "
                          f"not in source_hierarchy")

    # 4. Executable-state invariant. No blocked/pending/conflicted rule may be executable.
    if manifest["executable"] is not False:
        errors.append("manifest.executable must be false in this phase")
    for k, doc in koota_files.items():
        if doc.get("executable") is not False:
            errors.append(f"{k}.json executable must be false")
    ctrl_inv = control["executable_invariant"]
    if ctrl_inv["manifest_executable_flag"] is not False:
        errors.append("pack_control: manifest_executable_flag must be false")
    if ctrl_inv["derived_executable"] is not False:
        errors.append("pack_control: derived_executable must be false while blockers exist")
    if ctrl_inv["manifest_executable_flag"] and not ctrl_inv["derived_executable"]:
        errors.append("pack_control: manifest.executable exceeds derived_executable (INVARIANT)")
    if not ctrl_inv["blockers"]:
        errors.append("pack_control: blockers unexpectedly empty (pack cannot be ready this phase)")

    # 5. Parihara: every rule disabled.
    for r in parihara["rules"]:
        if r.get("enabled") is not False:
            errors.append(f"parihara {r['rule_id']}: enabled must be false")

    # 6. Manual cases: none verified this phase; category coverage complete.
    for c in manual["cases"]:
        if c.get("reviewer_status") == "MANUAL_VERIFIED":
            errors.append(f"manual case {c['case_id']}: MANUAL_VERIFIED not allowed "
                          "(no frozen edition / domain review)")
    coverage = manual.get("required_category_coverage", {})
    covered = {k for k in coverage if not k.startswith("_")}
    if len(covered) != 22:
        errors.append(f"manual coverage: expected 22 categories, found {len(covered)}")
    case_ids = {c["case_id"] for c in manual["cases"]}
    for cat, ids in coverage.items():
        if cat.startswith("_"):
            continue
        for cid in ids:
            if cid not in case_ids:
                errors.append(f"manual coverage {cat}: references missing case {cid}")

    # 7. Checksums + counts in pack_control match disk.
    for relpath, expected in control["checksums_sha256"].items():
        p = PRODUCT_ROOT / relpath
        if not p.exists():
            errors.append(f"pack_control checksum: missing file {relpath}")
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"pack_control checksum drift: {relpath} "
                          f"(regenerate pack_control.json after reviewing the change)")
    counts = control["counts"]
    if counts["total_rules"] != len(trace["rules"]):
        errors.append("pack_control.counts.total_rules stale")
    conflict_entries = sum(1 for r in trace["rules"]
                           if r.get("source_conflict_status") == "SOURCE_CONFLICT")
    if counts["unresolved_source_conflict_rule_entries"] != conflict_entries:
        errors.append("pack_control.counts conflict rule entries stale")
    if counts["approved_rules"] != 0:
        errors.append("pack_control: approved_rules must be 0 until domain review")
    if counts["manual_cases"] != len(manual["cases"]):
        errors.append("pack_control.counts.manual_cases stale")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(f"RULE PACK VALIDATION FAILED ({len(errors)} issue(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("RULE PACK VALIDATION PASSED (draft, non-executable; all invariants hold).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
