#!/usr/bin/env python3
"""eval_answer_audit.py — Phase 3 evaluation of the C×R×S answer-audit layer.

Scores answer_audit.audit_answer against the pre-registered fixture set
(eval_data/answer_audit_eval.jsonl) with gold `expected_findings`, `expected_passed`,
`expected_needs_rewrite`. Deterministic; needs no LLM. Reports finding-type precision/recall/F1
(micro + per-type), rewrite-recommendation precision/recall, false_rewrite_rate,
missed_critical_failure_rate, and the targeted behavioural accuracies (allowed alternate sense,
refutation-not-leak, phoneme-overreach detection, trace completeness). Emits a PHASE3_* label.

  python scripts/cg_wrapper_ablation/csr_match_filter/eval_answer_audit.py \
    --data scripts/cg_wrapper_ablation/csr_match_filter/eval_data/answer_audit_eval.jsonl \
    --explain --out runs/csr_phase3/answer_audit_eval.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import answer_audit as AA   # noqa: E402
from csr_match_filter.match import dominant_terms  # noqa: E402

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "eval_data" / "answer_audit_eval.jsonl"

# findings that constitute a CRITICAL frame failure the auditor MUST catch (drive missed-critical)
_CRITICAL_FINDINGS = ("phoneme_overreach_claim", "rejected_domain_promoted")
FALSE_REWRITE_BUDGET = 0.10


def load_data(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def _safe_div(n, d):
    return (n / d) if d else None


def run(rows):
    per = []
    for ex in rows:
        terms = ex.get("terms") or dominant_terms(ex["query"])[:1] or None
        res = AA.audit_answer(ex["query"], ex["answer"], ex["csr_trace_fixture"], terms=terms,
                              alternate_true_senses=ex.get("alternate_true_senses"),
                              false_claims=ex.get("false_claims"), answer_id=ex["id"])
        per.append({"ex": ex, "res": res, "pred": set(res.finding_types),
                    "gold": set(ex["expected_findings"])})
    return per


def metrics(per):
    # --- micro finding-type precision / recall / F1 ---
    tp = sum(len(p["pred"] & p["gold"]) for p in per)
    fp = sum(len(p["pred"] - p["gold"]) for p in per)
    fn = sum(len(p["gold"] - p["pred"]) for p in per)
    prec = _safe_div(tp, tp + fp)
    rec = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * prec * rec, prec + rec) if (prec and rec) else 0.0

    # --- per-finding-type ---
    by_type = {}
    types = sorted({t for p in per for t in (p["pred"] | p["gold"])})
    for t in types:
        ttp = sum(1 for p in per if t in p["pred"] and t in p["gold"])
        tfp = sum(1 for p in per if t in p["pred"] and t not in p["gold"])
        tfn = sum(1 for p in per if t not in p["pred"] and t in p["gold"])
        by_type[t] = {"support": ttp + tfn, "precision": _safe_div(ttp, ttp + tfp),
                      "recall": _safe_div(ttp, ttp + tfn)}

    # --- rewrite recommendation precision / recall ---
    rw_tp = sum(1 for p in per if p["res"].needs_rewrite and p["ex"]["expected_needs_rewrite"])
    rw_fp = sum(1 for p in per if p["res"].needs_rewrite and not p["ex"]["expected_needs_rewrite"])
    rw_fn = sum(1 for p in per if not p["res"].needs_rewrite and p["ex"]["expected_needs_rewrite"])
    rw_prec = _safe_div(rw_tp, rw_tp + rw_fp)
    rw_rec = _safe_div(rw_tp, rw_tp + rw_fn)

    # --- false_rewrite_rate: among answers that should PASS (no rewrite), fraction we rewrite ---
    should_pass = [p for p in per if not p["ex"]["expected_needs_rewrite"]]
    false_rewrite_rate = _safe_div(sum(1 for p in should_pass if p["res"].needs_rewrite),
                                   len(should_pass))

    # --- missed_critical_failure_rate: critical gold failures we fail to recommend rewriting ---
    crit = [p for p in per if p["ex"]["expected_needs_rewrite"]
            and (p["gold"] & set(_CRITICAL_FINDINGS))]
    missed_critical_failure_rate = _safe_div(sum(1 for p in crit if not p["res"].needs_rewrite),
                                             len(crit))

    # --- targeted behavioural accuracies ---
    def acc(filter_fn, ok_fn):
        sub = [p for p in per if filter_fn(p)]
        return _safe_div(sum(1 for p in sub if ok_fn(p)), len(sub))

    allowed_alternate_sense_accuracy = acc(
        lambda p: "alternate_true_sense_allowed" in p["gold"],
        lambda p: "alternate_true_sense_allowed" in p["pred"] and p["res"].passed)
    refutation_not_leak_accuracy = acc(
        lambda p: "rejected_domain_mentioned_as_refutation" in p["gold"],
        lambda p: ("rejected_domain_mentioned_as_refutation" in p["pred"]
                   and "rejected_domain_promoted" not in p["pred"] and p["res"].passed))
    phoneme_overreach_detection = acc(
        lambda p: "phoneme_overreach_claim" in p["gold"],
        lambda p: "phoneme_overreach_claim" in p["pred"])

    # --- trace completeness (data integrity: all three lanes present, primary non-empty) ---
    def complete(ex):
        t = ex["csr_trace_fixture"]
        return all(k in t for k in ("primary_domains", "secondary_domains", "rejected_domains")) \
            and bool(t["primary_domains"])
    trace_completeness = _safe_div(sum(1 for p in per if complete(p["ex"])), len(per))

    # --- exact-match agreement (all three: findings set, passed, needs_rewrite) ---
    exact = _safe_div(sum(1 for p in per if p["pred"] == p["gold"]
                          and p["res"].passed == p["ex"]["expected_passed"]
                          and p["res"].needs_rewrite == p["ex"]["expected_needs_rewrite"]), len(per))

    return {"n": len(per), "finding_precision": prec, "finding_recall": rec, "finding_f1": f1,
            "per_finding_type": by_type, "rewrite_precision": rw_prec, "rewrite_recall": rw_rec,
            "false_rewrite_rate": false_rewrite_rate,
            "missed_critical_failure_rate": missed_critical_failure_rate,
            "allowed_alternate_sense_accuracy": allowed_alternate_sense_accuracy,
            "refutation_not_leak_accuracy": refutation_not_leak_accuracy,
            "phoneme_overreach_detection": phoneme_overreach_detection,
            "trace_completeness": trace_completeness, "exact_match": exact,
            "n_critical_failures": len(crit)}


def decide_phase3(m):
    """Phase 3 decision label. Missed-critical dominates; then no-value; then over-aggressive rewrite."""
    if (m["missed_critical_failure_rate"] or 0.0) > 0.0:
        return "PHASE3_AUDIT_MISSES_CRITICAL_FAILURES"
    f1 = m["finding_f1"] or 0.0
    # no value: detector cannot discriminate (very low F1) or never recommends a needed rewrite
    if f1 <= 0.5 or (m["rewrite_recall"] is not None and m["rewrite_recall"] <= 0.0):
        return "PHASE3_AUDIT_NO_VALUE"
    if (m["false_rewrite_rate"] or 0.0) > FALSE_REWRITE_BUDGET:
        return "PHASE3_AUDIT_WEAK_REWRITE_TOO_AGGRESSIVE"
    rp, rr = (m["rewrite_precision"] or 0.0), (m["rewrite_recall"] or 0.0)
    if (f1 >= 0.95 and rp >= 0.9 and rr >= 0.9 and (m["false_rewrite_rate"] or 0.0) <= 0.05
            and (m["missed_critical_failure_rate"] or 0.0) == 0.0):
        return "PHASE3_ANSWER_AUDIT_PASS"
    return "PHASE3_AUDIT_NEEDS_HUMAN_REVIEW"


def _fmt(v):
    return "n/a" if v is None else f"{v:.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(_DATA))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = load_data(args.data)
    if args.limit:
        rows = rows[: args.limit]
    per = run(rows)
    m = metrics(per)
    label = decide_phase3(m)

    print("=" * 78)
    print(f"PHASE 3 — ANSWER-AUDIT EVAL   n={m['n']}   audit_backend=deterministic_csr (no LLM)")
    print("-" * 78)
    print(f"  finding-type    precision={_fmt(m['finding_precision'])}  "
          f"recall={_fmt(m['finding_recall'])}  F1={_fmt(m['finding_f1'])}")
    print(f"  rewrite rec     precision={_fmt(m['rewrite_precision'])}  "
          f"recall={_fmt(m['rewrite_recall'])}")
    print(f"  false_rewrite_rate           {_fmt(m['false_rewrite_rate'])}  "
          f"(budget {FALSE_REWRITE_BUDGET})")
    print(f"  missed_critical_failure_rate {_fmt(m['missed_critical_failure_rate'])}  "
          f"(n_critical={m['n_critical_failures']})")
    print(f"  allowed_alternate_sense_acc  {_fmt(m['allowed_alternate_sense_accuracy'])}")
    print(f"  refutation_not_leak_acc      {_fmt(m['refutation_not_leak_accuracy'])}")
    print(f"  phoneme_overreach_detection  {_fmt(m['phoneme_overreach_detection'])}")
    print(f"  trace_completeness           {_fmt(m['trace_completeness'])}")
    print(f"  exact_match (all 3 fields)   {_fmt(m['exact_match'])}")
    print("-" * 78)
    print("  per-finding-type:")
    for t, d in m["per_finding_type"].items():
        print(f"    {t:42} support={d['support']:>3}  "
              f"P={_fmt(d['precision'])} R={_fmt(d['recall'])}")
    print("-" * 78)
    print(f"LABEL: {label}")
    if args.explain:
        print("-" * 78 + "\nDISAGREEMENTS (pred != gold):")
        any_dis = False
        for p in per:
            if p["pred"] != p["gold"] or p["res"].needs_rewrite != p["ex"]["expected_needs_rewrite"]:
                any_dis = True
                print(f"  {p['ex']['id']:24} gold={sorted(p['gold'])} pred={sorted(p['pred'])} "
                      f"rw(gold={p['ex']['expected_needs_rewrite']},pred={p['res'].needs_rewrite})")
        if not any_dis:
            print("  (none — perfect agreement)")

    report = {"meta": {"n": m["n"], "data": str(args.data), "audit_backend": "deterministic_csr",
                       "false_rewrite_budget": FALSE_REWRITE_BUDGET}, "metrics": m, "label": label}
    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        report["per_example"] = [{"id": p["ex"]["id"], "gold": sorted(p["gold"]),
                                  "pred": sorted(p["pred"]), "passed": p["res"].passed,
                                  "needs_rewrite": p["res"].needs_rewrite,
                                  "status": p["res"].status} for p in per]
        outp.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
