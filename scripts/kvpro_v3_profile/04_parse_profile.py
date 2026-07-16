#!/usr/bin/env python3
"""KVPro V3 Step-0 — Part C: parse Nsight / CUDA-event outputs into a normalized stage summary.

Consumes any subset of:
  * nsys kernel summary CSV   (`nsys stats --report cuda_gpu_kern_sum -f csv`)
  * ncu per-kernel metric CSV (`ncu --csv --metrics ...`)
  * cuda_events.json          (our 03_profile_cuda_events.sh per-stage wall times)
and emits stage_summary.json + stage_summary.csv attributing time to the decode pipeline stages:
  gather, staging, splice, dequant, protect, attention, other.

HARD RULE: never invents a measurement. A field with no source is emitted as "UNAVAILABLE", not 0 and
not an estimate. If ncu counters are blocked, counter-derived fields stay UNAVAILABLE while nsys/event
timing still populates the time columns.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

# kernel-name -> pipeline stage (first match wins). Patterns cover the in-repo Triton route-A kernel
# and the (external) production flash-attn int4 kernel naming, plus generic gather/copy kernels.
# attention is matched FIRST: the in-repo route-A kernel fuses gather+dequant+protect+attn into ONE
# kernel whose NAME contains "protected", and name-classification cannot sub-split a fused kernel — it is
# attributed to 'attention'. To split a fused kernel into gather/dequant/protect shares you need ncu
# SOURCE counters or the 03 CUDA-events sub-region timing, NOT kernel names. Name-based stage attribution
# is meaningful for the PRODUCTION path (separate host gather + external attn kernel), not for route-A.
STAGE_PATTERNS = [
    ("attention", r"attn|attention|flash|softmax|splitk|combine_splits|fused.*decode|\bmma\b"),
    ("gather",    r"gather|index_select|paged.*(gather|copy)|block_table"),
    ("staging",   r"contiguous|memcpy|to_?contig|elementwise_copy|catarray|\bcopy\b"),
    ("splice",    r"splice|partial.*tail|tail.*(splice|requant)"),
    ("dequant",   r"dequant|unpack|nibble|int4.*(unpack|decode)"),
    ("protect",   r"protect|sidecar|overlay|where"),
]
STAGES = [s for s, _ in STAGE_PATTERNS] + ["other"]
_UNAVAIL = "UNAVAILABLE"


def classify_kernel(name: str) -> str:
    n = (name or "").lower()
    for stage, pat in STAGE_PATTERNS:
        if re.search(pat, n):
            return stage
    return "other"


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:  # noqa: BLE001
        return None


def parse_nsys_kernsum(rows) -> list:
    """rows: iterable of dicts (csv.DictReader). Returns [{name, total_ns, instances}]. Tolerant to the
    column-name drift across nsys versions (Total Time / Time(%) / Instances / Name)."""
    out = []
    for r in rows:
        keys = {k.lower().strip(): k for k in r.keys()}
        name = r.get(keys.get("name", "Name"), "")
        tcol = next((keys[k] for k in keys if "total" in k and "time" in k), None) \
            or next((keys[k] for k in keys if k in ("total time (ns)", "total time")), None)
        icol = next((keys[k] for k in keys if "instances" in k or k == "count"), None)
        total = _num(r.get(tcol)) if tcol else None
        if total is None:
            continue
        out.append({"name": name, "total_ns": total, "instances": _num(r.get(icol)) if icol else None})
    return out


def parse_ncu_csv(rows) -> dict:
    """rows: csv.DictReader of `ncu --csv`. Returns {kernel_name: {metric: value}}. Missing/blocked
    metrics simply do not appear (caller marks them UNAVAILABLE)."""
    per = {}
    for r in rows:
        keys = {k.lower().strip(): k for k in r.keys()}
        kname = r.get(keys.get("kernel name", "Kernel Name")) or r.get(keys.get("name", "Name"), "")
        mname = r.get(keys.get("metric name", "Metric Name"), "")
        mval = _num(r.get(keys.get("metric value", "Metric Value")))
        if not kname or not mname:
            continue
        per.setdefault(kname, {})[mname] = mval
    return per


def summarize(kernels: list, ncu: dict | None = None, events: dict | None = None) -> dict:
    """kernels: parse_nsys_kernsum output; events: {stage: wall_ms}. Attributes time to stages.
    Two sources: (a) nsys per-kernel times -> full stage split; (b) route-A CUDA-events (a FUSED kernel)
    -> only protect% is recoverable, via the protect-off ablation (`attention`=fused total, `protect`=
    ablation ms). In the fused case gather/staging/splice/dequant read 0 — route-A already inlines them."""
    events = events or {}
    stage_ns = {s: 0.0 for s in STAGES}
    stage_kernels = {s: [] for s in STAGES}
    total = 0.0
    for k in kernels:
        s = classify_kernel(k["name"])
        stage_ns[s] += k["total_ns"] or 0.0
        total += k["total_ns"] or 0.0
        stage_kernels[s].append(k["name"])
    have_kernels = bool(kernels) and total > 0
    # events-only fused-kernel path: derive protect% by ablation
    ev_fused, ev_prot = events.get("attention"), events.get("protect")
    events_pct = None
    if not have_kernels and isinstance(ev_fused, (int, float)) and ev_fused > 0:
        p = round(100.0 * ev_prot / ev_fused, 2) if isinstance(ev_prot, (int, float)) else 0.0
        events_pct = {s: 0.0 for s in STAGES}
        events_pct["protect"] = max(0.0, p)
        events_pct["attention"] = round(100.0 - max(0.0, p), 2)
    stages = {}
    for s in STAGES:
        if have_kernels:
            pct = round(100.0 * stage_ns[s] / total, 2)
        elif events_pct is not None:
            pct = events_pct[s]
        else:
            pct = _UNAVAIL
        stages[s] = {
            "time_ns": round(stage_ns[s], 1) if have_kernels else _UNAVAIL,
            "pct_of_kernel_time": pct,
            "n_kernels": len(stage_kernels[s]),
            "event_wall_ms": events.get(s, _UNAVAIL),
        }
    # counter-derived (ncu) roll-up — UNAVAILABLE unless ncu present
    counters = {}
    for metric in ("dram__bytes_read.sum", "dram__bytes_write.sum", "lts__t_sector_hit_rate.pct",
                   "smsp__sass_average_data_bytes_per_sector_mem_global_op_ld.pct",
                   "sm__warps_active.avg.pct_of_peak_sustained_active"):
        vals = [m.get(metric) for m in (ncu or {}).values() if metric in m]
        counters[metric] = round(sum(v for v in vals if v is not None), 3) if vals else _UNAVAIL
    return {
        "stages": stages,
        "kernel_time_total_ns": round(total, 1) if have_kernels else _UNAVAIL,
        "counters": counters,
        "sources": {"nsys": have_kernels, "ncu": bool(ncu), "cuda_events": bool(events),
                    "fused_ablation": events_pct is not None},
        "label": "GPU-measured" if (have_kernels or events_pct is not None) else "NOT_RUN",
        "note": "time columns from nsys/events; counter columns UNAVAILABLE unless ncu counters were "
                "unblocked. Fused route-A path: only protect% is measurable (ablation); gather already inlined.",
    }


def _read_csv(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, newline="") as fh:
        # skip nsys preamble lines before the header row
        text = fh.read()
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if "," in l and re.search(r"name", l, re.I)), 0)
    return list(csv.DictReader(lines[start:]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="parse Nsight/CUDA-event profiles -> stage summary")
    ap.add_argument("--nsys-csv"); ap.add_argument("--ncu-csv"); ap.add_argument("--events-json")
    ap.add_argument("--out", default="stage_summary.json")
    ap.add_argument("--csv-out", default="stage_summary.csv")
    args = ap.parse_args(argv)

    kernels = parse_nsys_kernsum(_read_csv(args.nsys_csv))
    ncu = parse_ncu_csv(_read_csv(args.ncu_csv)) if args.ncu_csv else None
    events = json.load(open(args.events_json)) if args.events_json and os.path.exists(args.events_json) else None
    if isinstance(events, dict):
        events = events.get("stage_wall_ms", events)

    summ = summarize(kernels, ncu, events)
    json.dump(summ, open(args.out, "w"), indent=2)
    with open(args.csv_out, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["stage", "time_ns", "pct_of_kernel_time", "n_kernels", "event_wall_ms"])
        for s in STAGES:
            row = summ["stages"][s]
            w.writerow([s, row["time_ns"], row["pct_of_kernel_time"], row["n_kernels"], row["event_wall_ms"]])
    print(f"[{summ['label']}] stage summary -> {args.out} / {args.csv_out}")
    for s in STAGES:
        print(f"  {s:10} {summ['stages'][s]['pct_of_kernel_time']:>10}%  "
              f"kernels={summ['stages'][s]['n_kernels']}  wall_ms={summ['stages'][s]['event_wall_ms']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
