"""Self-contained SVG plots (no matplotlib): representative trajectories and
DET frontiers. Deterministic; renders from the same simulator + analysis output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .calibration import fit_calibration
from .config import THRESHOLD_SWEEP, StudyConfig
from .detectors import score
from .observers import run_observer
from .trajectories import generate

RESULTS_DIR = Path(__file__).parent / "results"
PLOTS_DIR = RESULTS_DIR / "plots"

_COLORS = ["#2b6cb0", "#c53030", "#2f855a", "#6b46c1", "#b7791f", "#718096"]


def _poly(points: Sequence[Tuple[float, float]], color: str, width: float = 1.6) -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (f'<polyline fill="none" stroke="{color}" stroke-width="{width}" '
            f'points="{pts}"/>')


def _line_chart(
    series: Dict[str, List[float]],
    title: str,
    x0: float,
    y0: float,
    w: float,
    h: float,
    ymax: float = None,
) -> str:
    n = max((len(v) for v in series.values()), default=1)
    ymax = ymax or max((max(v) if v else 0.0 for v in series.values()), default=1.0)
    ymax = ymax if ymax > 0 else 1.0
    body = [f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#fff" '
            f'stroke="#cbd5e0"/>',
            f'<text x="{x0}" y="{y0-6}" font-size="12" font-family="sans-serif" '
            f'fill="#2d3748">{title}</text>']
    for k, (name, vals) in enumerate(series.items()):
        color = _COLORS[k % len(_COLORS)]
        pts = []
        for t, v in enumerate(vals):
            px = x0 + (t / max(n - 1, 1)) * w
            py = y0 + h - (min(v, ymax) / ymax) * h
            pts.append((px, py))
        body.append(_poly(pts, color))
        body.append(f'<text x="{x0+6}" y="{y0+14+13*k}" font-size="10" '
                    f'font-family="sans-serif" fill="{color}">{name}</text>')
    return "\n".join(body)


def _scatter_frontier(
    frontiers: Dict[str, dict],
    arms: List[str],
    x0: float,
    y0: float,
    w: float,
    h: float,
) -> str:
    body = [f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#fff" '
            f'stroke="#cbd5e0"/>',
            f'<text x="{x0}" y="{y0-6}" font-size="12" font-family="sans-serif" '
            f'fill="#2d3748">DET frontier: false-challenge rate (x) vs '
            f'adaptive-attack detection (y)</text>']
    # axis ticks
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gx = x0 + frac * w
        gy = y0 + h - frac * h
        body.append(f'<line x1="{gx}" y1="{y0}" x2="{gx}" y2="{y0+h}" '
                    f'stroke="#edf2f7"/>')
        body.append(f'<line x1="{x0}" y1="{gy}" x2="{x0+w}" y2="{gy}" '
                    f'stroke="#edf2f7"/>')
        body.append(f'<text x="{gx-8}" y="{y0+h+12}" font-size="9" '
                    f'font-family="sans-serif" fill="#718096">{frac:.2f}</text>')
        body.append(f'<text x="{x0-22}" y="{gy+3}" font-size="9" '
                    f'font-family="sans-serif" fill="#718096">{frac:.2f}</text>')
    for k, arm in enumerate(arms):
        color = _COLORS[k % len(_COLORS)]
        fr = frontiers[arm]
        pts = []
        order = np.argsort(fr["far"])
        for j in order:
            far = fr["far"][j]
            det = fr["det_adaptive"][j]
            px = x0 + far * w
            py = y0 + h - det * h
            pts.append((px, py))
        body.append(_poly(pts, color, 1.8))
        body.append(f'<text x="{x0+w-140}" y="{y0+14+13*k}" font-size="10" '
                    f'font-family="sans-serif" fill="{color}">{arm}</text>')
    return "\n".join(body)


def _svg(width: int, height: int, inner: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">\n'
            f'<rect width="{width}" height="{height}" fill="#f7fafc"/>\n'
            f'{inner}\n</svg>\n')


def render_trajectories(cfg: StudyConfig) -> Path:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    families = [
        ("F03_linear_drift", "legit linear drift"),
        ("F06_abrupt_takeover", "abrupt takeover"),
        ("F07_slow_linear_takeover", "slow linear takeover"),
        ("F10_detector_aware_optimized", "detector-aware (BCVF-evading)"),
    ]
    calibration = fit_calibration(cfg)
    panels = []
    W, PH = 520, 150
    for i, (fam, label) in enumerate(families):
        ev = generate(fam, seed=42_000 + i, cfg=cfg, sigma=0.30,
                      separation=4.0, ramp_duration=90.0, missing_rate=0.0)
        tr = run_observer(ev, cfg, guarded=False)
        dnorm = list(np.linalg.norm(tr.d, axis=-1))
        eF = score("F", ev, cfg, calibration).s_norm
        eE = score("E", ev, cfg, calibration).s_norm
        y0 = 30 + i * (PH + 34)
        panels.append(_line_chart(
            {"||d|| (raw)": dnorm,
             "BCVF 2nd-order z": list(np.clip(eF, 0, None)),
             "LLT+CUSUM z": list(np.clip(eE, 0, None))},
            f"{fam}  —  {label}",
            x0=60, y0=y0, w=W, h=PH, ymax=8.0))
    inner = "\n".join(panels)
    out = PLOTS_DIR / "trajectories.svg"
    out.write_text(_svg(640, 30 + len(families) * (PH + 34) + 20, inner))
    return out


def render_frontier(analysis: dict) -> Path:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    frontiers = analysis["frontiers"]
    arms = [a for a in ("C", "E", "F", "H", "I") if a in frontiers]
    inner = _scatter_frontier(frontiers, arms, x0=60, y0=30, w=460, h=340)
    out = PLOTS_DIR / "det_frontier.svg"
    out.write_text(_svg(600, 420, inner))
    return out


def render_all(cfg: StudyConfig, analysis: dict) -> List[Path]:
    return [render_trajectories(cfg), render_frontier(analysis)]
