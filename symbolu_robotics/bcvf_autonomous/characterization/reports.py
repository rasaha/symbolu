"""CSV + Markdown report writers for the characterization grid.

A SOTIF / ISO 26262 auditor wants a frozen artifact, not a Python
dataclass. The two writers in this module produce regulator-friendly
deliverables:

* :func:`render_grid_csv` — one row per (family, magnitude) config
  with the per-config Wilson 95% CI, pass count, and floor verdict.
  Pure ASCII, RFC-4180 quoting via :mod:`csv`.
* :func:`render_grid_markdown` — a structured report with a
  headline gate, per-config table, per-family roll-up, methodology
  block, and a failed-config section. Deterministic — same summary
  in, same string out — so the on-disk snapshot can be diffed.

The helpers operate on :class:`GridSummary` (or any compatible
duck-typed object) so the rendering logic is decoupled from the
sweep mechanics.
"""

from __future__ import annotations

import csv
import io
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional, Union


# Header row for the grid CSV. Order pinned so a SOTIF
# documentation pack consumed by Excel / pandas / a buyer's
# audit script never sees a column reorder.
GRID_CSV_FIELDS = (
    "family",
    "magnitude_label",
    "family_params",
    "n",
    "passed",
    "pass_rate",
    "ci_low",
    "ci_high",
    "meets_certification_floor",
)


def _format_family_params(params: Any) -> str:
    """Stable ``key=value`` rendering for the family_params dict.

    Empty dict (e.g. baseline) renders as the empty string. Numeric
    values are stringified directly so a downstream Excel parser
    sees ``accel_mag=0.3``, not ``accel_mag=0.3000000000000``.
    """
    if not params:
        return ""
    return ";".join(f"{k}={v}" for k, v in sorted(params.items()))


def render_grid_csv(grid_summary: Any) -> str:
    """Render a :class:`GridSummary` (or compatible) to a CSV string.

    One row per per-config entry. Header row is fixed at
    :data:`GRID_CSV_FIELDS`; downstream consumers can rely on the
    column order.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(GRID_CSV_FIELDS)
    for cfg in grid_summary.per_config:
        # PerConfigPassStat is a dataclass; mirror with attribute
        # access so the same renderer works on duck-typed inputs.
        writer.writerow([
            cfg.family,
            cfg.magnitude_label,
            _format_family_params(cfg.family_params),
            cfg.n,
            cfg.passed,
            f"{cfg.pass_rate:.6f}",
            f"{cfg.ci_low:.6f}",
            f"{cfg.ci_high:.6f}",
            "true" if cfg.meets_certification_floor else "false",
        ])
    return buf.getvalue()


def write_grid_csv(
    grid_summary: Any, path: Union[str, Path],
) -> Path:
    """Write the grid CSV to ``path``. Returns the resolved Path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_grid_csv(grid_summary), encoding="utf-8")
    return out


def render_grid_markdown(
    grid_summary: Any,
    *,
    title: str = "BCVF Characterization Grid — Certification Report",
    grid_label: str = "primary",
    generated_at: Optional[datetime] = None,
) -> str:
    """Render a regulator-friendly markdown report.

    Sections:

    1. **Headline gate** — pass / fail of the certification floor,
       FPR / FNR, min Wilson lower bound across the grid.
    2. **Per-(family, magnitude) results** — one row per config
       with n, passed, pass rate, CI low / high, floor verdict.
    3. **Per-family roll-up** — one row per family with aggregate
       pass rate.
    4. **Failed configs** — explicit list of any configs whose CI
       lower bound undershoots the floor (empty if the grid passes).
    5. **Methodology** — Wilson z, certification floor, sweep
       module reference.

    Deterministic up to ``generated_at`` (which defaults to UTC now);
    pass an explicit timestamp for byte-stable snapshots.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    s = grid_summary
    n_cells = int(s.n_cells)
    n_configs = len(s.per_config)
    cert_floor = float(s.certification_floor)
    z = float(s.wilson_z)
    fpr = float(s.false_positive_rate)
    fnr = float(s.false_negative_rate)
    min_ci = float(s.min_ci_lower_bound)
    below_floor = list(s.cells_below_certification_floor)
    floor_pass = len(below_floor) == 0

    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(
        f"_Generated: {generated_at.isoformat()}  ·  "
        f"Grid: `{grid_label}`  ·  Configs: {n_configs}  ·  Cells: {n_cells}_"
    )
    lines.append("")

    # 1. Headline gate
    lines.append("## Headline gate")
    lines.append("")
    lines.append(
        f"* **Per-config certification floor (Wilson {z:.4f}-CI low ≥ "
        f"{cert_floor:.2f}):** "
        f"{'PASS' if floor_pass else 'FAIL'} "
        f"({n_configs - len(below_floor)}/{n_configs} configs clear the floor)"
    )
    lines.append(
        f"* **False-positive rate (nominal-family cells):** {fpr:.3f}"
    )
    lines.append(
        f"* **False-negative rate (failure-family cells):** {fnr:.3f}"
    )
    lines.append(
        f"* **Minimum CI lower bound across the grid:** {min_ci:.4f}"
    )
    lines.append("")

    # 2. Per-config table
    lines.append("## Per-(family, magnitude) results")
    lines.append("")
    lines.append(
        "| Family | Magnitude | n | Passed | Pass rate | CI low | CI high | Floor |"
    )
    lines.append(
        "|---|---|---:|---:|---:|---:|---:|:---:|"
    )
    for cfg in s.per_config:
        lines.append(
            f"| `{cfg.family}` "
            f"| `{cfg.magnitude_label}` "
            f"| {cfg.n} "
            f"| {cfg.passed} "
            f"| {cfg.pass_rate:.3f} "
            f"| {cfg.ci_low:.3f} "
            f"| {cfg.ci_high:.3f} "
            f"| {'✓' if cfg.meets_certification_floor else '✗'} |"
        )
    lines.append("")

    # 3. Per-family roll-up
    lines.append("## Per-family roll-up")
    lines.append("")
    lines.append("| Family | Cells | Pass rate |")
    lines.append("|---|---:|---:|")
    for fam in sorted(s.per_family.keys()):
        rec = s.per_family[fam]
        total = int(rec.get("total", 0))
        pass_rate = float(rec.get("pass_rate", 0.0))
        lines.append(
            f"| `{fam}` | {total} | {pass_rate:.3f} |"
        )
    lines.append("")

    # 4. Failed configs
    lines.append("## Configs below the certification floor")
    lines.append("")
    if floor_pass:
        lines.append(
            "_None — every (family, magnitude) config's Wilson "
            f"{z:.4f}-CI lower bound clears the {cert_floor:.2f} floor._"
        )
    else:
        lines.append(
            "| Magnitude | n | Passed | Pass rate | CI low | "
            f"Floor ({cert_floor:.2f}) |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|")
        below_set = set(below_floor)
        for cfg in s.per_config:
            if cfg.magnitude_label in below_set:
                lines.append(
                    f"| `{cfg.magnitude_label}` "
                    f"| {cfg.n} "
                    f"| {cfg.passed} "
                    f"| {cfg.pass_rate:.3f} "
                    f"| {cfg.ci_low:.3f} "
                    f"| ✗ |"
                )
    lines.append("")

    # 5. Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        f"* Statistical bound: Wilson score interval, z = {z:.6f} "
        "(two-sided 95% CI)."
    )
    lines.append(
        f"* Certification floor: per-config CI lower bound must clear "
        f"**{cert_floor:.2f}**."
    )
    lines.append(
        "* Source: "
        "`symbolu_robotics.bcvf_autonomous.characterization.sweep::summarize_grid`."
    )
    lines.append(
        "* Floor calibration at n = 60: 60-of-60 pass → CI low ≈ 0.940; "
        "59/60 → 0.911; 58/60 → 0.886. The floor binds at the second "
        "statistical failure on a single config — the regime the audit "
        "named as the kernel-regression hot spot."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_grid_markdown(
    grid_summary: Any,
    path: Union[str, Path],
    *,
    title: str = "BCVF Characterization Grid — Certification Report",
    grid_label: str = "primary",
    generated_at: Optional[datetime] = None,
) -> Path:
    """Write the grid markdown report to ``path``. Returns the Path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_grid_markdown(
            grid_summary,
            title=title,
            grid_label=grid_label,
            generated_at=generated_at,
        ),
        encoding="utf-8",
    )
    return out
