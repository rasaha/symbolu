"""Cross-modal / context coupling candidates + matched controls.

These are CANDIDATE features, not a privileged mechanism. Every coupling statistic is
computed in three matched variants so the analysis can credit coupling only when REAL
coupling beats a fair all-modalities marginal baseline AND its controls:

  * real  — as observed.
  * shuf  — the pointer timing is decorrelated from the keyboard while each modality's
            marginal is preserved (circular shift / uniform re-draw / window permutation).
            Coupling that survives this is a marginal artifact, not coordination.
  * ctxm  — the same decorrelation but WITHIN each task-stage segment, so context/task
            -forced coupling is preserved and only the user-specific residual survives.

Statistics: max |lagged cross-correlation|, zero-lag cross-correlation, event
cross-correlogram peak, and windowed CCA mean canonical correlation. A spectral
coherence (phase meaningful only for continuous motion) is added when motion exists,
and is NOT given special weight.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from cyber_security.behavioral_biometrics.config import DEFAULT, FeatureConfig
from cyber_security.behavioral_biometrics.numerics import CCA

_STATS = ("xcorr_max_abs", "xcorr_zero", "correlogram_peak", "cca_mean_corr")


def _seed_for(session: Dict[str, Any], cfg: FeatureConfig) -> int:
    sid = session.get("session_meta", {}).get("session_id", "")
    return int(hashlib.sha256(f"{cfg.shuffle_seed}|{sid}".encode()).hexdigest()[:8], 16)


def _z(x: np.ndarray) -> np.ndarray:
    s = x.std()
    return (x - x.mean()) / s if s > 1e-9 else x - x.mean()


def _streams(session, cfg):
    events = session.get("events", [])
    kbd = sorted([e["t_source"] for e in events
                  if e.get("modality") == "keyboard" and e.get("type") == "key_down"])
    moves = sorted([e for e in events if e.get("modality") == "pointer" and e.get("type") == "move"],
                   key=lambda e: e["t_source"])
    btn = sorted([e["t_source"] for e in events if e.get("type") == "button_down"])
    if len(kbd) < 3 or len(moves) < 3:
        return None
    t0 = min(kbd[0], moves[0]["t_source"])
    t1 = max(kbd[-1], moves[-1]["t_source"])
    if t1 - t0 < 1.0:
        return None
    n = max(8, int((t1 - t0) * cfg.resample_hz))
    grid = np.linspace(t0, t1, n)
    rate = np.zeros(n)
    for kt in np.array(kbd):
        rate += np.exp(-0.5 * ((grid - kt) / 0.08) ** 2)
    mt = np.array([m["t_source"] for m in moves])
    mx = np.array([float(m["payload"].get("x", 0.0)) for m in moves])
    my = np.array([float(m["payload"].get("y", 0.0)) for m in moves])
    dt = np.diff(mt)
    dt = np.where(dt <= 0, 1e-6, dt)
    speed = np.sqrt(np.diff(mx) ** 2 + np.diff(my) ** 2) / dt
    ptr = np.interp(grid, mt[1:], speed, left=0.0, right=0.0)
    stages = _stage_per_sample(events, grid)
    return dict(grid=grid, rate=_z(rate), ptr=_z(ptr), stages=stages,
                kbd_t=kbd, btn_t=(btn or [m["t_source"] for m in moves]), span=(t0, t1))


def _stage_per_sample(events, grid) -> np.ndarray:
    marks = sorted([(e["t_source"], e.get("context", {}).get("task_stage", "")) for e in events],
                   key=lambda x: x[0])
    labels: Dict[str, int] = {}
    ids, mi, cur = [], 0, ""
    for t in grid:
        while mi < len(marks) and marks[mi][0] <= t:
            cur = marks[mi][1]
            mi += 1
        ids.append(labels.setdefault(cur, len(labels)))
    return np.array(ids)


def _xcorr(a, b, cfg) -> Tuple[float, float]:
    max_lag = max(1, min(int(cfg.coupling_max_lag_ms / 1000.0 * cfg.resample_hz), len(a) - 1))
    best, zero = 0.0, 0.0
    for L in range(-max_lag, max_lag + 1):
        if L < 0:
            aa, bb = a[:L], b[-L:]
        elif L > 0:
            aa, bb = a[L:], b[:-L]
        else:
            aa, bb = a, b
        if len(aa) < 4 or aa.std() < 1e-9 or bb.std() < 1e-9:
            continue
        c = float(np.corrcoef(aa, bb)[0, 1])
        if np.isnan(c):
            c = 0.0
        if L == 0:
            zero = c
        if abs(c) > abs(best):
            best = c
    return abs(best), zero


def _correlogram_peak(kbd_t, ptr_t, cfg) -> float:
    if len(kbd_t) < 3 or len(ptr_t) < 3:
        return 0.0
    kbd_t, ptr_t = np.array(kbd_t), np.array(ptr_t)
    max_lag = cfg.coupling_max_lag_ms / 1000.0
    step = cfg.coupling_lag_step_ms / 1000.0
    edges = np.arange(-max_lag, max_lag + step, step)
    hist = np.zeros(len(edges) - 1)
    for kt in kbd_t:
        d = ptr_t - kt
        d = d[np.abs(d) <= max_lag]
        if d.size:
            hist += np.histogram(d, bins=edges)[0]
    if hist.sum() == 0:
        return 0.0
    exp = hist.mean()
    return float((hist.max() - exp) / (exp + 1e-9))


def _cca_windows(session, cfg, permute: Optional[np.ndarray] = None) -> float:
    events = session.get("events", [])
    t_all = [e["t_source"] for e in events]
    if not t_all:
        return 0.0
    t0, t1 = min(t_all), max(t_all)
    w, s = cfg.window_seconds, cfg.window_stride_seconds
    Xk, Xp = [], []
    start = t0
    while start + w <= t1 + 1e-9:
        win = [e for e in events if start <= e["t_source"] < start + w]
        kv, pv = _kbd_vec(win), _ptr_vec(win)
        if kv is not None and pv is not None:
            Xk.append(kv)
            Xp.append(pv)
        start += s
    if len(Xk) < 4:
        return 0.0
    Xk, Xp = np.array(Xk), np.array(Xp)
    if permute is not None:
        idx = permute[:len(Xp)] % len(Xp)
        Xp = Xp[idx]
    try:
        return CCA.fit(Xk, Xp, ridge=cfg.ridge).mean_correlation()
    except np.linalg.LinAlgError:
        return 0.0


def _kbd_vec(win):
    downs = sorted(e["t_source"] for e in win
                   if e.get("modality") == "keyboard" and e.get("type") == "key_down")
    if len(downs) < 2:
        return None
    dt = np.diff(downs)
    return np.array([len(downs), float(np.mean(dt)), float(np.std(dt))])


def _ptr_vec(win):
    moves = sorted([e for e in win if e.get("modality") == "pointer" and e.get("type") == "move"],
                   key=lambda e: e["t_source"])
    if len(moves) < 2:
        return None
    x = np.array([float(m["payload"].get("x", 0.0)) for m in moves])
    y = np.array([float(m["payload"].get("y", 0.0)) for m in moves])
    t = np.array([m["t_source"] for m in moves])
    dt = np.diff(t)
    dt = np.where(dt <= 0, 1e-6, dt)
    speed = np.sqrt(np.diff(x) ** 2 + np.diff(y) ** 2) / dt
    return np.array([float(np.mean(speed)), float(np.std(speed)), float(len(moves))])


def _variant_stats(S, session, cfg, variant: str, seed: int) -> Dict[str, float]:
    rate, ptr, stages = S["rate"], S["ptr"], S["stages"]
    rng = np.random.default_rng(seed)
    t0, t1 = S["span"]
    if variant == "real":
        ptr_x = ptr
        ptr_t = S["btn_t"]
        perm = None
    elif variant == "shuf":
        shift = int(rng.integers(len(ptr) // 4, max(2, 3 * len(ptr) // 4)))
        ptr_x = np.roll(ptr, shift)
        ptr_t = list(rng.uniform(t0, t1, size=len(S["btn_t"])))
        perm = rng.permutation(10_000)
    else:  # ctxm: within-stage decorrelation
        ptr_x = ptr.copy()
        for s in np.unique(stages):
            idx = np.where(stages == s)[0]
            ptr_x[idx] = ptr[idx][rng.permutation(len(idx))]
        ptr_t = _within_stage_times(session, S["btn_t"], rng)
        perm = rng.permutation(10_000)
    xmax, xzero = _xcorr(rate, ptr_x, cfg)
    return {
        "xcorr_max_abs": xmax,
        "xcorr_zero": xzero,
        "correlogram_peak": _correlogram_peak(S["kbd_t"], ptr_t, cfg),
        "cca_mean_corr": _cca_windows(session, cfg, permute=perm),
    }


def _within_stage_times(session, times, rng):
    events = session.get("events", [])
    marks = sorted([(e["t_source"], e.get("context", {}).get("task_stage", "")) for e in events],
                   key=lambda x: x[0])
    if not marks:
        return list(rng.permutation(times))
    # assign each time to a stage, then jitter within that stage's time span
    stage_spans: Dict[str, List[float]] = {}
    for t, st in marks:
        stage_spans.setdefault(st, []).append(t)
    lo = {st: min(v) for st, v in stage_spans.items()}
    hi = {st: max(v) for st, v in stage_spans.items()}
    out = []
    for t in times:
        st = min(marks, key=lambda m: abs(m[0] - t))[1]
        a, b = lo.get(st, t), hi.get(st, t)
        out.append(float(rng.uniform(a, b)) if b > a else t)
    return out


def _coherence(session) -> Optional[float]:
    ms = sorted([e for e in session.get("events", []) if e.get("modality") == "motion"],
                key=lambda e: e["t_source"])
    if len(ms) < 32:
        return None
    ax = np.array([float(e["payload"].get("ax", 0.0)) for e in ms])
    gx = np.array([float(e["payload"].get("gx", 0.0)) for e in ms])
    if ax.std() < 1e-9 or gx.std() < 1e-9:
        return None
    fa, fg = np.fft.rfft(_z(ax)), np.fft.rfft(_z(gx))
    coh = np.abs(fa * np.conj(fg)) ** 2 / ((np.abs(fa) ** 2) * (np.abs(fg) ** 2) + 1e-12)
    return float(np.clip(np.nanmean(coh), 0.0, 1.0))


def extract(session: Dict[str, Any], cfg: Optional[FeatureConfig] = None) -> Dict[str, float]:
    cfg = cfg or DEFAULT.features
    out: Dict[str, float] = {"coupling_available": 0.0}
    S = _streams(session, cfg)
    if S is None:
        return out
    out["coupling_available"] = 1.0
    seed = _seed_for(session, cfg)
    variants = {"real": _variant_stats(S, session, cfg, "real", seed),
                "shuf": _variant_stats(S, session, cfg, "shuf", seed + 1),
                "ctxm": _variant_stats(S, session, cfg, "ctxm", seed + 2)}
    for stat in _STATS:
        out[stat] = variants["real"][stat]
        out[f"{stat}__shuf"] = variants["shuf"][stat]
        out[f"{stat}__ctxm"] = variants["ctxm"][stat]
    out["resid_vs_shuf"] = float(np.mean([variants["real"][s] - variants["shuf"][s] for s in _STATS]))
    out["resid_vs_ctxm"] = float(np.mean([variants["real"][s] - variants["ctxm"][s] for s in _STATS]))
    coh = _coherence(session)
    out["motion_coherence_available"] = 0.0 if coh is None else 1.0
    if coh is not None:
        out["motion_coherence"] = coh
    return out


def coupling_view(record: Dict[str, Any], arm: str) -> Dict[str, float]:
    """Select the coupling statistics for an analysis ARM into a COMMON feature-name
    slot, so the marginal+coupling model sees matched features across real/shuf/ctxm."""
    c = record.get("coupling", {})
    if not c.get("coupling_available"):
        return {}
    suffix = {"real": "", "shuf": "__shuf", "ctxm": "__ctxm"}[arm]
    return {f"cpl.{stat}": c.get(f"{stat}{suffix}", 0.0) for stat in _STATS}
