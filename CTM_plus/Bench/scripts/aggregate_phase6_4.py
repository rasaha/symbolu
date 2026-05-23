#!/usr/bin/env python3
"""aggregate_phase6_4.py — Phase 6.4 sweep aggregator + decision rule.

Loads the per-fraction JSONs produced by apply_phase6_4_sweep.sh,
extracts the headline §20.4.3 metrics, prints a comparison table, and
applies the user's decision rule:

  - If 4% PASS:       proceed to Phase 5 (vLLM integration)
  - If 8% PASS only:  make protect_fraction configurable in Phase 5,
                      update docs to default to 8%
  - If neither PASS:  STOP Phase 5, debug the native-kernel quality
                      path

PASS criteria (per §20.4.3 ship config):
  - int4_needle_accuracy   >= 0.90   (24 needles per fraction; allow
                                      occasional seed-driven miss)
  - int4_entropy_collapse_rate <= 0.10  (decode entropy collapse is
                                      the canary for repetition-loops)
  - int4_repeated_token_rate_mean <= 0.20  (sanity check; > 0.2 means
                                      decode is generating repeated
                                      tokens at a meaningful rate)

The headline gate is int4_needle_accuracy. The other two are
supporting checks that catch the "model degenerates into a loop" mode
that needle accuracy can sometimes still pass if the loop happens to
contain the needle code.

Exit 0 if any of {4%, 8%} passes (= GREEN to proceed); 1 otherwise.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FRACTIONS = [0.0, 0.02, 0.04, 0.08]

# §20.4.3 ship-config thresholds.
NEEDLE_ACCURACY_PASS    = 0.90
ENTROPY_COLLAPSE_PASS   = 0.10
REPEATED_TOKEN_PASS     = 0.20


def _find_int4_cell(
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Track_e_long_context.py emits a 'cells' list (or similar) with
    one entry per (context_length, cache_type). Find the INT4 cell."""
    # Try a few candidate keys — the harness has evolved.
    for top_key in ("cells", "results", "needle_results", "summary"):
        if top_key in payload and isinstance(payload[top_key], list):
            for cell in payload[top_key]:
                if not isinstance(cell, dict):
                    continue
                # Heuristic: look for any of the int4 metric prefixes.
                if any(k.startswith("int4_") for k in cell):
                    return cell
                # Also accept cells flagged by 'cache_type'.
                if cell.get("cache_type", "").startswith("int4"):
                    return cell
        if top_key in payload and isinstance(payload[top_key], dict):
            # Nested dict — recurse into values.
            for v in payload[top_key].values():
                if isinstance(v, dict) and any(k.startswith("int4_") for k in v):
                    return v
    # Last resort: top-level int4_ keys.
    if any(k.startswith("int4_") for k in payload):
        return payload
    return None


def _extract_metrics(payload: Dict[str, Any]) -> Dict[str, Optional[float]]:
    cell = _find_int4_cell(payload)
    if cell is None:
        return {
            "needle_accuracy": None,
            "entropy_collapse": None,
            "repeated_token_mean": None,
            "first_stutter_earliest": None,
        }
    return {
        "needle_accuracy":        cell.get("int4_needle_accuracy"),
        "entropy_collapse":       cell.get("int4_entropy_collapse_rate"),
        "repeated_token_mean":    cell.get("int4_repeated_token_rate_mean"),
        "first_stutter_earliest": cell.get("int4_first_stutter_earliest"),
    }


def _fmt(v: Optional[float], width: int = 8) -> str:
    if v is None:
        return "MISSING".rjust(width)
    if isinstance(v, float):
        return f"{v:.4f}".rjust(width)
    return str(v).rjust(width)


def _check_pass(metrics: Dict[str, Optional[float]]) -> Tuple[bool, List[str]]:
    """Return (pass, reasons-not-pass)."""
    reasons = []
    na = metrics["needle_accuracy"]
    if na is None or na < NEEDLE_ACCURACY_PASS:
        reasons.append(f"needle_accuracy {na} < {NEEDLE_ACCURACY_PASS}")
    ec = metrics["entropy_collapse"]
    if ec is None or ec > ENTROPY_COLLAPSE_PASS:
        reasons.append(f"entropy_collapse {ec} > {ENTROPY_COLLAPSE_PASS}")
    rt = metrics["repeated_token_mean"]
    if rt is None or rt > REPEATED_TOKEN_PASS:
        reasons.append(f"repeated_token_mean {rt} > {REPEATED_TOKEN_PASS}")
    return (len(reasons) == 0, reasons)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--indir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    rows: List[Dict[str, Any]] = []
    for frac in FRACTIONS:
        path = args.indir / f"protect_{frac}.json"
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            rows.append({"fraction": frac, "metrics": None, "pass": False,
                         "reasons": ["file missing"]})
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            print(f"BAD JSON: {path}: {e}", file=sys.stderr)
            rows.append({"fraction": frac, "metrics": None, "pass": False,
                         "reasons": [f"bad json: {e}"]})
            continue
        metrics = _extract_metrics(payload)
        ok, reasons = _check_pass(metrics)
        rows.append({
            "fraction": frac, "metrics": metrics,
            "pass": ok, "reasons": reasons,
        })

    print()
    print("=" * 70)
    print("Phase 6.4 sweep — Qwen2.5-7B, context_length=32000 (chars)")
    print("=" * 70)
    print(f"{'Fraction':>9} | {'NeedleAcc':>10} | {'EntCollapse':>11} | "
          f"{'RepTokMean':>11} | {'FirstStut':>9} | Status")
    print("-" * 70)
    for row in rows:
        if row["metrics"] is None:
            print(f"{row['fraction']*100:>7.1f}% | "
                  + " " * 50 + " | MISSING")
            continue
        m = row["metrics"]
        status = "PASS" if row["pass"] else "FAIL"
        print(f"{row['fraction']*100:>7.1f}% | "
              f"{_fmt(m['needle_accuracy'], 10)} | "
              f"{_fmt(m['entropy_collapse'], 11)} | "
              f"{_fmt(m['repeated_token_mean'], 11)} | "
              f"{_fmt(m['first_stutter_earliest'], 9)} | {status}")
        if not row["pass"]:
            for r in row["reasons"]:
                print(f"          - {r}")
    print()
    print(f"Gates: needle_accuracy >= {NEEDLE_ACCURACY_PASS}, "
          f"entropy_collapse <= {ENTROPY_COLLAPSE_PASS}, "
          f"repeated_token_mean <= {REPEATED_TOKEN_PASS}")
    print()

    # Decision rule.
    p4 = next((r for r in rows if r["fraction"] == 0.04), None)
    p8 = next((r for r in rows if r["fraction"] == 0.08), None)
    p4_ok = p4 is not None and p4["pass"]
    p8_ok = p8 is not None and p8["pass"]

    print("=" * 70)
    print("Decision rule")
    print("=" * 70)
    if p4_ok:
        decision = "PROCEED to Phase 5 (vLLM integration) with protect_fraction=0.04 default."
        verdict = "PASS_4"
        rc = 0
    elif p8_ok:
        decision = ("8% passes but 4% does not — PROCEED to Phase 5 with "
                    "protect_fraction CONFIGURABLE (default 0.08); update "
                    "KERNEL_6C3C_DESIGN.md to note the policy shift.")
        verdict = "PASS_8_FAIL_4"
        rc = 0
    else:
        decision = ("Neither 4% nor 8% passes — STOP Phase 5. Debug the "
                    "native-kernel quality path (likely candidates: mask "
                    "computation, kernel-algorithm mismatch on real K, or "
                    "the algorithm itself failing post-RoPE Qwen2.5).")
        verdict = "FAIL_BOTH"
        rc = 1
    print(decision)
    print()

    if args.output is not None:
        summary = {
            "phase": "6.4",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "context_length_chars": 32000,
            "needle_samples_per_fraction": 24,  # 8 samples × 3 depths
            "gates": {
                "needle_accuracy_min":  NEEDLE_ACCURACY_PASS,
                "entropy_collapse_max": ENTROPY_COLLAPSE_PASS,
                "repeated_token_max":   REPEATED_TOKEN_PASS,
            },
            "rows": rows,
            "verdict": verdict,
            "decision": decision,
        }
        args.output.write_text(json.dumps(summary, indent=2))
        print(f"Summary written to: {args.output}")

    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
