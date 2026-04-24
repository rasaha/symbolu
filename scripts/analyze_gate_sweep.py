#!/usr/bin/env python
"""Summarize a ``--gate-threshold`` sweep over probe_observables reports.

Usage (after the Diagnostic 1 sweep has produced one report per T):

    python scripts/analyze_gate_sweep.py

    # or restrict to a specific suffix prefix:
    python scripts/analyze_gate_sweep.py --pattern 'probe_*_diag1_gate_T*.md'

Parses each matched Markdown report, extracts the verdict-summary row
for every observable, and prints a T-keyed comparison table. Intended
to answer: "at which gate_threshold (if any) does AUC lift above the
0.500 baseline?"
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Verdict table row format from render_report in probe_observables.py:
# | `bcvf_total_cost` | 0.500 | **UNCORRELATED** | 2.7377 | 2.7377 |
_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*([\d.]+)\s*\|\s*\*\*([A-Z_]+)\*\*\s*\|"
    r"\s*([-\d.]+)\s*\|\s*([-\d.]+)\s*\|"
)

# Extract the T value from suffixes like "..._diag1_gate_T0.001".
_T_RE = re.compile(r"_T([0-9.eE+-]+)(?:\b|$)")


def parse_report(path: Path) -> Dict[str, Tuple[float, str, float, float]]:
    """Return {observable_name: (auc, classification, mean_c, mean_w)}."""
    out: Dict[str, Tuple[float, str, float, float]] = {}
    for line in path.read_text().splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        name, auc, cls, mean_c, mean_w = m.groups()
        out[name] = (float(auc), cls, float(mean_c), float(mean_w))
    return out


def extract_t(stem: str) -> Optional[float]:
    m = _T_RE.search(stem)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern", default="probe_*diag1_gate*.md",
        help="glob under --dir to match sweep reports "
             "(default: probe_*diag1_gate*.md)",
    )
    parser.add_argument(
        "--dir", type=Path, default=_REPO_ROOT / "docs" / "experiments",
        help="directory containing the reports",
    )
    parser.add_argument(
        "--observable", default="bcvf_total_cost",
        help="observable to highlight in the compact summary "
             "(default: bcvf_total_cost). Use 'all' to print every "
             "observable at every T.",
    )
    args = parser.parse_args(argv)

    reports = sorted(args.dir.glob(args.pattern))
    if not reports:
        print(f"no reports matched {args.dir / args.pattern}")
        return 1

    rows: List[Tuple[Optional[float], Path, Dict[str, Tuple[float, str, float, float]]]] = []
    for p in reports:
        rows.append((extract_t(p.stem), p, parse_report(p)))

    # Sort by T (None last), for readable sweep output.
    rows.sort(key=lambda r: (r[0] is None, r[0] if r[0] is not None else 0.0))

    if args.observable == "all":
        for t, p, parsed in rows:
            t_str = f"T={t:g}" if t is not None else "T=?"
            print(f"\n=== {p.stem}  ({t_str}) ===")
            for name, (auc, cls, mc, mw) in parsed.items():
                print(f"  {name:<42} AUC={auc:.3f}  {cls:<18}  "
                      f"mean_c={mc:+.4f}  mean_w={mw:+.4f}")
        return 0

    # Compact one-observable sweep table.
    print(f"Diagnostic 1 — {args.observable} AUC vs gate_threshold\n")
    print(f"{'T':>14}  {'AUC':>6}  {'Classification':<20}  "
          f"{'mean_correct':>13}  {'mean_wrong':>12}  report")
    print("-" * 100)
    best: Tuple[float, float] = (-1.0, 0.0)  # (auc, t)
    for t, p, parsed in rows:
        entry = parsed.get(args.observable)
        if entry is None:
            print(f"{(f'{t:g}' if t is not None else '?'):>14}  "
                  f"(observable {args.observable} missing from {p.name})")
            continue
        auc, cls, mc, mw = entry
        t_str = f"{t:g}" if t is not None else "?"
        print(f"{t_str:>14}  {auc:>6.3f}  {cls:<20}  "
              f"{mc:>+13.4f}  {mw:>+12.4f}  {p.name}")
        if t is not None and auc > best[0]:
            best = (auc, t)

    print()
    if best[0] >= 0.60:
        print(f"VERDICT: best AUC = {best[0]:.3f} at T={best[1]:g} "
              f"— TRUTH_CORRELATED. Rerun full 11-observable suite at this T.")
    elif best[0] >= 0.55:
        print(f"VERDICT: best AUC = {best[0]:.3f} at T={best[1]:g} "
              f"— marginal lift above noise. Expand N before trusting.")
    elif best[0] >= 0.0:
        print(f"VERDICT: best AUC = {best[0]:.3f} at T={best[1]:g} "
              f"— still UNCORRELATED across the sweep. Gate threshold is "
              f"NOT the limiting factor. Move to Diagnostic 2 "
              f"(independent predictors) or inspect per-sample variance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
