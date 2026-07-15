"""KVPro V3 Gate-1 — pure result parsing / aggregation / regression detection (CPU-testable).

The pod drivers (needle/hard-needle/mmlu) emit raw per-item records with a `cells` map
(fp, affine, S1..S4). This module turns those into per-cell accuracy (overall / per-seed /
per-group), deltas vs full precision and vs the current affine KVPro, and — most importantly —
REGRESSIONS: items the reference cell got right that a candidate gets wrong. No torch, no model.

Record schema (shared by all three benchmarks):
  { "model", "label": "MEASURED"|"NOT_RUN", "cells": [<names>],
    "items": [ { <group keys...>, "gold"?: <any>, "cells": { <cell>: {<benchmark fields>} } } ] }
Correctness is benchmark-specific (see _CORRECT).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Sequence

# ---- benchmark-specific correctness predicates ---- #
def _correct_needle(item, cell) -> bool:
    return bool(item["cells"][cell].get("hit"))


def _correct_hard_needle(item, cell) -> bool:
    return item["cells"][cell].get("label") == "HIT"


def _correct_mmlu(item, cell) -> bool:
    return item["cells"][cell].get("pred") == item.get("gold")


_CORRECT: Dict[str, Callable] = {
    "needle": _correct_needle,
    "hard_needle": _correct_hard_needle,
    "mmlu": _correct_mmlu,
}


def _acc(items, cell, correct_fn) -> Dict:
    tot = len(items)
    cor = sum(1 for it in items if correct_fn(it, cell))
    return {"correct": cor, "total": tot, "accuracy": (cor / tot) if tot else 0.0}


def aggregate(items: List[Dict], cells: Sequence[str], benchmark: str,
              group_keys: Sequence[str] = ()) -> Dict[str, Dict]:
    """Per-cell accuracy overall + per each group key (e.g. 'seed', 'context_len')."""
    fn = _CORRECT[benchmark]
    out = {}
    for cell in cells:
        rec = {"overall": _acc(items, cell, fn)}
        for gk in group_keys:
            groups = {}
            for it in items:
                groups.setdefault(it.get(gk), []).append(it)
            rec[f"by_{gk}"] = {str(k): _acc(v, cell, fn) for k, v in sorted(groups.items(), key=lambda x: str(x[0]))}
        out[cell] = rec
    return out


def regressions(items: List[Dict], benchmark: str, ref_cell: str, cand_cell: str) -> List[Dict]:
    """Items the ref cell got RIGHT but the candidate gets WRONG (the failures introduced)."""
    fn = _CORRECT[benchmark]
    bad = []
    for i, it in enumerate(items):
        if fn(it, ref_cell) and not fn(it, cand_cell):
            entry = {"index": i, "ref_cell": ref_cell, "cand_cell": cand_cell}
            for k in ("seed", "context_len", "mode", "needle", "gold"):
                if k in it:
                    entry[k] = it[k]
            entry["cand_detail"] = it["cells"][cand_cell]
            bad.append(entry)
    return bad


def answer_changes(items: List[Dict], benchmark: str, ref_cell: str, cand_cell: str) -> Dict:
    """How many items' EXACT answer changed cand-vs-ref (both directions), and the correctness
    regressions among them. For MMLU 'answer' = pred; for needle/hard-needle = hit-label."""
    fn = _CORRECT[benchmark]
    changed = 0
    for it in items:
        if benchmark == "mmlu":
            a = it["cells"][ref_cell].get("pred")
            b = it["cells"][cand_cell].get("pred")
        elif benchmark == "hard_needle":
            a = it["cells"][ref_cell].get("label")
            b = it["cells"][cand_cell].get("label")
        else:
            a = bool(it["cells"][ref_cell].get("hit"))
            b = bool(it["cells"][cand_cell].get("hit"))
        if a != b:
            changed += 1
    regr = regressions(items, benchmark, ref_cell, cand_cell)
    return {"changed": changed, "total": len(items),
            "regressions_introduced": len(regr), "regression_items": regr}


def summarize(records: Dict, benchmark: str, group_keys: Sequence[str] = ()) -> Dict:
    """Full summary for one benchmark's records: per-cell accuracy + deltas + regressions vs fp/affine.
    Returns {'label','cells','agg','vs_fp','vs_affine'}. Handles NOT_RUN / empty gracefully."""
    if not records or records.get("label") == "NOT_RUN" or not records.get("items"):
        return {"label": "NOT_RUN", "cells": records.get("cells", []) if records else [], "agg": {}}
    cells = records["cells"]
    items = records["items"]
    agg = aggregate(items, cells, benchmark, group_keys)
    cand_cells = [c for c in cells if c not in ("fp", "affine")]
    vs_fp, vs_aff = {}, {}
    ref_fp = agg.get("fp", {}).get("overall", {}).get("accuracy")
    ref_aff = agg.get("affine", {}).get("overall", {}).get("accuracy")
    for c in cand_cells + (["affine"] if "affine" in cells else []):
        ov = agg[c]["overall"]["accuracy"]
        if ref_fp is not None:
            vs_fp[c] = {"delta": round(ov - ref_fp, 4), **answer_changes(items, benchmark, "fp", c)}
        if ref_aff is not None and c != "affine":
            vs_aff[c] = {"delta": round(ov - ref_aff, 4), **answer_changes(items, benchmark, "affine", c)}
    return {"label": records.get("label", "MEASURED"), "model": records.get("model"),
            "cells": cells, "benchmark": benchmark, "agg": agg,
            "vs_fp": vs_fp, "vs_affine": vs_aff,
            "marginal_model": _is_marginal(records.get("model", ""))}


def _is_marginal(model: str) -> bool:
    """Qwen2.5-7B is the previously at-the-margin model; it gets the strict gate."""
    m = model.lower()
    return "qwen2.5-7b" in m or "qwen2_5_7b" in m or "qwen2.5_7b" in m
