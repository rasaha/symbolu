#!/usr/bin/env python3
"""Pre-flight validator for a RETURNED human-label file — run BEFORE the supervised-observation evaluator.

Catches rater/coordinator mistakes early so you don't discover them mid-evaluation: unknown or duplicate
item_ids, unparseable cells, blank primary labels, thin positive counts, and (for two raters) low
agreement. It reports EVERYTHING (does not stop at the first problem) and exits non-zero only on FATAL
issues (things that would make the evaluator crash or silently mis-join). Warnings (partial coverage,
low power, low κ) are surfaced but don't fail — the evaluator handles them via its SO_* labels.

OFFLINE, read-only, no runtime behavior. Pairs with eval_supervised_observation.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from csr_match_filter.eval_supervised_observation import (   # noqa: E402
    LABEL_FIELDS, _BINARY, _SCALES, _yn, _scale, cohen_kappa,
)

DEFAULT_MIN_POS = 20
DEFAULT_KAPPA_MIN = 0.40


def _tolerant_parse(raw: dict):
    """Parse one row, collecting (field, value, reason) issues instead of raising."""
    parsed, issues = {}, []
    for k in _BINARY:
        try:
            parsed[k] = _yn(raw.get(k))
        except ValueError:
            parsed[k] = None
            issues.append((k, raw.get(k), "not yes/no"))
    for k in _SCALES:
        try:
            parsed[k] = _scale(raw.get(k))
        except ValueError:
            parsed[k] = None
            issues.append((k, raw.get(k), "not an integer 1–5"))
    parsed["short_reason"] = (raw.get("short_reason") or "").strip() or None
    return parsed, issues


def load_label_file(path):
    """Return (rows[item_id]->parsed, cell_issues[item_id]->list, dup_ids[list]). Tolerant of bad cells."""
    p = Path(path)
    raws = []
    if p.suffix.lower() == ".jsonl":
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                raws.append({"item_id": rec.get("item_id"), **(rec.get("human_labels") or {})})
    else:
        with open(p, newline="", encoding="utf-8") as fh:
            raws.extend(csv.DictReader(fh))
    rows, issues, seen, dups = {}, {}, set(), []
    for raw in raws:
        iid = (str(raw.get("item_id") or "")).strip()
        if not iid:
            continue
        if iid in seen:
            dups.append(iid)
        seen.add(iid)
        parsed, iss = _tolerant_parse(raw)
        rows[iid] = parsed
        if iss:
            issues[iid] = iss
    return rows, issues, dups


def validate(label_files, keymap: dict, *, min_pos=DEFAULT_MIN_POS, kappa_min=DEFAULT_KAPPA_MIN) -> dict:
    """Validate one or two label files against the keymap. Returns a report with fatal[]/warnings[]/ok."""
    expected = set(keymap)
    raters = [load_label_file(f) for f in label_files]
    fatal, warnings, per_rater = [], [], []

    for i, (rows, issues, dups) in enumerate(raters):
        ids = set(rows)
        unknown = sorted(ids - expected)         # labeled item_ids absent from the keymap → cannot resolve
        missing = sorted(expected - ids)         # keymap items with no label → partial coverage
        blank_primary = sorted(iid for iid, p in rows.items() if p["rewrite_needed"] is None)
        n_pos = sum(1 for p in rows.values() if p["rewrite_needed"] is True)
        n_neg = sum(1 for p in rows.values() if p["rewrite_needed"] is False)
        per_rater.append({
            "file": str(label_files[i]), "n_rows": len(rows),
            "unknown_item_ids": unknown, "missing_item_ids_count": len(missing),
            "duplicate_item_ids": sorted(set(dups)), "unparseable_cells": issues,
            "blank_primary_label": blank_primary,
            "n_rewrite_yes": n_pos, "n_rewrite_no": n_neg,
        })
        if unknown:
            fatal.append(f"rater{i+1}: {len(unknown)} item_id(s) not in keymap (e.g. {unknown[:3]})")
        if dups:
            fatal.append(f"rater{i+1}: duplicate item_id(s) {sorted(set(dups))[:3]}")
        if issues:
            fatal.append(f"rater{i+1}: {sum(len(v) for v in issues.values())} unparseable cell(s) "
                         f"in {len(issues)} row(s)")
        if missing:
            warnings.append(f"rater{i+1}: {len(missing)} keymap item(s) unlabeled (partial coverage; "
                            f"those rows are excluded by the evaluator)")
        if blank_primary:
            warnings.append(f"rater{i+1}: {len(blank_primary)} blank rewrite_needed (rows excluded)")
        if n_pos < min_pos:
            warnings.append(f"rater{i+1}: only {n_pos} positives (< {min_pos}) → evaluator would emit "
                            f"SO_INSUFFICIENT_LABEL_POWER")

    # two-rater agreement (over the overlap)
    agreement = None
    if len(raters) == 2:
        r0, r1 = raters[0][0], raters[1][0]
        overlap = sorted(set(r0) & set(r1) & expected)
        kappa = {}
        for k in _BINARY:
            kappa[k] = cohen_kappa([r0[i][k] for i in overlap], [r1[i][k] for i in overlap])
        agreement = {"overlap_n": len(overlap), "cohen_kappa": kappa}
        kp = kappa.get("rewrite_needed")
        if kp is None:
            warnings.append("two raters but κ(rewrite_needed) is undefined (too little overlap/variance)")
        elif kp < kappa_min:
            warnings.append(f"κ(rewrite_needed)={kp} < {kappa_min} → evaluator would emit "
                            f"SO_INSUFFICIENT_RATER_AGREEMENT")

    return {
        "n_raters": len(raters), "keymap_items": len(expected),
        "per_rater": per_rater, "agreement": agreement,
        "min_pos": min_pos, "kappa_min": kappa_min,
        "fatal": fatal, "warnings": warnings, "ok": not fatal,
        "ready_for_evaluation": (not fatal) and any(r["n_rewrite_yes"] >= min_pos for r in per_rater),
    }


def format_report(rep: dict) -> str:
    L = [f"label validation — raters={rep['n_raters']} keymap_items={rep['keymap_items']}"]
    for r in rep["per_rater"]:
        L.append(f"  {Path(r['file']).name}: rows={r['n_rows']} "
                 f"pos={r['n_rewrite_yes']} neg={r['n_rewrite_no']} "
                 f"unknown={len(r['unknown_item_ids'])} unlabeled={r['missing_item_ids_count']} "
                 f"blank_primary={len(r['blank_primary_label'])} "
                 f"bad_cells={sum(len(v) for v in r['unparseable_cells'].values())}")
    if rep["agreement"]:
        L.append(f"  agreement: overlap={rep['agreement']['overlap_n']} "
                 f"κ(rewrite_needed)={rep['agreement']['cohen_kappa'].get('rewrite_needed')}")
    for w in rep["warnings"]:
        L.append(f"  ⚠ {w}")
    for f in rep["fatal"]:
        L.append(f"  ✖ FATAL {f}")
    L.append(f"  => ok={rep['ok']}  ready_for_evaluation={rep['ready_for_evaluation']}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a returned human-label file before evaluation.")
    ap.add_argument("--labels", required=True, help="label CSV/JSONL (comma-separate two files)")
    ap.add_argument("--keymap", required=True)
    ap.add_argument("--min-pos", type=int, default=DEFAULT_MIN_POS)
    ap.add_argument("--kappa-min", type=float, default=DEFAULT_KAPPA_MIN)
    ap.add_argument("--out", default=None, help="optional JSON report path")
    args = ap.parse_args(argv)

    keymap = json.loads(Path(args.keymap).read_text(encoding="utf-8"))
    files = [p for p in args.labels.split(",") if p.strip()]
    rep = validate(files, keymap, min_pos=args.min_pos, kappa_min=args.kappa_min)
    print(format_report(rep))
    if args.out:
        Path(args.out).write_text(json.dumps(rep, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
