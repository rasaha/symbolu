"""Deterministic, versioned feature extraction.

Produces, from a validated session, a feature record with four namespaces:
  * ``marginal``  — per-modality behavioral features (keyboard, pointer, touch, motion)
  * ``coupling``  — cross-modal / context candidates (filled by ``coupling.py``)
  * ``quality``   — instrument-quality features (usable but flagged; never identity on their own)
  * ``meta``      — provenance (participant/session/device/task, extractor version) — NEVER a model feature

Everything is a pure function of the session; no clock, RNG, or network. Feature
names are stable and sorted so ``feature_vector`` is reproducible.

Privacy: keyboard features use key CLASS and salted content-free key ids only. Digraph
timing is summarized as a distribution, never as a per-character table.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from cyber_security.behavioral_biometrics import coupling
from cyber_security.behavioral_biometrics.config import DEFAULT, FeatureConfig
from cyber_security.behavioral_biometrics.version import EXTRACTOR_VERSION


def _dist_stats(x: List[float], prefix: str) -> Dict[str, float]:
    a = np.asarray([v for v in x if v is not None and np.isfinite(v)], dtype=float)
    if a.size == 0:
        return {f"{prefix}.{s}": 0.0 for s in ("mean", "std", "median", "iqr", "p10", "p90", "cv")}
    mean = float(a.mean())
    std = float(a.std())
    med = float(np.median(a))
    p10, p90 = float(np.quantile(a, 0.1)), float(np.quantile(a, 0.9))
    iqr = float(np.quantile(a, 0.75) - np.quantile(a, 0.25))
    cv = float(std / mean) if mean != 0 else 0.0
    return {f"{prefix}.mean": mean, f"{prefix}.std": std, f"{prefix}.median": med,
            f"{prefix}.iqr": iqr, f"{prefix}.p10": p10, f"{prefix}.p90": p90, f"{prefix}.cv": cv}


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

def _keyboard_features(events: List[Dict[str, Any]], cfg: FeatureConfig) -> Dict[str, float]:
    downs = [e for e in events if e.get("modality") == "keyboard" and e.get("type") == "key_down"]
    ups = [e for e in events if e.get("modality") == "keyboard" and e.get("type") == "key_up"]
    out: Dict[str, float] = {}
    if not downs:
        out["kbd.present"] = 0.0
        return out
    out["kbd.present"] = 1.0

    # pair down/up by key identity (key_id if present else key_class), FIFO
    open_map: Dict[str, List[float]] = {}
    dwell: List[float] = []
    down_sorted = sorted(downs, key=lambda e: e["t_source"])
    ups_sorted = sorted(ups, key=lambda e: e["t_source"])
    key_of = lambda e: e["payload"].get("key_id") or e["payload"].get("key_class") or "?"
    pending: Dict[str, List[float]] = {}
    for e in down_sorted:
        pending.setdefault(key_of(e), []).append(e["t_source"])
    for e in ups_sorted:
        k = key_of(e)
        if pending.get(k):
            t_down = pending[k].pop(0)
            d = e["t_source"] - t_down
            if d >= 0:
                dwell.append(d)
    out.update(_dist_stats(dwell, "kbd.dwell"))

    # flight times (press-to-press, release-to-press)
    dt_down = [down_sorted[i + 1]["t_source"] - down_sorted[i]["t_source"]
               for i in range(len(down_sorted) - 1)]
    out.update(_dist_stats(dt_down, "kbd.flight_pp"))
    # release-to-press needs interleaving; approximate with matched up times
    ups_t = sorted(e["t_source"] for e in ups_sorted)
    downs_t = [e["t_source"] for e in down_sorted]
    rp = []
    j = 0
    for dt in downs_t[1:]:
        while j < len(ups_t) and ups_t[j] < dt:
            j += 1
        if 0 < j <= len(ups_t):
            rp.append(dt - ups_t[j - 1])
    out.update(_dist_stats(rp, "kbd.flight_rp"))

    # digraph timing distribution (privacy-safe: distribution only)
    digraph: Dict[Tuple[str, str], List[float]] = {}
    for i in range(len(down_sorted) - 1):
        a, b = key_of(down_sorted[i]), key_of(down_sorted[i + 1])
        digraph.setdefault((a, b), []).append(down_sorted[i + 1]["t_source"] - down_sorted[i]["t_source"])
    dg_medians = [float(np.median(v)) for v in digraph.values() if len(v) >= cfg.digraph_min_count]
    out.update(_dist_stats(dg_medians, "kbd.digraph"))
    out["kbd.digraph_types"] = float(len(dg_medians))

    # typing bursts + pauses
    pauses = [d for d in dt_down if d > 0.5]
    bursts = _bursts(downs_t, gap=0.5)
    out.update(_dist_stats(pauses, "kbd.pause"))
    out.update(_dist_stats(bursts, "kbd.burst"))

    # error/correction timing WITHOUT text: backspace inter-timing + rate
    bs = [e["t_source"] for e in down_sorted if e["payload"].get("key_class") == "backspace"]
    out["kbd.backspace_rate"] = float(len(bs) / max(1, len(down_sorted)))
    out.update(_dist_stats([bs[i + 1] - bs[i] for i in range(len(bs) - 1)], "kbd.backspace_gap"))

    # rhythm / variability
    out["kbd.rate_hz"] = float(len(down_sorted) / max(1e-6, (downs_t[-1] - downs_t[0]))) if len(downs_t) > 1 else 0.0
    out["kbd.rhythm_var"] = float(np.std(dt_down)) if dt_down else 0.0
    return out


def _bursts(times: List[float], gap: float) -> List[float]:
    if not times:
        return []
    bursts, start, prev = [], times[0], times[0]
    for t in times[1:]:
        if t - prev > gap:
            bursts.append(prev - start)
            start = t
        prev = t
    bursts.append(prev - start)
    return [b for b in bursts if b > 0]


# ---------------------------------------------------------------------------
# Pointer
# ---------------------------------------------------------------------------

def _pointer_features(events: List[Dict[str, Any]], cfg: FeatureConfig) -> Dict[str, float]:
    moves = sorted([e for e in events if e.get("modality") == "pointer" and e.get("type") == "move"],
                   key=lambda e: e["t_source"])
    out: Dict[str, float] = {}
    if len(moves) < 3:
        out["ptr.present"] = 0.0
        return out
    out["ptr.present"] = 1.0

    t = np.array([e["t_source"] for e in moves])
    x = np.array([float(e["payload"].get("x", 0.0)) for e in moves])
    y = np.array([float(e["payload"].get("y", 0.0)) for e in moves])
    dt = np.diff(t)
    dt = np.where(dt <= 0, 1e-6, dt)
    dx, dy = np.diff(x), np.diff(y)
    seg = np.sqrt(dx ** 2 + dy ** 2)
    vel = seg / dt
    out.update(_dist_stats(vel.tolist(), "ptr.vel"))
    acc = np.diff(vel) / dt[1:]
    out.update(_dist_stats(acc.tolist(), "ptr.acc"))
    jerk = np.diff(acc) / dt[2:] if acc.size > 1 else np.array([])
    out.update(_dist_stats(jerk.tolist(), "ptr.jerk"))

    # curvature: turning angle per unit path
    ang = np.arctan2(dy, dx)
    dang = np.abs(_wrap(np.diff(ang)))
    curv = dang / (seg[1:] + 1e-9)
    out.update(_dist_stats(curv.tolist(), "ptr.curv"))

    # path efficiency + length
    path_len = float(seg.sum())
    straight = float(np.hypot(x[-1] - x[0], y[-1] - y[0]))
    out["ptr.path_length"] = path_len
    out["ptr.path_efficiency"] = float(straight / path_len) if path_len > 0 else 0.0

    # pauses + movement segments
    move_pauses = dt[seg < 1e-4]
    out.update(_dist_stats(move_pauses.tolist(), "ptr.pause"))
    out.update(_dist_stats(seg.tolist(), "ptr.segment"))

    # overshoot / correction: velocity-direction reversals
    sign_rev = int(np.sum(np.diff(np.sign(dx)) != 0) + np.sum(np.diff(np.sign(dy)) != 0))
    out["ptr.reversals_per_sec"] = float(sign_rev / max(1e-6, t[-1] - t[0]))

    # click timing (button_down -> button_up dwell)
    downs = sorted([e for e in events if e.get("type") == "button_down"], key=lambda e: e["t_source"])
    ups = sorted([e for e in events if e.get("type") == "button_up"], key=lambda e: e["t_source"])
    clicks = []
    j = 0
    for d in downs:
        while j < len(ups) and ups[j]["t_source"] < d["t_source"]:
            j += 1
        if j < len(ups):
            clicks.append(ups[j]["t_source"] - d["t_source"])
            j += 1
    out.update(_dist_stats(clicks, "ptr.click_dwell"))
    out["ptr.click_rate"] = float(len(downs) / max(1e-6, t[-1] - t[0]))
    return out


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


# ---------------------------------------------------------------------------
# Touch + Motion (where available)
# ---------------------------------------------------------------------------

def _touch_features(events, cfg) -> Dict[str, float]:
    ts = [e for e in events if e.get("modality") == "touch"]
    if not ts:
        return {"touch.present": 0.0}
    out = {"touch.present": 1.0}
    pressure = [float(e["payload"].get("pressure", 0.0)) for e in ts if "pressure" in e["payload"]]
    size = [float(e["payload"].get("size", 0.0)) for e in ts if "size" in e["payload"]]
    out.update(_dist_stats(pressure, "touch.pressure"))
    out.update(_dist_stats(size, "touch.size"))
    return out


def _motion_features(events, cfg) -> Dict[str, float]:
    ms = [e for e in events if e.get("modality") == "motion"]
    if not ms:
        return {"motion.present": 0.0}
    out = {"motion.present": 1.0}
    for axis in ("ax", "ay", "az", "gx", "gy", "gz"):
        vals = [float(e["payload"].get(axis, 0.0)) for e in ms if axis in e["payload"]]
        if vals:
            out.update(_dist_stats(vals, f"motion.{axis}"))
    return out


# ---------------------------------------------------------------------------
# Quality features
# ---------------------------------------------------------------------------

def _quality_features(session: Dict[str, Any]) -> Dict[str, float]:
    events = session.get("events", [])
    by_mod = {}
    for e in events:
        by_mod[e.get("modality")] = by_mod.get(e.get("modality"), 0) + 1
    t = sorted(float(e.get("t_source", 0.0)) for e in events)
    span = (t[-1] - t[0]) if len(t) > 1 else 0.0
    dt = np.diff(t) if len(t) > 1 else np.array([])
    return {
        "q.n_events": float(len(events)),
        "q.kbd_events": float(by_mod.get("keyboard", 0)),
        "q.ptr_events": float(by_mod.get("pointer", 0)),
        "q.touch_events": float(by_mod.get("touch", 0)),
        "q.motion_events": float(by_mod.get("motion", 0)),
        "q.span_s": float(span),
        "q.sampling_stability": float(1.0 / (1.0 + np.std(dt))) if dt.size else 0.0,
        "q.kbd_available": float(by_mod.get("keyboard", 0) > 0),
        "q.ptr_available": float(by_mod.get("pointer", 0) > 0),
        "q.touch_available": float(by_mod.get("touch", 0) > 0),
        "q.motion_available": float(by_mod.get("motion", 0) > 0),
    }


# ---------------------------------------------------------------------------
# Top-level extraction
# ---------------------------------------------------------------------------

def extract(session: Dict[str, Any], cfg: Optional[FeatureConfig] = None,
            with_coupling: bool = True) -> Dict[str, Any]:
    """Return a feature record. Deterministic; identifiers live only in ``meta``."""
    cfg = cfg or DEFAULT.features
    events = session.get("events", [])
    meta = session.get("session_meta", {})

    marginal: Dict[str, float] = {}
    marginal.update(_keyboard_features(events, cfg))
    marginal.update(_pointer_features(events, cfg))
    marginal.update(_touch_features(events, cfg))
    marginal.update(_motion_features(events, cfg))

    record = {
        "marginal": marginal,
        "coupling": coupling.extract(session, cfg) if with_coupling else {},
        "quality": _quality_features(session),
        "meta": {
            "participant_pseudonym": meta.get("participant_pseudonym", ""),
            "session_id": meta.get("session_id", ""),
            "device_id": meta.get("device_id", ""),
            "task_id": meta.get("task_id", ""),
            "trial_id": meta.get("trial_id", ""),
            "device_class": meta.get("device_class", "unknown"),
            "role": meta.get("role", ""),
            "condition": meta.get("condition", "unspecified"),
            "data_provenance": meta.get("data_provenance", "REAL"),
            "data_origin": meta.get("data_origin"),
            "extractor_version": EXTRACTOR_VERSION,
        },
    }
    return record


# ---------------------------------------------------------------------------
# Vectorization (identifiers excluded from the model surface)
# ---------------------------------------------------------------------------

_NAMESPACES = ("marginal", "coupling", "quality")


def feature_names(record: Dict[str, Any], namespaces=("marginal",)) -> List[str]:
    names: List[str] = []
    for ns in namespaces:
        names.extend(f"{ns}::{k}" for k in record.get(ns, {}))
    return sorted(names)


def project_dicts(dicts: List[Dict[str, float]], names: List[str]) -> np.ndarray:
    """Project feature dicts onto a FIXED column order (defined by train). Unknown
    keys are ignored; missing keys 0-filled. This is how test/enroll vectors are kept
    aligned to the train-defined feature space (no test-driven column drift)."""
    idx = {n: i for i, n in enumerate(names)}
    X = np.zeros((len(dicts), len(names)), dtype=float)
    for r, d in enumerate(dicts):
        for k, v in d.items():
            if k in idx and v is not None and np.isfinite(v):
                X[r, idx[k]] = float(v)
    return X


def vectorize_dicts(dicts: List[Dict[str, float]]) -> Tuple[List[str], np.ndarray]:
    """Build a dense matrix over the union of keys of arbitrary flat feature dicts
    (used to assemble analysis arms that mix marginal + selected coupling slots).
    Missing keys 0-filled."""
    all_names = sorted({k for d in dicts for k in d})
    idx = {n: i for i, n in enumerate(all_names)}
    X = np.zeros((len(dicts), len(all_names)), dtype=float)
    for i, d in enumerate(dicts):
        for k, v in d.items():
            if v is not None and np.isfinite(v):
                X[i, idx[k]] = float(v)
    return all_names, X


def vectorize(records: List[Dict[str, Any]], namespaces=("marginal",)
              ) -> Tuple[List[str], np.ndarray]:
    """Build a dense matrix over the UNION of feature names in the given namespaces.
    Missing features are 0-filled. Identifier/meta fields are never included."""
    all_names = set()
    for r in records:
        for ns in namespaces:
            all_names.update(f"{ns}::{k}" for k in r.get(ns, {}))
    names = sorted(all_names)
    idx = {n: i for i, n in enumerate(names)}
    X = np.zeros((len(records), len(names)), dtype=float)
    for r_i, r in enumerate(records):
        for ns in namespaces:
            for k, v in r.get(ns, {}).items():
                nm = f"{ns}::{k}"
                if nm in idx and v is not None and np.isfinite(v):
                    X[r_i, idx[nm]] = float(v)
    return names, X
