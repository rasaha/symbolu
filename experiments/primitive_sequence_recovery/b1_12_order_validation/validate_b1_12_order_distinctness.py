"""B1.12 V1.2 order-distinctness — VALIDATION ONLY (descriptive).

Computes the pairwise order-distinctness matrix over the complete frozen candidate pool and
emits descriptive statistics, a mathematical self-metric equality check, unchanged-artifact
confirmations, descriptive correlations, and anonymous illustrative examples.

FROZEN definition (B1.12 V1.2), used verbatim, never modified here:

    d_ord|inv(x, y) = max(0, Lev(x, y) - Lev(sort(x), sort(y))) / max(|x|, |y|)

where x, y are a candidate's ordered consonant sequence (cons_seq). The per-word self metric
    d_ord|inv(x, sort(x))
is asserted (B1.12) to equal the previous V1.1 self-order measure  Lev(x, sort(x)) / |x|.

This script performs NO search, optimization, tuning, threshold adjustment, subset
reselection, or candidate ranking. It reads the frozen inputs and writes only the three new
validation artifacts. Deterministic; no network; no mutation of any frozen artifact.
"""

from __future__ import annotations

import csv
import itertools
import json
import pathlib
import statistics

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
G0 = EXP / "native_gate_g0"

INVENTORY = json.load(open(G0 / "candidate_inventory.json", encoding="utf-8"))["candidates"]
G0_REPORT = json.load(open(G0 / "native_gate_g0_report.json", encoding="utf-8"))
SELECTED = json.load(open(G0 / "selected_set_manifest.json", encoding="utf-8"))


# --------------------------------------------------------------------------- #
# frozen metric primitives
# --------------------------------------------------------------------------- #
def lev(a, b):
    """Levenshtein distance on token sequences (a, b are tuples of symbols)."""
    if a == b:
        return 0
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def _sort(x):
    return tuple(sorted(x))


def d_ord_inv(x, y):
    """FROZEN B1.12 V1.2 pairwise order-distinctness."""
    denom = max(len(x), len(y))
    if denom == 0:
        return 0.0
    return max(0, lev(x, y) - lev(_sort(x), _sort(y))) / denom


def v1_1_self_order(x):
    """Previous V1.1 self-order measure: Lev(x, sort(x)) / |x|."""
    return lev(tuple(x), _sort(x)) / len(x) if len(x) else 0.0


# --------------------------------------------------------------------------- #
def _pairwise():
    cands = [{"seq": tuple(c["cons_seq"]), "set": frozenset(c["cons_set"]),
              "n_tokens": c["n_tokens"], "n_distinct": c["n_distinct"],
              "repeated": c["repeated"]} for c in INVENTORY]
    n = len(cands)
    # full symmetric matrix (diagonal is identically 0 by construction)
    matrix = [[0.0] * n for _ in range(n)]
    pairs = []          # unique unordered off-diagonal pairs
    for i, j in itertools.combinations(range(n), 2):
        v = d_ord_inv(cands[i]["seq"], cands[j]["seq"])
        matrix[i][j] = matrix[j][i] = v
        ed = lev(cands[i]["seq"], cands[j]["seq"])
        inv_overlap = (len(cands[i]["set"] & cands[j]["set"]) /
                       len(cands[i]["set"] | cands[j]["set"])) if (cands[i]["set"] | cands[j]["set"]) else 0.0
        len_diff = abs(cands[i]["n_tokens"] - cands[j]["n_tokens"])
        same_inventory = _sort(cands[i]["seq"]) == _sort(cands[j]["seq"])
        pairs.append({"i": i, "j": j, "d_ord": v, "edit_distance": ed,
                      "inventory_overlap": inv_overlap, "length_diff": len_diff,
                      "same_inventory": same_inventory,
                      "repeated_either": cands[i]["repeated"] or cands[j]["repeated"]})
    return cands, matrix, pairs


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    return cov / ((vx * vy) ** 0.5) if vx > 0 and vy > 0 else 0.0


def _ranks(vals):
    order = sorted(range(len(vals)), key=lambda k: vals[k])
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


def _spearman(xs, ys):
    return _pearson(_ranks(xs), _ranks(ys))


def _stats(vals):
    s = sorted(vals)
    n = len(s)
    pos = [v for v in s if v > 0]
    return {
        "n_pairs": n,
        "min": round(s[0], 6), "max": round(s[-1], 6),
        "mean": round(sum(s) / n, 6), "median": round(statistics.median(s), 6),
        "q1": round(_quantile(s, 0.25), 6), "q2": round(_quantile(s, 0.50), 6),
        "q3": round(_quantile(s, 0.75), 6),
        "pct_exactly_0": round(100 * (n - len(pos)) / n, 4),
        "pct_gt_0": round(100 * len(pos) / n, 4),
        "pct_gt_0_25": round(100 * sum(1 for v in s if v > 0.25) / n, 4),
        "pct_gt_0_5": round(100 * sum(1 for v in s if v > 0.5) / n, 4),
        "pct_gt_0_75": round(100 * sum(1 for v in s if v > 0.75) / n, 4),
    }


def _histogram(vals, width=0.05):
    import math
    bins = {}
    nb = int(round(1.0 / width))
    for k in range(nb):
        bins[k] = 0
    for v in vals:
        k = min(nb - 1, int(v / width - 1e-12) if v > 0 else 0)
        bins[k] += 1
    rows = []
    for k in range(nb):
        rows.append({"bin_start": round(k * width, 4), "bin_end": round((k + 1) * width, 4),
                     "count": bins[k], "fraction": round(bins[k] / len(vals), 6)})
    return rows


def _confirm_unchanged():
    """Read-only confirmation that frozen G0 constants and the selected subset are unchanged.
    Compares the live module constants against the frozen report and against pinned values."""
    pinned = {"K": 6, "MAX_JACCARD_CAP": 0.34, "MEAN_JACCARD_CAP": 0.20, "POOL_SIZE": 20,
              "cons_len_range": [2, 4]}
    rep_consts = G0_REPORT["constants"]
    result = {"pinned_vs_report": rep_consts == pinned}
    try:
        import sys
        if str(EXP) not in sys.path:
            sys.path.insert(0, str(EXP))
        import b1_native_gate_g0 as G   # importing does NOT run build() (guarded by __main__)
        live = {"K": G.K, "MAX_JACCARD_CAP": G.MAX_JACCARD_CAP,
                "MEAN_JACCARD_CAP": G.MEAN_JACCARD_CAP, "POOL_SIZE": G.POOL_SIZE,
                "cons_len_range": [G.MIN_CONS, G.MAX_CONS]}
        result["module_vs_pinned"] = live == pinned
    except Exception as exc:   # pragma: no cover - parser import optional
        result["module_vs_pinned"] = f"import-skipped: {exc.__class__.__name__}"
    result["constants"] = rep_consts
    result["selected_subset"] = SELECTED["selected_words"]
    result["selected_subset_matches_report"] = (
        SELECTED["selected_words"] == G0_REPORT["selected_set"]["words"])
    result["core_pool_size"] = G0_REPORT["n_core_pool"]
    result["n_eligible_candidates"] = G0_REPORT["n_eligible_candidates"]
    return result


def _self_metric_equality(cands):
    """Verify d_ord|inv(x, sort(x)) == V1.1 self-order for every candidate (numeric)."""
    checks = []
    all_equal = True
    for idx, c in enumerate(cands):
        x = c["seq"]
        via_v12 = d_ord_inv(x, _sort(x))     # y = sort(x)
        via_v11 = v1_1_self_order(x)
        eq = abs(via_v12 - via_v11) < 1e-12
        all_equal = all_equal and eq
        checks.append({"anon_id": f"C{idx:03d}", "v12_self": round(via_v12, 6),
                       "v11_self": round(via_v11, 6), "equal": eq})
    return all_equal, checks


def _examples(cands, pairs):
    def anon(k):
        return f"C{k:03d}"

    def descr(pr):
        i, j = pr["i"], pr["j"]
        return {"pair": [anon(i), anon(j)], "d_ord": round(pr["d_ord"], 6),
                "edit_distance": pr["edit_distance"],
                "inventory_overlap": round(pr["inventory_overlap"], 4),
                "length_diff": pr["length_diff"], "same_inventory": pr["same_inventory"],
                "n_tokens": [cands[i]["n_tokens"], cands[j]["n_tokens"]],
                "n_distinct": [cands[i]["n_distinct"], cands[j]["n_distinct"]],
                "repeated_either": pr["repeated_either"]}

    nonzero = [p for p in pairs if p["d_ord"] > 0]
    highest = max(pairs, key=lambda p: (p["d_ord"], -p["edit_distance"]))
    lowest_nonzero = min(nonzero, key=lambda p: (p["d_ord"], p["edit_distance"])) if nonzero else None
    repeated = next((p for p in sorted(pairs, key=lambda p: -p["d_ord"])
                     if p["repeated_either"]), None)
    inv_diff_order_ident = next(
        (p for p in pairs if p["d_ord"] == 0.0 and p["inventory_overlap"] < 1.0), None)
    same_inv_reordered = [p for p in pairs if p["same_inventory"]]
    same_inv_reordered = max(same_inv_reordered, key=lambda p: p["d_ord"]) \
        if same_inv_reordered else None

    return {
        "note": "Anonymous IDs only; no spelling/identity revealed. Illustrative, not "
                "'good'/'bad'.",
        "highest_scoring_pair": descr(highest),
        "lowest_non_zero_pair": descr(lowest_nonzero) if lowest_nonzero else None,
        "repeated_symbol_pair": descr(repeated) if repeated else None,
        "inventory_different_but_order_identical_pair":
            descr(inv_diff_order_ident) if inv_diff_order_ident else
            "none present in pool",
        "same_inventory_maximally_reordered_pair":
            descr(same_inv_reordered) if same_inv_reordered else
            "no two distinct candidates share an identical consonant multiset (no anagram "
            "pair exists in the pool)",
    }


def run():
    cands, matrix, pairs = _pairwise()
    vals = [p["d_ord"] for p in pairs]
    stats = _stats(vals)
    hist = _histogram(vals)
    all_equal, self_checks = _self_metric_equality(cands)
    unchanged = _confirm_unchanged()

    dord = [p["d_ord"] for p in pairs]
    corr = {
        "vs_edit_distance": {
            "pearson": round(_pearson(dord, [p["edit_distance"] for p in pairs]), 4),
            "spearman": round(_spearman(dord, [p["edit_distance"] for p in pairs]), 4)},
        "vs_inventory_overlap": {
            "pearson": round(_pearson(dord, [p["inventory_overlap"] for p in pairs]), 4),
            "spearman": round(_spearman(dord, [p["inventory_overlap"] for p in pairs]), 4)},
        "vs_length_diff": {
            "pearson": round(_pearson(dord, [p["length_diff"] for p in pairs]), 4),
            "spearman": round(_spearman(dord, [p["length_diff"] for p in pairs]), 4)},
        "interpretation": "Descriptive Pearson/Spearman over unordered off-diagonal pairs. "
                          "NOT used for any thresholding, selection, or optimization.",
    }

    out = {
        "artifact_type": "b1_12_v1_2_order_distinctness_validation",
        "descriptive_only": True,
        "frozen_metric": "d_ord|inv(x,y) = max(0, Lev(x,y) - Lev(sort(x),sort(y))) / max(|x|,|y|)",
        "candidate_pool": {
            "source": "native_gate_g0/candidate_inventory.json (complete eligible pool)",
            "n_candidates": len(cands),
            "x_definition": "ordered consonant sequence (cons_seq) per candidate",
            "pairs_basis": "unique unordered off-diagonal pairs = C(n,2)",
        },
        "statistics": stats,
        "correlations_descriptive": corr,
        "self_metric_equality": {
            "claim": "d_ord|inv(x, sort(x)) == V1.1 self-order = Lev(x, sort(x)) / |x|",
            "all_candidates_equal": all_equal,
            "n_candidates_checked": len(self_checks),
            "proof": "sort(sort(x)) == sort(x) and Lev(a,a) == 0 and |sort(x)| == |x|, so the "
                     "V1.2 formula with y = sort(x) reduces to max(0, Lev(x,sort(x)) - 0)/|x| "
                     "= Lev(x, sort(x))/|x|, which is exactly the V1.1 self-order measure.",
        },
        "unchanged_confirmation": unchanged,
        "examples_anonymous": _examples(cands, pairs),
        "no_optimization_attestation": {
            "search_performed": False, "optimization_performed": False,
            "tuning_performed": False, "threshold_adjustment_performed": False,
            "subset_reselection_performed": False, "candidate_ranking_performed": False,
            "frozen_artifacts_modified": False, "experiment_outputs_modified": False,
            "note": "This script only reads frozen inputs and computes descriptive statistics; "
                    "it writes exclusively the three new validation artifacts.",
        },
    }

    (HERE / "pairwise_order_statistics.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with open(HERE / "pairwise_order_histogram.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bin_start", "bin_end", "count", "fraction"])
        for r in hist:
            w.writerow([r["bin_start"], r["bin_end"], r["count"], r["fraction"]])
    return out, hist


if __name__ == "__main__":
    result, _hist = run()
    s = result["statistics"]
    print("n_candidates:", result["candidate_pool"]["n_candidates"],
          "| n_pairs:", s["n_pairs"])
    print("min/median/mean/max:", s["min"], s["median"], s["mean"], s["max"])
    print("pct exactly 0 / >0 / >0.25 / >0.5 / >0.75:",
          s["pct_exactly_0"], s["pct_gt_0"], s["pct_gt_0_25"], s["pct_gt_0_5"], s["pct_gt_0_75"])
    print("self-metric equals V1.1 for all candidates:",
          result["self_metric_equality"]["all_candidates_equal"])
    print("constants unchanged:", result["unchanged_confirmation"]["pinned_vs_report"],
          result["unchanged_confirmation"]["module_vs_pinned"])
    print("selected subset:", result["unchanged_confirmation"]["selected_subset"])
    print("correlations:", result["correlations_descriptive"]["vs_edit_distance"],
          result["correlations_descriptive"]["vs_inventory_overlap"],
          result["correlations_descriptive"]["vs_length_diff"])
