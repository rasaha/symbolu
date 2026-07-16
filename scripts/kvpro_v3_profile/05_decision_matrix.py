#!/usr/bin/env python3
"""KVPro V3 Step-0 — Part G: decision matrix + single recommendation.

Consumes (any subset of) env_gate.json, stage_summary.json, cost_accounting.json, and the P8 quality
verdict, and emits a ranked candidate-project table plus EXACTLY ONE recommendation from:
  BUILD_GATHER_FIRST | BUILD_PROTECT_STREAM_FIRST | BUILD_COMBINED_KERNEL |
  FIX_PREREQUISITES_FIRST | NO_KERNEL_PROJECT_JUSTIFIED | INCONCLUSIVE

The recommendation is driven by MEASURED profile percentages, not prior expectations. With no measured
profile (blocked prereqs / not run) it returns FIX_PREREQUISITES_FIRST or INCONCLUSIVE — never a guess.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# ---- FROZEN decision thresholds (documented + justified in DECISION_THRESHOLDS.md, BEFORE results) ----
MIN_JUSTIFY_PCT = 8.0        # a removable bucket below this % of DECODE-KERNEL time can't justify a kernel
COMBINED_SPREAD_PCT = 8.0    # >=2 removable buckets each above this -> combined redesign
# Projected END-TO-END gain is bounded BELOW removable%: ~ removable% x decode_kernel_share x realizable.
# The ~0.27-0.30x decode-recovery ceiling caps the realizable fraction; we freeze a conservative cap and an
# end-to-end floor Z. MIN_JUSTIFY_PCT=8 is chosen so 8% x 0.5 ~= 4% clears Z=3% with margin.
REALIZABLE_FRACTION_CAP = 0.5
Z_MIN_PROJECTED_END_TO_END_PCT = 3.0

CANDIDATES = [
    "in_kernel_paged_gather_only",
    "store_as_consumed_layout_only",
    "combined_gather_plus_store_as_consumed",
    "dense_coalesced_bf16_protected_stream",
    "dense_coalesced_int8_protected_stream",
    "combined_gather_layout_protected_redesign",
    "phase6f_continuation",
    "other_from_profile",
]


def _pct(stages, name):
    v = stages.get(name, {}).get("pct_of_kernel_time")
    return v if isinstance(v, (int, float)) else None


def decide(env=None, stages=None, p8=None, cost=None):
    env = env or {}; p8 = p8 or {}; cost = cost or {}
    s = (stages or {}).get("stages", {})
    have_profile = bool(s) and (stages or {}).get("label") == "GPU-measured"

    # measured removable buckets (None if not measured)
    gather = _pct(s, "gather")
    staging = (_pct(s, "staging") or 0) + (_pct(s, "splice") or 0) if have_profile else None
    protect = _pct(s, "protect")
    attention = _pct(s, "attention")
    other = _pct(s, "other")
    gather_staging = None
    if have_profile:
        gather_staging = (gather or 0) + (staging or 0)

    p8_clean = p8.get("verdict") in ("P8_CLEAN", "GO") or p8.get("p8_quality_clean") is True
    p8_ran = bool(p8) and p8.get("verdict") not in (None, "NOT_RUN")

    # ----- ranked table (value = measured removable %, gated by quality/effort) -----
    def row(cid, value, qrisk, effort, ceiling_note):
        return {"candidate": cid, "measured_removable_pct": value, "quality_risk": qrisk,
                "engineering_effort": effort, "expected_ceiling_note": ceiling_note}
    NA = "UNAVAILABLE" if not have_profile else None
    ranked = [
        row("in_kernel_paged_gather_only", gather if have_profile else NA, "none", "medium",
            "removes host gather; bounded by redundant-staging fraction"),
        row("store_as_consumed_layout_only", staging if have_profile else NA, "none", "medium",
            "removes temp-buffer write/reread + splice; write-time cost shifts to prefill"),
        row("combined_gather_plus_store_as_consumed", gather_staging if have_profile else NA, "none", "medium-high",
            "route-A Triton already approximates this; measure it vs production"),
        row("dense_coalesced_bf16_protected_stream", protect if have_profile else NA, "none", "medium",
            "coalesces scattered protected reads; format unchanged"),
        row("dense_coalesced_int8_protected_stream",
            protect if have_profile else NA, "low (needs P8 quality PASS)", "medium",
            "halves protected bytes + coalesces; GATED on P8 fake-quant quality"),
        row("combined_gather_layout_protected_redesign",
            (gather_staging + (protect or 0)) if have_profile and gather_staging is not None else NA,
            "low", "high", "largest surface; highest effort; still under ~0.27-0.30x decode ceiling"),
        row("phase6f_continuation", other if have_profile else NA, "none", "low",
            "keep the existing route-A read-fusion path"),
        row("other_from_profile", other if have_profile else NA, "unknown", "unknown",
            "only if profiling surfaces an unaccounted tall pole"),
    ]
    # sort measured rows by value desc; UNAVAILABLE sinks to the bottom
    ranked.sort(key=lambda r: (r["measured_removable_pct"] if isinstance(r["measured_removable_pct"], (int, float)) else -1),
                reverse=True)

    # ----- single recommendation -----
    if not have_profile:
        prod = env.get("can_profile_production_kernel")
        triton = env.get("can_profile_triton_route_a")
        if prod is False and triton is False:
            rec, why = "FIX_PREREQUISITES_FIRST", (
                "No GPU profile available and neither the production fork nor the Triton route-A kernel "
                "is profilable. Restore prerequisites (see env_gate.json) before choosing a kernel project.")
        else:
            rec, why = "INCONCLUSIVE", (
                "Profilable kernel(s) exist but no stage_summary was provided. Run 01/02/03 + 04 first.")
        return {"recommendation": rec, "rationale": why, "ranked": ranked,
                "measured": {"have_profile": False}, "label": "NOT_MEASURED"}

    buckets = {"gather+staging": gather_staging or 0, "protected": protect or 0,
               "attention(fixed)": attention or 0, "other": other or 0}
    removable = {k: v for k, v in buckets.items() if k in ("gather+staging", "protected")}
    top_removable = max(removable.values()) if removable else 0
    big = [k for k, v in removable.items() if v >= COMBINED_SPREAD_PCT]

    if top_removable < MIN_JUSTIFY_PCT:
        rec = "NO_KERNEL_PROJECT_JUSTIFIED"
        why = (f"No removable bucket exceeds {MIN_JUSTIFY_PCT}% of kernel time "
               f"(gather+staging={gather_staging}, protected={protect}); time is dominated by "
               f"attention proper ({attention}%). A layout/gather kernel cannot pay off.")
    elif len(big) >= 2:
        rec = "BUILD_COMBINED_KERNEL"
        why = (f"Removable time is spread across multiple buckets each >{COMBINED_SPREAD_PCT}% "
               f"(gather+staging={gather_staging}, protected={protect}); a combined redesign captures both.")
    elif (protect or 0) >= (gather_staging or 0):
        rec = "BUILD_PROTECT_STREAM_FIRST"
        variant = "int8" if p8_clean else "bf16"
        why = (f"Scattered protected reads are the tallest removable pole ({protect}% vs gather+staging "
               f"{gather_staging}%). Densify/coalesce the protected stream ({variant}; "
               f"{'P8 quality PASS' if p8_clean else 'P8 not clean/!run -> keep bf16'}).")
    else:
        rec = "BUILD_GATHER_FIRST"
        why = (f"Gather+staging is the tallest removable pole ({gather_staging}% vs protected {protect}%). "
               f"In-kernel gather + store-as-consumed first (route-A Triton is the starting point).")

    return {"recommendation": rec, "rationale": why, "ranked": ranked,
            "measured": {"have_profile": True, "buckets": buckets, "p8_ran": p8_ran, "p8_clean": p8_clean,
                         "projected_end_to_end_pct_upper": round(top_removable * REALIZABLE_FRACTION_CAP, 2),
                         "z_floor_pct": Z_MIN_PROJECTED_END_TO_END_PCT},
            "label": "GPU-measured"}


def _load(p):
    return json.load(open(p)) if p and os.path.exists(p) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Step-0 decision matrix")
    ap.add_argument("--env"); ap.add_argument("--stages"); ap.add_argument("--p8"); ap.add_argument("--cost")
    ap.add_argument("--out", default="decision.json")
    a = ap.parse_args(argv)
    d = decide(_load(a.env), _load(a.stages), _load(a.p8), _load(a.cost))
    json.dump(d, open(a.out, "w"), indent=2)
    print(f"\nRECOMMENDATION: {d['recommendation']}  [{d['label']}]")
    print(f"  {d['rationale']}")
    print(f"{'candidate':44} {'removable%':>11} {'qrisk':>22} {'effort':>12}")
    for r in d["ranked"]:
        print(f"  {r['candidate']:42} {str(r['measured_removable_pct']):>11} "
              f"{r['quality_risk']:>22} {r['engineering_effort']:>12}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
