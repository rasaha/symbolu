#!/usr/bin/env python3
"""eval_framed_answers_robustness.py — Phase 2B robustness validation.

Re-runs the FROZEN Phase 1 frame + FROZEN Phase 2 framed prompt on a larger held-out dataset
(framed_answer_eval_v2.jsonl), scored by a PRE-REGISTERED, locked rubric (framed_answer_rubric_v1)
via a pluggable judge (deterministic / stub / optional LLM), across multiple answer models. Reports
per-backend + pooled metrics, framed-base deltas, stratified breakdowns, a failure report, and a
Phase 2B decision label. Validation only — no Phase 1/2 logic, thresholds, or prompts are changed.

  python .../eval_framed_answers_robustness.py --data .../framed_answer_eval_v2.jsonl \
    --rubric .../framed_answer_rubric_v1.yaml --answer-backends mistral --judge-backend deterministic \
    --semantic-backend real --arms base,framed --out runs/csr_phase2b/robustness_eval.json --write-traces
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import CSRThresholds  # noqa: E402
from csr_match_filter import eval_framed_answers as EF   # frame + arms (frozen Phase 2)  # noqa: E402
from csr_match_filter import eval_match_filter as EV     # KB + frame adapter  # noqa: E402
from csr_match_filter import judge_adapter as JU         # noqa: E402
from csr_match_filter import llm_adapter as LA           # noqa: E402

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "eval_data" / "framed_answer_eval_v2.jsonl"
_RUBRIC = _HERE / "eval_data" / "framed_answer_rubric_v1.yaml"
_KB_V2 = _HERE / "eval_data" / "framed_answer_kb_v2.json"
_FROZEN = CSRThresholds()

BOOL_METRICS = ("primary_frame_correct", "secondary_handling_correct", "rejected_domain_avoidance",
                "factuality_preserved")
GATE_KEYS = ("primary_frame_correct", "rejected_domain_avoidance", "phoneme_overreach_rate",
             "factuality_preserved", "must_include_recall", "must_not_violation_rate", "clarity_proxy")


def load_data(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def load_rubric(path):
    txt = Path(path).read_text()
    try:
        import yaml
        cfg = yaml.safe_load(txt)
    except Exception:
        ver = re.search(r"version:\s*(\S+)", txt)
        lock = re.search(r"locked:\s*(\w+)", txt)
        cfg = {"version": ver.group(1) if ver else "framed_answer_rubric_v1",
               "locked": (lock.group(1).lower() == "true") if lock else True}
    return cfg


def merged_kb():
    kb = EV.load_kb()
    if _KB_V2.exists():
        for k, v in json.loads(_KB_V2.read_text()).items():
            if not k.startswith("_"):
                kb[k] = v
    return kb


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return (sum(vals) / len(vals)) if vals else None


def metric(judge_out, key):
    if key == "phoneme_overreach_rate":
        return 1.0 if judge_out["phoneme_overreach"] else 0.0
    if key == "clarity_proxy":
        return judge_out["clarity_score"]
    if key == "must_include_recall":
        return judge_out["must_include_recall"]
    if key == "must_not_violation_rate":
        return judge_out["must_not_violation_rate"]
    v = judge_out.get(key)
    return (1.0 if v else 0.0) if isinstance(v, bool) else v


def aggregate(per, arm):
    out = {}
    for k in BOOL_METRICS + ("phoneme_overreach_rate", "must_include_recall",
                             "must_not_violation_rate", "clarity_proxy"):
        out[k] = _mean([metric(p["scores"][arm], k) for p in per])
    out["trace_completeness"] = _mean([p["trace_complete"] for p in per])
    return out


def stratify(per, arms, key_fn):
    groups = {}
    for p in per:
        for g in key_fn(p):
            groups.setdefault(g, []).append(p)
    rows = {}
    for g, ps in sorted(groups.items()):
        b = _mean([metric(p["scores"]["base"], "primary_frame_correct") for p in ps]) if "base" in arms else None
        f = _mean([metric(p["scores"]["framed"], "primary_frame_correct") for p in ps]) if "framed" in arms else None
        fr = _mean([metric(p["scores"]["framed"], "rejected_domain_avoidance") for p in ps]) if "framed" in arms else None
        rows[g] = {"n": len(ps), "base_primary": b, "framed_primary": f,
                   "delta_primary": (None if (b is None or f is None) else round(f - b, 3)),
                   "framed_rejected_avoid": fr}
    return rows


def lift_distribution(per):
    """Is the framed-base primary lift distributed, or does one category account for all of it?"""
    def overall(rows):
        b = _mean([metric(p["scores"]["base"], "primary_frame_correct") for p in rows])
        f = _mean([metric(p["scores"]["framed"], "primary_frame_correct") for p in rows])
        return None if (b is None or f is None) else f - b
    total = overall(per)
    cats = sorted({p["category"] for p in per})
    dominated_by = None
    for c in cats:
        rest = [p for p in per if p["category"] != c]
        d = overall(rest)
        if total is not None and total > 0 and d is not None and d <= 0:
            dominated_by = c
    pos_cats = sum(1 for c in cats
                   if (lambda r: (lambda b, f: f is not None and b is not None and f >= b)(
                       _mean([metric(p["scores"]["base"], "primary_frame_correct") for p in r]),
                       _mean([metric(p["scores"]["framed"], "primary_frame_correct") for p in r]))
                       )([p for p in per if p["category"] == c]))
    return {"overall_delta": (None if total is None else round(total, 3)),
            "dominated_by_single_category": dominated_by,
            "categories_framed_ge_base": pos_cats, "n_categories": len(cats)}


def failure_report(per):
    out = {"base_succeeds_framed_fails": [], "framed_succeeds_base_fails": [], "both_fail": [],
           "rejected_leaks": [], "secondary_promoted": [], "factuality_regressions": [],
           "phoneme_overreach": []}
    for p in per:
        b, f = p["scores"].get("base", {}), p["scores"].get("framed", {})
        bp, fp = b.get("primary_frame_correct"), f.get("primary_frame_correct")
        if bp and not fp:
            out["base_succeeds_framed_fails"].append(p["id"])
        if fp and not bp:
            out["framed_succeeds_base_fails"].append(p["id"])
        if (bp is False) and (fp is False):
            out["both_fail"].append(p["id"])
        if f.get("rejected_domain_avoidance") is False:
            out["rejected_leaks"].append(p["id"])
        if f.get("secondary_promoted"):
            out["secondary_promoted"].append(p["id"])
        if b.get("factuality_preserved") and not f.get("factuality_preserved"):
            out["factuality_regressions"].append(p["id"])
        if f.get("phoneme_overreach"):
            out["phoneme_overreach"].append(p["id"])
    return out


def decide_phase2b(base, framed, judge_backend, robust, polysemy_ok):
    bf, ff = base["factuality_preserved"], framed["factuality_preserved"]
    if bf is not None and ff is not None and ff < bf - 0.05:
        return "PHASE2B_FACTUALITY_REGRESSION"

    def ge(a, b, d=0.0):
        return a is not None and b is not None and a >= b + d

    prim_ok = ge(framed["primary_frame_correct"], base["primary_frame_correct"], 0.10) or \
        (framed["primary_frame_correct"] or 0) >= 0.80
    rej_ok = ge(framed["rejected_domain_avoidance"], base["rejected_domain_avoidance"], 0.10) or \
        (framed["rejected_domain_avoidance"] or 0) >= 0.90
    over = framed["phoneme_overreach_rate"] or 0.0
    over_ok = over <= (base["phoneme_overreach_rate"] or 1.0) and over <= 0.05
    fact_ok = ff is None or bf is None or ff >= bf - 0.05
    trace_ok = (framed.get("trace_completeness") or 0) >= 0.95
    if not (prim_ok and rej_ok and over_ok and fact_ok and trace_ok):
        return "PHASE2B_NO_ROBUST_LIFT"
    if not (robust and polysemy_ok):
        return "PHASE2B_NEEDS_HUMAN_REVIEW"
    return "PHASE2B_ROBUSTNESS_PASS" if judge_backend == "real_llm_judge" \
        else "PHASE2B_WEAK_PASS_DETERMINISTIC_ONLY"


def run_backend(backend, rows, frames, arms, judge):
    llm, llm_info = LA.load_llm_adapter(backend)
    per = []
    for ex in rows:
        trace, terms = frames[ex["id"]]
        answers, postcheck = {}, {"needed_rewrite": False}
        for arm in arms:
            try:
                ans, pci = EF.run_arm(arm, ex, trace, terms, llm)
            except Exception as exc:
                import traceback
                print(f"[error] answer backend '{llm.backend}' ({llm_info}) failed on {ex['id']}/{arm}:"
                      f" {type(exc).__name__}: {exc!r}")
                traceback.print_exc()
                return None, llm
            answers[arm] = ans
            if arm == "framed_postcheck":
                postcheck = pci
        scores = {arm: judge.score(ex["query"], answers[arm], ex, terms) for arm in arms}
        complete = 1.0 if (all(answers.get(a) for a in arms) and trace.scores) else 0.0
        per.append({"id": ex["id"], "category": ex.get("category"),
                    "answer_type": ex.get("answer_type"), "ambiguity_type": ex.get("ambiguity_type"),
                    "unknown": bool(ex.get("unknown_terms")), "answers": answers, "scores": scores,
                    "postcheck": postcheck, "trace_complete": complete})
    return (per, llm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(_DATA))
    ap.add_argument("--rubric", default=str(_RUBRIC))
    ap.add_argument("--answer-backends", default="stub")
    ap.add_argument("--judge-backend", default="deterministic", choices=["deterministic", "stub", "llm"])
    ap.add_argument("--judge-llm-backend", default="stub", help="LLM backend for --judge-backend llm")
    ap.add_argument("--semantic-backend", default="hashing",
                    choices=["hashing", "lexical", "demo", "real"])
    ap.add_argument("--arms", default="base,framed")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--explain-failures", action="store_true")
    ap.add_argument("--write-traces", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = load_data(args.data)
    if args.limit:
        rows = rows[: args.limit]
    rubric_cfg = load_rubric(args.rubric)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    answer_backends = [b.strip() for b in args.answer_backends.split(",") if b.strip()]

    judge_llm = None
    if args.judge_backend == "llm":
        judge_llm, _ = LA.load_llm_adapter(args.judge_llm_backend)
    judge, judge_info = JU.load_judge(args.judge_backend, rubric_cfg, judge_llm)

    kb = merged_kb()
    adapter, provider, sem_info = EF.build_frame_adapter(args.semantic_backend, kb)
    frames = {ex["id"]: EF.frame_for(ex, adapter, provider) for ex in rows}

    print("=" * 80)
    print(f"PHASE 2B — ROBUSTNESS VALIDATION   rubric={rubric_cfg.get('version')} "
          f"locked={rubric_cfg.get('locked')}  judge={judge.judge_backend} "
          f"(production_valid={judge.production_valid})")
    print(f"  frame={sem_info}  n={len(rows)}  arms={arms}  answer_backends={answer_backends}  "
          f"thresholds=frozen {_FROZEN.primary_match}/{_FROZEN.secondary_match}")

    report = {"meta": {"n": len(rows), "arms": arms, "rubric_version": rubric_cfg.get("version"),
                       "rubric_locked": bool(rubric_cfg.get("locked")), "rubric_pre_registered": True,
                       "judge_backend": judge.judge_backend, "judge_production_valid": judge.production_valid,
                       "semantic_frame_backend": sem_info, "answer_backends": answer_backends},
              "backends": {}, "labels": {}}
    per_by_backend = {}
    for backend in answer_backends:
        res = run_backend(backend, rows, frames, arms, judge)
        if res[0] is None:
            print(f"  [skip] backend {backend} failed.")
            continue
        per, llm = res
        per_by_backend[backend] = (per, llm)
        metrics = {arm: aggregate(per, arm) for arm in arms}
        deltas = {k: (None if (metrics["framed"][k] is None or metrics["base"][k] is None)
                      else round(metrics["framed"][k] - metrics["base"][k], 4))
                  for k in GATE_KEYS} if ("framed" in arms and "base" in arms) else {}
        ld = lift_distribution(per) if ("framed" in arms and "base" in arms) else {}
        poly = stratify(per, arms, lambda p: ["polysemy"] if p["ambiguity_type"] in
                        ("polysemy", "sense_by_context", "homonym") else [])
        poly_ok = True
        if "polysemy" in poly and poly["polysemy"]["delta_primary"] is not None:
            poly_ok = poly["polysemy"]["delta_primary"] >= -0.10
        robust = (ld.get("dominated_by_single_category") is None and
                  ld.get("categories_framed_ge_base", 0) >= max(2, (ld.get("n_categories", 0) // 2)))
        label = decide_phase2b(metrics.get("base", {}), metrics.get("framed", {}),
                               judge.judge_backend, robust, poly_ok) if "framed" in arms else "N/A"
        report["backends"][backend] = {
            "llm_backend": llm.backend, "production_valid": llm.production_valid,
            "metrics": metrics, "deltas": deltas, "lift_distribution": ld,
            "polysemy_ok": poly_ok, "robust": robust,
            "stratified": {"by_answer_type": stratify(per, arms, lambda p: [p["answer_type"]]),
                           "by_ambiguity_type": stratify(per, arms, lambda p: [p["ambiguity_type"]]),
                           "by_unknown": stratify(per, arms, lambda p: ["unknown" if p["unknown"] else "known"]),
                           "by_category": stratify(per, arms, lambda p: [p["category"]])},
            "failures": failure_report(per), "label": label}
        report["labels"][backend] = label

        # ---- print ----
        print("-" * 80)
        print(f"ANSWER BACKEND: {llm.backend} ({backend})  production_valid={llm.production_valid}")
        print("  metric".ljust(32) + "".join(a[:13].rjust(14) for a in arms) + "       Δ(f-b)")
        for k in GATE_KEYS:
            row = "  " + k.ljust(30)
            for a in arms:
                v = metrics[a].get(k)
                row += ("n/a" if v is None else f"{v:.3f}").rjust(14)
            d = deltas.get(k)
            row += ("" if d is None else f"   {d:+.3f}")
            print(row)
        tc = metrics["framed"].get("trace_completeness") if "framed" in arms else None
        print(f"  trace_completeness".ljust(32) + ("n/a" if tc is None else f"{tc:.3f}").rjust(14))
        print(f"  lift_distribution: {ld}")
        print(f"  polysemy_ok={poly_ok}  robust={robust}")
        print(f"  LABEL[{backend}]: {label}")
        if args.explain_failures:
            fr = report["backends"][backend]["failures"]
            for k in ("framed_succeeds_base_fails", "base_succeeds_framed_fails", "rejected_leaks",
                      "secondary_promoted", "factuality_regressions", "phoneme_overreach"):
                if fr[k]:
                    print(f"    {k} (n={len(fr[k])}): {fr[k][:12]}")

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        blob = dict(report)
        if args.write_traces:
            blob["traces"] = {b: [{"id": p["id"], "category": p["category"], "answers": p["answers"],
                                   "scores": p["scores"]} for p in per]
                              for b, (per, _llm) in per_by_backend.items()}
        outp.write_text(json.dumps(blob, indent=2))
        print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
