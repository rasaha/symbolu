"""Phase 6M.7 — decode-time bucket attribution + frozen-threshold verdict.

Extends the 6M attribution (companion to PHASE_6M_ATTRIBUTION_FINDINGS.md, which
used torch.profiler kernel-NAME buckets) into a clean CODE-REGION split from the
already-wired `DecodeProfiler` (phase5b_backend_install.py). Ingests the per-region
CPU+GPU summary emitted by `bench_phase6_decode_phase_profile.py --json-out` and
attributes decode time to the five buckets the throughput-recovery plan cares about:

    write-path · decode-kernel · sidecar/gather · scheduler/host · memory-bandwidth

then applies the FROZEN decision thresholds (below) to name the top lever.

HARD RULES (match the plan's guardrails):
  * NO fabricated numbers. memory-bandwidth needs ncu (Test 1 roofline); ncu is
    blocked on the available pods (ERR_NVGPUCTRPERM), so it is reported UNAVAILABLE,
    never estimated.
  * The DecodeProfiler regions cover the int4 READ/WRITE attention path only — NOT
    the model GEMMs. So a bucket's share of the *instrumented int4 path* is an UPPER
    BOUND on its share of *end-to-end* decode (int4 path ⊆ end-to-end). We exploit
    that: a write-path share below the 10% threshold on the int4 path is DEFINITIVE
    that write is below 10% end-to-end (threshold #1 fails with certainty). The
    reverse (>= 10% on the int4 path) needs the end-to-end GPU total to decide.
  * Thresholds are frozen constants; they are not tunable from the CLI.

Usage (CPU, anywhere — no GPU):
    python CTM_plus/Bench/scripts/analyze_phase6m7_decode_attribution.py \
        --summary bench_out/phase6m7/decode_phase_profile.json \
        --roofline-verdict unknown \
        --out PHASE_6M7_decode_attribution_report.txt

Self-test (no files needed):
    python CTM_plus/Bench/scripts/analyze_phase6m7_decode_attribution.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_UNAVAIL = "UNAVAILABLE"

# --------------------------------------------------------------------------- #
# FROZEN decision thresholds — DO NOT loosen post-hoc (plan guardrail).
# Mirrors the user's gate:
#   (1) write-path >= 10% of end-to-end decode -> optimize write kernels first.
#   (2) decode-kernel / sidecar traffic dominates -> build compact-sidecar in-repo
#       decode kernel (6F) -- GATED on the Test-1 roofline verdict.
#   (3) capacity remains the aggregate limiter after throughput recovery ->
#       tighten the pool AFTERWARD (evaluated from the 6L/6M.6 capacity harness,
#       not this decode attribution; surfaced here as a note only).
# --------------------------------------------------------------------------- #
WRITE_PATH_MATERIAL_PCT = 10.0     # threshold (1)
READ_DOMINATES_PCT = 50.0          # (decode_kernel + sidecar_gather) share that
                                   # marks the read path as the top lever (2)
# Roofline (Test 1) verdicts that GREENLIGHT the read-path kernel rewrite (6F).
ROOFLINE_GREENLIGHT = {"compute-bound", "bandwidth-bound-uncoalesced"}
ROOFLINE_VALUES = ROOFLINE_GREENLIGHT | {
    "bandwidth-bound-coalesced", "latency/occupancy-bound", "unknown"}

# region-name (suffix after the `batched.`/`one.` path prefix) -> bucket.
# Both the batched (B>1) and the B=1 `one.*` paths map to the same logical bucket;
# a run uses one path or the other, so we SUM across the prefixes.
_REGION_BUCKET = {
    "write":            "write_path",
    "kernel":           "decode_kernel",
    "view_gather":      "sidecar_gather",   # packed-gather + 3 sidecar reads (BUNDLED)
    "splice":           "staging",
    "bf16_backing":     "staging",
    "kernel_prep":      "staging",
    "seqids_blockids":  "block_resolution",
}
BUCKETS = ["write_path", "decode_kernel", "sidecar_gather", "staging",
           "block_resolution"]


def _strip_prefix(region: str) -> str:
    for pref in ("batched.", "one."):
        if region.startswith(pref):
            return region[len(pref):]
    return region


def roll_buckets(summary: Dict[str, dict]) -> Dict[str, Dict[str, float]]:
    """summary: {region_name: {gpu_us_total, cpu_us_total, ...}}.
    Returns {bucket: {gpu_us, cpu_us, regions:[...]}} summing batched.*+one.*."""
    out = {b: {"gpu_us": 0.0, "cpu_us": 0.0, "regions": []} for b in BUCKETS}
    unmapped = {}
    for region, v in (summary or {}).items():
        bucket = _REGION_BUCKET.get(_strip_prefix(region))
        gpu = float(v.get("gpu_us_total") or 0.0)
        cpu = float(v.get("cpu_us_total") or 0.0)
        if bucket is None:
            unmapped[region] = gpu
            continue
        out[bucket]["gpu_us"] += gpu
        out[bucket]["cpu_us"] += cpu
        out[bucket]["regions"].append(region)
    if unmapped:
        out["_unmapped"] = unmapped  # surfaced, never silently dropped
    return out


def attribute(summary: Dict[str, dict], roofline_verdict: str = "unknown",
              total_step_gpu_us: Optional[float] = None) -> dict:
    """Produce the 5-bucket attribution + frozen-threshold verdict.

    total_step_gpu_us: end-to-end per-run GPU time INCLUDING the model GEMMs
      (e.g. from PHASE_6M_ATTRIBUTION_FINDINGS 6M.4 torch.profiler). Optional; when
      absent we fall back to the int4-path denominator and report shares as an
      UPPER BOUND on the end-to-end share.
    """
    rolled = roll_buckets(summary)
    int4_path_gpu = sum(rolled[b]["gpu_us"] for b in BUCKETS)
    int4_path_cpu = sum(rolled[b]["cpu_us"] for b in BUCKETS)

    def pct_of_int4(b):
        return round(100.0 * rolled[b]["gpu_us"] / int4_path_gpu, 2) if int4_path_gpu > 0 else _UNAVAIL

    buckets_pct = {b: pct_of_int4(b) for b in BUCKETS}
    # end-to-end denominator (incl GEMMs) if the caller supplied it.
    e2e_pct = None
    if isinstance(total_step_gpu_us, (int, float)) and total_step_gpu_us > 0:
        e2e_pct = {b: round(100.0 * rolled[b]["gpu_us"] / total_step_gpu_us, 2) for b in BUCKETS}

    write_int4_share = buckets_pct["write_path"]
    read_share = None
    if int4_path_gpu > 0:
        read_share = round(buckets_pct["decode_kernel"] + buckets_pct["sidecar_gather"], 2)

    # ---- FROZEN threshold logic ----
    verdict, reason = _verdict(
        int4_path_gpu, write_int4_share, e2e_pct, read_share, roofline_verdict)

    return {
        "label": "REGION-MEASURED" if int4_path_gpu > 0 else _UNAVAIL,
        "int4_path_gpu_us": round(int4_path_gpu, 1),
        "int4_path_cpu_us": round(int4_path_cpu, 1),
        "buckets_gpu_us": {b: round(rolled[b]["gpu_us"], 1) for b in BUCKETS},
        "buckets_pct_of_int4_path": buckets_pct,
        "buckets_pct_of_end_to_end": e2e_pct if e2e_pct is not None else _UNAVAIL,
        "memory_bandwidth_pct": _UNAVAIL,   # needs ncu roofline (Test 1) — BLOCKED
        "scheduler_host_cpu_us": round(int4_path_cpu, 1),  # host-dispatch proxy
        "read_path_share_pct_of_int4": read_share if read_share is not None else _UNAVAIL,
        "roofline_verdict": roofline_verdict,
        "unmapped_regions": rolled.get("_unmapped", {}),
        "verdict": verdict,
        "reason": reason,
        "frozen_thresholds": {
            "write_path_material_pct": WRITE_PATH_MATERIAL_PCT,
            "read_dominates_pct": READ_DOMINATES_PCT,
            "roofline_greenlight": sorted(ROOFLINE_GREENLIGHT),
        },
        "notes": [
            "sidecar_gather BUNDLES the packed-KV gather with the 3 sidecar reads "
            "(scale/xmin/protect); the sidecar-only split needs audit_phase6g_"
            "sidecar_overhead.py or a finer region.",
            "memory_bandwidth (is the decode kernel compute- or bandwidth-bound) is "
            "the Test-1 roofline question; ncu is BLOCKED (ERR_NVGPUCTRPERM) on the "
            "available pods, so it is UNAVAILABLE here, never estimated.",
            "scheduler/host overhead: per-region cpu_us is the host-dispatch proxy; "
            "the whole-step GPU-busy residual (~77% busy at saturation) is 6M.4, not "
            "re-derived here (regions exclude the model GEMMs).",
            "capacity/density (threshold 3) is evaluated from the 6L/6M.6 capacity "
            "harness, not this decode attribution.",
        ],
    }


def _verdict(int4_path_gpu, write_int4_share, e2e_pct, read_share, roofline_verdict
             ) -> Tuple[str, str]:
    if not (isinstance(int4_path_gpu, (int, float)) and int4_path_gpu > 0):
        return ("INSUFFICIENT_DATA",
                "No instrumented region GPU time — run bench_phase6_decode_phase_"
                "profile.py --json-out on the pod (profiler must be ON).")
    # Threshold (1): write-path >= 10% of END-TO-END decode.
    # int4-path share is an UPPER BOUND on the end-to-end share.
    if isinstance(write_int4_share, (int, float)) and write_int4_share < WRITE_PATH_MATERIAL_PCT:
        t1 = (f"write-path is {write_int4_share:.1f}% of the int4 read/write path, "
              f"which UPPER-BOUNDS its end-to-end share (int4 path ⊆ end-to-end) — "
              f"so it is DEFINITIVELY < {WRITE_PATH_MATERIAL_PCT:.0f}% end-to-end. "
              "Threshold (1) FAILS: write kernels are NOT the top lever.")
    elif e2e_pct is not None:
        w = e2e_pct["write_path"]
        if w >= WRITE_PATH_MATERIAL_PCT:
            return ("OPTIMIZE_WRITE_KERNELS_FIRST",
                    f"write-path is {w:.1f}% of end-to-end decode (>= "
                    f"{WRITE_PATH_MATERIAL_PCT:.0f}%). Threshold (1) fires: enable/"
                    "optimize the byte-eq-gated CUDA write kernels first.")
        t1 = (f"write-path is {w:.1f}% of end-to-end decode (< "
              f"{WRITE_PATH_MATERIAL_PCT:.0f}%). Threshold (1) fails.")
    else:
        return ("INDETERMINATE_NEED_END_TO_END",
                f"write-path is {write_int4_share:.1f}% of the int4 path (>= "
                f"{WRITE_PATH_MATERIAL_PCT:.0f}% upper bound) — supply "
                "--total-step-gpu-us (6M.4 torch.profiler) to test the end-to-end "
                "threshold.")

    # Threshold (2): read path (decode-kernel + sidecar/gather) dominates.
    if isinstance(read_share, (int, float)) and read_share >= READ_DOMINATES_PCT:
        if roofline_verdict in ROOFLINE_GREENLIGHT:
            return ("BUILD_COMPACT_SIDECAR_DECODE_KERNEL",
                    t1 + f" Read path dominates ({read_share:.1f}% of the int4 path) "
                    f"AND the roofline verdict is '{roofline_verdict}' (greenlight) — "
                    "the top lever is the compact-sidecar in-repo decode kernel (6F).")
        if roofline_verdict in ("bandwidth-bound-coalesced",):
            return ("PREFER_HARDWARE_HBM_LOW_CEILING_FOR_6F",
                    t1 + f" Read path dominates ({read_share:.1f}%) but the roofline "
                    "verdict is bandwidth-bound-coalesced — 6F has a low ceiling; "
                    "prefer the H200 HBM leg (Test 2).")
        return ("BLOCKED_ON_ROOFLINE",
                t1 + f" Read path dominates ({read_share:.1f}% of the int4 path), so "
                "the compact-sidecar decode kernel (6F) is the candidate lever — but "
                "6F is GATED on the Test-1 roofline (compute- vs bandwidth-bound), "
                "which is BLOCKED on ncu (ERR_NVGPUCTRPERM). Get a profiling-enabled "
                "pod and run roofline_ncu_runner.sh before funding the kernel rewrite.")
    return ("READ_PATH_LIKELY_LEVER_CONFIRM_ROOFLINE",
            t1 + f" Read path share is {read_share}% of the int4 path; it is the "
            "likely lever but does not clear the dominance bar — confirm with the "
            "Test-1 roofline (ncu-blocked) before funding 6F.")


def build_report(a: dict) -> str:
    L: List[str] = []
    L.append("=" * 78)
    L.append("Phase 6M.7 — decode-time bucket attribution (code-region, no ncu)")
    L.append("=" * 78)
    L.append(f"label: {a['label']}   int4 read/write-path GPU: {a['int4_path_gpu_us']} us")
    L.append(f"roofline verdict (Test 1): {a['roofline_verdict']}")
    L.append("")
    hdr = f"  {'bucket':<20} {'GPU us':>12} {'% int4 path':>12} {'% end-to-end':>13}"
    L.append(hdr)
    L.append("  " + "-" * (len(hdr) - 2))
    e2e = a["buckets_pct_of_end_to_end"]
    for b in BUCKETS:
        gpu = a["buckets_gpu_us"][b]
        pi = a["buckets_pct_of_int4_path"][b]
        pe = e2e[b] if isinstance(e2e, dict) else _UNAVAIL
        L.append(f"  {b:<20} {gpu:>12.1f} {str(pi):>12} {str(pe):>13}")
    L.append(f"  {'memory_bandwidth':<20} {_UNAVAIL:>12} {_UNAVAIL:>12} {_UNAVAIL:>13}")
    L.append("  " + "-" * (len(hdr) - 2))
    L.append(f"  read-path share (kernel+sidecar): {a['read_path_share_pct_of_int4']}% of int4 path")
    L.append(f"  host-dispatch proxy (region cpu): {a['scheduler_host_cpu_us']} us")
    if a["unmapped_regions"]:
        L.append(f"  UNMAPPED regions (surfaced): {a['unmapped_regions']}")
    L.append("")
    L.append("-" * 78)
    L.append(f"VERDICT: {a['verdict']}")
    L.append(f"  {a['reason']}")
    L.append("-" * 78)
    L.append("")
    L.append("FROZEN thresholds (not tunable): "
             f"write>={a['frozen_thresholds']['write_path_material_pct']}% e2e -> write kernels; "
             f"read>={a['frozen_thresholds']['read_dominates_pct']}% -> 6F kernel (gated on roofline).")
    for n in a["notes"]:
        L.append(f"  · {n}")
    return "\n".join(L) + "\n"


def load_summary(path: Path, pick_b: Optional[int]) -> Tuple[Dict[str, dict], Optional[float]]:
    """Ingest the bench JSON. Accepts either a bare summary dict, or the bench's
    per-B list [{B, wall_s_med, n_out_avg, summary}, ...]. Returns (summary, wall_s)
    for the chosen B (default: the largest B = closest to saturation)."""
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "summary" not in data:
        return data, None                 # already a bare region->stats dict
    records = data if isinstance(data, list) else [data]
    records = [r for r in records if isinstance(r, dict) and r.get("summary")]
    if not records:
        return {}, None
    if pick_b is not None:
        rec = next((r for r in records if r.get("B") == pick_b), None) or records[-1]
    else:
        rec = max(records, key=lambda r: r.get("B", 0))   # saturation-most
    return rec["summary"], rec.get("wall_s_med")


# --------------------------------------------------------------------------- #
def _selftest() -> int:
    # Case A: write-path tiny (3% of int4 path) -> definitively fails threshold 1;
    # read (kernel 60% + gather 25% = 85%) dominates; roofline unknown -> BLOCKED.
    summ = {
        "batched.write":           {"gpu_us_total": 30.0, "cpu_us_total": 40.0},
        "batched.kernel":          {"gpu_us_total": 600.0, "cpu_us_total": 20.0},
        "batched.view_gather":     {"gpu_us_total": 250.0, "cpu_us_total": 300.0},
        "batched.splice":          {"gpu_us_total": 60.0, "cpu_us_total": 30.0},
        "batched.bf16_backing":    {"gpu_us_total": 30.0, "cpu_us_total": 10.0},
        "batched.kernel_prep":     {"gpu_us_total": 20.0, "cpu_us_total": 15.0},
        "batched.seqids_blockids": {"gpu_us_total": 10.0, "cpu_us_total": 90.0},
    }
    a = attribute(summ, roofline_verdict="unknown")
    assert a["buckets_pct_of_int4_path"]["write_path"] == 3.0, a["buckets_pct_of_int4_path"]
    assert a["verdict"] == "BLOCKED_ON_ROOFLINE", a["verdict"]
    assert a["memory_bandwidth_pct"] == _UNAVAIL
    print("  write<10% + read-dominant + roofline unknown -> BLOCKED_ON_ROOFLINE: PASS")

    # Case B: same shape but roofline = compute-bound -> greenlight 6F kernel.
    a = attribute(summ, roofline_verdict="compute-bound")
    assert a["verdict"] == "BUILD_COMPACT_SIDECAR_DECODE_KERNEL", a["verdict"]
    print("  write<10% + read-dominant + compute-bound -> BUILD 6F kernel: PASS")

    # Case C: bandwidth-bound-coalesced -> low-ceiling / prefer H200.
    a = attribute(summ, roofline_verdict="bandwidth-bound-coalesced")
    assert a["verdict"] == "PREFER_HARDWARE_HBM_LOW_CEILING_FOR_6F", a["verdict"]
    print("  bandwidth-bound-coalesced -> prefer H200 (6F low ceiling): PASS")

    # Case D: write-path large on the int4 path AND end-to-end supplied >=10% -> write kernels.
    big_write = dict(summ)
    big_write["batched.write"] = {"gpu_us_total": 400.0, "cpu_us_total": 40.0}
    a = attribute(big_write, roofline_verdict="unknown", total_step_gpu_us=3000.0)
    # write 400 / e2e 3000 = 13.3% >= 10 -> fires
    assert a["verdict"] == "OPTIMIZE_WRITE_KERNELS_FIRST", a["verdict"]
    print("  write 13.3% end-to-end -> OPTIMIZE_WRITE_KERNELS_FIRST: PASS")

    # Case E: write >=10% of int4 path but NO end-to-end denominator -> indeterminate.
    a = attribute(big_write, roofline_verdict="unknown")
    assert a["verdict"] == "INDETERMINATE_NEED_END_TO_END", a["verdict"]
    print("  write>=10% int4 path, no e2e -> INDETERMINATE_NEED_END_TO_END: PASS")

    # Case F: empty summary -> insufficient.
    a = attribute({}, roofline_verdict="unknown")
    assert a["verdict"] == "INSUFFICIENT_DATA" and a["label"] == _UNAVAIL
    print("  empty summary -> INSUFFICIENT_DATA: PASS")

    # Case G: one.* prefix maps to the same buckets as batched.*.
    a = attribute({"one.kernel": {"gpu_us_total": 90.0}, "one.write": {"gpu_us_total": 10.0}},
                  roofline_verdict="unknown")
    assert a["buckets_pct_of_int4_path"]["decode_kernel"] == 90.0
    assert a["buckets_pct_of_int4_path"]["write_path"] == 10.0
    print("  one.* prefix rolls into buckets: PASS")

    # Case H: unmapped region is surfaced, not dropped.
    a = attribute({"batched.kernel": {"gpu_us_total": 100.0},
                   "batched.mystery": {"gpu_us_total": 5.0}}, roofline_verdict="unknown")
    assert a["unmapped_regions"] == {"batched.mystery": 5.0}, a["unmapped_regions"]
    print("  unmapped region surfaced: PASS")

    # load_summary: per-B list picks the largest B by default.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.json"
        p.write_text(json.dumps([
            {"B": 1, "wall_s_med": 1.0, "summary": {"one.kernel": {"gpu_us_total": 1.0}}},
            {"B": 8, "wall_s_med": 2.0, "summary": {"batched.kernel": {"gpu_us_total": 9.0}}},
        ]))
        summ, wall = load_summary(p, None)
        assert wall == 2.0 and "batched.kernel" in summ
        summ1, _ = load_summary(p, 1)
        assert "one.kernel" in summ1
    print("  load_summary picks max-B + honours --b: PASS")

    print("\nself-test: 9/9 PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Phase 6M.7 decode attribution")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--summary", type=Path, help="bench_phase6_decode_phase_profile.py --json-out")
    p.add_argument("--b", type=int, default=None, help="pick a specific B (default: largest)")
    p.add_argument("--roofline-verdict", default="unknown", choices=sorted(ROOFLINE_VALUES),
                   help="Test-1 (6M.5) roofline verdict; UNAVAILABLE until an ncu-unlocked pod runs it")
    p.add_argument("--total-step-gpu-us", type=float, default=None,
                   help="end-to-end per-run GPU us incl GEMMs (6M.4 torch.profiler) to test the "
                        "end-to-end 10%% write threshold; omit to use the int4-path upper bound")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.summary:
        p.error("provide --summary PATH (or --selftest)")
    if not args.summary.exists():
        p.error(f"summary not found: {args.summary}")

    summary, _wall = load_summary(args.summary, args.b)
    a = attribute(summary, args.roofline_verdict, args.total_step_gpu_us)
    report = build_report(a)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        # also drop the machine-readable attribution next to the text report
        args.out.with_suffix(".json").write_text(json.dumps(a, indent=2))
        print(f"Report -> {args.out}  (+ {args.out.with_suffix('.json').name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
