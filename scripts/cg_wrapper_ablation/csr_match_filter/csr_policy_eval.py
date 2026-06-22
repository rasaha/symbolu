#!/usr/bin/env python3
"""csr_policy_eval.py — P-B: does CSR_policy beat the Phase 3 needs_rewrite gate? (implements
docs/CSR_GUNA_VRITTI_POLICY_PB_PREREG.md). CPU-only, analysis-only; no runtime/Phase 1-3/audit change.

Compares a deterministic CSR_policy (non-overlapping [D] terms: (1-MATCH_primary), trajectory_drift,
guna_quality, audit_severity) against the exact current `AnswerAuditResult.needs_rewrite` gate, scored
against INDEPENDENT rubric_v2 residual labels. Pinned weights hidden_risk = p_v = p_g = new_guna = 0.

  python csr_policy_eval.py --traces robustness_eval_v2.json --out csr_policy_eval.json
"""

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import answer_audit as AA               # noqa: E402
from csr_match_filter import trajectory as TRAJ               # NON_OVERLAP_PARTITION  # noqa: E402
from csr_match_filter import phase4_probe as PB               # group_kfold_indices  # noqa: E402
from csr_match_filter.match import dominant_terms             # noqa: E402

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "eval_data" / "framed_answer_eval_v2_rubricv2.jsonl"

# non-overlapping finding buckets (disjoint partition from the spec / trajectory.py)
FRAME_MOVE = TRAJ.NON_OVERLAP_PARTITION["trajectory_drift"]   # frame/domain movement only
SEVERITY = TRAJ.NON_OVERLAP_PARTITION["audit_severity"]       # factuality/phoneme only
GUNA_FIND = TRAJ.NON_OVERLAP_PARTITION["guna_quality"]        # expression quality only
GRID = (0.0, 0.5, 1.0)
DECISIONS = ("PB_POLICY_BEATS_AUDIT_GATE", "PB_POLICY_NO_INCREMENTAL_VALUE",
             "PB_AUDIT_REPACKAGING_ONLY", "PB_TERM_OVERLAP_INVALID", "PB_INSUFFICIENT_LABEL_POWER")


# ---- labels & features --------------------------------------------------------------------------

def rubric_truth(scores: dict) -> dict:
    """Independent ground truth from the rubric_v2 judge output (NOT the Phase 3 audit)."""
    def _false(k):
        v = scores.get(k)
        return v in (0, 0.0, False)
    fv, rl, fa = _false("primary_frame_correct"), _false("rejected_domain_avoidance"), \
        _false("factuality_preserved")
    sp = bool(scores.get("secondary_promoted"))
    return {"frame_violation": fv, "rejected_leak": rl, "factuality": fa, "secondary": sp,
            "should_rewrite": (fv or rl or fa), "critical": (rl or fa)}


def features_from_findings(finding_types, inv_match: float) -> dict:
    fts = set(finding_types)
    return {"inv_match": float(inv_match),
            "traj_drift": float(sum(f in fts for f in FRAME_MOVE)),
            "guna": float(sum(f in fts for f in GUNA_FIND)),
            "severity": float(sum(f in fts for f in SEVERITY))}


def overlap_ok() -> bool:
    s = [set(FRAME_MOVE), set(SEVERITY), set(GUNA_FIND)]
    return all(s[i].isdisjoint(s[j]) for i in range(3) for j in range(i + 1, 3))


def policy_risk(feat: dict, w: dict) -> float:
    return (w["inv_match"] * feat["inv_match"] + w["traj"] * feat["traj_drift"]
            + w["guna"] * feat["guna"] + w["sev"] * feat["severity"])


# ---- fit / predict / metrics --------------------------------------------------------------------

def _metrics(truth, pred):
    truth = np.asarray(truth, bool); pred = np.asarray(pred, bool)
    tp = int((truth & pred).sum()); fp = int((~truth & pred).sum())
    fn = int((truth & ~pred).sum()); tn = int((~truth & ~pred).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    fr = fp / (fp + tn) if (fp + tn) else 0.0           # false-rewrite rate on truth-negatives
    return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
            "false_rewrite_rate": round(fr, 3), "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def fit_policy(rows, fr_cap):
    """Grid-search weights + threshold maximizing F1 on `rows`, s.t. false-rewrite <= fr_cap."""
    truth = [r["truth"]["should_rewrite"] for r in rows]
    best, best_f1 = None, -1.0
    for wi, wt, wg, ws in itertools.product(GRID, repeat=4):
        if wi == wt == wg == ws == 0:
            continue
        w = {"inv_match": wi, "traj": wt, "guna": wg, "sev": ws}
        risks = np.array([policy_risk(r["feat"], w) for r in rows])
        for tau in np.unique(np.r_[risks, risks + 1e-9]):
            pred = risks >= tau
            m = _metrics(truth, pred)
            if m["false_rewrite_rate"] <= fr_cap and m["f1"] > best_f1:
                best_f1, best = m["f1"], (w, float(tau))
    return best or ({"inv_match": 0, "traj": 1, "guna": 0, "sev": 0}, 0.5)


def predict(rows, w, tau):
    return [policy_risk(r["feat"], w) >= tau for r in rows]


def cv_oof_policy(rows, n_splits=5, seed=0, fr_cap=0.10):
    groups = np.array([r["group"] for r in rows], dtype=object)
    oof = [None] * len(rows)
    for tr, te in PB.group_kfold_indices(groups, n_splits, seed):
        if len(tr) == 0 or len(te) == 0:
            continue
        w, tau = fit_policy([rows[i] for i in tr], fr_cap)
        for i, dec in zip(te, predict([rows[i] for i in te], w, tau)):
            oof[i] = bool(dec)
    return [bool(x) if x is not None else False for x in oof]


def per_class_recall(rows, pred):
    out = {}
    for cls in ("frame_violation", "rejected_leak", "factuality", "secondary"):
        idx = [i for i, r in enumerate(rows) if r["truth"][cls]]
        out[cls] = round(sum(pred[i] for i in idx) / len(idx), 3) if idx else None
    return out


def missed_critical_rate(rows, pred):
    crit = [i for i, r in enumerate(rows) if r["truth"]["critical"]]
    return round(sum(not pred[i] for i in crit) / len(crit), 3) if crit else 0.0


def bootstrap_f1_delta(truth, pred_a, pred_b, n_boot=1000, seed=0):
    truth = np.asarray(truth, bool); a = np.asarray(pred_a, bool); b = np.asarray(pred_b, bool)
    base = _metrics(truth, a)["f1"] - _metrics(truth, b)["f1"]
    rng = np.random.default_rng(seed); n = len(truth); ds = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        ds.append(_metrics(truth[idx], a[idx])["f1"] - _metrics(truth[idx], b[idx])["f1"])
    lo, hi = np.percentile(ds, [2.5, 97.5])
    return {"delta": round(float(base), 3), "ci_low": round(float(lo), 3),
            "ci_high": round(float(hi), 3), "excludes_zero": bool(lo > 0 or hi < 0)}


def term_contribution(rows, w, tau, fr_cap):
    """Marginal F1 effect of each term: zero it out, refit threshold, measure F1 drop."""
    truth = [r["truth"]["should_rewrite"] for r in rows]
    full = _metrics(truth, predict(rows, w, tau))["f1"]
    out = {}
    for term in ("inv_match", "traj", "guna", "sev"):
        w2 = dict(w); w2[term] = 0.0
        if all(v == 0 for v in w2.values()):
            out[term] = None; continue
        risks = np.array([policy_risk(r["feat"], w2) for r in rows])
        best = -1.0
        for t in np.unique(risks):
            m = _metrics(truth, risks >= t)
            if m["false_rewrite_rate"] <= fr_cap and m["f1"] > best:
                best = m["f1"]
        out[term] = round(full - best, 3)            # F1 lost when the term is removed
    return out


def decide(net, agreement, missed_pol, missed_base, fr_pol, fr_base, improved_class, n_pos,
           fr_tol=0.02):
    if not overlap_ok():
        return "PB_TERM_OVERLAP_INVALID"
    if n_pos < 10:
        return "PB_INSUFFICIENT_LABEL_POWER"
    if (net["delta"] > 0 and net["excludes_zero"] and missed_pol <= missed_base
            and fr_pol <= fr_base + fr_tol and improved_class):
        return "PB_POLICY_BEATS_AUDIT_GATE"
    if agreement >= 0.97 and net["delta"] <= 0:
        return "PB_AUDIT_REPACKAGING_ONLY"
    return "PB_POLICY_NO_INCREMENTAL_VALUE"


# ---- data loading (recomputes the C×R×S frame for MATCH_primary) ---------------------------------

def build_rows(traces_path, data_path, arms, semantic_backend="real"):
    from csr_match_filter import eval_framed_answers as EF
    from csr_match_filter import eval_match_filter as EV
    blob = json.loads(Path(traces_path).read_text())
    tr = blob.get("traces")
    src = next(iter(tr.values())) if isinstance(tr, dict) else (tr if isinstance(tr, list) else [])
    by_id = {ex["id"]: ex for ex in (json.loads(l) for l in Path(data_path).read_text().splitlines()
                                     if l.strip())}
    kb = EV.load_kb(str(EV._KB))
    adapter, provider, sem = EF.build_frame_adapter(semantic_backend, kb)
    rows = []
    for r in src:
        ex = by_id.get(r["id"])
        if ex is None:
            continue
        trace, terms = EF.frame_for(ex, adapter, provider)
        frame = {"primary_domains": trace.primary_domains, "secondary_domains": trace.secondary_domains,
                 "rejected_domains": trace.rejected_domains}
        match_primary = max([s.match for s in trace.scores if s.domain in trace.primary_domains],
                            default=0.0)
        group = terms[0] if terms else r["id"]
        alt = ex.get("expected_secondary_true_senses", [])
        fc = ex.get("false_claims", [])
        subj = dominant_terms(ex["query"])[:1] or None
        for arm in arms:
            ans = (r.get("answers") or {}).get(arm)
            sc = (r.get("scores") or {}).get(arm)
            if ans is None or sc is None:
                continue
            res = AA.audit_answer(ex["query"], ans, frame, terms=subj, alternate_true_senses=alt,
                                  false_claims=fc)
            rows.append({"id": r["id"], "arm": arm, "group": group,
                         "baseline_rewrite": bool(res.needs_rewrite),
                         "truth": rubric_truth(sc),
                         "feat": features_from_findings(res.finding_types, 1.0 - float(match_primary)),
                         "finding_types": sorted(set(res.finding_types))})
    return rows, sem


def run(rows, n_splits=5, seed=0):
    truth = [r["truth"]["should_rewrite"] for r in rows]
    n_pos = int(sum(truth))
    fr_base = _metrics(truth, [r["baseline_rewrite"] for r in rows])["false_rewrite_rate"]
    fr_cap = fr_base + 0.02
    base_pred = [r["baseline_rewrite"] for r in rows]
    pol_pred = cv_oof_policy(rows, n_splits, seed, fr_cap)
    w_full, tau_full = fit_policy(rows, fr_cap)                # for the term-contribution table only

    base_m = _metrics(truth, base_pred)
    pol_m = _metrics(truth, pol_pred)
    net = bootstrap_f1_delta(truth, pol_pred, base_pred, seed=seed)
    agreement = float(np.mean([p == b for p, b in zip(pol_pred, base_pred)]))
    base_cls, pol_cls = per_class_recall(rows, base_pred), per_class_recall(rows, pol_pred)
    improved_class = any((pol_cls[c] or 0) > (base_cls[c] or 0)
                         for c in pol_cls if pol_cls[c] is not None)
    missed_base = missed_critical_rate(rows, base_pred)
    missed_pol = missed_critical_rate(rows, pol_pred)
    decision = decide(net, agreement, missed_pol, missed_base, pol_m["false_rewrite_rate"], fr_base,
                      improved_class, n_pos)
    return {
        "n_rows": len(rows), "n_should_rewrite_truth": n_pos,
        "overlap_ok": overlap_ok(),
        "overlap_map": {"trajectory_drift": list(FRAME_MOVE), "audit_severity": list(SEVERITY),
                        "guna_quality": list(GUNA_FIND)},
        "baseline_needs_rewrite": base_m, "csr_policy": pol_m,
        "net_f1_improvement": net, "decision_agreement": round(agreement, 3),
        "missed_critical_rate": {"baseline": missed_base, "policy": missed_pol},
        "per_class_recall": {"baseline": base_cls, "policy": pol_cls},
        "term_contribution_f1": term_contribution(rows, w_full, tau_full, fr_cap),
        "fitted_weights_full_data": {"weights": w_full, "tau": tau_full,
                                     "pinned_zero": ["hidden_risk", "canonical_p_v", "canonical_p_g",
                                                     "new_guna_detector"]},
        "decision": decision,
    }


def to_markdown(rep):
    b, p = rep["baseline_needs_rewrite"], rep["csr_policy"]
    out = ["# P-B — CSR_policy vs Phase 3 needs_rewrite", "",
           f"n_rows={rep['n_rows']} · should_rewrite positives={rep['n_should_rewrite_truth']} · "
           f"overlap_ok={rep['overlap_ok']}", "",
           "| metric | baseline needs_rewrite | CSR_policy |", "|---|---|---|",
           f"| precision | {b['precision']} | {p['precision']} |",
           f"| recall | {b['recall']} | {p['recall']} |",
           f"| F1 | {b['f1']} | {p['f1']} |",
           f"| false-rewrite rate | {b['false_rewrite_rate']} | {p['false_rewrite_rate']} |",
           f"| missed-critical rate | {rep['missed_critical_rate']['baseline']} | "
           f"{rep['missed_critical_rate']['policy']} |", "",
           f"net F1 improvement = {rep['net_f1_improvement']['delta']} "
           f"[{rep['net_f1_improvement']['ci_low']}, {rep['net_f1_improvement']['ci_high']}] · "
           f"decision agreement = {rep['decision_agreement']}", "",
           f"per-class recall (baseline → policy): " +
           "; ".join(f"{c}: {rep['per_class_recall']['baseline'][c]}→{rep['per_class_recall']['policy'][c]}"
                     for c in rep['per_class_recall']['policy']), "",
           f"term contribution (F1 lost if removed): {rep['term_contribution_f1']}", "",
           f"## DECISION: {rep['decision']}"]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", default="robustness_eval_v2.json")
    ap.add_argument("--data", default=str(_DATA))
    ap.add_argument("--arms", default="base,framed")
    ap.add_argument("--semantic-backend", default="real")
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    rows, sem = build_rows(args.traces, args.data, arms, args.semantic_backend)
    if "hashing" in str(sem):
        print(f"⚠️  WARNING: semantic frame backend is '{sem}' (not real) — MATCH_primary is degraded; "
              "results not production-valid.")
    rep = run(rows, args.n_splits, args.seed)
    rep["semantic_frame_backend"] = sem
    out = Path(args.out) if args.out else Path("csr_policy_eval.json")
    out.write_text(json.dumps(rep, indent=2))
    out.with_suffix(".md").write_text(to_markdown(rep))
    print("=" * 80)
    print("P-B — CSR_policy vs Phase 3 needs_rewrite")
    print(f"  n={rep['n_rows']} pos={rep['n_should_rewrite_truth']}  baseline F1={rep['baseline_needs_rewrite']['f1']}"
          f"  policy F1={rep['csr_policy']['f1']}  ΔF1={rep['net_f1_improvement']['delta']}"
          f" {('[CI>0]' if rep['net_f1_improvement']['excludes_zero'] else '[CI~0]')}")
    print(f"  false_rewrite base={rep['baseline_needs_rewrite']['false_rewrite_rate']} "
          f"policy={rep['csr_policy']['false_rewrite_rate']}  agreement={rep['decision_agreement']}")
    print(f"  term_contribution_f1={rep['term_contribution_f1']}")
    print(f"  DECISION: {rep['decision']}")
    print(f"wrote {out} + {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
