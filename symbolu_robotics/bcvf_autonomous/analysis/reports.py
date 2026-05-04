"""CSV + Markdown report writers for :class:`FleetSummary`.

A SOTIF clause-10 (operational design + field monitoring) audit
ends up asking for two artifacts: a per-episode tabular index
(spreadsheet shape) and a fleet-level narrative (regulator-readable
markdown). This module emits both from a :class:`FleetSummary`
without coupling the data model to a particular reporting flow —
the methods on the dataclass delegate here.

* :func:`render_fleet_csv` — one row per episode with the headline
  metrics (id, classification, n_steps, M, argmax-flips, V2 state
  flips, near-vetoes, fraction engaged, deadband-fired rate, BCVF
  totals).
* :func:`render_fleet_markdown` — fleet-level narrative with
  headline aggregates, classification breakdown, per-predictor
  exclusion incidence, near-veto roster, V2 state-flip roster,
  and a per-episode index sorted by argmax-flip rate.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Union


# Header row for the per-episode CSV. Column order is pinned so a
# downstream Excel / pandas / audit-script consumer can rely on it.
FLEET_CSV_FIELDS = (
    "episode_id",
    "classification",
    "n_steps",
    "M",
    "n_argmax_flips",
    "argmax_flip_rate",
    "n_v2_state_flips",
    "n_near_vetoes",
    "fraction_engaged",
    "deadband_fired_rate",
    "mean_bcvf_total",
    "max_bcvf_total",
    "excluded_ever_count",
)


def _flip_rate(ep: Any) -> float:
    return ep.n_argmax_flips / ep.n_steps if ep.n_steps > 0 else 0.0


def render_fleet_csv(fleet_summary: Any) -> str:
    """Render a :class:`FleetSummary` to a per-episode CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(FLEET_CSV_FIELDS)
    for ep in fleet_summary.episodes:
        writer.writerow([
            ep.episode_id,
            "" if ep.classification is None else ep.classification,
            ep.n_steps,
            ep.M,
            ep.n_argmax_flips,
            f"{_flip_rate(ep):.6f}",
            ep.n_v2_state_flips,
            ep.n_near_vetoes,
            "" if ep.fraction_engaged is None
            else f"{ep.fraction_engaged:.6f}",
            f"{ep.deadband_fired_rate:.6f}",
            f"{ep.mean_bcvf_total:.6f}",
            f"{ep.max_bcvf_total:.6f}",
            ep.excluded_ever_count,
        ])
    return buf.getvalue()


def write_fleet_csv(
    fleet_summary: Any, path: Union[str, Path],
) -> Path:
    """Write the per-episode fleet CSV to ``path``."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_fleet_csv(fleet_summary), encoding="utf-8")
    return out


def render_fleet_markdown(
    fleet_summary: Any,
    *,
    title: str = "BCVF Fleet Summary",
    label: Optional[str] = None,
    generated_at: Optional[datetime] = None,
    top_k_episodes: int = 25,
) -> str:
    """Render a regulator-friendly fleet markdown report.

    Sections:

    1. **Headline aggregates** — episode count, total simulator steps,
       argmax-flip percentiles, V2 engaged fraction, deadband rate.
    2. **Classification breakdown** — counts per ``classification``.
    3. **Per-predictor exclusion incidence** — fraction of episodes
       in which each predictor was ever excluded.
    4. **Near-veto roster** — episodes / ticks where a predictor
       crested 70% of the exclusion threshold without being excluded.
    5. **V2 state-flip roster** — UNIFORM ↔ ENGAGED transitions.
    6. **Per-episode index** — top ``top_k_episodes`` by argmax-flip
       rate (the noisy episodes a triage tool inspects first).

    Deterministic up to ``generated_at``.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    s = fleet_summary
    n = int(s.n_episodes)
    n_steps = int(s.n_total_steps)
    label_prefix = f" — `{label}`" if label else ""

    lines: List[str] = []
    lines.append(f"# {title}{label_prefix}")
    lines.append("")
    lines.append(
        f"_Generated: {generated_at.isoformat()}  ·  "
        f"Episodes: {n}  ·  Total steps: {n_steps}_"
    )
    lines.append("")

    # 1. Headline aggregates
    lines.append("## Headline aggregates")
    lines.append("")
    fl = s.argmax_flips_per_step
    lines.append(
        f"* **Argmax flips per step:** mean **{fl['mean']:.4f}**  ·  "
        f"p50 {fl['p50']:.4f}  ·  p95 {fl['p95']:.4f}  ·  p99 {fl['p99']:.4f}"
    )
    if s.v2_engaged_fraction is not None:
        eng = s.v2_engaged_fraction
        lines.append(
            f"* **V2 engaged fraction:** mean {eng['mean']:.4f}  ·  "
            f"p50 {eng['p50']:.4f}  ·  p95 {eng['p95']:.4f}  ·  p99 {eng['p99']:.4f}"
        )
    else:
        lines.append("* **V2 engaged fraction:** n/a (V2 was never enabled)")
    lines.append(
        f"* **Deadband-fire rate (mean across episodes):** "
        f"{s.deadband_fired_rate:.4f}"
    )
    lines.append(
        f"* **Near-vetoes detected (fleet-wide):** {len(s.near_vetoes)}"
    )
    lines.append(
        f"* **V2 state flips detected (fleet-wide):** {len(s.v2_state_flips)}"
    )
    lines.append("")

    # 2. Classification breakdown
    lines.append("## Classification breakdown")
    lines.append("")
    if s.classification_counts:
        lines.append("| Classification | Episodes |")
        lines.append("|---|---:|")
        for cls in sorted(s.classification_counts.keys()):
            lines.append(f"| `{cls}` | {s.classification_counts[cls]} |")
    else:
        lines.append("_No classifications were recorded for this fleet._")
    lines.append("")

    # 3. Per-predictor exclusion incidence
    lines.append("## Per-predictor exclusion incidence")
    lines.append("")
    if s.per_predictor_excluded_rate:
        lines.append("| Predictor index | Excluded-ever rate |")
        lines.append("|---:|---:|")
        for i, rate in enumerate(s.per_predictor_excluded_rate):
            lines.append(f"| {i} | {rate:.4f} |")
    else:
        lines.append("_No predictor exclusion observed._")
    lines.append("")

    # 4. Near-veto roster
    lines.append("## Near-veto roster")
    lines.append("")
    if s.near_vetoes:
        lines.append(
            "| Episode | Tick | Predictor | Peak fraction | Metadata |"
        )
        lines.append("|---|---:|---:|---:|---|")
        for nv in s.near_vetoes:
            meta = (
                ", ".join(f"{k}={v}" for k, v in sorted(nv.metadata.items()))
                if getattr(nv, "metadata", None) else ""
            )
            lines.append(
                f"| `{nv.episode_id}` | {nv.tick} | "
                f"{nv.predictor_idx} | {nv.peak_fraction:.3f} | {meta} |"
            )
    else:
        lines.append("_No near-veto events observed._")
    lines.append("")

    # 5. V2 state flip roster
    lines.append("## V2 state-flip roster")
    lines.append("")
    if s.v2_state_flips:
        lines.append(
            "| Episode | Tick | From → To | Engage signal | Metadata |"
        )
        lines.append("|---|---:|:---:|---:|---|")
        for vf in s.v2_state_flips:
            meta = (
                ", ".join(f"{k}={v}" for k, v in sorted(vf.metadata.items()))
                if getattr(vf, "metadata", None) else ""
            )
            lines.append(
                f"| `{vf.episode_id}` | {vf.tick} | "
                f"{vf.from_state} → {vf.to_state} | "
                f"{vf.engage_signal:.3f} | {meta} |"
            )
    else:
        lines.append("_No V2 state-flip events observed._")
    lines.append("")

    # 6. Per-episode index — top K by argmax-flip rate
    lines.append(f"## Per-episode index (top {top_k_episodes} by flip rate)")
    lines.append("")
    if s.episodes:
        ranked = sorted(
            s.episodes,
            key=lambda ep: (-_flip_rate(ep), ep.episode_id),
        )[:top_k_episodes]
        lines.append(
            "| Episode | Classification | Steps | M | Flips | "
            "Flip rate | Engaged | Deadband |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
        for ep in ranked:
            cls = ep.classification or ""
            engaged = (
                f"{ep.fraction_engaged:.3f}"
                if ep.fraction_engaged is not None else "—"
            )
            lines.append(
                f"| `{ep.episode_id}` | {cls} | {ep.n_steps} | {ep.M} | "
                f"{ep.n_argmax_flips} | {_flip_rate(ep):.4f} | "
                f"{engaged} | {ep.deadband_fired_rate:.4f} |"
            )
        if len(s.episodes) > top_k_episodes:
            lines.append("")
            lines.append(
                f"_…{len(s.episodes) - top_k_episodes} more episodes omitted "
                "from this top-K view; the per-episode CSV carries the "
                "complete index._"
            )
    else:
        lines.append("_No episodes in this summary._")
    lines.append("")

    # Methodology footer
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "* Source: "
        "`symbolu_robotics.bcvf_autonomous.analysis::aggregate_fleet` "
        "(batch) or `StreamingFleetMonitor.summary(window=...)` (online)."
    )
    lines.append(
        "* Argmax flip = a tick where ``argmax(per_step_weights[t]) "
        "!= argmax(per_step_weights[t-1])``."
    )
    lines.append(
        "* Near-veto = a predictor that reached ≥ 70% of the exclusion "
        "threshold ``T_exclude`` consecutive-suspect ticks without "
        "being excluded."
    )
    lines.append(
        "* V2 state flip = a UNIFORM ↔ ENGAGED transition emitted by "
        "the §14a Schmitt-trigger consumer."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_fleet_markdown(
    fleet_summary: Any,
    path: Union[str, Path],
    *,
    title: str = "BCVF Fleet Summary",
    label: Optional[str] = None,
    generated_at: Optional[datetime] = None,
    top_k_episodes: int = 25,
) -> Path:
    """Write the regulator-friendly fleet markdown report to ``path``."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_fleet_markdown(
            fleet_summary,
            title=title,
            label=label,
            generated_at=generated_at,
            top_k_episodes=top_k_episodes,
        ),
        encoding="utf-8",
    )
    return out
