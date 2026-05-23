#!/usr/bin/env python3
"""aggregate_phase6_4.py — Phase 6.4 sweep aggregator + decision rule.

Reads per-fraction JSONs produced by apply_phase6_4_sweep.sh. The actual
schema (per `track_e_long_context.py` output) has a flat `needle_rows`
array; each row is one (cache_type, context_length, depth_percent,
sample_idx) trial with fields:

    cache_type            "baseline" | "int4-per-channel"
    context_length_chars  int   (e.g. 32000 — these are CHARS, not tokens)
    context_length_tokens int   (e.g. 6836 — actual token count)
    depth_percent         float
    sample_idx            int
    correct               bool
    first_stutter_position int  (-1 = no stutter detected)
    repeated_token_rate   float
    decode_entropy_mean   float
    decode_entropy_collapsed bool
    decode_tokens_per_s   float

For each fraction we filter cache_type="int4-per-channel" and aggregate.
Also surfaces the matching baseline metrics for context (the baseline
should be ~identical across fractions modulo seed noise, since it's the
same model on the same prompts — but we show it to confirm no harness
drift).

Decision rule (user-specified):
  - If 4% PASS       -> proceed to Phase 5 (default fraction 0.04)
  - If 4% FAIL, 8% PASS -> proceed to Phase 5 with configurable fraction,
                          default 0.08
  - If neither       -> stop Phase 5, debug

PASS criteria (per fraction, on int4-per-channel rows):
  - needle_accuracy_int4         >= 0.90  (most needles answered correctly)
  - entropy_collapse_rate_int4   <= 0.10  (decode entropy not collapsing)
  - repeated_token_mean_int4     <= 0.30  (decode not loopy; slightly
                                            looser than baseline because
                                            INT4 introduces some noise)

Also reports the int4-vs-baseline DELTA on needle accuracy so the
algorithm's quality cost is visible regardless of absolute thresholds.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FRACTIONS = [0.0, 0.02, 0.04, 0.08]

NEEDLE_ACCURACY_PASS   = 0.90
ENTROPY_COLLAPSE_PASS  = 0.10
REPEATED_TOKEN_PASS    = 0.30


def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not rows:
        return {
            "n_trials":            0,
            "needle_accuracy":     None,
            "entropy_collapse":    None,
            "repeated_token_mean": None,
            "first_stutter_earliest": None,
            "decode_tokens_per_s_mean": None,
        }
    stutters = [r["first_stutter_position"] for r in rows
                if r.get("first_stutter_position", -1) >= 0]
    return {
        "n_trials":            len(rows),
        "needle_accuracy":     sum(1 for r in rows if r["correct"]) / len(rows),
        "entropy_collapse":    sum(1 for r in rows if r["decode_entropy_collapsed"]) / len(rows),
        "repeated_token_mean": statistics.mean(r["repeated_token_rate"] for r in rows),
        "first_stutter_earliest": min(stutters) if stutters else -1,
        "decode_tokens_per_s_mean": statistics.mean(
            r["decode_tokens_per_s"] for r in rows
        ),
    }


def _extract_rows_by_cache_type(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out = {"baseline": [], "int4-per-channel": []}
    for row in payload.get("needle_rows", []):
        ct = row.get("cache_type")
        if ct in out:
            out[ct].append(row)
    return out


def _fmt(v, width: int = 8) -> str:
    if v is None:
        return "MISSING".rjust(width)
    if isinstance(v, float):
        return f"{v:.4f}".rjust(width)
    return str(v).rjust(width)


def _check_pass(m: Dict[str, Optional[float]]) -> Tuple[bool, List[str]]:
    reasons = []
    if m["needle_accuracy"] is None or m["needle_accuracy"] < NEEDLE_ACCURACY_PASS:
        reasons.append(f"needle_accuracy {m['needle_accuracy']} < {NEEDLE_ACCURACY_PASS}")
    if m["entropy_collapse"] is None or m["entropy_collapse"] > ENTROPY_COLLAPSE_PASS:
        reasons.append(f"entropy_collapse {m['entropy_collapse']} > {ENTROPY_COLLAPSE_PASS}")
    if m["repeated_token_mean"] is None or m["repeated_token_mean"] > REPEATED_TOKEN_PASS:
        reasons.append(f"repeated_token_mean {m['repeated_token_mean']} > {REPEATED_TOKEN_PASS}")
    return (len(reasons) == 0, reasons)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--indir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    rows: List[Dict[str, Any]] = []
    context_length_tokens = None
    for frac in FRACTIONS:
        path = args.indir / f"protect_{frac}.json"
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            rows.append({
                "fraction": frac, "metrics_int4": None,
                "metrics_baseline": None, "pass": False,
                "reasons": ["file missing"],
            })
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            print(f"BAD JSON: {path}: {e}", file=sys.stderr)
            rows.append({
                "fraction": frac, "metrics_int4": None,
                "metrics_baseline": None, "pass": False,
                "reasons": [f"bad json: {e}"],
            })
            continue
        by_ct = _extract_rows_by_cache_type(payload)
        if context_length_tokens is None:
            for r in payload.get("needle_rows", []):
                if "context_length_tokens" in r:
                    context_length_tokens = r["context_length_tokens"]
                    break
        m_int4 = _aggregate(by_ct["int4-per-channel"])
        m_base = _aggregate(by_ct["baseline"])
        ok, reasons = _check_pass(m_int4)
        rows.append({
            "fraction": frac, "metrics_int4": m_int4,
            "metrics_baseline": m_base, "pass": ok, "reasons": reasons,
        })

    print()
    print("=" * 78)
    print("Phase 6.4 sweep — Qwen2.5-7B")
    if context_length_tokens is not None:
        print(f"  context_length: 32000 chars  ~=  {context_length_tokens} tokens")
    print("=" * 78)
    print(f"{'Frac':>5} | {'Cache':>17} | {'NeedleAcc':>9} | {'EntCol':>7} | "
          f"{'RepRate':>7} | {'FirstStut':>9} | {'tok/s':>6} | Status")
    print("-" * 100)
    for row in rows:
        frac_str = f"{row['fraction']*100:>4.1f}%"
        for ct, label, m in [
            ("baseline", "baseline (FP16)", row["metrics_baseline"]),
            ("int4",     "int4-per-channel", row["metrics_int4"]),
        ]:
            if m is None or m["n_trials"] == 0:
                print(f"{frac_str:>5} | {label:>17} | "
                      + (" " * 65) + " | MISSING")
                continue
            status = ""
            if ct == "int4":
                status = "PASS" if row["pass"] else "FAIL"
            print(f"{frac_str:>5} | {label:>17} | "
                  f"{_fmt(m['needle_accuracy'], 9)} | "
                  f"{_fmt(m['entropy_collapse'], 7)} | "
                  f"{_fmt(m['repeated_token_mean'], 7)} | "
                  f"{_fmt(m['first_stutter_earliest'], 9)} | "
                  f"{_fmt(m['decode_tokens_per_s_mean'], 6)} | {status}")
        # int4-vs-baseline accuracy delta.
        mi, mb = row["metrics_int4"], row["metrics_baseline"]
        if mi and mb and mi["needle_accuracy"] is not None and mb["needle_accuracy"] is not None:
            delta = mi["needle_accuracy"] - mb["needle_accuracy"]
            print(f"      |  (int4-baseline) | needle_acc delta = "
                  f"{delta:+.4f}  ({delta*100:+.1f}%)")
        if not row["pass"]:
            for r in row["reasons"]:
                print(f"      | (fail reason)   | {r}")
        print()
    print(f"Gates (on int4 rows): needle_acc >= {NEEDLE_ACCURACY_PASS}, "
          f"ent_collapse <= {ENTROPY_COLLAPSE_PASS}, "
          f"rep_token <= {REPEATED_TOKEN_PASS}")
    print()

    # Decision rule.
    p4 = next((r for r in rows if r["fraction"] == 0.04), None)
    p8 = next((r for r in rows if r["fraction"] == 0.08), None)
    p4_ok = p4 is not None and p4["pass"]
    p8_ok = p8 is not None and p8["pass"]

    print("=" * 78)
    print("Decision rule")
    print("=" * 78)
    if p4_ok:
        decision = ("PROCEED to Phase 5 (vLLM integration) with "
                    "protect_fraction=0.04 default.")
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
            "context_length_tokens": context_length_tokens,
            "needle_samples_per_fraction": 24,
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
