#!/usr/bin/env python3
"""SUPERVISED OBSERVATION evaluator — does the Phase 3 needs_rewrite gate predict INDEPENDENT HUMAN
rewrite necessity, and do the C×R×S / DerivedVrittiTrajectory / GunaQualityDiagnostic diagnostics add
incremental value beyond it?

Pre-registration: docs/CSR_SUPERVISED_OBSERVATION_PREREG.md. This is OFFLINE EVALUATION ONLY — it reuses
production code (`answer_audit`, the C×R×S frame, `trajectory`, `guna`) to *recompute* predictors and
scores them against human labels. It changes NO runtime behavior, no Phase 1–3 logic, no CSR_policy
weights; it wires nothing into decisions; it uses no canonical p_v / p_g, no hidden-risk, no Bhava, and
NEVER uses rubric_v2 as the human ground truth.

Two layers, deliberately separated so the decision engine is CPU-testable without embeddings/GPU:
  • recompute_predictors(...)  — reuses production frame+audit+diagnostics (needs the KB/embeddings; pod)
  • run(rows, ...)             — pure-numpy scoring + decision over rows that already carry {feat, human}

Predictor sets (disjoint feature families = the pre-registered non-overlap partition):
  A baseline = Phase 3 needs_rewrite gate (a single bit; not fit)
  B audit fields         = {audit_severity}                       (factuality + phoneme)
  C audit + C×R×S        = B + {inv_match}                        (1 − MATCH_primary)
  D audit + trajectory   = B + {traj_drift}                       (frame-movement findings)
  E audit + Guna         = B + {guna_quality}                     (answer_too_generic)
  F all diagnostics      = B + {inv_match, traj_drift, guna_quality}
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_ABL = _HERE.parent
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

from csr_match_filter import trajectory as TRAJ   # noqa: E402  (NON_OVERLAP_PARTITION)

# ---- disjoint feature families (each maps to the findings it consumes; ∅ = not a finding) ---------
SEVERITY = tuple(TRAJ.NON_OVERLAP_PARTITION["audit_severity"])
FRAME_MOVE = tuple(TRAJ.NON_OVERLAP_PARTITION["trajectory_drift"])
GUNA_FIND = tuple(TRAJ.NON_OVERLAP_PARTITION["guna_quality"])
FEATURE_FINDINGS = {
    "inv_match": frozenset(),               # C×R×S frame score — not an audit finding
    "audit_severity": frozenset(SEVERITY),
    "traj_drift": frozenset(FRAME_MOVE),
    "guna_quality": frozenset(GUNA_FIND),
}
PREDICTOR_SETS = {
    "B_audit": ("audit_severity",),
    "C_audit_csr": ("audit_severity", "inv_match"),
    "D_audit_traj": ("audit_severity", "traj_drift"),
    "E_audit_guna": ("audit_severity", "guna_quality"),
    "F_all": ("audit_severity", "inv_match", "traj_drift", "guna_quality"),
}
GRID = (0.0, 0.5, 1.0)

LABEL_FIELDS = (
    "rewrite_needed", "answer_acceptable", "primary_frame_correct", "rejected_domain_leak",
    "secondary_overpromoted", "generic_low_signal", "clear_and_useful_1to5",
    "factual_or_grounded_1to5", "overconfident_or_overstated", "frame_label_parroting",
    "needs_clarification", "short_reason",
)
_BINARY = ("rewrite_needed", "answer_acceptable", "primary_frame_correct", "rejected_domain_leak",
           "secondary_overpromoted", "generic_low_signal", "overconfident_or_overstated",
           "frame_label_parroting", "needs_clarification")
_SCALES = ("clear_and_useful_1to5", "factual_or_grounded_1to5")

DECISIONS = (
    "SO_AUDIT_GATE_VALIDATED", "SO_DIAGNOSTICS_ADD_SIGNAL", "SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE",
    "SO_AUDIT_GATE_FAILS_HUMAN_LABELS", "SO_INSUFFICIENT_RATER_AGREEMENT",
    "SO_INSUFFICIENT_LABEL_POWER", "SO_TERM_OVERLAP_INVALID",
)


# ================================================================================================ #
#  label / value parsing
# ================================================================================================ #
def _yn(v):
    """Parse a yes/no/blank cell to True/False/None (raises on a non-empty unparseable token)."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("", "null", "none", "na", "n/a"):
        return None
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    raise ValueError(f"unparseable yes/no value {v!r}")


def _scale(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "null", "none", "na", "n/a"):
        return None
    f = float(s)
    if not (1.0 <= f <= 5.0):
        raise ValueError(f"scale out of range 1–5: {v!r}")
    return f


def parse_label_row(raw: dict) -> dict:
    out = {}
    for k in _BINARY:
        out[k] = _yn(raw.get(k))
    for k in _SCALES:
        out[k] = _scale(raw.get(k))
    out["short_reason"] = (raw.get("short_reason") or "").strip() or None
    return out


def load_labels(path) -> dict:
    """item_id -> parsed label dict. Accepts CSV (template) or JSONL packet with filled human_labels."""
    p = Path(path)
    rows = {}
    if p.suffix.lower() == ".jsonl":
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            rows[rec["item_id"]] = parse_label_row(rec.get("human_labels") or {})
    else:
        with open(p, newline="", encoding="utf-8") as fh:
            for raw in csv.DictReader(fh):
                iid = (raw.get("item_id") or "").strip()
                if iid:
                    rows[iid] = parse_label_row(raw)
    if not rows:
        raise ValueError(f"no labels loaded from {path}")
    return rows


# ================================================================================================ #
#  join: labels -> keymap -> trace answer/prompt
# ================================================================================================ #
def join_rows(labels_by_rater: list[dict], keymap: dict, answers_by_id: dict, prompts: dict):
    """Return (rows, report). Fails loudly if a labeled item_id is absent from the keymap.

    Rows missing the primary human label (rewrite_needed) from the primary rater are EXCLUDED explicitly
    (recorded in report['excluded']), not silently dropped or faked.
    """
    primary = labels_by_rater[0]
    rows, excluded = [], []
    for iid, lab in primary.items():
        if iid not in keymap:
            raise KeyError(f"labeled item_id {iid!r} not in keymap (cannot resolve source/arm)")
        km = keymap[iid]
        sid, arm = km["source_id"], km["arm"]
        if sid not in answers_by_id or arm not in (answers_by_id.get(sid) or {}):
            raise KeyError(f"item {iid!r} -> {sid!r}/{arm!r} has no trace answer")
        if sid not in prompts:
            raise KeyError(f"item {iid!r} -> {sid!r} has no prompt (eval-data join)")
        if lab.get("rewrite_needed") is None:
            excluded.append({"item_id": iid, "reason": "missing primary human label rewrite_needed"})
            continue
        raters = [lab] + [r[iid] for r in labels_by_rater[1:] if iid in r]
        rows.append({
            "item_id": iid, "source_id": sid, "arm": arm, "group": sid,
            "prompt": prompts[sid], "answer": answers_by_id[sid][arm],
            "human": lab, "human_raters": raters,
        })
    return rows, {"n_labeled": len(primary), "n_joined": len(rows), "excluded": excluded}


# ================================================================================================ #
#  predictor recompute (POD path — reuses production frame+audit+diagnostics; needs the KB/embeddings)
# ================================================================================================ #
def recompute_predictors(rows, traces_path, eval_data_path, semantic_backend="real"):
    """Fill row['baseline_needs_rewrite'] + row['feat'] using PRODUCTION code. Sets availability flags;
    if the C×R×S frame cannot be built (no embeddings), MATCH is marked unavailable — never faked."""
    from csr_match_filter import answer_audit as AA
    from csr_match_filter import guna as GUNA
    from csr_match_filter.match import dominant_terms

    by_id = {ex["id"]: ex for ex in
             (json.loads(l) for l in Path(eval_data_path).read_text().splitlines() if l.strip())}

    match_available = True
    frame_for = adapter = provider = None
    try:
        from csr_match_filter import eval_framed_answers as EF
        from csr_match_filter import eval_match_filter as EV
        kb = EV.load_kb(str(EV._KB))
        adapter, provider, sem = EF.build_frame_adapter(semantic_backend, kb)
        frame_for = EF.frame_for
        if sem != "real":
            match_available = False
    except Exception:                                   # noqa: BLE001 — embeddings/KB unavailable
        match_available = False
        sem = "unavailable"

    frame_cache = {}
    for row in rows:
        sid = row["source_id"]
        ex = by_id.get(sid)
        if ex is None:
            raise KeyError(f"source id {sid!r} absent from eval-data {eval_data_path}")
        if sid not in frame_cache:
            if frame_for is not None and match_available:
                trace, terms = frame_for(ex, adapter, provider)
                frame = {"primary_domains": trace.primary_domains,
                         "secondary_domains": trace.secondary_domains,
                         "rejected_domains": trace.rejected_domains}
                inv_match = 1.0 - max([s.match for s in trace.scores
                                       if s.domain in trace.primary_domains], default=0.0)
            else:                                       # no embeddings: domains from eval-data, no MATCH
                frame = {"primary_domains": ex.get("expected_primary", []),
                         "secondary_domains": ex.get("expected_secondary", []),
                         "rejected_domains": ex.get("expected_rejected", [])}
                terms = dominant_terms(ex["query"])[:1]
                inv_match = None
            frame_cache[sid] = (frame, terms, inv_match)
        frame, terms, inv_match = frame_cache[sid]
        subj = (dominant_terms(ex["query"])[:1] or None)
        res = AA.audit_answer(ex["query"], row["answer"], frame, terms=subj,
                              alternate_true_senses=ex.get("expected_secondary_true_senses", []),
                              false_claims=ex.get("false_claims", []))
        fts = set(res.finding_types)
        traj = TRAJ.derive_trajectory(res.finding_types, answer=row["answer"])
        GUNA.derive_guna(res.finding_types, answer=row["answer"])   # exercised; features come from fts
        row["baseline_needs_rewrite"] = bool(res.needs_rewrite)
        row["finding_types"] = sorted(fts)
        row["feat"] = {
            "inv_match": inv_match,
            "audit_severity": float(sum(f in fts for f in SEVERITY)),
            "traj_drift": float(len(traj["drift_flags"])),
            "guna_quality": float(sum(f in fts for f in GUNA_FIND)),
        }
        row["availability"] = {"match": match_available}
    return {"semantic_frame_backend": sem, "match_available": match_available}


# ================================================================================================ #
#  metrics
# ================================================================================================ #
def _metrics(truth, pred) -> dict:
    t = np.asarray(truth, bool)
    p = np.asarray(pred, bool)
    tp = int(np.sum(p & t)); fp = int(np.sum(p & ~t))
    fn = int(np.sum(~p & t)); tn = int(np.sum(~p & ~t))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "false_rewrite_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
        "missed_rewrite_rate": round(fn / (fn + tp), 4) if fn + tp else 0.0,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "n_pos": int(tp + fn), "n_neg": int(fp + tn),
    }


def _f1(truth, pred) -> float:
    return _metrics(truth, pred)["f1"]


def bootstrap_delta_f1(truth, pred_cand, pred_base, n_boot=2000, seed=0) -> dict:
    t = np.asarray(truth, bool); c = np.asarray(pred_cand, bool); b = np.asarray(pred_base, bool)
    n = len(t)
    rng = np.random.default_rng(seed)
    deltas = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        deltas[i] = _f1(t[idx], c[idx]) - _f1(t[idx], b[idx])
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    point = _f1(t, c) - _f1(t, b)
    return {"delta_f1": round(float(point), 4), "ci_low": round(float(lo), 4),
            "ci_high": round(float(hi), 4), "excludes_zero": bool(lo > 0.0)}


# ---- agreement ----------------------------------------------------------------------------------
def cohen_kappa(a, b) -> float | None:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 2:
        return None
    a2 = np.array([int(bool(x)) for x, _ in pairs]); b2 = np.array([int(bool(y)) for _, y in pairs])
    po = float(np.mean(a2 == b2))
    pa, pb = a2.mean(), b2.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return round((po - pe) / (1 - pe), 4)


def _pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 4)


def spearman(a, b) -> float | None:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 2:
        return None
    xs = np.argsort(np.argsort([p[0] for p in pairs]))
    ys = np.argsort(np.argsort([p[1] for p in pairs]))
    return _pearson(xs, ys)


# ================================================================================================ #
#  grouped-CV grid fit for a predictor set
# ================================================================================================ #
def group_kfold_indices(groups, n_splits=5, seed=0):
    uniq = sorted(set(groups))
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    fold_of = {g: i % n_splits for i, g in enumerate(uniq)}
    folds = [[] for _ in range(n_splits)]
    for i, g in enumerate(groups):
        folds[fold_of[g]].append(i)
    for k in range(n_splits):
        test = folds[k]
        train = [i for j in range(n_splits) if j != k for i in folds[j]]
        if test and train:
            yield train, test


def _score(feat, keys, w):
    return sum(w[k] * float(feat.get(k) or 0.0) for k in keys)


def _fit_on(rows, keys, fr_cap):
    """Grid over weights∈GRID and τ swept; maximize F1 s.t. false_rewrite ≤ fr_cap. Returns (w, τ)."""
    truth = [bool(r["human"]["rewrite_needed"]) for r in rows]
    best = (-1.0, {k: 0.0 for k in keys}, 0.5)
    for combo in itertools.product(GRID, repeat=len(keys)):
        if not any(combo):
            continue
        w = dict(zip(keys, combo))
        scores = [_score(r["feat"], keys, w) for r in rows]
        lo = min(scores)
        # τ must exceed the minimum score so the prediction actually USES the feature — a τ at/below
        # the minimum predicts every row positive (a degenerate classifier that ignores the features
        # and can spuriously "beat" a broken baseline). Uninformative features -> no valid τ -> skipped.
        for tau in sorted(t for t in set(scores) if t > lo):
            pred = [s >= tau for s in scores]
            m = _metrics(truth, pred)
            if m["false_rewrite_rate"] <= fr_cap and m["f1"] > best[0]:
                best = (m["f1"], w, tau)
    return best[1], best[2]


def cv_oof(rows, keys, n_splits, seed, fr_cap):
    """Out-of-fold predictions for a predictor set (grouped by source id)."""
    pred = [False] * len(rows)
    any_fold = False
    for train_idx, test_idx in group_kfold_indices([r["group"] for r in rows], n_splits, seed):
        any_fold = True
        w, tau = _fit_on([rows[i] for i in train_idx], keys, fr_cap)
        for i in test_idx:
            pred[i] = _score(rows[i]["feat"], keys, w) >= tau
    if not any_fold:                                      # too few groups to split — fit on all
        w, tau = _fit_on(rows, keys, fr_cap)
        pred = [_score(r["feat"], keys, w) >= tau for r in rows]
    return pred


# ================================================================================================ #
#  overlap validity
# ================================================================================================ #
def set_overlap(keys) -> list:
    """Return finding collisions: pairs of feature keys whose underlying findings intersect."""
    collisions = []
    for a, b in itertools.combinations(keys, 2):
        inter = FEATURE_FINDINGS[a] & FEATURE_FINDINGS[b]
        if inter:
            collisions.append({"a": a, "b": b, "shared_findings": sorted(inter)})
    return collisions


def feature_availability(rows, keys) -> dict:
    """Which feature keys are actually populated (e.g. inv_match is None when MATCH unavailable)."""
    avail = {}
    for k in keys:
        avail[k] = all(r["feat"].get(k) is not None for r in rows)
    return avail


# ================================================================================================ #
#  decision engine
# ================================================================================================ #
def decide(*, baseline_f1, best_set_name, best_delta, best_ci_excl_zero, best_overlap,
           missed_worse, fr_worse, n_pos, kappa, single_rater,
           thresholds) -> tuple[str, dict]:
    th = thresholds
    reasons = {}
    # 1. rater agreement (only meaningful with ≥2 raters)
    if (not single_rater) and kappa is not None and kappa < th["kappa_min"]:
        return "SO_INSUFFICIENT_RATER_AGREEMENT", {"kappa": kappa, "kappa_min": th["kappa_min"]}
    # 2. label power
    if n_pos < th["min_pos"]:
        return "SO_INSUFFICIENT_LABEL_POWER", {"n_pos": n_pos, "min_pos": th["min_pos"]}
    # gate: does the best candidate clear ALL of §5.7?
    gate_pass = (best_delta >= th["delta_f1_min"] and best_ci_excl_zero
                 and not missed_worse and not fr_worse)
    reasons.update(gate_pass=gate_pass, best_set=best_set_name, best_delta=best_delta,
                   ci_excludes_zero=best_ci_excl_zero, missed_worse=missed_worse, fr_worse=fr_worse)
    # 3. an improvement explained by a double-counted (overlapping) feature is invalid
    if gate_pass and best_overlap:
        return "SO_TERM_OVERLAP_INVALID", {**reasons, "overlap": best_overlap}
    # 4./5. a clean improvement — but a single rater cannot license ADD_SIGNAL
    if gate_pass:
        if single_rater:
            return "SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE", {**reasons,
                                                           "note": "single_rater_descriptive_only"}
        return "SO_DIAGNOSTICS_ADD_SIGNAL", reasons
    # no clean improvement:
    if baseline_f1 < th["base_fail_f1"]:
        return "SO_AUDIT_GATE_FAILS_HUMAN_LABELS", {"baseline_f1": baseline_f1,
                                                    "base_fail_f1": th["base_fail_f1"]}
    if baseline_f1 >= th["base_good_f1"]:
        return "SO_AUDIT_GATE_VALIDATED", {"baseline_f1": baseline_f1, **reasons}
    return "SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE", {"baseline_f1": baseline_f1, **reasons}


DEFAULT_THRESHOLDS = {"min_pos": 20, "kappa_min": 0.4, "delta_f1_min": 0.05, "fr_tol": 0.02,
                      "base_fail_f1": 0.40, "base_good_f1": 0.60}


def run(rows, *, n_splits=5, seed=0, single_rater=True, thresholds=None) -> dict:
    if not rows:
        raise ValueError("no joined rows to evaluate")
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    truth = [bool(r["human"]["rewrite_needed"]) for r in rows]
    n_pos = int(sum(truth))
    base_pred = [bool(r.get("baseline_needs_rewrite")) for r in rows]
    base_m = _metrics(truth, base_pred)
    fr_cap = base_m["false_rewrite_rate"] + th["fr_tol"]

    # which feature families are usable on this data (inv_match drops out if MATCH unavailable)
    sets_report, best = {}, None
    for name, keys in PREDICTOR_SETS.items():
        avail = feature_availability(rows, keys)
        usable_keys = tuple(k for k in keys if avail[k])
        unavailable = [k for k in keys if not avail[k]]
        if not usable_keys:
            sets_report[name] = {"unavailable": unavailable, "skipped": True}
            continue
        pred = cv_oof(rows, usable_keys, n_splits, seed, fr_cap)
        m = _metrics(truth, pred)
        boot = bootstrap_delta_f1(truth, pred, base_pred, seed=seed)
        overlap = set_overlap(usable_keys)
        missed_worse = m["missed_rewrite_rate"] > base_m["missed_rewrite_rate"]
        fr_worse = m["false_rewrite_rate"] > base_m["false_rewrite_rate"] + th["fr_tol"]
        agreement = float(np.mean([p == b for p, b in zip(pred, base_pred)]))
        entry = {"keys": list(usable_keys), "unavailable": unavailable, "metrics": m,
                 "delta_f1_vs_baseline": boot, "overlap": overlap,
                 "missed_worse": missed_worse, "fr_worse": fr_worse,
                 "decision_agreement_vs_baseline": round(agreement, 3)}
        sets_report[name] = entry
        cand = (boot["delta_f1"], name, entry)
        if best is None or cand[0] > best[0]:
            best = cand

    # 1–5 scale summaries + correlation with the audit-severity feature (where present)
    scale_summary = {}
    for s in _SCALES:
        vals = [r["human"][s] for r in rows if r["human"][s] is not None]
        sev = [r["feat"].get("audit_severity") for r in rows if r["human"][s] is not None]
        scale_summary[s] = {"n": len(vals), "mean": round(float(np.mean(vals)), 3) if vals else None,
                            "spearman_vs_audit_severity": spearman(
                                [r["human"][s] for r in rows], [r["feat"].get("audit_severity")
                                                                for r in rows])}

    # rater agreement (only if ≥2 raters provided per row anywhere)
    multi = any(len(r["human_raters"]) >= 2 for r in rows)
    agreement_report = {"single_rater_descriptive_only": (single_rater or not multi)}
    if multi:
        for k in _BINARY:
            a = [r["human_raters"][0].get(k) for r in rows if len(r["human_raters"]) >= 2]
            b = [r["human_raters"][1].get(k) for r in rows if len(r["human_raters"]) >= 2]
            agreement_report.setdefault("cohen_kappa", {})[k] = cohen_kappa(a, b)
        for k in _SCALES:
            a = [r["human_raters"][0].get(k) for r in rows if len(r["human_raters"]) >= 2]
            b = [r["human_raters"][1].get(k) for r in rows if len(r["human_raters"]) >= 2]
            agreement_report.setdefault("spearman", {})[k] = spearman(a, b)
    is_single = single_rater or not multi
    primary_kappa = (agreement_report.get("cohen_kappa", {}) or {}).get("rewrite_needed")

    if best is None:
        decision, dreasons = ("SO_INSUFFICIENT_LABEL_POWER"
                              if n_pos < th["min_pos"] else "SO_AUDIT_GATE_VALIDATED"), {}
    else:
        decision, dreasons = decide(
            baseline_f1=base_m["f1"], best_set_name=best[1], best_delta=best[2]["delta_f1_vs_baseline"]["delta_f1"],
            best_ci_excl_zero=best[2]["delta_f1_vs_baseline"]["excludes_zero"],
            best_overlap=best[2]["overlap"], missed_worse=best[2]["missed_worse"],
            fr_worse=best[2]["fr_worse"], n_pos=n_pos, kappa=primary_kappa,
            single_rater=is_single, thresholds=th)

    return {
        "n_rows": len(rows), "n_human_rewrite_needed": n_pos,
        "primary_target": "human_rewrite_needed",
        "thresholds": th,
        "baseline_needs_rewrite": base_m,
        "predictor_sets": sets_report,
        "best_set": best[1] if best else None,
        "scale_summary": scale_summary,
        "rater_agreement": agreement_report,
        "single_rater_descriptive_only": is_single,
        "overlap_map": {k: sorted(v) for k, v in FEATURE_FINDINGS.items()},
        "decision": decision, "decision_reasons": dreasons,
    }


# ================================================================================================ #
#  reporting
# ================================================================================================ #
def to_markdown(rep) -> str:
    b = rep["baseline_needs_rewrite"]
    L = [f"# Supervised Observation — audit gate vs human `rewrite_needed`",
         "", f"- rows: **{rep['n_rows']}**  ·  human rewrite_needed=yes: **{rep['n_human_rewrite_needed']}**"
         f"  ·  single_rater_descriptive_only: **{rep['single_rater_descriptive_only']}**",
         f"- **DECISION: `{rep['decision']}`**", "",
         "| set | F1 | precision | recall | false_rw | missed_rw | ΔF1 vs gate | CI>0 | overlap |",
         "|---|---|---|---|---|---|---|---|---|",
         f"| A_baseline (needs_rewrite) | {b['f1']} | {b['precision']} | {b['recall']} |"
         f" {b['false_rewrite_rate']} | {b['missed_rewrite_rate']} | — | — | — |"]
    for name, e in rep["predictor_sets"].items():
        if e.get("skipped"):
            L.append(f"| {name} | _skipped: {','.join(e['unavailable'])} unavailable_ |||||||| ")
            continue
        m, d = e["metrics"], e["delta_f1_vs_baseline"]
        L.append(f"| {name} | {m['f1']} | {m['precision']} | {m['recall']} | {m['false_rewrite_rate']} |"
                 f" {m['missed_rewrite_rate']} | {d['delta_f1']} [{d['ci_low']},{d['ci_high']}] |"
                 f" {d['excludes_zero']} | {'⚠ ' + str(len(e['overlap'])) if e['overlap'] else 'ok'} |")
    L += ["", f"- best set: **{rep['best_set']}**",
          f"- overlap_map (disjoint families): `{rep['overlap_map']}`",
          f"- decision_reasons: `{rep['decision_reasons']}`", ""]
    if rep["scale_summary"]:
        L.append("1–5 scales: " + "  ".join(
            f"{k}: mean={v['mean']} ρ_sev={v['spearman_vs_audit_severity']}"
            for k, v in rep["scale_summary"].items()))
    ar = rep["rater_agreement"]
    if "cohen_kappa" in ar:
        L.append(f"rater κ (rewrite_needed): {ar['cohen_kappa'].get('rewrite_needed')}")
    return "\n".join(L) + "\n"


# ================================================================================================ #
#  CLI
# ================================================================================================ #
def main(argv=None):
    ap = argparse.ArgumentParser(description="Supervised observation evaluator (offline; no runtime change).")
    ap.add_argument("--labels", required=True,
                    help="filled labels CSV/JSONL (comma-separate two files for two raters)")
    ap.add_argument("--keymap", required=True)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--eval-data", required=True)
    ap.add_argument("--out", default="supervised_observation_eval.json")
    ap.add_argument("--report", default="supervised_observation_eval.md")
    ap.add_argument("--semantic-backend", default="real")
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-pos", type=int, default=DEFAULT_THRESHOLDS["min_pos"])
    args = ap.parse_args(argv)

    label_paths = [p for p in args.labels.split(",") if p.strip()]
    labels_by_rater = [load_labels(p) for p in label_paths]
    single_rater = len(labels_by_rater) < 2
    keymap = json.loads(Path(args.keymap).read_text(encoding="utf-8"))

    blob = json.loads(Path(args.traces).read_text(encoding="utf-8"))
    tr = blob.get("traces") or {}
    src = next(iter(tr.values())) if isinstance(tr, dict) else tr
    answers_by_id = {ex["id"]: (ex.get("answers") or {}) for ex in src}
    prompts = {json.loads(l)["id"]: json.loads(l)["query"]
               for l in Path(args.eval_data).read_text().splitlines() if l.strip()}

    rows, join_report = join_rows(labels_by_rater, keymap, answers_by_id, prompts)
    pred_report = recompute_predictors(rows, args.traces, args.eval_data, args.semantic_backend)
    rep = run(rows, n_splits=args.n_splits, seed=args.seed, single_rater=single_rater,
              thresholds={"min_pos": args.min_pos})
    rep["join_report"] = join_report
    rep["predictor_recompute"] = pred_report

    Path(args.out).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    Path(args.report).write_text(to_markdown(rep), encoding="utf-8")
    print(f"rows={rep['n_rows']} pos={rep['n_human_rewrite_needed']} "
          f"baseline_f1={rep['baseline_needs_rewrite']['f1']} best={rep['best_set']}")
    print(f"DECISION: {rep['decision']}")
    print(f"wrote {args.out} + {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
