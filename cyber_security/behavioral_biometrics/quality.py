"""Synchronization + timing quality diagnostics and the mechanical instrumentation
verdict — the FIRST hard gate.

Timing quality is checked before any identity analysis. A session that does not clear
the frozen thresholds is flagged INSTRUMENTATION_DEGRADED or INSTRUMENTATION_NOT_READY
and is EXCLUDED from identity analysis with a recorded reason — never silently dropped.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from cyber_security.behavioral_biometrics.config import DEFAULT, InstrumentationThresholds

READY = "INSTRUMENTATION_READY"
DEGRADED = "INSTRUMENTATION_DEGRADED"
NOT_READY = "INSTRUMENTATION_NOT_READY"


def _source_times(events: List[Dict[str, Any]]) -> np.ndarray:
    return np.array([float(e.get("t_source", 0.0)) for e in events], dtype=float)


def analyze(session: Dict[str, Any], thr: InstrumentationThresholds = None) -> Dict[str, Any]:
    """Per-session quality summary + instrumentation verdict."""
    thr = thr or DEFAULT.instrumentation
    events = session.get("events", []) or []
    n = len(events)
    stats = session.get("collector_stats", {}) or {}
    dropped = int(stats.get("dropped", 0))

    summary: Dict[str, Any] = {"n_events": n, "dropped": dropped}

    if n == 0:
        summary.update({"verdict": NOT_READY, "reasons": ["no_events"], "metrics": {}})
        return summary

    t_src = _source_times(events)
    t_mono = np.array([float(e.get("t_monotonic", 0.0)) for e in events], dtype=float)
    t_recv = np.array([float(e.get("t_receipt", 0.0)) for e in events], dtype=float)
    seqs = [e.get("seq") for e in events]

    # --- integrity ---
    total_intended = n + dropped
    drop_rate = dropped / total_intended if total_intended else 0.0

    dup_keys = [(e.get("seq"), e.get("modality"), e.get("type"), round(float(e.get("t_source", 0)), 6))
                for e in events]
    duplicates = len(dup_keys) - len(set(dup_keys))
    dup_rate = duplicates / n

    reorder = int(np.sum(np.diff(t_src) < 0)) if n > 1 else 0
    seq_reorder = 0
    numeric_seqs = [s for s in seqs if isinstance(s, int)]
    if len(numeric_seqs) > 1:
        seq_reorder = int(np.sum(np.diff(numeric_seqs) <= 0))
    reorder_rate = max(reorder, seq_reorder) / max(1, n - 1)

    # --- timing ---
    order = np.argsort(t_src, kind="mergesort")
    t_sorted = t_src[order]
    # Sampling jitter is a property of PERIODICALLY-sampled streams (pointer moves,
    # motion) — NOT event-driven keyboard, whose inter-event spacing is irregular by
    # nature. Quantization is the timer RESOLUTION (finest distinct timestamp step)
    # across all events, so a coarse tick is caught independent of sample rate.
    jitter_ms = _sampling_jitter(events)
    quantization_ms = _timer_resolution_ms(t_sorted)

    drift_ppm = _clock_drift_ppm(t_src, t_mono)
    # collector overhead: receipt - monotonic-at-ingest (same monotonic domain)
    overhead = t_recv - t_mono
    overhead_ms = float(np.median(overhead[np.isfinite(overhead)]) * 1000.0) if n else 0.0
    # source->collector latency after aligning source onto the monotonic timeline
    latency_ms = _source_latency_ms(t_src, t_mono)

    # --- coverage / activity ---
    span = float(t_sorted[-1] - t_sorted[0]) if n > 1 else 0.0
    active_fraction, gap_count = _activity(t_sorted, gap_s=1.0)
    modality_alignment = _modality_alignment(events)

    metrics = {
        "drop_rate": drop_rate,
        "duplicate_rate": dup_rate,
        "reorder_rate": reorder_rate,
        "jitter_ms": jitter_ms,
        "quantization_ms": quantization_ms,
        "clock_drift_ppm": drift_ppm,
        "source_to_receipt_ms": latency_ms,
        "collector_overhead_ms": overhead_ms,
        "session_seconds": span,
        "active_fraction": active_fraction,
        "sparse_gap_count": gap_count,
        "modality_alignment": modality_alignment,
        "n_events": n,
    }
    verdict, reasons = _verdict(metrics, thr)
    summary["metrics"] = metrics
    summary["verdict"] = verdict
    summary["reasons"] = reasons
    return summary


def _mad(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    med = np.median(x)
    return float(np.median(np.abs(x - med)))


def _sampling_jitter(events: List[Dict[str, Any]]) -> float:
    """Sampling jitter on periodically-sampled streams (pointer move, motion), worst
    across streams. Measured as the MAD of residuals from a linear fit of timestamp vs
    sample index — NOT the raw inter-sample MAD, which sorting caps at ~half the sample
    interval. Keyboard is event-driven and excluded."""
    streams: Dict[str, List[float]] = {}
    for e in events:
        mod, typ = e.get("modality"), e.get("type")
        if mod == "pointer" and typ == "move":
            streams.setdefault("pointer_move", []).append(float(e.get("t_source", 0.0)))
        elif mod == "motion":
            streams.setdefault("motion", []).append(float(e.get("t_source", 0.0)))
    jitter = 0.0
    for ts in streams.values():
        if len(ts) < 4:
            continue
        arr = np.sort(np.array(ts))
        idx = np.arange(len(arr))
        slope, intercept = np.polyfit(idx, arr, 1)
        resid = arr - (slope * idx + intercept)
        jitter = max(jitter, float(_mad(resid) * 1000.0))
    return jitter


def _timer_resolution_ms(t_sorted: np.ndarray) -> float:
    """Finest distinct positive timestamp step across all events — the effective timer
    resolution. Large == timestamps snapped to a coarse grid (quantization)."""
    if t_sorted.size < 3:
        return 0.0
    dt = np.diff(t_sorted)
    dt = dt[dt > 1e-9]
    if dt.size == 0:
        return 0.0
    return float(np.min(dt) * 1000.0)


def _infer_quantization(dt_pos: np.ndarray) -> float:
    """Estimate the timestamp grid: the smallest robust positive inter-arrival step.
    A coarse grid (large value) means quantized timestamps."""
    if dt_pos.size == 0:
        return 0.0
    return float(np.quantile(dt_pos, 0.05))


def _clock_drift_ppm(t_src: np.ndarray, t_mono: np.ndarray) -> float:
    good = np.isfinite(t_src) & np.isfinite(t_mono)
    if good.sum() < 3:
        return 0.0
    x = t_src[good] - t_src[good][0]
    y = t_mono[good] - t_mono[good][0]
    if np.ptp(x) < 1e-9:
        return 0.0
    slope = np.polyfit(x, y, 1)[0]
    return float(abs(slope - 1.0) * 1e6)


def _source_latency_ms(t_src: np.ndarray, t_mono: np.ndarray) -> float:
    good = np.isfinite(t_src) & np.isfinite(t_mono)
    if good.sum() < 3:
        return 0.0
    x = t_src[good]
    y = t_mono[good]
    if np.ptp(x) < 1e-9:
        return float(abs(np.median(y - x)) * 1000.0)
    slope, intercept = np.polyfit(x, y, 1)
    aligned = slope * x + intercept
    resid = y - aligned
    return float(np.median(np.abs(resid)) * 1000.0)


def _activity(t_sorted: np.ndarray, gap_s: float):
    if t_sorted.size < 2:
        return 0.0, 0
    span = t_sorted[-1] - t_sorted[0]
    if span <= 0:
        return 0.0, 0
    dt = np.diff(t_sorted)
    gaps = dt[dt > gap_s]
    idle = float(gaps.sum())
    active_fraction = max(0.0, 1.0 - idle / span)
    return active_fraction, int(gaps.size)


def _modality_alignment(events: List[Dict[str, Any]]) -> float:
    """Fraction of the session span covered by >=2 modalities simultaneously (coarse
    1s bins). 0 == modalities never overlap; ~1 == well-aligned multimodal stream."""
    by_mod: Dict[str, List[float]] = {}
    for e in events:
        by_mod.setdefault(e.get("modality", "?"), []).append(float(e.get("t_source", 0.0)))
    active_mods = [m for m, ts in by_mod.items() if m in ("keyboard", "pointer", "touch", "motion")]
    if len(active_mods) < 2:
        return 0.0
    all_t = np.array([t for ts in by_mod.values() for t in ts])
    lo, hi = all_t.min(), all_t.max()
    if hi - lo <= 0:
        return 0.0
    nbins = max(1, int(np.ceil(hi - lo)))
    bins_per_mod = {}
    for m in active_mods:
        b = set(int(t - lo) for t in by_mod[m])
        bins_per_mod[m] = b
    overlap = 0
    for i in range(nbins):
        present = sum(1 for m in active_mods if i in bins_per_mod[m])
        if present >= 2:
            overlap += 1
    return overlap / nbins


def _verdict(m: Dict[str, float], thr: InstrumentationThresholds):
    """Three-way gate. Each metric is tested against its ready and degraded bounds."""
    ready_fail: List[str] = []
    degraded_fail: List[str] = []

    def upper(name, val, ready, degraded):
        if val > ready:
            ready_fail.append(name)
        if val > degraded:
            degraded_fail.append(name)

    def lower(name, val, ready, degraded):
        if val < ready:
            ready_fail.append(name)
        if val < degraded:
            degraded_fail.append(name)

    upper("drop_rate", m["drop_rate"], thr.max_drop_rate, thr.max_drop_rate_degraded)
    upper("duplicate_rate", m["duplicate_rate"], thr.max_duplicate_rate, thr.max_duplicate_rate_degraded)
    upper("reorder_rate", m["reorder_rate"], thr.max_reorder_rate, thr.max_reorder_rate_degraded)
    upper("jitter_ms", m["jitter_ms"], thr.max_jitter_ms, thr.max_jitter_ms_degraded)
    upper("quantization_ms", m["quantization_ms"], thr.max_quantization_ms, thr.max_quantization_ms_degraded)
    upper("clock_drift_ppm", m["clock_drift_ppm"], thr.max_clock_drift_ppm, thr.max_clock_drift_ppm_degraded)
    upper("source_to_receipt_ms", m["source_to_receipt_ms"], thr.max_source_to_receipt_ms,
          thr.max_source_to_receipt_ms_degraded)
    upper("collector_overhead_ms", m["collector_overhead_ms"], thr.max_collector_overhead_ms,
          thr.max_collector_overhead_ms_degraded)
    lower("session_seconds", m["session_seconds"], thr.min_session_seconds, thr.min_session_seconds_degraded)
    lower("n_events", m["n_events"], thr.min_events, thr.min_events_degraded)
    lower("active_fraction", m["active_fraction"], thr.min_active_fraction, thr.min_active_fraction_degraded)

    if not ready_fail:
        return READY, []
    if not degraded_fail:
        return DEGRADED, ready_fail
    return NOT_READY, degraded_fail


def summarize_cohort(quality_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {READY: 0, DEGRADED: 0, NOT_READY: 0}
    for q in quality_summaries:
        counts[q.get("verdict", NOT_READY)] = counts.get(q.get("verdict", NOT_READY), 0) + 1
    return {"counts": counts, "n": len(quality_summaries)}
