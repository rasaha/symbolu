"""
analyze.py — aggregate raw per-seed results into means/stds and B-A/C-B/C-Cnp deltas.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Dict, List


def _mean_std(xs: List[float]):
    if not xs:
        return (float("nan"), float("nan"))
    m = statistics.mean(xs)
    s = statistics.pstdev(xs) if len(xs) > 1 else 0.0
    return (m, s)


def aggregate(raw: List[Dict]) -> Dict:
    """raw: list of {seed, arm, metrics:{task:{metric:val}}}. Returns aggregate."""
    arms = sorted({r["arm"] for r in raw})
    tasks = sorted({t for r in raw for t in r["metrics"]})
    agg = {"arms": arms, "tasks": tasks, "by_arm_task": {}}
    for arm in arms:
        agg["by_arm_task"][arm] = {}
        for task in tasks:
            accs = [r["metrics"][task]["accuracy"] for r in raw
                    if r["arm"] == arm and task in r["metrics"] and "accuracy" in r["metrics"][task]]
            m, s = _mean_std(accs)
            agg["by_arm_task"][arm][task] = {"acc_mean": m, "acc_std": s, "n_seeds": len(accs), "raw": accs}

    def delta(a, b):
        out = {}
        for task in tasks:
            xa = agg["by_arm_task"].get(a, {}).get(task, {}).get("acc_mean", float("nan"))
            xb = agg["by_arm_task"].get(b, {}).get(task, {}).get("acc_mean", float("nan"))
            out[task] = xa - xb
        return out

    agg["deltas"] = {
        "B_minus_A": delta("B", "A"),
        "C_minus_B": delta("C", "B"),
        "C_minus_CnoPhase": delta("C", "C-no-Phase"),
    }
    return agg


def render_tables(agg: Dict) -> str:
    """Markdown tables: per-arm×task accuracy (mean±std) and the decisive deltas."""
    arms = agg["arms"]; tasks = agg["tasks"]
    lines = ["# Results tables\n", "## Accuracy (mean ± std over seeds)\n"]
    header = "| task | " + " | ".join(arms) + " |"
    sep = "|" + "---|" * (len(arms) + 1)
    lines += [header, sep]
    for task in tasks:
        cells = []
        for arm in arms:
            d = agg["by_arm_task"].get(arm, {}).get(task, {})
            m = d.get("acc_mean", float("nan")); s = d.get("acc_std", 0.0)
            cells.append(f"{m:.2f}±{s:.2f}")
        lines.append(f"| {task} | " + " | ".join(cells) + " |")
    lines.append("\n## Decisive deltas (accuracy)\n")
    lines += ["| task | B−A | C−B | C−(C-no-Phase) |", "|---|---|---|---|"]
    for task in tasks:
        ba = agg["deltas"]["B_minus_A"].get(task, float("nan"))
        cb = agg["deltas"]["C_minus_B"].get(task, float("nan"))
        cc = agg["deltas"]["C_minus_CnoPhase"].get(task, float("nan"))
        lines.append(f"| {task} | {ba:+.2f} | {cb:+.2f} | {cc:+.2f} |")
    return "\n".join(lines) + "\n"


def main(raw_dir: str, out_path: str):
    raw = []
    for p in sorted(Path(raw_dir).glob("*.json")):
        raw.append(json.loads(p.read_text()))
    agg = aggregate(raw)
    Path(out_path).write_text(json.dumps(agg, indent=2))
    return agg


if __name__ == "__main__":
    import sys
    main(sys.argv[1], sys.argv[2])
