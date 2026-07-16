#!/usr/bin/env python3
"""KVPro V3 Step-0 — Part H analyser: classify the INT4 unzip as MEMORY-BOUND /
COMPUTE-BOUND / BOTH-TIGHTENABLE from the two-half-kernel probe (unzip_bound_probe.py),
and map the verdict to the actionable lever.

PRIMARY verdict = the three MEASURED times (fetch f, math m, full F) at the decision
context (the largest measured — least launch/timer noise). NO peak assumptions:
  F <= HIDE*max(f,m) and f >= OVR*m   -> MEMORY-BOUND   (math hides under fetch)
  F <= HIDE*max(f,m) and m >= OVR*f   -> COMPUTE-BOUND  (fetch hides under math)
  F >= ADD*(f+m)                       -> BOTH-TIGHTENABLE (serial; neither hides)
  else                                 -> PARTIALLY-OVERLAPPED

SECONDARY roofline CROSS-CHECK (needs peak assumptions, corroborates only):
  achieved read GB/s = fetch_bytes / f;  util = achieved / peak_HBM.
  memory-bound & util >= SAT_HI -> HBM-SATURATED  (lever: faster HBM — H100/H200; layout won't help)
  memory-bound & util <= SAT_LO -> HBM-UNSATURATED (lever: coalesce/compact the streams)

ABLATION: FULL_full - FULL_compact = the route-A full-fp16-K penalty (what a compact-protect
read kernel would remove). Reported as a % of the full-kernel time.

All thresholds are FROZEN below (DECISION_THRESHOLDS.md) BEFORE any GPU number is viewed.
Pure-CPU + deterministic (test_unzip_probe_cpu.py); prints/propagates UNAVAILABLE, never fabricates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# ---- FROZEN classification thresholds (pre-registered; see DECISION_THRESHOLDS.md) ----
OVR = 1.5        # one side must be >= 1.5x the other to "dominate"
HIDE = 1.25      # FULL within 1.25x max(f,m) => the smaller op is hidden (overlapped)
ADD = 0.75       # FULL >= 0.75x (f+m) => times roughly ADD (serial; neither hidden)
SAT_HI = 0.60    # achieved read BW >= 60% of peak HBM => bandwidth-saturated
SAT_LO = 0.40    # achieved read BW <= 40% of peak HBM => bandwidth-under-utilised

# ---- FROZEN 6F-A gates (pre-registered; DECISION_THRESHOLDS.md Part 6F-A) ----
READ_GAIN_MIN = 0.20     # page-local layout must cut fetch latency by >= 20% (Route-C read gate)
AGG_PROJ_MIN = 0.15      # projected aggregate-TPS improvement must be >= 15% to authorise 6F-C
WRITE_COST_MAX = 0.25    # added per-token write cost must be < 25% of the read-side gain (append spike)

# Projection shares (MODELED assumptions — the decode-kernel breakdown is UNAVAILABLE without
# ncu/production nsys; overridable, and auto-loaded from a stage_summary.json when present).
# projected_aggregate ~= unzip_full_improvement x alpha x beta x realizable, where
#   alpha = unzip-read share of the decode-attention kernel time,
#   beta  = decode-attention kernel share of the whole decode step,
#   realizable = implementation-loss factor (<= 1).
_PROJ = {
    "optimistic":  {"alpha": 0.90, "beta": 0.70, "realizable": 0.90},
    "default":     {"alpha": 0.70, "beta": 0.50, "realizable": 0.70},
    "conservative": {"alpha": 0.50, "beta": 0.30, "realizable": 0.60},
}

# Peak table (DEFAULT; overridable by --peak-hbm-gbps / --peak-fp32-tflops). Matched by
# family token(s) against the real torch device name (which often lacks SXM/PCIe, e.g.
# "NVIDIA H100 80GB HBM3") — first rule whose ALL substrings appear wins, most specific
# first. The three-times verdict does NOT use these; only the roofline cross-check does.
_PEAKS = [
    (("A100", "40GB"), {"hbm_gbps": 1555.0, "fp32_tflops": 19.5}, "A100-40GB"),
    (("A100",),        {"hbm_gbps": 2039.0, "fp32_tflops": 19.5}, "A100-80GB-SXM"),
    (("H100", "PCIE"), {"hbm_gbps": 2000.0, "fp32_tflops": 51.0}, "H100-PCIe"),
    (("H100", "NVL"),  {"hbm_gbps": 3900.0, "fp32_tflops": 67.0}, "H100-NVL"),
    (("H100",),        {"hbm_gbps": 3350.0, "fp32_tflops": 67.0}, "H100-SXM"),
    (("H200",),        {"hbm_gbps": 4800.0, "fp32_tflops": 67.0}, "H200-SXM"),
    (("A6000",),       {"hbm_gbps": 768.0,  "fp32_tflops": 38.7}, "A6000"),
    (("L40",),         {"hbm_gbps": 864.0,  "fp32_tflops": 90.5}, "L40S"),
]
_DEFAULT_PEAK = {"hbm_gbps": 2039.0, "fp32_tflops": 19.5, "assumed": "A100-SXM4-80GB"}


def peaks_for(device_name, override_hbm=None, override_fp32=None):
    up = (device_name or "").upper()
    match = None
    for subs, pk, label in _PEAKS:
        if all(s in up for s in subs):
            match = (pk, label)
            break
    if match:
        base = dict(match[0]); base["matched_device"] = match[1]
    else:
        base = {"hbm_gbps": _DEFAULT_PEAK["hbm_gbps"], "fp32_tflops": _DEFAULT_PEAK["fp32_tflops"],
                "matched_device": f"UNKNOWN({device_name}) -> default {_DEFAULT_PEAK['assumed']}"}
    if override_hbm:
        base["hbm_gbps"] = float(override_hbm); base["matched_device"] += " +hbm-override"
    if override_fp32:
        base["fp32_tflops"] = float(override_fp32); base["matched_device"] += " +fp32-override"
    return base


def classify_times(f, m, F):
    """PRIMARY verdict from three times (ms). No peak assumptions. Returns a dict."""
    if not all(isinstance(x, (int, float)) and x > 0 for x in (f, m, F)):
        return {"verdict": "UNAVAILABLE", "reason": "non-positive/missing time(s)"}
    hi, lo = max(f, m), min(f, m)
    dominant = ("memory" if f >= OVR * m else "compute" if m >= OVR * f else "balanced")
    # HIDDEN is tested BEFORE serial: when one side is tiny, F ~= the larger AND F > ADD*(f+m)
    # simultaneously (f+m ~= the larger), so the hidden regime must win — it's the memory/
    # compute-bound signal. Serial only applies when F genuinely approaches f+m with neither hidden.
    if F <= HIDE * hi:
        overlap = "hidden"
        verdict = {"memory": "MEMORY-BOUND", "compute": "COMPUTE-BOUND",
                   "balanced": "BALANCED-OVERLAPPED"}[dominant]
    elif F >= ADD * (f + m):
        overlap, verdict = "serial", "BOTH-TIGHTENABLE"
    else:
        overlap = "partial"
        verdict = {"memory": "MEMORY-BOUND", "compute": "COMPUTE-BOUND",
                   "balanced": "PARTIALLY-OVERLAPPED"}[dominant]
    return {"verdict": verdict, "dominant": dominant, "overlap": overlap,
            "fetch_ms": round(f, 5), "math_ms": round(m, 5), "full_ms": round(F, 5),
            "fetch_over_math": round(f / m, 3), "full_over_max": round(F / hi, 3),
            "full_over_sum": round(F / (f + m), 3)}


def roofline(model, f_ms, m_ms, F_ms, peak):
    """Cross-check: achieved read GB/s vs peak HBM; achieved dequant GFLOP/s vs peak fp32."""
    if not model or not all(isinstance(x, (int, float)) and x > 0 for x in (f_ms, m_ms, F_ms)):
        return {"label": "UNAVAILABLE"}
    B = model["total_fetch_bytes"]; FL = model["total_dequant_flops"]
    read_gbps = B / (f_ms * 1e-3) / 1e9
    full_gbps = B / (F_ms * 1e-3) / 1e9
    math_gflops = FL / (m_ms * 1e-3) / 1e9
    util = read_gbps / peak["hbm_gbps"]
    ai = FL / B
    ridge = peak["fp32_tflops"] * 1e3 / peak["hbm_gbps"]     # FLOP/byte (TFLOP/s*1e3 -> GFLOP/s)
    return {
        "label": "MODELED-x-MEASURED",
        "achieved_read_gbps": round(read_gbps, 1), "full_effective_gbps": round(full_gbps, 1),
        "achieved_dequant_gflops": round(math_gflops, 1),
        "peak_hbm_gbps": peak["hbm_gbps"], "peak_fp32_gflops": round(peak["fp32_tflops"] * 1e3, 1),
        "hbm_utilization": round(util, 3),
        "arithmetic_intensity_flop_per_byte": round(ai, 4),
        "roofline_ridge_flop_per_byte": round(ridge, 2),
        "roofline_region": "memory" if ai < ridge else "compute",
        "bandwidth_state": ("SATURATED" if util >= SAT_HI else
                            "UNDER-UTILISED" if util <= SAT_LO else "MID"),
    }


def _lever(verdict, roof, ablation_pct):
    if verdict == "MEMORY-BOUND":
        if roof.get("bandwidth_state") == "SATURATED":
            base = ("HBM-bound and SATURATED: the unzip is moving bytes near peak HBM. The lever is "
                    "faster memory (H100/H200 HBM3e), NOT layout — coalescing a saturated bus won't help.")
        elif roof.get("bandwidth_state") == "UNDER-UTILISED":
            base = ("Bandwidth-bound but UNDER-UTILISED: the scattered packed/scale/xmin/protect reads "
                    "waste HBM. The lever is coalescing/compacting the streams (compact-protect read "
                    "kernel, densified layout) — a 6F-style read fusion, before buying hardware.")
        else:
            base = ("Memory-bound (mid utilisation): both a compact/coalesced read kernel AND faster HBM "
                    "help; measure the compact-protect ablation before committing.")
        if isinstance(ablation_pct, (int, float)) and ablation_pct >= 15.0:
            base += (f" The full-fp16-K protect load alone is {ablation_pct}% of the route-A full time — "
                     "a compact-protect sidecar read is the first, format-preserving win.")
        return base
    if verdict == "COMPUTE-BOUND":
        return ("Compute-bound: the dequant affine (code*scale+xmin + select), not the fetch, is the tax. "
                "Levers: cheaper per-element math (fuse the affine, drop xmin where quality permits), or "
                "native low-precision decode (int8 tensor path). Faster HBM would NOT help.")
    if verdict == "BOTH-TIGHTENABLE":
        return ("Serial fetch+math: neither hides the other, so BOTH are on the critical path. A fused "
                "read kernel that overlaps the packed-stream fetch with the dequant (software pipelining) "
                "can recover up to the smaller of the two — the largest structural win available here.")
    return ("Overlapped/mixed: fetch and math partially hide each other; no single dominant lever. Re-check "
            "at the largest context and confirm the roofline region before authorising a kernel.")


def _bw(model, ms):
    if not model or not (isinstance(ms, (int, float)) and ms > 0):
        return None
    return round(model["total_fetch_bytes"] / (ms * 1e-3) / 1e9, 1)


def project_aggregate(unzip_improvement, shares_override=None):
    """MODELED aggregate-TPS projection from the MEASURED unzip full-time improvement, across the
    conservative/default/optimistic share scenarios. Returns the three numbers + a gate verdict
    (PASS if even conservative clears AGG_PROJ_MIN; FAIL if even optimistic cannot; else
    PROVISIONAL — needs a measured decode-attention share). Never fabricates a measured share."""
    scen = {}
    for name, s in _PROJ.items():
        sh = dict(s)
        if shares_override:
            sh.update({k: v for k, v in shares_override.items() if v is not None})
        scen[name] = round(unzip_improvement * sh["alpha"] * sh["beta"] * sh["realizable"], 4)
    # FAIL if even the optimistic shares miss the gate; PASS if the CENTRAL (default) estimate
    # clears it; PROVISIONAL if only optimistic clears (measure the real decode shares to decide).
    if scen["optimistic"] < AGG_PROJ_MIN:
        verdict = "FAIL"
    elif scen["default"] >= AGG_PROJ_MIN:
        verdict = "PASS"
    else:
        verdict = "PROVISIONAL"
    return {"label": "MODELED", "unzip_full_improvement": round(unzip_improvement, 4),
            "scenarios_pct": {k: round(v * 100, 2) for k, v in scen.items()},
            "gate_min_pct": round(AGG_PROJ_MIN * 100, 1), "gate_verdict": verdict,
            "shares_assumed": _PROJ, "shares_override": shares_override or {},
            "note": "MODELED (alpha=unzip-read share of decode-attn kernel; beta=decode-attn share of "
                    "step; realizable). The decode breakdown is UNAVAILABLE without ncu/nsys; supply "
                    "--decode-attn-share (beta) / --unzip-share (alpha) or a stage_summary to firm this up."}


def sixfa_analysis(per, ctxs, dc, peak, shares_override=None):
    """6F-A: page-local (per-head-contiguous) vs current (S,H,*) layout — read/full improvement,
    effective bandwidth, oracle, the >=20% read gate, and the aggregate projection."""
    row = per[str(dc)]
    fc, fp = row.get("fetch_only_ms"), row.get("fetch_pagelocal_ms")
    Fc, Fp = row.get("full_compact_ms"), row.get("full_pagelocal_ms")
    oracle = row.get("oracle_max_abs_diff")
    if not all(isinstance(x, (int, float)) for x in (fc, fp, Fc, Fp)):
        return {"label": "UNAVAILABLE", "reason": "probe lacks page-local timings (rerun the probe)"}
    read_gain = (fc - fp) / fc if fc > 0 else float("nan")
    full_gain = (Fc - Fp) / Fc if Fc > 0 else float("nan")
    model = row.get("model_compact")
    per_ctx_gain = {}
    for c in ctxs:
        rr = per[str(c)]
        a, b = rr.get("fetch_only_ms"), rr.get("fetch_pagelocal_ms")
        per_ctx_gain[str(c)] = round((a - b) / a, 4) if isinstance(a, (int, float)) and a > 0 else None
    read_pass = bool(read_gain >= READ_GAIN_MIN)
    proj = project_aggregate(max(full_gain, 0.0), shares_override)
    oracle_ok = isinstance(oracle, (int, float)) and abs(oracle) < 1e-6
    return {
        "label": "GPU-measured", "decision_context": dc,
        "oracle_max_abs_diff": oracle, "oracle_ok": oracle_ok,
        "current": {"fetch_ms": fc, "full_ms": Fc, "eff_read_gbps": _bw(model, fc),
                    "hbm_util": round(_bw(model, fc) / peak["hbm_gbps"], 3) if _bw(model, fc) else None},
        "pagelocal": {"fetch_ms": fp, "full_ms": Fp, "eff_read_gbps": _bw(model, fp),
                      "hbm_util": round(_bw(model, fp) / peak["hbm_gbps"], 3) if _bw(model, fp) else None},
        "read_improvement_pct": round(read_gain * 100, 2),
        "full_improvement_pct": round(full_gain * 100, 2),
        "read_improvement_by_context_pct": {k: (round(v * 100, 2) if v is not None else None)
                                            for k, v in per_ctx_gain.items()},
        "read_gate_min_pct": round(READ_GAIN_MIN * 100, 1), "read_gate_pass": read_pass,
        "aggregate_projection": proj,
        "gates_6fa": {"read_ge_20pct": read_pass, "aggregate_ge_15pct": proj["gate_verdict"],
                      "oracle_exact": oracle_ok,
                      "write_lt_25pct_of_gain": "SEE append_spike (09_append_feasibility_spike.py)"},
        "note": "Same values in both layouts (oracle must be 0). Effective BW = modeled bytes / measured "
                "fetch (transaction efficiency proper needs ncu, blocked). read_gate is the Route-C read "
                "condition; aggregate projection is MODELED; write cost is measured by the append spike.",
    }


def analyse(probe, override_hbm=None, override_fp32=None, decision_ctx=None, shares_override=None):
    if not probe or probe.get("label") != "GPU-measured":
        return {"label": probe.get("label", "UNAVAILABLE") if probe else "UNAVAILABLE",
                "verdict": "UNAVAILABLE",
                "reason": (probe or {}).get("error", "no GPU-measured probe")}
    per = probe.get("per_ctx", {})
    ctxs = sorted((int(k) for k in per), key=int)
    if not ctxs:
        return {"label": "UNAVAILABLE", "verdict": "UNAVAILABLE", "reason": "empty per_ctx"}
    dc = int(decision_ctx) if decision_ctx else ctxs[-1]        # largest = least noise
    row = per[str(dc)]
    peak = peaks_for((probe.get("device") or {}).get("name"), override_hbm, override_fp32)

    f, m = row.get("fetch_only_ms"), row.get("math_only_ms")
    Fc, Ff = row.get("full_compact_ms"), row.get("full_fullprotect_ms")
    primary = classify_times(f, m, Fc)                          # production compact path
    roof = roofline(row.get("model_compact"), f, m, Fc, peak)

    ablation_pct = None
    if isinstance(Ff, (int, float)) and isinstance(Fc, (int, float)) and Ff > 0:
        ablation_pct = round(100.0 * (Ff - Fc) / Ff, 2)         # fp16-pool share of route-A full

    lever = _lever(primary.get("verdict"), roof, ablation_pct)
    # per-context table for the trend (verdict can flip with launch noise at small ctx)
    trend = {}
    for c in ctxs:
        r = per[str(c)]
        trend[str(c)] = classify_times(r.get("fetch_only_ms"), r.get("math_only_ms"),
                                       r.get("full_compact_ms")).get("verdict")
    sixfa = sixfa_analysis(per, ctxs, dc, peak, shares_override)
    return {
        "label": "GPU-measured", "decision_context": dc, "device": probe.get("device"),
        "peaks_used": peak, "primary_compact_path": primary, "roofline_crosscheck": roof,
        "route_a_fp16_pool_ablation": {
            "full_compact_ms": Fc, "full_fullprotect_ms": Ff,
            "fp16_pool_penalty_pct_of_route_a_full": ablation_pct,
            "note": "FULL_full - FULL_compact = the int4_fused_attention_kernel.py:140 full-fp16-K load; "
                    "a compact-protect read kernel removes it. Production (6c.3C) already stores compact."},
        "verdict": primary.get("verdict"), "lever": lever,
        "verdict_by_context": trend,
        "sixfa_pagelocal": sixfa,
        "thresholds": {"OVR": OVR, "HIDE": HIDE, "ADD": ADD, "SAT_HI": SAT_HI, "SAT_LO": SAT_LO,
                       "READ_GAIN_MIN": READ_GAIN_MIN, "AGG_PROJ_MIN": AGG_PROJ_MIN,
                       "WRITE_COST_MAX": WRITE_COST_MAX},
    }


def _fmt(d):
    if d.get("label") != "GPU-measured":
        return f"[{d.get('verdict', 'UNAVAILABLE')}] {d.get('reason', '')}"
    p = d["primary_compact_path"]; r = d["roofline_crosscheck"]; ab = d["route_a_fp16_pool_ablation"]
    lines = [
        f"VERDICT (compact/production unzip @ ctx={d['decision_context']}): {d['verdict']}",
        f"  three-times: fetch={p['fetch_ms']}ms math={p['math_ms']}ms full={p['full_ms']}ms  "
        f"(f/m={p['fetch_over_math']}, F/max={p['full_over_max']}, F/sum={p['full_over_sum']}; "
        f"dominant={p['dominant']}, overlap={p['overlap']})",
    ]
    if r.get("label") != "UNAVAILABLE":
        lines.append(f"  roofline x-check [{d['peaks_used']['matched_device']}]: read {r['achieved_read_gbps']} "
                     f"GB/s = {int(r['hbm_utilization']*100)}% of {r['peak_hbm_gbps']} peak ({r['bandwidth_state']}); "
                     f"dequant {r['achieved_dequant_gflops']} GFLOP/s; AI={r['arithmetic_intensity_flop_per_byte']} "
                     f"vs ridge {r['roofline_ridge_flop_per_byte']} ({r['roofline_region']}-region)")
    lines.append(f"  fp16-pool ablation: compact={ab['full_compact_ms']}ms full-protect={ab['full_fullprotect_ms']}ms "
                 f"-> fp16 pool = {ab['fp16_pool_penalty_pct_of_route_a_full']}% of route-A full")
    lines.append(f"  verdict-by-context: {d['verdict_by_context']}")
    lines.append(f"  LEVER: {d['lever']}")
    s = d.get("sixfa_pagelocal", {})
    if s.get("label") == "GPU-measured":
        cur, pl = s["current"], s["pagelocal"]
        proj = s["aggregate_projection"]
        lines += [
            "",
            f"6F-A page-local layout @ ctx={s['decision_context']} (oracle diff={s['oracle_max_abs_diff']:.1e}, "
            f"exact={s['oracle_ok']}):",
            f"  fetch: current={cur['fetch_ms']}ms ({cur['eff_read_gbps']} GB/s, {int((cur['hbm_util'] or 0)*100)}% peak) "
            f"-> pagelocal={pl['fetch_ms']}ms ({pl['eff_read_gbps']} GB/s, {int((pl['hbm_util'] or 0)*100)}% peak)",
            f"  READ IMPROVEMENT = {s['read_improvement_pct']}%  vs gate >= {s['read_gate_min_pct']}%  "
            f"-> {'PASS' if s['read_gate_pass'] else 'FAIL'}   (full-unzip improvement {s['full_improvement_pct']}%)",
            f"  by-context: {s['read_improvement_by_context_pct']}",
            f"  aggregate projection [MODELED] cons/def/opt = "
            f"{proj['scenarios_pct']['conservative']}/{proj['scenarios_pct']['default']}/"
            f"{proj['scenarios_pct']['optimistic']}%  vs gate >= {proj['gate_min_pct']}% -> {proj['gate_verdict']}",
            f"  6F-A gates: read>=20%={s['gates_6fa']['read_ge_20pct']} | agg>=15%={s['gates_6fa']['aggregate_ge_15pct']} "
            f"| oracle_exact={s['gates_6fa']['oracle_exact']} | write<25%: run the append spike",
        ]
    elif s:
        lines.append(f"6F-A page-local: {s.get('reason', 'UNAVAILABLE')}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Classify the INT4 unzip as memory/compute-bound")
    ap.add_argument("--probe", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    "runs", "unzip_bound.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "runs", "unzip_bound_verdict.json"))
    ap.add_argument("--peak-hbm-gbps", type=float)
    ap.add_argument("--peak-fp32-tflops", type=float)
    ap.add_argument("--decision-ctx", type=int)
    ap.add_argument("--unzip-share", type=float, help="alpha: unzip-read share of decode-attn kernel (MEASURED if known)")
    ap.add_argument("--decode-attn-share", type=float, help="beta: decode-attn kernel share of the step (MEASURED if known)")
    a = ap.parse_args(argv)
    probe = json.load(open(a.probe)) if os.path.exists(a.probe) else None
    shares = {}
    if a.unzip_share is not None:
        shares["alpha"] = a.unzip_share
    if a.decode_attn_share is not None:
        shares["beta"] = a.decode_attn_share
    d = analyse(probe, a.peak_hbm_gbps, a.peak_fp32_tflops, a.decision_ctx, shares or None)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(d, open(a.out, "w"), indent=2)
    print(_fmt(d))
    print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
