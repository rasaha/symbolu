"""Build regime-gated telemetry snapshots from DEV counterfactual results.

The regimes model how much prior evidence the POLICY has for this domain:
  cold    -> no observed evidence (n=0)
  partial -> first N dev observations per (model, task_class)
  mature  -> all dev observations
A separate "full" snapshot (== mature) is used by the fixed benchmark baselines.

Telemetry is versioned so decision records can pin the snapshot they used.
"""
from __future__ import annotations

from typing import Any, Dict, List

PARTIAL_N = 3


def _cell_stats(scores: List[float], schema_valids: List[bool], n: int) -> Dict[str, Any]:
    use_q = scores[:n]
    use_s = schema_valids[:n]
    if not use_q:
        return {"quality_mean": None, "schema_valid_rate": None, "n": 0}
    return {"quality_mean": sum(use_q) / len(use_q),
            "schema_valid_rate": sum(1 for s in use_s if s) / len(use_s),
            "n": len(use_q)}


def build_snapshots(dev_results: Dict[str, Dict[str, Any]], dev_tasks: List[Dict[str, Any]],
                    version_tag: str) -> Dict[str, Dict[str, Any]]:
    """dev_results: {task_id: {model_id: {quality, schema_valid, ...}}}.
    Returns {regime: {model_id: {task_class: cell_stats}, "_version": ...}}."""
    # collect per (model, class) ordered score lists
    by_mc: Dict[str, Dict[str, Dict[str, List]]] = {}
    task_class = {t["task_id"]: t["task_class"] for t in dev_tasks}
    for tid in sorted(dev_results):
        tc = task_class[tid]
        for mid, r in dev_results[tid].items():
            by_mc.setdefault(mid, {}).setdefault(tc, {"q": [], "s": []})
            by_mc[mid][tc]["q"].append(r["quality"])
            by_mc[mid][tc]["s"].append(r["schema_valid"])

    def make(n_fn):
        snap: Dict[str, Any] = {}
        for mid, classes in by_mc.items():
            snap[mid] = {}
            for tc, lists in classes.items():
                n = n_fn(len(lists["q"]))
                snap[mid][tc] = _cell_stats(lists["q"], lists["s"], n)
        return snap

    cold = {"_version": f"{version_tag}:cold"}
    cold.update({mid: {tc: {"quality_mean": None, "schema_valid_rate": None, "n": 0}
                       for tc in classes} for mid, classes in by_mc.items()})
    partial = make(lambda total: min(PARTIAL_N, total))
    partial["_version"] = f"{version_tag}:partial"
    mature = make(lambda total: total)
    mature["_version"] = f"{version_tag}:mature"
    full = dict(mature)
    full["_version"] = f"{version_tag}:full-benchmark"
    return {"cold": cold, "partial": partial, "mature": mature, "full": full}
