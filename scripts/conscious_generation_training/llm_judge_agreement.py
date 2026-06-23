#!/usr/bin/env python3
"""llm_judge_agreement.py — inter-judge agreement + audit-comparison metrics for the weak LLM-judge eval.
Doc: docs/CG_TRAINING_LLM_JUDGE_EVAL.md. Pure, CPU-only, torch-free, numpy-free.

These are EVALUATOR-USABILITY diagnostics only (do judges agree, do they track the rule/audit scorer).
They never validate training and never override the Phase-3 audit.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from llm_judge_rubric import BINARY_FIELDS, NUMERIC_FIELDS   # noqa: E402  (sibling import; path set by caller)


# ---- pairwise primitives -------------------------------------------------------------------------
def percent_agreement(a: List, b: List) -> Optional[float]:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None
    return round(sum(1 for x, y in pairs if x == y) / len(pairs), 4)


def cohen_kappa(a: List[int], b: List[int]) -> Optional[float]:
    """Cohen's kappa for two raters on binary 0/1 labels."""
    pairs = [(int(x), int(y)) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for x, y in pairs if x == y) / n
    pa1 = sum(x for x, _ in pairs) / n
    pb1 = sum(y for _, y in pairs) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)                    # chance agreement
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return round((po - pe) / (1 - pe), 4)


def fleiss_kappa(label_matrix: List[List[int]]) -> Optional[float]:
    """Fleiss' kappa for >=3 raters. label_matrix[item] = list of 0/1 labels (one per rater)."""
    rows = [r for r in label_matrix if r]
    if len(rows) == 0:
        return None
    n_raters = len(rows[0])
    if n_raters < 3 or any(len(r) != n_raters for r in rows):
        return None
    N = len(rows)
    p_cat = [0.0, 0.0]                                        # marginal proportion per class {0,1}
    for r in rows:
        p_cat[1] += sum(r)
        p_cat[0] += n_raters - sum(r)
    total = N * n_raters
    p_cat = [c / total for c in p_cat]
    p_bar = 0.0
    for r in rows:
        n1 = sum(r)
        n0 = n_raters - n1
        p_i = (n0 * n0 + n1 * n1 - n_raters) / (n_raters * (n_raters - 1))
        p_bar += p_i
    p_bar /= N
    pe = p_cat[0] ** 2 + p_cat[1] ** 2
    if pe >= 1.0:
        return 1.0 if p_bar >= 1.0 else 0.0
    return round((p_bar - pe) / (1 - pe), 4)


def mean_abs_diff(a: List[float], b: List[float]) -> Optional[float]:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None
    return round(sum(abs(x - y) for x, y in pairs) / len(pairs), 4)


def pearson(a: List[float], b: List[float]) -> Optional[float]:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in pairs)
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def _rank(vals: List[float]) -> List[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(a: List[float], b: List[float]) -> Optional[float]:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 2:
        return None
    return pearson(_rank([p[0] for p in pairs]), _rank([p[1] for p in pairs]))


# ---- aggregate report across judges --------------------------------------------------------------
def _column(labels_by_judge: Dict[str, Dict[str, Dict]], judge: str, ids: List[str], field: str):
    return [labels_by_judge[judge].get(i, {}).get(field) for i in ids]


def agreement_report(labels_by_judge: Dict[str, Dict[str, Dict]]) -> Dict:
    """labels_by_judge[judge_id][item_id] = parsed-label dict (valid items only). Returns binary + numeric
    agreement and an overall average percent-agreement used for the decision gate. None if < 2 judges."""
    judges = sorted(labels_by_judge)
    if len(judges) < 2:
        return {"n_judges": len(judges), "computable": False,
                "note": "agreement requires >= 2 judges; single-judge run"}
    common = set(labels_by_judge[judges[0]])
    for j in judges[1:]:
        common &= set(labels_by_judge[j])
    ids = sorted(common)
    rep: Dict = {"n_judges": len(judges), "judges": judges, "n_common_items": len(ids),
                 "computable": len(ids) > 0, "binary": {}, "numeric": {}}
    if not ids:
        rep["note"] = "no common valid items across judges"
        return rep
    pa_values = []
    for f in BINARY_FIELDS:
        cols = {j: [1 if v else 0 for v in _column(labels_by_judge, j, ids, f)] for j in judges}
        # average pairwise percent agreement + first-pair Cohen kappa (+ Fleiss if >=3)
        pas, kappas = [], []
        for x in range(len(judges)):
            for y in range(x + 1, len(judges)):
                pas.append(percent_agreement(cols[judges[x]], cols[judges[y]]))
                kappas.append(cohen_kappa(cols[judges[x]], cols[judges[y]]))
        pa = round(sum(p for p in pas if p is not None) / len([p for p in pas if p is not None]), 4) \
            if any(p is not None for p in pas) else None
        entry = {"percent_agreement": pa, "cohen_kappa_firstpair": kappas[0] if kappas else None}
        if len(judges) >= 3:
            matrix = [[cols[j][k] for j in judges] for k in range(len(ids))]
            entry["fleiss_kappa"] = fleiss_kappa(matrix)
        rep["binary"][f] = entry
        if pa is not None:
            pa_values.append(pa)
    for f in NUMERIC_FIELDS:
        cols = {j: _column(labels_by_judge, j, ids, f) for j in judges}
        x0, x1 = cols[judges[0]], cols[judges[1]]
        rep["numeric"][f] = {"mean_abs_diff_firstpair": mean_abs_diff(x0, x1),
                             "pearson_firstpair": pearson(x0, x1),
                             "spearman_firstpair": spearman(x0, x1)}
    rep["avg_percent_agreement"] = round(sum(pa_values) / len(pa_values), 4) if pa_values else None
    return rep


# ---- comparison vs rule/audit scorer -------------------------------------------------------------
# rubric field -> how the Phase-3 audit expresses the same notion (for the overlap comparison only)
_AUDIT_OVERLAP = ("primary_frame_correct", "rejected_domain_leak", "secondary_overpromotion",
                  "answer_acceptable", "rewrite_needed")


def audit_comparison(records_by_id: Dict[str, Dict], judge_labels: Dict[str, Dict]) -> Optional[Dict]:
    """Compare ONE judge's labels against Phase-3 audit labels carried on the records (record['_audit']).
    Reports overlap agreement + lenient/strict counts on rewrite_needed. Never overrides the audit."""
    items = [i for i in judge_labels if i in records_by_id and records_by_id[i].get("_audit")]
    if not items:
        return None
    per_field = {}
    for f in _AUDIT_OVERLAP:
        j = [1 if judge_labels[i].get(f) else 0 for i in items if f in records_by_id[i]["_audit"]]
        a = [1 if records_by_id[i]["_audit"].get(f) else 0 for i in items if f in records_by_id[i]["_audit"]]
        per_field[f] = {"percent_agreement": percent_agreement(j, a), "cohen_kappa": cohen_kappa(j, a),
                        "n": len(j)}
    # lenient = judge would EMIT (no rewrite) where audit says rewrite_needed; strict = the converse
    lenient = strict = disagree_ids = 0
    examples = []
    for i in items:
        af = records_by_id[i]["_audit"]
        if "rewrite_needed" not in af:
            continue
        jr, ar = bool(judge_labels[i].get("rewrite_needed")), bool(af["rewrite_needed"])
        if jr != ar:
            disagree_ids += 1
            if not jr and ar:
                lenient += 1
            elif jr and not ar:
                strict += 1
            if len(examples) < 12:
                examples.append({"id": i, "judge_rewrite_needed": jr, "audit_rewrite_needed": ar})
    pas = [v["percent_agreement"] for v in per_field.values() if v["percent_agreement"] is not None]
    return {"n": len(items), "per_field": per_field,
            "agreement_with_audit": round(sum(pas) / len(pas), 4) if pas else None,
            "llm_judge_more_lenient_count": lenient, "llm_judge_more_strict_count": strict,
            "audit_disagreement_count": disagree_ids, "audit_disagreement_examples": examples}
