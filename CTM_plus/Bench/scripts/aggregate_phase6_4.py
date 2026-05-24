#!/usr/bin/env python3
"""aggregate_phase6_4.py — Phase 6.4 sweep aggregator + decision rule.

Per-fraction needle test results from track_e_long_context.py are
flat-rowed in `needle_rows[]`, one entry per (cache_type,
context_length, depth_percent, sample_idx) trial. We filter cache_type
∈ {"baseline", "int4-per-channel"}, aggregate, and apply a
delta-based decision rule against the FP16 baseline (NOT against
absolute thresholds — those were 7k-token-calibrated and don't transfer
to long context, where baseline itself has 33% entropy_collapse and 30%
repeated_token_rate per the 30k-token rerun).

Decision rule (revised after the 30k-token sweep):

  PRIMARY GATE (fail-on-miss):
    needle_accuracy_delta >= -0.05    (vs FP16 baseline; 1 needle out of
                                       24 may drift before the gate fails)

  SUPPORTING DIAGNOSTICS (printed, don't fail by themselves):
    repeated_token_mean_delta vs baseline
    first_stutter delta vs baseline
    entropy_collapse_delta vs baseline    (NOT a gate — at long context
                                           more protect -> sharper attn
                                           -> faster post-answer collapse;
                                           higher than baseline doesn't
                                           mean broken)

  EXCEPTION — entropy_collapse becomes a gate ONLY IF combined with
              degraded repeat:
    decode_loop = (repeated_token_delta > +0.10 AND
                   entropy_collapse_delta > +0.20)
    Fires for the rare case where the model loops/degenerates but
    happens to land on the correct needle by luck (so the primary
    needle gate doesn't catch it). Both signals must spike together
    to call it a real loop.

Outcomes (mechanical):

  4% PRIMARY pass AND no decode-loop      -> Phase 5 default = 0.04
  4% PRIMARY fail, 8% PRIMARY pass        -> Phase 5 default = 0.08
  Neither 4% nor 8% PRIMARY pass          -> STOP Phase 5, debug
"""

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FRACTIONS = [0.0, 0.02, 0.04, 0.08]

NEEDLE_DELTA_GATE         = -0.05
DECODE_LOOP_REPEAT_DELTA  = +0.10
DECODE_LOOP_ENTROPY_DELTA = +0.20


def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not rows:
        return {
            "n_trials":               0,
            "needle_accuracy":        None,
            "entropy_collapse":       None,
            "repeated_token_mean":    None,
            "first_stutter_earliest": None,
            "decode_tokens_per_s_mean": None,
        }
    stutters = [r["first_stutter_position"] for r in rows
                if r.get("first_stutter_position", -1) >= 0]
    return {
        "n_trials":               len(rows),
        "needle_accuracy":        sum(1 for r in rows if r["correct"]) / len(rows),
        "entropy_collapse":       sum(1 for r in rows if r["decode_entropy_collapsed"]) / len(rows),
        "repeated_token_mean":    statistics.mean(r["repeated_token_rate"] for r in rows),
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


def _fmt(v, width: int = 8, sign: bool = False) -> str:
    if v is None:
        return "MISSING".rjust(width)
    if isinstance(v, float):
        if sign:
            return f"{v:+.4f}".rjust(width)
        return f"{v:.4f}".rjust(width)
    return str(v).rjust(width)


def _check_pass(m_int4: Optional[Dict],
                m_base: Optional[Dict]) -> Tuple[bool, List[str], List[str]]:
    """Returns (pass, fail_reasons, advisory_notes).

    Advisory notes are printed alongside but do NOT cause failure unless
    they constitute a decode-loop pattern (both repeat and entropy
    spiked together).
    """
    if m_int4 is None or m_base is None or m_int4["n_trials"] == 0:
        return False, ["missing data"], []
    if m_int4["needle_accuracy"] is None or m_base["needle_accuracy"] is None:
        return False, ["missing needle_accuracy"], []

    needle_delta = m_int4["needle_accuracy"] - m_base["needle_accuracy"]
    rep_delta    = m_int4["repeated_token_mean"] - m_base["repeated_token_mean"]
    ent_delta    = m_int4["entropy_collapse"]    - m_base["entropy_collapse"]

    fail_reasons: List[str] = []
    advisory: List[str] = []

    # PRIMARY GATE.
    if needle_delta < NEEDLE_DELTA_GATE:
        fail_reasons.append(
            f"needle_accuracy_delta {needle_delta:+.4f} < {NEEDLE_DELTA_GATE} "
            f"(int4 {m_int4['needle_accuracy']:.4f} vs baseline "
            f"{m_base['needle_accuracy']:.4f})"
        )

    # DIAGNOSTICS.
    advisory.append(
        f"repeated_token_mean_delta = {rep_delta:+.4f} "
        f"(int4 {m_int4['repeated_token_mean']:.4f} vs "
        f"baseline {m_base['repeated_token_mean']:.4f})"
    )
    stutter_delta = (m_int4["first_stutter_earliest"]
                     - m_base["first_stutter_earliest"])
    advisory.append(
        f"first_stutter_delta = {stutter_delta:+d} "
        f"(int4 {m_int4['first_stutter_earliest']} vs "
        f"baseline {m_base['first_stutter_earliest']})"
    )
    advisory.append(
        f"entropy_collapse_delta = {ent_delta:+.4f} "
        f"(int4 {m_int4['entropy_collapse']:.4f} vs "
        f"baseline {m_base['entropy_collapse']:.4f})  DIAGNOSTIC ONLY"
    )

    # EXCEPTION — entropy_collapse becomes a gate combined with repeat.
    if rep_delta > DECODE_LOOP_REPEAT_DELTA and ent_delta > DECODE_LOOP_ENTROPY_DELTA:
        fail_reasons.append(
            f"decode-loop pattern: repeat +{rep_delta:.4f} AND entropy "
            f"+{ent_delta:.4f} (both > gates {DECODE_LOOP_REPEAT_DELTA}/"
            f"{DECODE_LOOP_ENTROPY_DELTA}) — model may be looping despite "
            f"correct needle"
        )

    return (len(fail_reasons) == 0, fail_reasons, advisory)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--indir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    rows: List[Dict[str, Any]] = []
    context_length_tokens: Optional[int] = None
    context_length_chars:  Optional[int] = None

    for frac in FRACTIONS:
        path = args.indir / f"protect_{frac}.json"
        if not path.exists():
            rows.append({
                "fraction": frac, "metrics_int4": None,
                "metrics_baseline": None, "pass": False,
                "fail_reasons": ["file missing"], "advisory": [],
            })
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            rows.append({
                "fraction": frac, "metrics_int4": None,
                "metrics_baseline": None, "pass": False,
                "fail_reasons": [f"bad json: {e}"], "advisory": [],
            })
            continue
        by_ct = _extract_rows_by_cache_type(payload)
        # Capture context info on the first valid file.
        if context_length_tokens is None:
            for r in payload.get("needle_rows", []):
                if "context_length_tokens" in r:
                    context_length_tokens = r["context_length_tokens"]
                    context_length_chars  = r.get("context_length_chars")
                    break
        m_int4 = _aggregate(by_ct["int4-per-channel"])
        m_base = _aggregate(by_ct["baseline"])
        ok, fail_reasons, advisory = _check_pass(m_int4, m_base)
        rows.append({
            "fraction": frac, "metrics_int4": m_int4,
            "metrics_baseline": m_base, "pass": ok,
            "fail_reasons": fail_reasons, "advisory": advisory,
        })

    print()
    print("=" * 86)
    print("Phase 6.4 sweep — Qwen2.5-7B")
    if context_length_chars is not None:
        print(f"  context_length: {context_length_chars} chars  ~=  "
              f"{context_length_tokens} tokens")
    print("=" * 86)
    print(f"{'Frac':>5} | {'Cache':>17} | {'NeedleAcc':>9} | "
          f"{'EntCol':>7} | {'RepRate':>7} | {'FirstStut':>9} | {'tok/s':>6}")
    print("-" * 86)
    for row in rows:
        frac_str = f"{row['fraction']*100:>4.1f}%"
        # baseline first, then int4.
        for ct, label, m in [
            ("baseline", "baseline (FP16)", row["metrics_baseline"]),
            ("int4",     "int4-per-channel", row["metrics_int4"]),
        ]:
            if m is None or m["n_trials"] == 0:
                print(f"{frac_str:>5} | {label:>17} | "
                      + (" " * 56) + " MISSING")
                continue
            print(f"{frac_str:>5} | {label:>17} | "
                  f"{_fmt(m['needle_accuracy'], 9)} | "
                  f"{_fmt(m['entropy_collapse'], 7)} | "
                  f"{_fmt(m['repeated_token_mean'], 7)} | "
                  f"{_fmt(m['first_stutter_earliest'], 9)} | "
                  f"{_fmt(m['decode_tokens_per_s_mean'], 6)}")
        # Verdict + deltas (only if both metric sets are present).
        if row["metrics_int4"] and row["metrics_baseline"] \
                and row["metrics_int4"]["n_trials"] > 0:
            mi, mb = row["metrics_int4"], row["metrics_baseline"]
            needle_delta = mi["needle_accuracy"] - mb["needle_accuracy"]
            status = "PASS" if row["pass"] else "FAIL"
            print(f"      | int4-vs-baseline | needle_delta = "
                  f"{needle_delta:+.4f}  ({needle_delta*100:+.1f}%)   "
                  f"VERDICT: {status}")
            for line in row["advisory"]:
                print(f"      | (diagnostic)     | {line}")
            for reason in row["fail_reasons"]:
                print(f"      | (fail reason)    | {reason}")
        print()

    print(f"Primary gate:  needle_accuracy_delta >= {NEEDLE_DELTA_GATE}")
    print(f"Decode-loop:   fires only if repeat +{DECODE_LOOP_REPEAT_DELTA} "
          f"AND entropy +{DECODE_LOOP_ENTROPY_DELTA} simultaneously.")
    print(f"entropy_collapse alone is NOT a gate (high at long context even "
          f"on FP16 baseline).")
    print()

    p4 = next((r for r in rows if r["fraction"] == 0.04), None)
    p8 = next((r for r in rows if r["fraction"] == 0.08), None)
    p4_ok = p4 is not None and p4["pass"]
    p8_ok = p8 is not None and p8["pass"]

    print("=" * 86)
    print("Decision rule")
    print("=" * 86)
    if p4_ok:
        decision = ("PROCEED to Phase 5 with protect_fraction default = 0.04. "
                    "Expose 0.08 as a safe-mode config knob.")
        verdict = "PASS_4"
        rc = 0
    elif p8_ok:
        decision = ("4% fails primary gate but 8% passes — PROCEED to Phase 5 "
                    "with protect_fraction default = 0.08. Update "
                    "KERNEL_6C3C_DESIGN.md to record the policy shift.")
        verdict = "PASS_8_FAIL_4"
        rc = 0
    else:
        decision = ("Neither 4% nor 8% passes — STOP Phase 5. Debug the "
                    "native-kernel quality path (mask computation, kernel-"
                    "algorithm mismatch on real K, or algorithm failing "
                    "post-RoPE Qwen2.5).")
        verdict = "FAIL_BOTH"
        rc = 1
    print(decision)
    print()

    if args.output is not None:
        summary = {
            "phase": "6.4",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "context_length_chars":  context_length_chars,
            "context_length_tokens": context_length_tokens,
            "needle_samples_per_fraction": 24,
            "gates": {
                "needle_delta_min":         NEEDLE_DELTA_GATE,
                "decode_loop_repeat_delta": DECODE_LOOP_REPEAT_DELTA,
                "decode_loop_entropy_delta": DECODE_LOOP_ENTROPY_DELTA,
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
