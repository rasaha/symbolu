"""
analyze_traces.py — derive a FAILURE_TAXONOMY.json from a REAL_MODEL_TRACES.jsonl file.

Use it to freeze an existing run's failure taxonomy (e.g. the RM1-v1 baseline) without re-running the
model, and to diff RM1-v1 vs RM1-v1.1 after the extraction-normalization fix:

    python -m experiments.hybrid_token_event_attention.real_model.analyze_traces \
        results/rm1_v1/RM1_v1_TRACES.jsonl -o results/rm1_v1/RM1_v1_FAILURE_TAXONOMY.json

Prints the taxonomy to stdout; writes it to -o when given. Reads only; never mutates the traces.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List

from .run_real_model import build_failure_taxonomy


def load_traces(path: str) -> List[Dict]:
    rows: List[Dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Derive FAILURE_TAXONOMY.json from RM1 traces")
    p.add_argument("traces", help="path to a REAL_MODEL_TRACES.jsonl file")
    p.add_argument("-o", "--out", default=None, help="write taxonomy JSON here (optional)")
    args = p.parse_args(argv)

    rows = [r for r in load_traces(args.traces) if "quarantine" in r or "n_proposed" in r]
    if not rows:
        print(f"No RM1 arm traces found in {args.traces} (blocked run or empty).", file=sys.stderr)
        return 2
    tax = build_failure_taxonomy(rows)
    text = json.dumps(tax, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"[analyze_traces] wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
