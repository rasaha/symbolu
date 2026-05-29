#!/usr/bin/env python3
# Phase 6L — KV block capacity instrumentation and live-concurrency demo.
#
# Empirically tests the claim: "protected int4 sustains ~1.8× live long-context
# concurrency per GB before KV-block starvation vs bf16, net of sidecar tax."
#
# This is a thin analysis layer on top of phase6k14_saturation.py.  The GPU
# capture path calls phase6k14 --worker (via subprocess) with --resident-pressure
# and long max-tokens; this script reads the per-cell JSON outputs, computes the
# two new metrics (seq_per_kblock + demonstrated_density_ratio), enforces the
# CEILING_NOT_REACHED guard, and prints the Phase 6L comparison table.
#
# Key design decisions:
#   - seq_per_kblock = demonstrated_live / (total_blocks / 1000). total_blocks
#     already reflects the KV memory budget including the sidecar tax, so this
#     metric is proportional to seq/GB without per-quant byte arithmetic.
#   - demonstrated_density_ratio is None if either cell has CEILING_NOT_REACHED.
#   - CEILING_NOT_REACHED = largest B tried for that cell was still fully clean
#     (no preemption, no OOM, peak_util < 90%) — we never pressured the pool.
#   - submitted B ≠ live concurrency: peak_live from _StepProbe is the real
#     number; we never use batch size as a proxy for resident concurrency.
#
# Modes:
#   --selftest      CPU-only; 7 cases verifying CEILING_NOT_REACHED, submitted≠live,
#                   demonstrated gating, density ratio from live not submitted B.
#   --compare       GPU; runs both cells via phase6k14 --worker, prints table.
#   --from-jsons    CPU; re-prints table from previously saved JSONs (no re-run).
#
# Run:
#   python CTM_plus/Bench/scripts/phase6l_capacity_demo.py --selftest
#   PHASE6K10_AUTO_HOOK=0 python CTM_plus/Bench/scripts/phase6l_capacity_demo.py \
#       --compare --mml 8192 --max-tokens 512 --prompt-frac 0.95 \
#       --b-list 48,72,96,128,160 --out-dir /tmp/phase6l
#   python CTM_plus/Bench/scripts/phase6l_capacity_demo.py \
#       --from-jsons /tmp/phase6l/*.json

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Claim window: density ratio in [LO, HI] counts as supporting the ~1.8× claim.
CLAIM_LO, CLAIM_HI = 1.5, 2.5
# Block utilization threshold above which saturation is considered observed.
PRESSURE_PCT = 90.0
_EPS = 1e-9


# ─── Pure-Python analysis core (no torch/vllm; selftest-able) ─────────────────

def _seq_per_kblock(peak_live: int, total_blocks: int) -> Optional[float]:
    """Demonstrated live seqs per 1000 KV blocks.  Proportional to seq/GB."""
    if not peak_live or not total_blocks:
        return None
    return round(1000.0 * peak_live / total_blocks, 3)


def _ceiling_not_reached(cell_rows: list[dict]) -> bool:
    """True if the largest B tried for this cell was still completely clean
    (completed=B, no OOM, no preemption, peak_util<90%).  When True, we never
    pressured the KV pool — peak_live is a floor, not a demonstrated ceiling."""
    if not cell_rows:
        return True
    max_b = max(r.get("batch", 0) for r in cell_rows)
    for r in cell_rows:
        if r.get("batch") != max_b:
            continue
        pu = r.get("peak_util") or 0.0
        clean = (
            not r.get("oom")
            and not r.get("slot_exhausted")
            and r.get("completed") == max_b
            and (r.get("preempts") or 0) == 0
            and not r.get("error")
            and pu < (PRESSURE_PCT / 100.0)   # peak_util stored as fraction in 6k14
        )
        if clean:
            return True   # largest B was still clean -> ceiling not reached
    return False


def _demonstrated_live(cell_rows: list[dict]) -> Optional[int]:
    """Peak live concurrency from rows where saturation was actually observed.
    Returns None if no saturation row exists (CEILING_NOT_REACHED implied)."""
    sat_rows = [r for r in cell_rows if r.get("saturation_observed")]
    if not sat_rows:
        return None
    candidates = [r.get("peak_live") for r in sat_rows if r.get("peak_live")]
    return max(candidates) if candidates else None


def _total_blocks_for_cell(cell_rows: list[dict]) -> Optional[int]:
    """Best total_blocks estimate for a cell (from the highest-B row that has it)."""
    for r in sorted(cell_rows, key=lambda x: x.get("batch", 0), reverse=True):
        v = r.get("total_blocks")
        if v:
            return int(v)
    return None


def _phase6l_analyze(rows: list[dict]) -> dict:
    """Extend phase6k14's analysis with seq_per_kblock and demonstrated_density_ratio.

    Inputs are the per-cell×B JSON dicts written by phase6k14 run_worker.
    Returns an analysis dict that can drive format_table."""
    by_cell: dict[str, list[dict]] = {}
    for r in rows:
        c = r.get("cell")
        if c:
            by_cell.setdefault(c, []).append(r)

    result: dict = {
        "by_cell": {},
        "ceiling_not_reached": [],
        "slot_exhausted_at": {},
        "demonstrated_density_ratio": None,
        "claim_demonstrated": False,
        "claim_status": "NO_DATA",
    }

    for cell, crows in by_cell.items():
        cnr = _ceiling_not_reached(crows)
        dem_live = _demonstrated_live(crows)
        total_blk = _total_blocks_for_cell(crows)
        spkb = _seq_per_kblock(dem_live, total_blk) if dem_live else None
        slot_x = sorted(set(
            r["batch"] for r in crows if r.get("slot_exhausted")))
        any_sat = any(r.get("saturation_observed") for r in crows)

        result["by_cell"][cell] = {
            "ceiling_not_reached": cnr,
            "saturation_observed": any_sat,
            "demonstrated_live": dem_live,
            "total_blocks": total_blk,
            "seq_per_kblock": spkb,
            "slot_exhausted_at": slot_x,
            # Pass through key scalars from the highest-B row for the table.
            "max_concurrency": next((r.get("max_concurrency") for r in
                                     sorted(crows, key=lambda x: x.get("batch", 0),
                                            reverse=True) if r.get("max_concurrency")),
                                    None),
            "hbm_gb": next((r.get("hbm_gb") for r in
                             sorted(crows, key=lambda x: x.get("batch", 0),
                                    reverse=True) if r.get("hbm_gb")), None),
            "peak_util_pct": next((round((r.get("peak_util") or 0) * 100, 1)
                                   for r in sorted(crows,
                                                   key=lambda x: x.get("batch", 0),
                                                   reverse=True)
                                   if r.get("saturation_observed")), None),
            "agg_tps": next((r.get("agg_tps") for r in
                              sorted(crows, key=lambda x: x.get("batch", 0),
                                     reverse=True) if r.get("agg_tps")), None),
            "submitted_b_max": max((r.get("batch", 0) for r in crows), default=0),
            "n_preemptions": sum(r.get("preempts") or 0 for r in crows
                                 if r.get("saturation_observed")),
        }
        if cnr:
            result["ceiling_not_reached"].append(cell)
        if slot_x:
            result["slot_exhausted_at"][cell] = slot_x

    # Density ratio — only when both cells observed saturation.
    bf16 = result["by_cell"].get("bf16", {})
    prot = result["by_cell"].get("protected", {})
    bf16_spkb = bf16.get("seq_per_kblock")
    prot_spkb = prot.get("seq_per_kblock")

    if result["slot_exhausted_at"]:
        result["claim_status"] = "INVALID_SLOT_EXHAUSTION"
    elif result["ceiling_not_reached"]:
        result["claim_status"] = "CEILING_NOT_REACHED"
        result["claim_status_detail"] = (
            f"cells {result['ceiling_not_reached']} never hit the block limit — "
            "raise B or --max-tokens to force pressure")
    elif bf16_spkb and prot_spkb and bf16_spkb > _EPS:
        ratio = round(prot_spkb / bf16_spkb, 3)
        result["demonstrated_density_ratio"] = ratio
        in_window = CLAIM_LO <= ratio <= CLAIM_HI
        result["claim_demonstrated"] = in_window
        result["claim_status"] = "DEMONSTRATED" if in_window else "MEASURED_OUTSIDE_WINDOW"
        result["claim_status_detail"] = (
            f"ratio={ratio:.2f}× "
            f"({'within' if in_window else 'outside'} [{CLAIM_LO}–{CLAIM_HI}] window)")
    else:
        result["claim_status"] = "NO_DATA"

    return result


def format_table(analysis: dict, mml: int = 0,
                 max_tokens: int = 0, prompt_frac: float = 0.0) -> str:
    L = []
    L.append("=" * 84)
    L.append("PHASE 6L — live concurrency capacity demo")
    if mml:
        L.append(f"  mml={mml}  max_tokens={max_tokens}  prompt_frac={prompt_frac}")
    L.append("=" * 84)

    def _v(d: dict, k: str, pct: bool = False) -> str:
        v = d.get(k)
        if v is None:
            return "N/A"
        if pct and isinstance(v, float):
            return f"{v:.1f}%"
        return str(v)

    cells_in_order = [c for c in ("bf16", "protected") if c in analysis["by_cell"]]
    header = f"  {'metric':<34}" + "".join(f"  {c:>14}" for c in cells_in_order)
    L.append(header)
    L.append("  " + "-" * (34 + 16 * len(cells_in_order)))

    rows = [
        ("submitted_b_max",    "submitted_b_max",    False),
        ("total_blocks",       "total_blocks",        False),
        ("est_max_conc (vLLM)","max_concurrency",     False),
        ("peak_kv_util_%",     "peak_util_pct",       True),
        ("saturation_observed","saturation_observed",  False),
        ("ceiling_not_reached","ceiling_not_reached",  False),
        ("n_preemptions",      "n_preemptions",       False),
        ("demonstrated_live",  "demonstrated_live",   False),
        ("seq_per_kblock",     "seq_per_kblock",      False),
        ("hbm_gb",             "hbm_gb",              False),
        ("tokens/sec",         "agg_tps",             False),
    ]
    for label, key, pct in rows:
        row = f"  {label:<34}"
        for c in cells_in_order:
            cd = analysis["by_cell"].get(c, {})
            row += f"  {_v(cd, key, pct):>14}"
        L.append(row)

    L.append("  " + "-" * (34 + 16 * len(cells_in_order)))
    ratio = analysis.get("demonstrated_density_ratio")
    L.append(f"  {'demonstrated_density_ratio':<34}  {str(ratio) + 'x':>14}")
    L.append("")

    status = analysis.get("claim_status", "NO_DATA")
    detail = analysis.get("claim_status_detail", "")
    L.append(f"  CLAIM (~1.8× seq/GB): {status}")
    if detail:
        L.append(f"  {detail}")
    if analysis["slot_exhausted_at"]:
        L.append(f"  !! SLOT-EXHAUSTED: {analysis['slot_exhausted_at']} "
                 "(6K.14 regression — results invalid)")
    if "CEILING_NOT_REACHED" in status:
        L.append("  -> re-run with higher B or --max-tokens 1024")
    L.append("=" * 84)
    return "\n".join(L)


# ─── Selftest (CPU-only, no torch/vllm) ──────────────────────────────────────

def _selftest() -> int:
    # Shorthand: build a fake phase6k14 result row.
    def row(cell, B, completed=None, oom=False, preempts=0, slot_x=False,
            peak_live=None, peak_util=None, saturation=None, total_blocks=1000,
            max_concurrency=None, hbm_gb=None, agg_tps=None, error=None):
        pu_frac = (peak_util / 100.0) if peak_util is not None else None
        sat = saturation if saturation is not None else bool(
            (pu_frac or 0) >= 0.90 or preempts > 0 or oom)
        return {
            "cell": cell, "batch": B, "completed": completed if completed is not None else B,
            "oom": oom, "preempts": preempts, "slot_exhausted": slot_x,
            "peak_live": peak_live, "peak_util": pu_frac,
            "saturation_observed": sat, "total_blocks": total_blocks,
            "max_concurrency": max_concurrency, "hbm_gb": hbm_gb,
            "agg_tps": agg_tps, "error": error,
        }

    # 1. CEILING_NOT_REACHED when largest B was still clean (low util, no preempt).
    rows_low = [
        row("bf16", 48, peak_live=48, peak_util=40.0),
        row("bf16", 64, peak_live=64, peak_util=52.0),  # largest B, still clean
    ]
    assert _ceiling_not_reached(rows_low), "expected CEILING_NOT_REACHED at 52% util"
    assert _demonstrated_live(rows_low) is None, "no saturation -> None"
    print("  CEILING_NOT_REACHED (low util, no preempt): PASS")

    # 2. submitted_B can exceed demonstrated_live when requests queue.
    rows_sat = [
        row("bf16", 128, completed=128, peak_live=55, peak_util=95.0,
            preempts=3, total_blocks=1000),
    ]
    assert not _ceiling_not_reached(rows_sat), "high util + preempt -> saturated"
    dem = _demonstrated_live(rows_sat)
    assert dem == 55, f"demonstrated_live should be 55, got {dem}"
    assert dem < 128, "demonstrated_live < submitted_B (queuing observed)"
    print("  submitted_B != demonstrated_live (queuing): PASS")

    # 3. demonstrated=False (CEILING_NOT_REACHED) even with large submitted B.
    rows_nosig = [row("protected", 200, peak_live=200, peak_util=60.0)]
    a = _phase6l_analyze(rows_nosig)
    assert "CEILING_NOT_REACHED" in a["claim_status"], a["claim_status"]
    assert a["demonstrated_density_ratio"] is None
    assert not a["claim_demonstrated"]
    print("  demonstrated=False when no saturation signal: PASS")

    # 4. Density ratio from demonstrated_live, NOT submitted_B.
    # bf16: peak_live=55 at blocks=1000 → spkb=55; protected: peak_live=99 at blocks=900 → spkb=110.
    rows_both = [
        row("bf16",       128, peak_live=55, peak_util=95.0, preempts=1, total_blocks=1000),
        row("protected",  200, peak_live=99, peak_util=95.0, preempts=2, total_blocks=900),
    ]
    a2 = _phase6l_analyze(rows_both)
    assert a2["by_cell"]["bf16"]["demonstrated_live"] == 55
    assert a2["by_cell"]["protected"]["demonstrated_live"] == 99
    bf16_spkb = a2["by_cell"]["bf16"]["seq_per_kblock"]
    prot_spkb = a2["by_cell"]["protected"]["seq_per_kblock"]
    assert bf16_spkb is not None and abs(bf16_spkb - 55.0) < 0.01, bf16_spkb
    assert prot_spkb is not None and abs(prot_spkb - 110.0) < 0.01, prot_spkb
    ratio = a2["demonstrated_density_ratio"]
    assert ratio is not None and abs(ratio - 2.0) < 0.01, ratio
    # Confirm submitted B was NOT used: bf16 submitted 128, protected 200 → naive=1.56×.
    # The demonstrated ratio (2.0×) differs because it uses peak_live per block, not batch size.
    assert abs(ratio - (200 / 128)) > 0.1, "ratio must come from live/blocks, not submitted_B"
    print(f"  density ratio from live (not submitted_B): {ratio:.2f}× PASS")

    # 5. Claim DEMONSTRATED when ratio in [1.5, 2.5].
    assert a2["claim_demonstrated"], a2["claim_status"]
    assert a2["claim_status"] == "DEMONSTRATED"
    print("  claim DEMONSTRATED (ratio in window): PASS")

    # 6. Claim NOT DEMONSTRATED when ratio outside window (e.g. sidecar eats the gain).
    rows_bad = [
        row("bf16",       64, peak_live=55, peak_util=93.0, preempts=1, total_blocks=1000),
        row("protected",  64, peak_live=52, peak_util=96.0, preempts=2, total_blocks=820),
        # protected has fewer blocks (sidecar tax), similar live seqs → ratio ≈ 1.15×
    ]
    a3 = _phase6l_analyze(rows_bad)
    assert a3["demonstrated_density_ratio"] is not None
    assert not a3["claim_demonstrated"], a3
    assert a3["claim_status"] == "MEASURED_OUTSIDE_WINDOW"
    print(f"  claim not demonstrated (ratio={a3['demonstrated_density_ratio']:.2f}× "
          f"outside window): PASS")

    # 7. INVALID when slot-exhaustion present.
    rows_slotx = [
        row("protected", 64, slot_x=True, peak_live=40, peak_util=70.0),
    ]
    a4 = _phase6l_analyze(rows_slotx)
    assert a4["claim_status"] == "INVALID_SLOT_EXHAUSTION"
    assert not a4["claim_demonstrated"]
    print("  INVALID_SLOT_EXHAUSTION detected: PASS")

    print("\nSELFTEST PASS (7/7)")
    return 0


# ─── GPU driver (subprocess into phase6k14 --worker) ─────────────────────────

_K14 = Path(__file__).resolve().parent / "phase6k14_saturation.py"


def _run_worker(cell: str, mml: int, b: int, max_tokens: int,
                prompt_frac: float, gpu_util: float,
                out_path: str, env: dict) -> dict:
    cmd = [sys.executable, str(_K14), "--worker",
           "--mml", str(mml), "--batch", str(b),
           "--max-tokens", str(max_tokens),
           "--prompt-frac", str(prompt_frac),
           "--gpu-util", str(gpu_util),
           "--resident-pressure"]
    cell_env = dict(env)
    cell_env["CELL"] = cell
    cell_env["OUTPUT"] = out_path
    cell_env.setdefault("PHASE6E_FUSED_WRITER", "1")
    cell_env.pop("PHASE6B3_FORCE_EAGER", None)
    print(f"\n[6L] {cell} mml={mml} B={b} gen={max_tokens} pf={prompt_frac} "
          f"util={gpu_util}", flush=True)
    subprocess.run(cmd, env=cell_env, check=False)
    try:
        return json.loads(Path(out_path).read_text())
    except Exception as e:
        return {"cell": cell, "batch": b, "error": str(e)[:80]}


def run_compare(model: str, mml: int, b_list: list[int], max_tokens: int,
                prompt_frac: float, gpu_util: float, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cells = ["bf16", "protected"]
    env = dict(os.environ)
    env["PHASE6K10_AUTO_HOOK"] = env.get("PHASE6K10_AUTO_HOOK", "0")
    # Largest B first for each cell (to force saturation immediately), then
    # descend so we also have a clean reference point.
    sweep = sorted(b_list, reverse=True)
    rows = []
    for cell in cells:
        for b in sweep:
            out_path = str(out_dir / f"phase6l_{cell}_mml{mml}_B{b}.json")
            r = _run_worker(cell, mml, b, max_tokens, prompt_frac,
                            gpu_util, out_path, env)
            rows.append(r)
            # Early stop per cell: if OOM at this B, smaller B will be clean; keep going.
            # If saturation already observed at high B, still run lower B for the table.
    a = _phase6l_analyze(rows)
    report = {
        "model": model, "mml": mml, "max_tokens": max_tokens,
        "prompt_frac": prompt_frac, "gpu_util": gpu_util,
        "b_list": b_list, "analysis": a,
    }
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n[6L] report -> {report_path}", flush=True)
    print(format_table(a, mml=mml, max_tokens=max_tokens, prompt_frac=prompt_frac))
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 6L capacity instrumentation")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--compare", action="store_true",
                    help="GPU: run both cells and print comparison table")
    ap.add_argument("--from-jsons", nargs="+", metavar="JSON",
                    help="CPU: re-print table from existing JSON result files")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mml", type=int, default=8192)
    ap.add_argument("--b-list", default="48,72,96,128,160",
                    help="Comma-separated batch sizes; straddle bf16 and 2× bf16 est")
    ap.add_argument("--max-tokens", type=int, default=512,
                    help="Generation length per sequence (≥512 to create KV pressure)")
    ap.add_argument("--prompt-frac", type=float, default=0.95,
                    help="Fill prompts to this fraction of mml")
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--out-dir", default="/tmp/phase6l",
                    help="Directory for per-cell×B JSON results and report.json")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    b_list = [int(x) for x in args.b_list.split(",")]

    if args.from_jsons:
        rows = []
        for p in args.from_jsons:
            try:
                rows.append(json.loads(Path(p).read_text()))
            except Exception as e:
                print(f"[6L] skip {p}: {e}", file=sys.stderr)
        a = _phase6l_analyze(rows)
        print(format_table(a))
        return 0 if a.get("claim_demonstrated") else 1

    if args.compare:
        report = run_compare(
            args.model, args.mml, b_list, args.max_tokens,
            args.prompt_frac, args.gpu_util, Path(args.out_dir),
        )
        a = report["analysis"]
        return 0 if a.get("claim_demonstrated") else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
