#!/usr/bin/env python3
"""⚠️  SYNTHETIC LABEL GENERATOR — PLUMBING SMOKE-TEST ONLY. NOT REAL DATA. NEVER REPORT ITS OUTPUT.

Fills the rater template with RANDOM placeholder labels so you can confirm the supervised-observation
evaluator runs end-to-end on the real trace + keymap *before* human raters finish. The labels are noise;
any SO_* decision produced from them is meaningless and must never be recorded as a finding (doing so
would violate docs/CSR_SUPERVISED_OBSERVATION_PREREG.md — model/random output is not human truth).

Output filename is forced to contain `SYNTHETIC` so it can't be mistaken for a real label file.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import sys
_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
from csr_match_filter.eval_supervised_observation import LABEL_FIELDS, _BINARY, _SCALES   # noqa: E402

_BANNER = "⚠️  SYNTHETIC / RANDOM LABELS — NOT REAL HUMAN DATA — DO NOT REPORT"


def item_ids_from_packet(path: Path) -> list[str]:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        return [json.loads(l)["item_id"] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    with open(p, newline="", encoding="utf-8") as fh:
        return [r["item_id"].strip() for r in csv.DictReader(fh) if r.get("item_id", "").strip()]


def synth_labels(item_ids, seed=0):
    rng = random.Random(seed)
    rows = []
    for iid in item_ids:
        row = {"item_id": iid}
        for k in _BINARY:
            row[k] = rng.choice(["yes", "no"])
        for k in _SCALES:
            row[k] = rng.randint(1, 5)
        row["short_reason"] = ""
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate SYNTHETIC labels (smoke-test only; not real data).")
    ap.add_argument("--packet", required=True, help="packet jsonl or labels template csv (for item_ids)")
    ap.add_argument("--out", default="supervised_observation_labels_SYNTHETIC.csv")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    if "SYNTHETIC" not in Path(args.out).name.upper():
        ap.error("--out filename must contain 'SYNTHETIC' (these labels are not real)")

    ids = item_ids_from_packet(args.packet)
    rows = synth_labels(ids, seed=args.seed)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", *LABEL_FIELDS])
        w.writeheader()
        w.writerows(rows)
    print(_BANNER)
    print(f"wrote {args.out}  ({len(rows)} rows, seed={args.seed})")
    print("Use ONLY to verify the evaluator wiring; the resulting SO_* decision is meaningless.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
