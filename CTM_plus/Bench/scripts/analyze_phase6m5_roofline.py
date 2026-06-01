"""Phase 6M.5 — roofline analyzer for ncu SpeedOfLight output.

THE GATE (Test 1 of the Phase 6M throughput-recovery plan). Reads the
Nsight Compute (`ncu`) CSV export produced by the §9/§Test-1 runbook
(`roofline_ncu_runner.sh`) and classifies the int4 decode-attention kernel
(and, for reference, bf16's) as one of:

  * compute-bound                 -> SM% >> DRAM% (dequant arithmetic on SMs).
                                     6F kernel work viable; HBM bandwidth won't
                                     help; H100 native INT4 is the HW lever.
  * bandwidth-bound, uncoalesced  -> DRAM% high-ish BUT sectors/request low
                                     (scattered paged gather + 3 sidecar reads).
                                     Lever = software layout/coalescing fix in 6F
                                     (the actionable "HBM-level" answer, §HBM).
  * bandwidth-bound, coalesced    -> DRAM% ~100% with good sectors/request.
                                     Raw HBM bandwidth is the wall -> H200 HBM3e
                                     (Test 2); 6F has a low ceiling.
  * latency/occupancy-bound       -> neither SM nor DRAM near peak; warps stall.

This script changes NO kernels and runs NO GPU work. It only parses the
counters `ncu` collected on the pod and emits the verdict + the raw SoL
split, so the conclusion is reproducible from the committed CSV.

ncu CSV schema (the "details" page; one row per (kernel, metric)). We key
off these columns and tolerate either the human-readable Metric Name or the
raw metric ID:

    "Kernel Name", "Metric Name", "Metric Unit", "Metric Value"
    [optional] "ID" / "Kernel Time" to disambiguate invocations.

Usage (on the pod, after the runbook exports CSVs):
    python CTM_plus/Bench/scripts/analyze_phase6m5_roofline.py \
        --int4-csv int4_captured_ncu.csv \
        --bf16-csv bf16_stock_ncu.csv \
        --int4-kernel-substr fwd_kvcache \
        --out PHASE_6M5_roofline_report.txt

CPU-only self-test (no GPU, no ncu needed):
    python CTM_plus/Bench/scripts/analyze_phase6m5_roofline.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Logical SpeedOfLight / Memory fields -> candidate ncu metric matchers.
#
# Each logical field maps to a list of case-insensitive substrings checked
# against BOTH the "Metric Name" (human-readable, e.g. "Compute (SM)
# Throughput") and the raw metric ID (e.g. "sm__throughput.avg.pct_of_peak_
# sustained_elapsed"). First match wins; order = most-specific first.
# ---------------------------------------------------------------------------
FIELD_MATCHERS: Dict[str, List[str]] = {
    # Compute (SM) throughput, % of peak.
    "sm_pct": [
        "sm__throughput.avg.pct_of_peak_sustained_elapsed",
        "compute (sm) throughput",
        "compute (sm)[%]",
        "sm throughput",
    ],
    # DRAM (device-memory) throughput, % of peak. The raw-bandwidth wall.
    "dram_pct": [
        "dram__throughput.avg.pct_of_peak_sustained_elapsed",
        "dram throughput",
    ],
    # SpeedOfLight "Memory Throughput" = max over the memory subsystem; can be
    # high (L1/L2/shared) even when DRAM is moderate. Useful as a cross-check.
    "mem_pct": [
        "gpu__compute_memory_throughput.avg.pct_of_peak_sustained_elapsed",
        "memory throughput",
    ],
    # Achieved occupancy, % — distinguishes latency/occupancy-bound.
    "occ_pct": [
        "sm__warps_active.avg.pct_of_peak_sustained_active",
        "achieved occupancy",
    ],
    # Global-load sectors per request: the coalescing signal. 32 = perfectly
    # coalesced (one 128B transaction = 32 sectors served per request when the
    # warp's 32 threads hit one aligned line); a scattered gather drives this
    # DOWN toward 1-4 (each thread its own sector). LOW => uncoalesced.
    "sectors_per_req_ld": [
        "l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_ld.ratio",
        "sectors/req",
        "sectors per request",
    ],
    # Duration (ns) — for weighting/sanity, not classification.
    "duration_ns": [
        "gpu__time_duration.sum",
        "duration",
    ],
}

# Classification thresholds (percent of peak unless noted). Tunable via CLI.
# Documented heuristics, not magic: a kernel is compute-bound when the SM
# pipes are near saturation and clearly ahead of DRAM; bandwidth-bound when
# DRAM is the engine near saturation. The raw split is always printed so a
# human can sanity-check a borderline call.
DEFAULTS = {
    "compute_sm_floor": 60.0,    # SM% must be at least this to call compute-bound
    "compute_lead": 15.0,        # ...and lead DRAM% by at least this margin
    "bandwidth_dram_floor": 60.0,  # DRAM% at/above this => bandwidth-pressured
    "saturated_dram": 90.0,      # DRAM% near peak => raw-bandwidth wall (case 1)
    "coalesce_good": 24.0,       # sectors/req >= this => coalesced (of max 32)
    "idle_ceiling": 50.0,        # both SM% & DRAM% below this => latency/occ-bound
}

# Verdict tags (stable strings the findings doc + downstream gates key on).
V_COMPUTE = "compute-bound"
V_BW_UNCOALESCED = "bandwidth-bound-uncoalesced"
V_BW_COALESCED = "bandwidth-bound-coalesced"
V_OCCUPANCY = "latency/occupancy-bound"
V_MIXED = "mixed/inconclusive"

# Which downstream lever each verdict hands off to (mirrors plan §decision tree).
VERDICT_LEVER = {
    V_COMPUTE: ("6F kernel work viable (in-kernel dequant); H100 native INT4 is "
                "the HW lever. HBM bandwidth will NOT help."),
    V_BW_UNCOALESCED: ("6F read-path LAYOUT/coalescing fix (interleave nibbles + "
                       "scale + xmin + protected into one contiguous transaction). "
                       "The actionable 'HBM-level' answer (plan §HBM)."),
    V_BW_COALESCED: ("Raw HBM bandwidth is the wall -> H200 HBM3e (Test 2). 6F "
                     "kernel work has a low ceiling here."),
    V_OCCUPANCY: ("Neither engine near peak -> launch/occupancy/latency bound. "
                  "Re-check operating point (B, context); 6M.4 says <1% host sync "
                  "at saturation, so a low-occupancy verdict warrants a re-run."),
    V_MIXED: ("Borderline — read the raw SM/DRAM split below and re-run at the "
              "exact saturation operating point before gating Test 3."),
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _to_float(s: str) -> Optional[float]:
    """Coerce an ncu metric value: strips commas, %, and surrounding quotes."""
    if s is None:
        return None
    s = s.strip().strip('"').replace(",", "").replace("%", "").strip()
    if not s or s.lower() in ("n/a", "nan", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _find_col(header: List[str], *candidates: str) -> Optional[int]:
    low = [h.strip().strip('"').lower() for h in header]
    for cand in candidates:
        for i, h in enumerate(low):
            if h == cand:
                return i
        for i, h in enumerate(low):
            if cand in h:
                return i
    return None


def parse_ncu_csv(path: Path) -> Dict[str, Dict[str, List[float]]]:
    """Parse an ncu CSV export into {kernel_name: {metric_name_lower: [values]}}.

    Multiple invocations of the same kernel accumulate into the value list so
    the caller can take a median (decode launches one kernel per layer/step).
    """
    out: Dict[str, Dict[str, List[float]]] = {}
    with path.open(newline="") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r]
    if not rows:
        return out
    # ncu may prepend "==PROF==" banner lines before the CSV header. Find the
    # header: the first row that contains both a Kernel Name and Metric columns.
    header_idx = None
    for i, r in enumerate(rows):
        low = [c.strip().strip('"').lower() for c in r]
        if any("kernel name" in c for c in low) and any("metric name" in c for c in low):
            header_idx = i
            break
    if header_idx is None:
        return out
    header = rows[header_idx]
    k_kernel = _find_col(header, "kernel name")
    k_metric = _find_col(header, "metric name")
    k_value = _find_col(header, "metric value")
    k_unit = _find_col(header, "metric unit")
    if k_kernel is None or k_metric is None or k_value is None:
        return out
    for r in rows[header_idx + 1:]:
        if max(k_kernel, k_metric, k_value) >= len(r):
            continue
        kernel = r[k_kernel].strip().strip('"')
        metric = r[k_metric].strip().strip('"').lower()
        unit = (r[k_unit].strip().strip('"').lower() if k_unit is not None
                and k_unit < len(r) else "")
        val = _to_float(r[k_value])
        if not kernel or not metric or val is None:
            continue
        # Stash the unit alongside the name so "% of peak" vs raw can be told
        # apart if needed (we fold unit into the key for substring matching).
        key = metric if not unit else f"{metric} [{unit}]"
        out.setdefault(kernel, {}).setdefault(key, []).append(val)
        # Also store under the bare metric name (no unit) for matcher hits.
        if unit:
            out[kernel].setdefault(metric, []).append(val)
    return out


def resolve_fields(metrics: Dict[str, List[float]]) -> Dict[str, Optional[float]]:
    """Map a kernel's raw metric dict onto the logical SoL fields (median)."""
    resolved: Dict[str, Optional[float]] = {}
    for field, matchers in FIELD_MATCHERS.items():
        val: Optional[float] = None
        for matcher in matchers:
            m = matcher.lower()
            for mname, vals in metrics.items():
                if m in mname and vals:
                    val = float(median(vals))
                    break
            if val is not None:
                break
        resolved[field] = val
    return resolved


def pick_kernel(parsed: Dict[str, Dict[str, List[float]]],
                substr: Optional[str]) -> Optional[str]:
    """Choose the kernel of interest: substring match if given, else the one
    with the largest total Duration (the hot kernel)."""
    if not parsed:
        return None
    if substr:
        for name in parsed:
            if substr.lower() in name.lower():
                return name
    # Fall back to longest-running kernel by summed duration.
    best, best_dur = None, -1.0
    for name, metrics in parsed.items():
        f = resolve_fields(metrics)
        d = f.get("duration_ns") or 0.0
        if d > best_dur:
            best, best_dur = name, d
    return best or next(iter(parsed))


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify(fields: Dict[str, Optional[float]],
             th: Dict[str, float]) -> Tuple[str, str]:
    """Return (verdict_tag, one-line reason) from resolved SoL fields."""
    sm = fields.get("sm_pct")
    dram = fields.get("dram_pct")
    sectors = fields.get("sectors_per_req_ld")
    occ = fields.get("occ_pct")

    if sm is None and dram is None:
        return V_MIXED, ("no SM/DRAM SpeedOfLight metrics found — check the CSV "
                         "has the SpeedOfLight section")

    sm = sm if sm is not None else 0.0
    dram = dram if dram is not None else 0.0

    # 1. Both engines idle -> latency / occupancy / launch bound.
    if sm < th["idle_ceiling"] and dram < th["idle_ceiling"]:
        occ_txt = f", occ {occ:.0f}%" if occ is not None else ""
        return V_OCCUPANCY, (f"SM {sm:.0f}% and DRAM {dram:.0f}% both below "
                             f"{th['idle_ceiling']:.0f}%{occ_txt} — neither engine "
                             f"near peak")

    # 2. Compute-bound: SM near peak and clearly ahead of DRAM.
    if sm >= th["compute_sm_floor"] and (sm - dram) >= th["compute_lead"]:
        return V_COMPUTE, (f"SM {sm:.0f}% >= {th['compute_sm_floor']:.0f}% and "
                           f"leads DRAM {dram:.0f}% by {sm - dram:.0f}pt")

    # 3. Bandwidth-pressured: DRAM is the lead engine / near floor.
    if dram >= th["bandwidth_dram_floor"] and dram >= sm:
        if sectors is not None and sectors < th["coalesce_good"]:
            return V_BW_UNCOALESCED, (
                f"DRAM {dram:.0f}% leads SM {sm:.0f}%, sectors/req "
                f"{sectors:.1f} < {th['coalesce_good']:.0f} (of 32) => scattered "
                f"gather wasting effective bandwidth")
        if dram >= th["saturated_dram"]:
            sec_txt = (f", sectors/req {sectors:.1f}" if sectors is not None else "")
            return V_BW_COALESCED, (f"DRAM {dram:.0f}% >= "
                                    f"{th['saturated_dram']:.0f}% (near peak)"
                                    f"{sec_txt} => raw bandwidth wall")
        sec_txt = (f", sectors/req {sectors:.1f}" if sectors is not None
                   else ", sectors/req unknown")
        return V_BW_COALESCED, (f"DRAM {dram:.0f}% leads SM {sm:.0f}%{sec_txt} "
                                f"(not fully saturated — treat as coalesced "
                                f"bandwidth pressure)")

    # 4. Neither clean compute nor clean bandwidth.
    return V_MIXED, (f"SM {sm:.0f}% vs DRAM {dram:.0f}% — no clean winner; "
                     f"inspect raw split")


def _fmt(v: Optional[float], suffix: str = "%") -> str:
    return f"{v:.1f}{suffix}" if v is not None else "  n/a"


def build_report(int4_fields: Dict[str, Optional[float]],
                 int4_kernel: str,
                 bf16_fields: Optional[Dict[str, Optional[float]]],
                 bf16_kernel: Optional[str],
                 verdict: str, reason: str,
                 th: Dict[str, float]) -> str:
    L: List[str] = []
    L.append("=" * 78)
    L.append("Phase 6M.5 — Roofline: int4 decode-attention bound classification")
    L.append("=" * 78)
    L.append("")
    L.append(f"int4 kernel: {int4_kernel}")
    if bf16_kernel:
        L.append(f"bf16 kernel: {bf16_kernel}")
    L.append("")
    cols = [
        ("Compute (SM) %", "sm_pct"),
        ("DRAM %",         "dram_pct"),
        ("Memory %",       "mem_pct"),
        ("Achieved occ %", "occ_pct"),
        ("Sectors/req (ld)", "sectors_per_req_ld"),
    ]
    width = max(len(c[0]) for c in cols)
    L.append(f"{'SpeedOfLight metric':<{width}} | {'int4':>10} | {'bf16':>10}")
    L.append("-" * (width + 26))
    for label, key in cols:
        suffix = "" if key == "sectors_per_req_ld" else "%"
        iv = _fmt(int4_fields.get(key), suffix)
        bv = _fmt(bf16_fields.get(key) if bf16_fields else None, suffix)
        L.append(f"{label:<{width}} | {iv:>10} | {bv:>10}")
    L.append("")
    L.append("-" * 78)
    L.append(f"VERDICT (int4 attention kernel): {verdict.upper()}")
    L.append(f"  reason: {reason}")
    L.append(f"  lever:  {VERDICT_LEVER.get(verdict, '(see plan §decision tree)')}")
    L.append("-" * 78)
    L.append("")
    L.append("Thresholds used (override via CLI):")
    for k, v in th.items():
        L.append(f"  {k:<22} = {v}")
    L.append("")
    L.append("Reminder (plan §HBM): int4 reads ~half the KV bytes of bf16 yet runs")
    L.append("slower — so a raw-bandwidth-saturated verdict is a priori unlikely;")
    L.append("compute-bound or bandwidth-uncoalesced are the expected outcomes.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Self-test (CPU-only; synthesizes ncu CSVs and asserts the classifier)
# ---------------------------------------------------------------------------
def _write_synth_csv(path: Path, kernel: str,
                     sm: float, dram: float, mem: float,
                     occ: float, sectors: float) -> None:
    header = ['"ID"', '"Kernel Name"', '"Section Name"',
              '"Metric Name"', '"Metric Unit"', '"Metric Value"']
    rows = [
        (kernel, "GPU Speed Of Light Throughput",
         "Compute (SM) Throughput", "%", sm),
        (kernel, "GPU Speed Of Light Throughput",
         "Memory Throughput", "%", mem),
        (kernel, "GPU Speed Of Light Throughput",
         "DRAM Throughput", "%", dram),
        (kernel, "Occupancy", "Achieved Occupancy", "%", occ),
        (kernel, "Memory Workload Analysis",
         "L2 Sectors/Req", "", sectors),
        (kernel, "GPU Speed Of Light Throughput", "Duration", "ns", 825000),
    ]
    with path.open("w", newline="") as f:
        f.write("==PROF== Connected to process 1234\n")
        f.write(",".join(header) + "\n")
        for i, (k, sec, mname, unit, val) in enumerate(rows):
            f.write(f'"{i}","{k}","{sec}","{mname}","{unit}","{val}"\n')


def _selftest() -> int:
    import tempfile
    th = dict(DEFAULTS)
    cases = [
        # (name, sm, dram, mem, occ, sectors, expected_verdict)
        ("compute-bound",        82, 30, 55, 65, 30, V_COMPUTE),
        ("bw-uncoalesced",       40, 72, 80, 50, 4,  V_BW_UNCOALESCED),
        ("bw-coalesced-sat",     35, 95, 96, 40, 30, V_BW_COALESCED),
        ("bw-coalesced-moderate", 30, 65, 70, 45, 28, V_BW_COALESCED),
        ("occupancy-bound",      22, 18, 30, 15, 30, V_OCCUPANCY),
    ]
    n_ok = 0
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for name, sm, dram, mem, occ, sectors, expected in cases:
            p = d / f"{name}.csv"
            _write_synth_csv(p, f"flash_fwd_kvcache_int4_{name}",
                             sm, dram, mem, occ, sectors)
            parsed = parse_ncu_csv(p)
            assert parsed, f"{name}: parse produced nothing"
            kname = pick_kernel(parsed, "int4")
            fields = resolve_fields(parsed[kname])
            assert abs((fields["sm_pct"] or -1) - sm) < 1e-6, (name, fields["sm_pct"])
            assert abs((fields["dram_pct"] or -1) - dram) < 1e-6, (name, fields["dram_pct"])
            assert abs((fields["sectors_per_req_ld"] or -1) - sectors) < 1e-6, name
            verdict, reason = classify(fields, th)
            assert verdict == expected, (
                f"{name}: got {verdict!r} ({reason}), expected {expected!r}")
            print(f"  {name:<22} -> {verdict:<28} PASS")
            n_ok += 1

        # Multi-invocation median: two rows for same metric -> median taken.
        p = d / "median.csv"
        with p.open("w", newline="") as f:
            f.write('"Kernel Name","Metric Name","Metric Unit","Metric Value"\n')
            f.write('"k","Compute (SM) Throughput","%","80"\n')
            f.write('"k","Compute (SM) Throughput","%","60"\n')
            f.write('"k","Compute (SM) Throughput","%","70"\n')
            f.write('"k","DRAM Throughput","%","20"\n')
        fields = resolve_fields(parse_ncu_csv(p)["k"])
        assert abs(fields["sm_pct"] - 70.0) < 1e-6, fields["sm_pct"]
        print(f"  {'median-of-invocations':<22} -> sm_pct={fields['sm_pct']:.0f} PASS")
        n_ok += 1

        # Missing SoL section -> MIXED, no crash.
        p = d / "empty.csv"
        with p.open("w", newline="") as f:
            f.write('"Kernel Name","Metric Name","Metric Unit","Metric Value"\n')
            f.write('"k","L2 Hit Rate","%","50"\n')
        verdict, _ = classify(resolve_fields(parse_ncu_csv(p)["k"]), th)
        assert verdict == V_MIXED, verdict
        print(f"  {'missing-SoL-section':<22} -> {verdict} PASS")
        n_ok += 1

    print(f"\nself-test: {n_ok}/{n_ok} PASS")
    return 0


# ---------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Phase 6M.5 roofline analyzer")
    p.add_argument("--selftest", action="store_true",
                   help="CPU-only; classify synthetic ncu CSVs and assert.")
    p.add_argument("--int4-csv", type=Path,
                   help="ncu CSV export for the int4_captured cell")
    p.add_argument("--bf16-csv", type=Path, default=None,
                   help="ncu CSV export for the bf16_stock cell (reference)")
    p.add_argument("--int4-kernel-substr", default="int4",
                   help="substring to pick the int4 attention kernel "
                        "(default 'int4'; try 'fwd_kvcache' or 'flash_fwd')")
    p.add_argument("--bf16-kernel-substr", default="flash_fwd",
                   help="substring to pick the bf16 attention kernel")
    p.add_argument("--out", type=Path, default=None,
                   help="write the report here (also printed to stdout)")
    # Threshold overrides.
    for k, v in DEFAULTS.items():
        p.add_argument(f"--{k.replace('_', '-')}", type=float, default=v)
    args = p.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.int4_csv:
        p.error("--int4-csv is required (or pass --selftest)")
    if not args.int4_csv.exists():
        p.error(f"int4 CSV not found: {args.int4_csv}")

    th = {k: getattr(args, k) for k in DEFAULTS}

    int4_parsed = parse_ncu_csv(args.int4_csv)
    if not int4_parsed:
        print(f"ERROR: parsed no kernels/metrics from {args.int4_csv}. "
              f"Is it an ncu CSV with a SpeedOfLight section?", file=sys.stderr)
        return 2
    int4_kernel = pick_kernel(int4_parsed, args.int4_kernel_substr)
    int4_fields = resolve_fields(int4_parsed[int4_kernel])

    bf16_fields = None
    bf16_kernel = None
    if args.bf16_csv and args.bf16_csv.exists():
        bf16_parsed = parse_ncu_csv(args.bf16_csv)
        if bf16_parsed:
            bf16_kernel = pick_kernel(bf16_parsed, args.bf16_kernel_substr)
            bf16_fields = resolve_fields(bf16_parsed[bf16_kernel])

    verdict, reason = classify(int4_fields, th)
    report = build_report(int4_fields, int4_kernel, bf16_fields, bf16_kernel,
                          verdict, reason, th)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        print(f"Report written to: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
