#!/usr/bin/env python3
"""B1.12 — Gate G0 structural audit v1 (AUDITOR role). Deterministic; no judges, no network, no G1.

Runs the frozen V1.1/V1.2 G0 contract EXACTLY over the frozen 35-word developmental pool (curator commit
d50fbb9). Reveals the ordered parser sequences (curator sealed them), builds the frozen opaque-ID map, computes
all frozen metrics, enumerates every size-6 subset, applies the frozen hard constraints + objective + tie-breaks,
and returns exactly one of: G0_PASS / G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET / G0_INVALID.

Frozen contract (unchanged here):
  k = 6; length band [2,6];
  d_edit(x,y) = Lev(x,y)/max(|x|,|y|); pairwise hard floor d_edit >= 0.34;
  d_ord|inv(x,y) = max(0, Lev(x,y) - Lev(sort(x),sort(y)))/max(|x|,|y|)   (V1.2; reported diagnostic);
  s(x) = d_ord|inv(x, sort(x)) = d_edit(x, sort(x)); per-word hard eligibility s(x) >= 0.34;
  endpoint no-majority: any single first/last opaque-id in <= 3 of the 6 words;
  ordered bigram Jaccard <= 0.50 (every pair); ordered trigram Jaccard <= 0.34 (every pair with both len>=3);
  within-subset length span <= 2;
  LCS ratio / positional overlap / repetition-profile = diagnostics; multiset Jaccard = tie-break (c) only;
  objective: maximize min pairwise d_edit; tie-break (a) max mean pairwise d_edit, (b) max mean unique-trigram
  count, (c) min mean multiset-Jaccard, (d) alphabetical by candidate-id tuple.

EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
from collections import Counter

import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
POOL = HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json"
OUT = HERE / "results" / "b1_12_g0_audit_v1"

POOL_SHA_EXPECTED = "8cf857891f95bb07e66a3048f7eabe4f1e5814777889abdf6dadb0d5d296d0b4"
PARSER_SHA_EXPECTED = "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947"
COMMITS = {"B1_12_ORDERED_VARNA_COMPOSITION_PREREG.md": "2c613f4",
           "B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_1.md": "6f197fd",
           "B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_2.md": "7935f48",
           "b1_12_candidate_pool_v1/b1_12_candidate_pool_v1.json": "d50fbb9"}

K = 6
LMIN, LMAX = 2, 6
TAU_EDIT = 0.34
TAU_SELF = 0.34
ENDPOINT_MAJORITY_CAP = 3          # <= ceil(k/2)
BIGRAM_JACCARD_CAP = 0.50
TRIGRAM_JACCARD_CAP = 0.34
LENGTH_SPAN_CAP = 2

FORBIDDEN_UNIT_TYPES = {"unsupported", "missing"}


# ---------------------------------------------------------------- primitive metrics
def lev(a, b):
    a, b = list(a), list(b)
    m, n = len(a), len(b)
    if m == 0:
        return n
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        ai = a[i - 1]
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (0 if ai == b[j - 1] else 1))
            prev = cur
    return dp[n]


def lcs_len(a, b):
    a, b = list(a), list(b)
    m, n = len(a), len(b)
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prevrow = dp[:]
        for j in range(1, n + 1):
            dp[j] = prevrow[j - 1] + 1 if a[i - 1] == b[j - 1] else max(dp[j - 1], prevrow[j])
    return dp[n]


def d_edit(x, y):
    return lev(x, y) / max(len(x), len(y))


def d_ord_given_inv(x, y):
    num = lev(x, y) - lev(sorted(x), sorted(y))
    return max(0, num) / max(len(x), len(y))


def s_selforder(x):
    return d_ord_given_inv(x, sorted(x))          # == d_edit(x, sorted(x))


def lcs_ratio(x, y):
    return lcs_len(x, y) / max(len(x), len(y))


def positional_overlap(x, y):
    n = min(len(x), len(y))
    return sum(1 for i in range(n) if x[i] == y[i]) / n if n else 0.0


def multiset_jaccard(x, y):
    cx, cy = Counter(x), Counter(y)
    inter = sum((cx & cy).values())
    union = sum((cx | cy).values())
    return inter / union if union else 0.0


def repetition_profile_distance(x, y):
    cx, cy = Counter(x), Counter(y)
    keys = set(cx) | set(cy)
    l1 = sum(abs(cx.get(k, 0) - cy.get(k, 0)) for k in keys)
    return l1 / (len(x) + len(y)) if (len(x) + len(y)) else 0.0


def bigrams(x):
    return {(x[i], x[i + 1]) for i in range(len(x) - 1)}


def trigrams(x):
    return {(x[i], x[i + 1], x[i + 2]) for i in range(len(x) - 2)}


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 0.0


# ---------------------------------------------------------------- audit
def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    invalid_reasons = []

    # ---- Step 1: verify immutable inputs ----
    pool_sha = _sha(POOL)
    parser_sha = _sha(HERE / "sanskrit_stage1_parser.py")
    if pool_sha != POOL_SHA_EXPECTED:
        invalid_reasons.append(f"pool_sha_mismatch:{pool_sha}")
    if parser_sha != PARSER_SHA_EXPECTED:
        invalid_reasons.append(f"parser_sha_mismatch:{parser_sha}")
    input_hashes = {"pool_file": "b1_12_candidate_pool_v1/b1_12_candidate_pool_v1.json",
                    "pool_sha256": pool_sha, "pool_sha256_expected": POOL_SHA_EXPECTED,
                    "parser_sha256": parser_sha, "parser_sha256_expected": PARSER_SHA_EXPECTED,
                    "parser_spec_version": P.SPEC_VERSION, "controlling_commits": COMMITS}
    (OUT / "input_hashes.json").write_text(json.dumps(input_hashes, indent=2, sort_keys=True), encoding="utf-8")

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    words = pool["words"]
    if len(words) != 35:
        invalid_reasons.append(f"pool_size_not_35:{len(words)}")

    # ---- Step 2: parse the frozen pool (reveal sequences) ----
    parsed = {}
    parser_outputs = []
    for w in words:
        cid, dev, iast = w["id"], w["devanagari"], w["iast"]
        r = P.parse(dev)
        av = r.get("atomic_varnas", [])
        warnings = list(r.get("warnings", []))
        units = [{"unit": u.get("unit"), "type": u.get("type"), "origin": u.get("origin"),
                  "aspirated": u.get("aspirated"), "vowel_length": u.get("vowel_length"),
                  "source_akshara_index": u.get("source_akshara_index"),
                  "is_initial": u.get("is_initial"), "is_final": u.get("is_final")} for u in av]
        bad = sorted({u["type"] for u in units if u["type"] in FORBIDDEN_UNIT_TYPES})
        n = len(units)
        length_ok = LMIN <= n <= LMAX
        valid = (not warnings) and (not bad) and length_ok
        mult = r.get("multiplicity", {})
        parser_outputs.append({
            "id": cid, "iast": iast, "devanagari": dev, "length": n,
            "atomic_varnas": units,
            "aksharas": r.get("aksharas"),
            "varna_counts": mult.get("varna_counts"), "geminations": mult.get("geminations"),
            "warnings": warnings, "forbidden_unit_types_present": bad,
            "parser_valid": valid, "length_in_band": length_ok,
        })
        parsed[cid] = {"iast": iast, "identities": [(u["type"], u["unit"]) for u in units],
                       "valid": valid, "length": n}
    (OUT / "parser_outputs.json").write_text(
        json.dumps({"schema": "b1_12_parser_outputs_v1", "words": parser_outputs}, ensure_ascii=False,
                   indent=2, sort_keys=True), encoding="utf-8")

    # ---- Step 3: frozen opaque-ID map (identity = (type,unit); assign by ascending (type,unit)) ----
    distinct = sorted({ident for p in parsed.values() for ident in p["identities"]})
    opaque = {ident: f"U{idx + 1:02d}" for idx, ident in enumerate(distinct)}
    id_map_records = [{"opaque_id": opaque[ident], "type": ident[0], "unit": ident[1]} for ident in distinct]
    id_map_bytes = json.dumps({"schema": "b1_12_opaque_varna_id_map_v1", "n_identities": len(distinct),
                               "map": id_map_records}, ensure_ascii=False, indent=2,
                              sort_keys=True).encode("utf-8")
    (OUT / "opaque_varna_id_map.json").write_bytes(id_map_bytes)
    opaque_map_sha = hashlib.sha256(id_map_bytes).hexdigest()

    # opaque-id sequences (canonical sort = ascending opaque-id label = ascending (type,unit) rank)
    seq = {cid: [opaque[i] for i in parsed[cid]["identities"]] for cid in parsed}

    # ---- Step 4/5: candidate-level metrics + eligibility ----
    cand = {}
    for cid, x in seq.items():
        cand[cid] = {"id": cid, "iast": parsed[cid]["iast"], "length": len(x),
                     "s_selforder": round(s_selforder(x), 6),
                     "first_unit": x[0], "last_unit": x[-1],
                     "n_unique_bigrams": len(bigrams(x)), "n_unique_trigrams": len(trigrams(x)),
                     "parser_valid": parsed[cid]["valid"]}
    for cid in cand:
        c = cand[cid]
        c["length_ok"] = LMIN <= c["length"] <= LMAX
        c["selforder_ok"] = c["s_selforder"] >= TAU_SELF
        c["eligible"] = c["parser_valid"] and c["length_ok"] and c["selforder_ok"]
    (OUT / "candidate_level_metrics.json").write_text(
        json.dumps({"schema": "b1_12_candidate_level_v1", "tau_self": TAU_SELF, "length_band": [LMIN, LMAX],
                    "candidates": [cand[c] for c in sorted(cand)]}, ensure_ascii=False, indent=2,
                   sort_keys=True), encoding="utf-8")

    eligible = sorted(cid for cid in cand if cand[cid]["eligible"])

    # ---- Step 4: full pairwise metrics ----
    ids = sorted(cand)
    pairwise = {}
    for a, b in itertools.combinations(ids, 2):
        xa, xb = seq[a], seq[b]
        de = d_edit(xa, xb)
        pairwise[f"{a}|{b}"] = {
            "d_edit": round(de, 6),
            "d_ord_given_inv": round(d_ord_given_inv(xa, xb), 6),
            "lcs_ratio": round(lcs_ratio(xa, xb), 6),
            "positional_overlap": round(positional_overlap(xa, xb), 6),
            "multiset_jaccard": round(multiset_jaccard(xa, xb), 6),
            "repetition_profile_distance": round(repetition_profile_distance(xa, xb), 6),
            "abs_length_diff": abs(len(xa) - len(xb)),
            "first_unit_match": xa[0] == xb[0], "last_unit_match": xa[-1] == xb[-1],
            "bigram_jaccard": round(jaccard(bigrams(xa), bigrams(xb)), 6),
            "trigram_jaccard": round(jaccard(trigrams(xa), trigrams(xb)), 6),
            "trigram_defined": len(xa) >= 3 and len(xb) >= 3,
        }
    (OUT / "pairwise_metrics.json").write_text(
        json.dumps({"schema": "b1_12_pairwise_v1", "note": "d_ord_given_inv is a reported diagnostic, not a "
                    "hard pairwise floor (V1.2)", "pairs": pairwise}, ensure_ascii=False, indent=2,
                   sort_keys=True), encoding="utf-8")

    # fast lookup matrices over eligible ids
    def pk(a, b):
        return f"{a}|{b}" if a < b else f"{b}|{a}"
    d_edit_ok = {}
    bigram_ok = {}
    trigram_ok = {}
    for a, b in itertools.combinations(eligible, 2):
        m = pairwise[pk(a, b)]
        d_edit_ok[(a, b)] = m["d_edit"] >= TAU_EDIT
        bigram_ok[(a, b)] = m["bigram_jaccard"] <= BIGRAM_JACCARD_CAP
        trigram_ok[(a, b)] = (not m["trigram_defined"]) or (m["trigram_jaccard"] <= TRIGRAM_JACCARD_CAP)

    # ---- Step 6: enumerate all size-6 subsets over eligible ----
    def subset_constraints(sub):
        lens = [cand[c]["length"] for c in sub]
        c_span = (max(lens) - min(lens)) <= LENGTH_SPAN_CAP
        firsts = Counter(cand[c]["first_unit"] for c in sub)
        lasts = Counter(cand[c]["last_unit"] for c in sub)
        c_first = max(firsts.values()) <= ENDPOINT_MAJORITY_CAP
        c_last = max(lasts.values()) <= ENDPOINT_MAJORITY_CAP
        c_self = all(cand[c]["selforder_ok"] for c in sub)     # always true over eligible; reported
        pairs = list(itertools.combinations(sub, 2))
        c_edit = all(d_edit_ok[p] for p in pairs)
        c_big = all(bigram_ok[p] for p in pairs)
        c_tri = all(trigram_ok[p] for p in pairs)
        return {"edit_floor": c_edit, "selforder": c_self, "endpoint_first": c_first,
                "endpoint_last": c_last, "bigram": c_big, "trigram": c_tri, "length_span": c_span}

    n_subsets = 0
    indiv = Counter()
    all_ok_subsets = []
    # sequential survival order per Step 6: edit -> selforder -> endpoint(first&last) -> bigram -> trigram -> span
    seq_order = ["edit_floor", "selforder", "endpoint", "bigram", "trigram", "length_span"]
    seq_survivors = Counter()
    elim_first = Counter()   # first (in sequential order) constraint each failing subset violates

    for sub in itertools.combinations(eligible, K):
        n_subsets += 1
        cc = subset_constraints(sub)
        endpoint = cc["endpoint_first"] and cc["endpoint_last"]
        flat = {"edit_floor": cc["edit_floor"], "selforder": cc["selforder"], "endpoint": endpoint,
                "bigram": cc["bigram"], "trigram": cc["trigram"], "length_span": cc["length_span"]}
        for k2, v in flat.items():
            if v:
                indiv[k2] += 1
        # sequential survival + principal eliminator
        survived = True
        for k2 in seq_order:
            if flat[k2]:
                if survived:
                    seq_survivors[k2] += 1
            else:
                if survived:
                    elim_first[k2] += 1
                survived = False
        if all(flat.values()):
            all_ok_subsets.append(sub)

    constraint_counts = {
        "schema": "b1_12_subset_constraint_counts_v1",
        "n_eligible_candidates": len(eligible),
        "total_size6_subsets": n_subsets,
        "satisfying_each_constraint_independently": dict(indiv),
        "surviving_sequential_order": {k2: seq_survivors[k2] for k2 in seq_order},
        "principal_eliminating_constraint_counts": dict(elim_first),
        "n_satisfying_all_constraints": len(all_ok_subsets),
        "sequential_order": seq_order,
    }
    (OUT / "subset_constraint_counts.json").write_text(
        json.dumps(constraint_counts, indent=2, sort_keys=True), encoding="utf-8")

    # ---- Step 7: mechanical selection among fully-eligible subsets ----
    def subset_scores(sub):
        pairs = list(itertools.combinations(sorted(sub), 2))
        edits = [pairwise[pk(a, b)]["d_edit"] for a, b in pairs]
        msj = [pairwise[pk(a, b)]["multiset_jaccard"] for a, b in pairs]
        min_edit = min(edits)
        mean_edit = sum(edits) / len(edits)
        mean_unique_tri = sum(cand[c]["n_unique_trigrams"] for c in sub) / len(sub)
        mean_msj = sum(msj) / len(msj)
        return min_edit, mean_edit, mean_unique_tri, mean_msj

    status = None
    selection = None
    if invalid_reasons:
        status = "G0_INVALID"
    elif not all_ok_subsets:
        status = "G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET"
    else:
        # objective: max min_edit; tie-break (a) max mean_edit, (b) max mean_unique_tri,
        # (c) min mean_msj, (d) alphabetical by candidate-id tuple
        best = None
        for sub in all_ok_subsets:
            mi, me, mt, mm = subset_scores(sub)
            key = (-mi, -me, -mt, mm, tuple(sorted(sub)))
            if best is None or key < best[0]:
                best = (key, sub, (mi, me, mt, mm))
        _, sub, (mi, me, mt, mm) = best
        status = "G0_PASS"
        selection = {
            "selected_subset": sorted(sub),
            "selected_words": [{"id": c, "iast": cand[c]["iast"], "length": cand[c]["length"]}
                               for c in sorted(sub)],
            "objective_min_pairwise_d_edit": round(mi, 6),
            "tie_break_mean_pairwise_d_edit": round(me, 6),
            "tie_break_mean_unique_trigram_count": round(mt, 6),
            "tie_break_mean_multiset_jaccard": round(mm, 6),
        }

    (OUT / "selection.json").write_text(
        json.dumps({"schema": "b1_12_selection_v1", "status": status,
                    "selected_subset": (selection["selected_subset"] if selection else None),
                    "selection": selection}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # ---- diagnostics summary ----
    ord_vals = [pairwise[p]["d_ord_given_inv"] for p in pairwise]
    elig_ord = [pairwise[pk(a, b)]["d_ord_given_inv"] for a, b in itertools.combinations(eligible, 2)]
    diag = {
        "n_pairs_all": len(pairwise),
        "d_ord_given_inv_all_pool": {"min": round(min(ord_vals), 4), "max": round(max(ord_vals), 4),
                                     "mean": round(sum(ord_vals) / len(ord_vals), 4),
                                     "n_zero": sum(1 for v in ord_vals if v == 0.0),
                                     "n_positive": sum(1 for v in ord_vals if v > 0.0)},
        "d_ord_given_inv_eligible": ({"min": round(min(elig_ord), 4), "max": round(max(elig_ord), 4),
                                      "mean": round(sum(elig_ord) / len(elig_ord), 4),
                                      "n_zero": sum(1 for v in elig_ord if v == 0.0),
                                      "n_positive": sum(1 for v in elig_ord if v > 0.0)}
                                     if elig_ord else None),
    }

    # ---- Step 8: run manifest + subset search summary ----
    length_dist = Counter(cand[c]["length"] for c in cand)
    selforder_dist = {
        "min": round(min(cand[c]["s_selforder"] for c in cand), 4),
        "max": round(max(cand[c]["s_selforder"] for c in cand), 4),
        "n_ge_0.34": sum(1 for c in cand if cand[c]["s_selforder"] >= TAU_SELF),
        "n_lt_0.34": sum(1 for c in cand if cand[c]["s_selforder"] < TAU_SELF),
    }
    search_summary = {
        "schema": "b1_12_subset_search_summary_v1",
        "n_eligible_candidates": len(eligible),
        "total_size6_subsets": n_subsets,
        "n_satisfying_all": len(all_ok_subsets),
        "constraint_independent_counts": dict(indiv),
        "principal_eliminating_constraint_counts": dict(elim_first),
        "order_specific_diagnostic": diag,
        "status": status,
    }
    (OUT / "subset_search_summary.json").write_text(
        json.dumps(search_summary, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "schema": "b1_12_g0_audit_run_manifest_v1",
        "label": "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
        "role": "G0 AUDITOR (V1.1 §13) — pool frozen at curator commit d50fbb9; membership unchanged",
        "controlling_commits": COMMITS,
        "frozen_contract": {"k": K, "length_band": [LMIN, LMAX], "tau_edit": TAU_EDIT, "tau_self": TAU_SELF,
                            "endpoint_majority_cap": ENDPOINT_MAJORITY_CAP,
                            "bigram_jaccard_cap": BIGRAM_JACCARD_CAP, "trigram_jaccard_cap": TRIGRAM_JACCARD_CAP,
                            "length_span_cap": LENGTH_SPAN_CAP,
                            "objective": "maximize min pairwise d_edit",
                            "tie_break": ["max mean d_edit", "max mean unique-trigram count",
                                          "min mean multiset-jaccard", "alphabetical"]},
        "pool_sha256": pool_sha, "parser_sha256": parser_sha, "opaque_map_sha256": opaque_map_sha,
        "n_words_frozen": len(words), "n_parser_valid": sum(1 for c in cand if cand[c]["parser_valid"]),
        "n_length_ok": sum(1 for c in cand if cand[c]["length_ok"]),
        "n_selforder_ok": sum(1 for c in cand if cand[c]["selforder_ok"]),
        "n_eligible": len(eligible),
        "length_distribution": {str(k2): v for k2, v in sorted(length_dist.items())},
        "selforder_distribution": selforder_dist,
        "total_size6_subsets": n_subsets, "n_satisfying_all": len(all_ok_subsets),
        "invalid_reasons": invalid_reasons,
        "status": status,
        "no_thresholds_changed": True, "no_pool_membership_changed": True,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {"status": status, "manifest": manifest, "selection": selection,
            "constraint_counts": constraint_counts, "diag": diag}


if __name__ == "__main__":
    res = run()
    print(json.dumps({"status": res["status"],
                      "n_eligible": res["manifest"]["n_eligible"],
                      "total_subsets": res["manifest"]["total_size6_subsets"],
                      "n_satisfying_all": res["manifest"]["n_satisfying_all"],
                      "independent_counts": res["constraint_counts"]["satisfying_each_constraint_independently"],
                      "principal_eliminators": res["constraint_counts"]["principal_eliminating_constraint_counts"],
                      "selforder_dist": res["manifest"]["selforder_distribution"],
                      "selection": res["selection"]}, ensure_ascii=False, indent=2))
