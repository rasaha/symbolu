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

# Product-framing input (Phase 6L (b)): the density win is paid for in decode
# latency. Per-sequence decode throughput must reach at least this fraction of
# bf16's to be a candidate for live/interactive serving; below it, the
# demonstrated density win is a BATCH/OFFLINE story until the int4 decode kernel
# is optimized. A framing threshold to classify the run, NOT a hard SLA and NOT
# a funding decision (that is surfaced to the user).
INTERACTIVE_TPS_RATIO_MIN = 0.7

# Canonical int4_protected sidecar tensors (PHASE_6G_SIDECAR_DIET_FINDINGS.md).
# Discovery matches these names as substrings of writer attributes; ordering
# here drives the printed breakdown.
SIDECAR_NAMES = ["k_protect_ext", "k_scale_ext", "k_xmin_ext",
                 "v_scale_ext", "v_xmin_ext", "_k_stage_pool"]


def _bytes_to_gb(b) -> float:
    return round(b / 1e9, 4) if b else 0.0


# GPU-side sidecar discovery lives in the worker (phase6k14_saturation.py
# ``_discover_sidecar_bytes``), not here: it needs torch + the live writers, and
# keeping it there lets the worker record the per-tensor bytes WITHOUT importing
# this analysis module back (phase6l stays a pure-CPU consumer). This module
# only reads the recorded ``sidecar_bytes_by_tensor`` from the per-cell JSONs
# (or, as a fallback, from a Phase 6G audit JSON via --sidecar-audit).


def _audit_sidecar_bytes(audit_path: str) -> dict:
    """Fallback source of EXACT per-tensor sidecar BYTES from a Phase 6G
    sidecar-audit JSON (audit_phase6g_sidecar_overhead.py output), for capacity
    runs whose per-cell JSONs predate the live worker-side discovery (their
    ``sidecar_bytes_by_tensor`` is empty). Restricted to the canonical
    SIDECAR_NAMES so the total matches the printed breakdown; the audit's raw
    byte counts are used directly, keeping the decimal-GB unit consistent with
    hbm_gb. Returns {} on any failure (caller then estimates from the delta)."""
    try:
        payload = json.loads(Path(audit_path).read_text())
    except Exception:
        return {}
    out: dict[str, int] = {}
    for r in payload.get("sidecar_ranked") or []:
        name, b = r.get("tensor"), r.get("total_bytes")
        if name in SIDECAR_NAMES and b:
            out[name] = out.get(name, 0) + int(b)
    return out


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


def _rep_row(cell_rows: list[dict]) -> dict:
    """Representative row for STATIC HBM/sidecar accounting: prefer the highest-B
    saturated row that has hbm_gb (the real saturated operating point), else the
    highest-B row with hbm_gb, else the highest-B row."""
    sat = [r for r in cell_rows if r.get("saturation_observed") and r.get("hbm_gb")]
    pool = sat or [r for r in cell_rows if r.get("hbm_gb")] or cell_rows
    return max(pool, key=lambda r: r.get("batch", 0)) if pool else {}


def _sidecar_gb_by_tensor(row: dict) -> dict:
    """Convert a row's raw sidecar byte counts to GB per canonical tensor."""
    raw = (row or {}).get("sidecar_bytes_by_tensor") or {}
    return {k: _bytes_to_gb(v) for k, v in raw.items()}


def _cell_accounting(rep: dict, sc_by_tensor: dict, sc_total: Optional[float]) -> dict:
    """Per-cell HBM accounting block."""
    hbm = rep.get("hbm_gb")
    mw = rep.get("model_weights_gb")
    kvb = rep.get("kv_cache_budget_gb")
    nonsc = None
    if None not in (hbm, mw, kvb) and sc_total is not None:
        nonsc = round(hbm - mw - kvb - sc_total, 3)
    return {
        "hbm_gb_total": hbm,
        "model_weights_gb": mw,
        "kv_cache_budget_gb": kvb,
        "sidecar_gb_total": sc_total if sc_total is not None else 0.0,
        "sidecar_gb_by_tensor": sc_by_tensor,
        "non_sidecar_overhead_gb": nonsc,
    }


def _phase6l_analyze(rows: list[dict], audit_path: Optional[str] = None) -> dict:
    """Extend phase6k14's analysis with seq_per_kblock and demonstrated_density_ratio.

    Inputs are the per-cell×B JSON dicts written by phase6k14 run_worker.
    `audit_path` optionally points at a Phase 6G sidecar-audit JSON used as a
    fallback source of exact per-tensor sidecar bytes when the per-cell JSONs
    don't embed them (older runs that predate the live worker-side discovery).
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

    # ── block-budget (raw) ratio: kept as the "raw" number for backward compat ──
    bf16 = result["by_cell"].get("bf16", {})
    prot = result["by_cell"].get("protected", {})
    bf16_spkb = bf16.get("seq_per_kblock")
    prot_spkb = prot.get("seq_per_kblock")
    if bf16_spkb and prot_spkb and bf16_spkb > _EPS:
        result["demonstrated_density_ratio"] = round(prot_spkb / bf16_spkb, 3)

    # ── HBM accounting + sidecar tax + net-of-tax density (the real numbers) ──
    bf16_rows = by_cell.get("bf16", [])
    prot_rows = by_cell.get("protected", [])
    bf16_rep, prot_rep = _rep_row(bf16_rows), _rep_row(prot_rows)
    bf16_hbm, prot_hbm = bf16_rep.get("hbm_gb"), prot_rep.get("hbm_gb")
    bf16_live = _demonstrated_live(bf16_rows)
    prot_live = _demonstrated_live(prot_rows)

    # Per-tensor sidecar breakdown (protected only; bf16 has none by definition).
    # Primary source: live worker-side discovery embedded in the per-cell JSON.
    # Fallback: a Phase 6G sidecar-audit JSON (--sidecar-audit) for older runs.
    sc_by_tensor = _sidecar_gb_by_tensor(prot_rep)
    sc_source_label = "live tensor introspection (writer sidecar tensors)"
    if not sc_by_tensor and audit_path:
        audit_bytes = _audit_sidecar_bytes(audit_path)
        if audit_bytes:
            sc_by_tensor = {k: _bytes_to_gb(v) for k, v in audit_bytes.items()}
            sc_source_label = (
                f"Phase 6G sidecar audit ({Path(audit_path).name}) — measured on "
                "a separate run, not this capacity run")
    breakdown_available = bool(sc_by_tensor)
    sc_total = round(sum(sc_by_tensor.values()), 3) if breakdown_available else None

    result["hbm_accounting"] = {
        "bf16": _cell_accounting(bf16_rep, {}, 0.0),
        "protected": _cell_accounting(prot_rep, sc_by_tensor, sc_total),
    }

    # Sidecar-tax comparison.
    sidecar_tax = None
    if bf16_hbm is not None and prot_hbm is not None:
        abs_delta = round(prot_hbm - bf16_hbm, 3)
        measured = sc_total                 # None if discovery failed
        estimated = measured is None
        sidecar_tax = {
            "protected_hbm_gb": prot_hbm,
            "bf16_hbm_gb": bf16_hbm,
            "absolute_hbm_delta_gb": abs_delta,
            "measured_sidecar_tax_gb": measured,
            "sidecar_tax_estimated": estimated,
            "sidecar_tax_source": (
                sc_source_label if not estimated else
                "UNAVAILABLE — per-tensor discovery returned nothing; "
                "absolute HBM delta is reported instead (it also includes "
                "CUDA-graph pools + misc, so it is an upper bound on the tax)"),
            "sidecar_tax_pct_of_protected_hbm": (
                round(100.0 * measured / prot_hbm, 2)
                if measured and prot_hbm else None),
            "sidecar_tax_pct_of_delta": (
                round(100.0 * measured / abs_delta, 2)
                if measured and abs(abs_delta) > _EPS else None),
            "non_sidecar_residual_delta_gb": (
                round(abs_delta - measured, 3) if measured is not None else None),
            "sidecar_breakdown_available": breakdown_available,
            "sidecar_gb_by_tensor": sc_by_tensor or None,
        }
    result["sidecar_tax"] = sidecar_tax

    # Capacity-density: real net-of-tax (HEADLINE) + clearly-labeled counterfactual.
    density = None
    if bf16_live and prot_live and bf16_hbm and prot_hbm and bf16_hbm > _EPS:
        bf16_spg = round(bf16_live / bf16_hbm, 3)
        prot_spg = round(prot_live / prot_hbm, 3)
        net_ratio = round(prot_spg / bf16_spg, 3) if bf16_spg > _EPS else None
        cf_spg = cf_ratio = None
        if sc_total and (prot_hbm - sc_total) > _EPS:
            cf_spg = round(prot_live / (prot_hbm - sc_total), 3)
            cf_ratio = round(cf_spg / bf16_spg, 3) if bf16_spg > _EPS else None
        density = {
            "bf16_demonstrated_live": bf16_live,
            "protected_demonstrated_live": prot_live,
            "raw_live_ratio": round(prot_live / bf16_live, 3),
            "bf16_hbm_gb": bf16_hbm,
            "protected_hbm_gb": prot_hbm,
            "bf16_seq_per_gb": bf16_spg,
            "protected_seq_per_gb": prot_spg,
            "net_density_ratio": net_ratio,        # <-- HEADLINE (real, net of tax)
            "headline_metric": "net_density_ratio",
            # Counterfactual — NOT a serving number (sidecars are required for
            # int4 dequant; you cannot run protected without them).
            "protected_seq_per_gb_without_sidecars": cf_spg,
            "net_density_ratio_without_sidecars": cf_ratio,
            "counterfactual_note": (
                "without_sidecars is a COUNTERFACTUAL upper bound (sidecars are "
                "mandatory for int4 dequant); it is NOT the real serving density"),
            "claim_window": [CLAIM_LO, CLAIM_HI],
            "net_density_in_window": (
                net_ratio is not None and CLAIM_LO <= net_ratio <= CLAIM_HI),
        }
    result["density"] = density

    # ── Throughput tax (Phase 6L (b)): the latency cost of the density win ──
    # Density is not free: int4's UNoptimized decode path runs far fewer tok/s.
    # Quantify it BOTH ways — aggregate (cluster tok/s) and per-live-sequence
    # (per-user streaming rate) — so the product-positioning call is data-backed.
    throughput = None
    bf16_tps, prot_tps = bf16_rep.get("agg_tps"), prot_rep.get("agg_tps")
    if bf16_tps and prot_tps and bf16_live and prot_live:
        agg_ratio = round(prot_tps / bf16_tps, 3)
        bf16_tps_seq = round(bf16_tps / bf16_live, 3)
        prot_tps_seq = round(prot_tps / prot_live, 3)
        per_seq_ratio = (round(prot_tps_seq / bf16_tps_seq, 3)
                         if bf16_tps_seq > _EPS else None)
        per_seq_slowdown = (round(1.0 / per_seq_ratio, 2)
                            if per_seq_ratio and per_seq_ratio > _EPS else None)
        interactive_viable = (per_seq_ratio is not None
                              and per_seq_ratio >= INTERACTIVE_TPS_RATIO_MIN)
        net_ratio_d = density["net_density_ratio"] if density else None
        if interactive_viable:
            fit = ("interactive-capable — per-seq decode throughput is within the "
                   f"{INTERACTIVE_TPS_RATIO_MIN:.0%} live-serving bar")
        else:
            fit = ("BATCH/OFFLINE density play — fits throughput-insensitive, "
                   "density-bound workloads (offline eval, bulk summarization, "
                   "agentic batch). Interactive serving would need int4 "
                   "decode-kernel optimization to close the per-user gap")
        throughput = {
            "bf16_agg_tps": bf16_tps,
            "protected_agg_tps": prot_tps,
            "aggregate_tps_ratio": agg_ratio,            # cluster tok/s (≈0.22x)
            "bf16_tps_per_live_seq": bf16_tps_seq,
            "protected_tps_per_live_seq": prot_tps_seq,
            "per_seq_tps_ratio": per_seq_ratio,          # per-user tok/s (≈0.11x)
            "per_seq_slowdown_x": per_seq_slowdown,      # ≈9x slower per user
            "interactive_tps_ratio_min": INTERACTIVE_TPS_RATIO_MIN,
            "interactive_viable": interactive_viable,
            "workload_fit": fit,
            "framing_note": (
                f"DENSITY +{net_ratio_d}x net seq/GB  vs  THROUGHPUT {agg_ratio}x "
                f"aggregate / {per_seq_ratio}x per-user tok/s. The density win is "
                "real and paid for in latency; positioning depends on whether the "
                "target workload is throughput-insensitive (batch/offline) or "
                "latency-sensitive (interactive)."),
        }
    result["throughput"] = throughput

    # ── Claim gating: prefer the real net-of-tax ratio; fall back to block-budget ──
    net_ratio = density["net_density_ratio"] if density else None
    if result["slot_exhausted_at"]:
        result["claim_status"] = "INVALID_SLOT_EXHAUSTION"
    elif result["ceiling_not_reached"]:
        result["claim_status"] = "CEILING_NOT_REACHED"
        result["claim_status_detail"] = (
            f"cells {result['ceiling_not_reached']} never hit the block limit — "
            "raise B or --max-tokens to force pressure")
    elif net_ratio is not None:
        in_window = CLAIM_LO <= net_ratio <= CLAIM_HI
        result["headline_density_ratio"] = net_ratio
        result["headline_metric"] = "net_density_ratio"
        result["claim_demonstrated"] = in_window
        result["claim_status"] = "DEMONSTRATED" if in_window else "MEASURED_OUTSIDE_WINDOW"
        result["claim_status_detail"] = (
            f"net_density_ratio={net_ratio:.2f}× (live seqs per actual HBM GB, "
            f"net of sidecar tax) {'within' if in_window else 'outside'} "
            f"[{CLAIM_LO}–{CLAIM_HI}] window")
    elif result["demonstrated_density_ratio"] is not None:
        # No HBM data (e.g. unit tests) — fall back to block-budget seq_per_kblock.
        r = result["demonstrated_density_ratio"]
        in_window = CLAIM_LO <= r <= CLAIM_HI
        result["headline_density_ratio"] = r
        result["headline_metric"] = "seq_per_kblock (HBM unavailable; block-budget)"
        result["claim_demonstrated"] = in_window
        result["claim_status"] = "DEMONSTRATED" if in_window else "MEASURED_OUTSIDE_WINDOW"
        result["claim_status_detail"] = (
            f"ratio={r:.2f}× (block-budget seq_per_kblock; HBM data unavailable) "
            f"{'within' if in_window else 'outside'} [{CLAIM_LO}–{CLAIM_HI}] window")
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
    L.append(f"  {'raw seq_per_kblock ratio':<34}  {str(ratio) + 'x':>14}")

    # ── Sidecar / HBM accounting ──
    st = analysis.get("sidecar_tax")
    acc = analysis.get("hbm_accounting", {})
    if st:
        L.append("")
        L.append("  Sidecar / HBM accounting:")
        L.append(f"    bf16 total HBM:        {st['bf16_hbm_gb']:.2f} GB")
        L.append(f"    protected total HBM:   {st['protected_hbm_gb']:.2f} GB")
        L.append(f"    absolute HBM delta:    +{st['absolute_hbm_delta_gb']:.2f} GB")
        if st.get("measured_sidecar_tax_gb") is not None:
            L.append(f"    measured sidecar tax:  {st['measured_sidecar_tax_gb']:.2f} GB "
                     f"({st['sidecar_tax_pct_of_protected_hbm']:.1f}% of protected HBM, "
                     f"{st['sidecar_tax_pct_of_delta']:.1f}% of delta)")
            pc = acc.get("protected", {}).get("sidecar_gb_by_tensor", {})
            if pc:
                L.append("    sidecar tensor breakdown:")
                for nm in SIDECAR_NAMES:
                    if nm in pc:
                        L.append(f"      {nm:<16} {pc[nm]:.3f} GB")
                for nm in sorted(k for k in pc if k not in SIDECAR_NAMES):
                    L.append(f"      {nm:<16} {pc[nm]:.3f} GB")
            if st.get("non_sidecar_residual_delta_gb") is not None:
                L.append(f"    non-sidecar residual delta: "
                         f"{st['non_sidecar_residual_delta_gb']:.2f} GB "
                         "(CUDA-graph pools + misc)")
        else:
            L.append("    measured sidecar tax:  UNAVAILABLE "
                     "(per-tensor discovery failed)")
            L.append(f"      source: {st.get('sidecar_tax_source')}")

    # ── Demonstrated density (net of sidecar tax) ──
    dn = analysis.get("density")
    if dn:
        L.append("")
        L.append("  Demonstrated density (net of sidecar tax):")
        L.append(f"    bf16 live seqs:        {dn['bf16_demonstrated_live']}")
        L.append(f"    protected live seqs:   {dn['protected_demonstrated_live']}")
        L.append(f"    raw live ratio:        {dn['raw_live_ratio']:.2f}x")
        L.append(f"    bf16 seq/GB:           {dn['bf16_seq_per_gb']:.3f}")
        L.append(f"    protected seq/GB:      {dn['protected_seq_per_gb']:.3f}")
        L.append(f"    NET density ratio:     {dn['net_density_ratio']:.2f}x"
                 "   <-- HEADLINE (VC-safe, net of tax)")
        if dn.get("net_density_ratio_without_sidecars") is not None:
            L.append(f"    [counterfactual] no-sidecar ratio: "
                     f"{dn['net_density_ratio_without_sidecars']:.2f}x "
                     "(NOT a serving number — sidecars are mandatory for dequant)")

    # ── Throughput tax (latency cost of the density win) — product framing ──
    tp = analysis.get("throughput")
    if tp:
        L.append("")
        L.append("  Throughput tax (latency cost of the density win):")
        L.append(f"    bf16 agg tok/s:        {tp['bf16_agg_tps']}")
        L.append(f"    protected agg tok/s:   {tp['protected_agg_tps']}")
        L.append(f"    aggregate tps ratio:   {tp['aggregate_tps_ratio']:.2f}x "
                 "(cluster throughput)")
        L.append(f"    bf16 tok/s per seq:    {tp['bf16_tps_per_live_seq']:.2f}")
        L.append(f"    protected tok/s/seq:   {tp['protected_tps_per_live_seq']:.2f}")
        L.append(f"    per-user tps ratio:    {tp['per_seq_tps_ratio']:.2f}x"
                 + (f"  (~{tp['per_seq_slowdown_x']:.1f}x slower per user)"
                    if tp.get("per_seq_slowdown_x") else ""))
        L.append(f"    interactive-viable:    {tp['interactive_viable']} "
                 f"(bar: per-user >= {tp['interactive_tps_ratio_min']:.0%} of bf16)")
        L.append(f"    -> {tp['workload_fit']}")
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
            max_concurrency=None, hbm_gb=None, agg_tps=None, error=None,
            sidecar_bytes=None, model_weights_gb=None, kv_cache_budget_gb=None):
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
            "sidecar_bytes_by_tensor": sidecar_bytes or {},
            "model_weights_gb": model_weights_gb,
            "kv_cache_budget_gb": kv_cache_budget_gb,
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

    # 8. Sidecar tax + net-of-tax density — LIVE-measured Phase 6L numbers
    #    (mml=8192, B=128; worker tensor introspection). The +4.39 GB HBM delta
    #    is ~99.8% sidecars within max_memory_allocated (CUDA-graph pools are
    #    non-PyTorch, so the tracked residual is ~0.01 GB). NB: the old "3.42 GB"
    #    was the 6G audit at mml=32K (binary GiB) — a different config.
    GB = 1e9
    sc = {"k_protect_ext": 1.015 * GB, "k_scale_ext": 0.812 * GB,
          "k_xmin_ext": 0.812 * GB, "v_scale_ext": 0.812 * GB,
          "v_xmin_ext": 0.812 * GB, "_k_stage_pool": 0.117 * GB}   # total 4.38 GB
    rows_real = [
        row("bf16", 128, peak_live=58, peak_util=100.0, preempts=8,
            total_blocks=28310, hbm_gb=42.44, agg_tps=597.3,
            model_weights_gb=14.25),
        row("protected", 128, peak_live=117, peak_util=100.0, preempts=6,
            total_blocks=28310, hbm_gb=46.83, agg_tps=130.4,
            sidecar_bytes=sc, model_weights_gb=14.25),
    ]
    ar = _phase6l_analyze(rows_real)
    stx = ar["sidecar_tax"]
    assert abs(stx["absolute_hbm_delta_gb"] - 4.39) < 0.01, stx
    assert abs(stx["measured_sidecar_tax_gb"] - 4.38) < 0.01, stx
    assert stx["sidecar_tax_estimated"] is False
    assert abs(stx["non_sidecar_residual_delta_gb"] - 0.01) < 0.01, stx
    assert abs(stx["sidecar_tax_pct_of_delta"] - 99.77) < 0.1, stx
    assert stx["sidecar_breakdown_available"] is True
    dn = ar["density"]
    assert dn["bf16_demonstrated_live"] == 58 and dn["protected_demonstrated_live"] == 117
    assert abs(dn["raw_live_ratio"] - 2.017) < 0.01, dn
    assert abs(dn["bf16_seq_per_gb"] - 1.367) < 0.01, dn
    assert abs(dn["protected_seq_per_gb"] - 2.498) < 0.01, dn
    assert abs(dn["net_density_ratio"] - 1.83) < 0.02, dn          # HEADLINE
    # net (1.83) must differ from raw (2.02): the tax is subtracted via HBM.
    assert abs(dn["net_density_ratio"] - dn["raw_live_ratio"]) > 0.1, dn
    assert ar["claim_status"] == "DEMONSTRATED"
    assert ar["headline_metric"] == "net_density_ratio"
    assert abs(ar["headline_density_ratio"] - 1.83) < 0.02
    print(f"  sidecar tax {stx['measured_sidecar_tax_gb']:.2f}GB -> "
          f"net density {dn['net_density_ratio']:.2f}x (HEADLINE): PASS")

    # 9. Guardrail: counterfactual no-sidecar ratio is computed, labeled, and is
    #    NOT the headline (headline stays the real net-of-tax ratio).
    assert dn["net_density_ratio_without_sidecars"] is not None
    assert dn["net_density_ratio_without_sidecars"] > dn["net_density_ratio"]
    assert ar["headline_density_ratio"] == dn["net_density_ratio"]
    assert ar["headline_density_ratio"] != dn["net_density_ratio_without_sidecars"]
    print("  counterfactual labeled, NOT headline (guardrail): PASS")

    # 10. Graceful degradation: no per-tensor discovery -> breakdown unavailable,
    #     but absolute delta + net density + raw ratio + claim still computed.
    rows_nodisc = [
        row("bf16", 128, peak_live=58, peak_util=100.0, preempts=8,
            total_blocks=28310, hbm_gb=42.44),
        row("protected", 128, peak_live=117, peak_util=100.0, preempts=6,
            total_blocks=28310, hbm_gb=46.83),       # sidecar_bytes empty
    ]
    ad = _phase6l_analyze(rows_nodisc)
    assert ad["sidecar_tax"]["measured_sidecar_tax_gb"] is None
    assert ad["sidecar_tax"]["sidecar_tax_estimated"] is True
    assert ad["sidecar_tax"]["sidecar_breakdown_available"] is False
    assert abs(ad["sidecar_tax"]["absolute_hbm_delta_gb"] - 4.39) < 0.01
    assert abs(ad["density"]["net_density_ratio"] - 1.83) < 0.02   # still computes
    assert ad["claim_status"] == "DEMONSTRATED"                    # headline survives
    print("  graceful degradation (no breakdown, headline survives): PASS")

    # 11. --sidecar-audit fallback: a run with NO embedded sidecar bytes can
    #     still get an EXACT per-tensor tax from a Phase 6G audit JSON (for runs
    #     that predate the live worker-side discovery). The numbers below are the
    #     OLD 6G audit inventory (mml=32K, ~3.42 GB) — deliberately a DIFFERENT
    #     config than the live 8K tax (~4.38 GB), which is exactly what the audit
    #     fallback represents. Non-canonical tensors (protect_mask) are dropped so
    #     the total matches the printed breakdown.
    import tempfile
    with tempfile.TemporaryDirectory() as _d:
        _audit = Path(_d) / "audit_mml8192.json"
        _audit.write_text(json.dumps({"sidecar_ranked": [
            {"tensor": "k_protect_ext", "total_bytes": int(0.82e9)},
            {"tensor": "k_scale_ext",   "total_bytes": int(0.65e9)},
            {"tensor": "k_xmin_ext",    "total_bytes": int(0.65e9)},
            {"tensor": "v_scale_ext",   "total_bytes": int(0.65e9)},
            {"tensor": "v_xmin_ext",    "total_bytes": int(0.65e9)},
            {"tensor": "protect_mask",  "total_bytes": 800000},   # dropped
        ]}))
        aa = _phase6l_analyze(rows_nodisc, audit_path=str(_audit))
    sx = aa["sidecar_tax"]
    assert sx["sidecar_breakdown_available"] is True, sx
    assert sx["sidecar_tax_estimated"] is False, sx
    assert abs(sx["measured_sidecar_tax_gb"] - 3.42) < 0.01, sx
    assert "Phase 6G sidecar audit" in sx["sidecar_tax_source"], sx
    assert abs(aa["density"]["net_density_ratio"] - 1.83) < 0.02
    print("  --sidecar-audit fallback (exact tax for older runs): PASS")

    # 12. Throughput tax (Phase 6L (b) product-framing input): the density win
    #     is paid for in decode latency — quantify it aggregate AND per-user.
    tp = ar["throughput"]                       # ar = rows_real analysis (597.3/130.4)
    assert abs(tp["aggregate_tps_ratio"] - 0.218) < 0.005, tp      # ~0.22x cluster
    assert abs(tp["per_seq_tps_ratio"] - 0.108) < 0.005, tp        # ~0.11x per user
    assert tp["per_seq_slowdown_x"] > 8.5, tp                      # ~9x slower/user
    assert tp["interactive_viable"] is False, tp                  # below the 0.7 bar
    assert "BATCH/OFFLINE" in tp["workload_fit"], tp
    # density still the claim headline; throughput is the cost companion, not the claim.
    assert ar["headline_metric"] == "net_density_ratio"
    print(f"  throughput tax {tp['aggregate_tps_ratio']:.2f}x agg / "
          f"{tp['per_seq_tps_ratio']:.2f}x per-user "
          f"(~{tp['per_seq_slowdown_x']:.0f}x slower/user): PASS")

    # Smoke: format_table renders the new sections without error.
    _ = format_table(ar, mml=8192, max_tokens=512, prompt_frac=0.95)

    print("\nSELFTEST PASS (12/12)")
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
                prompt_frac: float, gpu_util: float, out_dir: Path,
                audit_path: Optional[str] = None,
                cells: Optional[list[str]] = None,
                awq_model: Optional[str] = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cells = cells or ["bf16", "protected"]
    env = dict(os.environ)
    env["PHASE6K10_AUTO_HOOK"] = env.get("PHASE6K10_AUTO_HOOK", "0")
    # Phase 6O: thread the AWQ checkpoint + base model id to the worker so the
    # awq_bf16 / awq_protected cells can build with quantization=awq.
    if awq_model:
        env["AWQ_MODEL"] = awq_model
    env["BASE_MODEL"] = model
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
    a = _phase6l_analyze(rows, audit_path=audit_path)
    report = {
        "model": model, "mml": mml, "max_tokens": max_tokens,
        "prompt_frac": prompt_frac, "gpu_util": gpu_util,
        "b_list": b_list,
        # Surface the accounting sections at the top level for easy audit.
        "hbm_accounting": a.get("hbm_accounting"),
        "sidecar_tax": a.get("sidecar_tax"),
        "density": a.get("density"),
        "throughput": a.get("throughput"),
        "analysis": a,
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
    ap.add_argument("--sidecar-audit", default=None, metavar="JSON",
                    help="Optional Phase 6G sidecar-audit JSON "
                         "(audit_phase6g_sidecar_overhead.py output) used as a "
                         "fallback source of exact per-tensor sidecar bytes when "
                         "the per-cell JSONs predate the live worker-side "
                         "discovery (their sidecar_bytes_by_tensor is empty).")
    ap.add_argument("--cells", default=None,
                    help="comma-separated cells to run (default 'bf16,protected'). "
                         "Phase 6O: use 'awq_bf16,awq_protected' to measure the "
                         "AWQ-weights + int4-KV stack's REAL combined HBM "
                         "(model_weights_gb + sidecar tax), or mix all four.")
    ap.add_argument("--awq-model", default="Qwen/Qwen2.5-7B-Instruct-AWQ",
                    help="AWQ checkpoint id for the awq_* cells.")
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
        a = _phase6l_analyze(rows, audit_path=args.sidecar_audit)
        print(format_table(a))
        return 0 if a.get("claim_demonstrated") else 1

    if args.compare:
        cells = ([c.strip() for c in args.cells.split(",") if c.strip()]
                 if args.cells else None)
        report = run_compare(
            args.model, args.mml, b_list, args.max_tokens,
            args.prompt_frac, args.gpu_util, Path(args.out_dir),
            audit_path=args.sidecar_audit, cells=cells, awq_model=args.awq_model,
        )
        a = report["analysis"]
        return 0 if a.get("claim_demonstrated") else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
