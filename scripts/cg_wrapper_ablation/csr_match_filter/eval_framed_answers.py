#!/usr/bin/env python3
"""eval_framed_answers.py — Phase 2: does C×R×S-framed answering beat base LLM answering?

Three arms, ONE model, different prompts:
  base              — the LLM answers the bare question
  framed            — answer inside the FROZEN Phase 1 C×R×S frame (primary/secondary/rejected + rules)
  framed_postcheck  — framed, then audit; one rewrite if it drifts

The frame is built by the frozen Phase 1 scorer (imported read-only; thresholds unchanged at 0.20/0.05).
Scoring is a deterministic rubric proxy (judge_backend=deterministic_rubric), NOT human evaluation.
Stub LLM => PHASE2_STUB_SMOKE_ONLY (harness validation only). No Bhava/hidden-state/logit/governance.

Usage:
  python scripts/cg_wrapper_ablation/csr_match_filter/eval_framed_answers.py \
    --llm-backend stub --semantic-backend hashing \
    --out runs/csr_phase2/framed_answer_eval.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import CSRThresholds, build_trace, dominant_terms  # noqa: E402
from csr_match_filter import answer_audit as AA         # Phase 3 audit (opt-in)  # noqa: E402
from csr_match_filter import eval_match_filter as EV   # reuse frame adapter + KB  # noqa: E402
from csr_match_filter import llm_adapter as LA          # noqa: E402
from csr_match_filter import prompts as P               # noqa: E402
from csr_match_filter import rubric as RB               # noqa: E402

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "eval_data" / "framed_answer_eval.jsonl"
_FROZEN = CSRThresholds()   # Phase 1 frozen thresholds (primary=0.20, secondary=0.05) — DO NOT change

RUBRIC_KEYS = ("primary_frame_correct", "secondary_handling_correct", "rejected_domain_avoidance",
               "phoneme_overreach_rate", "factuality_preserved", "must_include_recall",
               "must_not_violation_rate", "answer_clarity_proxy")
DELTA_KEYS = ("primary_frame_correct", "rejected_domain_avoidance", "phoneme_overreach_rate",
              "factuality_preserved", "must_include_recall")


def load_data(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def build_frame_adapter(semantic_backend, kb):
    """Frame-building semantic adapter (Phase 1). Falls back to hashing if 'real' is unavailable."""
    provider = EV.ContextualDefinitionProvider(kb)
    made = EV.make_adapter(semantic_backend, provider, {})
    if isinstance(made, tuple):
        adapter, info = made
        if adapter is None:                       # real unavailable -> hashing fallback for the frame
            provider = EV.ContextualDefinitionProvider(kb)
            adapter = EV.make_adapter("hashing", provider, {})
            return adapter, provider, f"hashing (real frame unavailable: {info})"
        return adapter, provider, info or semantic_backend
    return made, provider, semantic_backend


def frame_for(ex, adapter, provider):
    provider.context = ex.get("context")
    terms = ex.get("dominant_terms") or dominant_terms(ex["query"])
    trace = build_trace(ex["query"], terms, ex["candidate_domains"], adapter=adapter, thr=_FROZEN)
    return trace, terms


def run_arm(arm, ex, trace, terms, llm):
    """Generate one arm's answer; return (answer, postcheck_info)."""
    q, eid = ex["query"], ex["id"]
    pc = {"needed_rewrite": False, "reasons": []}
    if arm == "base":
        return llm.generate(P.build_base_prompt(q, eid)), pc
    framed = llm.generate(P.build_framed_prompt(
        q, trace.primary_domains, trace.secondary_domains, trace.rejected_domains, eid))
    if arm == "framed":
        return framed, pc
    # framed_postcheck
    needed, reasons = P.postcheck_answer(framed, trace.primary_domains, trace.secondary_domains,
                                         trace.rejected_domains)
    pc = {"needed_rewrite": needed, "reasons": reasons}
    if not needed:
        return framed, pc
    rewritten = llm.generate(P.build_rewrite_prompt(
        framed, q, trace.primary_domains, trace.secondary_domains, trace.rejected_domains,
        reasons, eid))
    return rewritten, pc


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return (sum(vals) / len(vals)) if vals else None


def aggregate(per, arm):
    out = {}
    for k in RUBRIC_KEYS:
        out[k] = _mean([p["scores"][arm].get(k) for p in per])
    out["postcheck_rewrite_rate"] = _mean([1.0 if p["postcheck"]["needed_rewrite"] else 0.0
                                           for p in per]) if arm == "framed_postcheck" else None
    return out


def audit_arm(ex, trace, answer, llm, rewrite_mode):
    """Phase 3 (opt-in): audit one arm's answer vs the frozen frame. Returns a serialisable dict.

    rewrite_mode: off (no prompt) | suggest (attach a rewrite prompt, do NOT call the model) |
    auto (build the prompt AND perform one rewrite). Never changes the original arm's score.
    """
    res = AA.audit_answer(ex["query"], answer, trace,
                          alternate_true_senses=ex.get("alternate_true_senses"),
                          false_claims=ex.get("false_claims"), answer_id=ex["id"])
    rec = res.to_dict()
    rec["critical"] = any(f["severity"] == "critical" for f in rec["findings"])
    if rewrite_mode != "off" and res.needs_rewrite:
        prompt = AA.build_rewrite_prompt(ex["query"], answer, trace, res)
        rec["rewrite_prompt"] = prompt
        if rewrite_mode == "auto":
            rec["rewritten_answer"] = llm.generate(prompt)
    return rec


def aggregate_audit(per, arm):
    audits = [p["audit"][arm] for p in per if "audit" in p and arm in p["audit"]]
    if not audits:
        return None
    n = len(audits)
    return {"audit_pass_rate": sum(a["passed"] for a in audits) / n,
            "rewrite_recommended_rate": sum(a["needs_rewrite"] for a in audits) / n,
            "critical_findings_rate": sum(a["critical"] for a in audits) / n}


def _delta(a, b):
    return None if (a is None or b is None) else round(a - b, 4)


def decide_label(llm_backend, m):
    # any real generator (API or local HF) gets a behavioral verdict; stub/fallback = smoke only
    if llm_backend not in ("real", "local_hf"):
        return "PHASE2_STUB_SMOKE_ONLY"
    base, framed = m.get("base", {}), m.get("framed", {})
    bf, ff = base.get("factuality_preserved"), framed.get("factuality_preserved")
    if bf is not None and ff is not None and ff < bf - 0.05:
        return "PHASE2_FACTUALITY_REGRESSION"

    def improved(key, lo):
        a, b = framed.get(key), base.get(key)
        return a is not None and b is not None and (a >= b + 0.10 or a >= lo)
    rej_ok = improved("rejected_domain_avoidance", 0.90)
    prim_ok = improved("primary_frame_correct", 0.75)
    over = framed.get("phoneme_overreach_rate")
    over_ok = over is not None and over <= (base.get("phoneme_overreach_rate") or 1.0) and over <= 0.05
    return "PHASE2_FRAMED_ANSWER_PASS" if (rej_ok and prim_ok and over_ok) else "PHASE2_NO_BEHAVIORAL_LIFT"


def summarize(per, arms, meta, explain, out, write_traces):
    metrics = {arm: aggregate(per, arm) for arm in arms}
    metrics_tc = _mean([p.get("trace_complete", 1.0) for p in per])
    deltas = {}
    if "framed" in arms and "base" in arms:
        deltas["framed_minus_base"] = {k: _delta(metrics["framed"][k], metrics["base"][k])
                                       for k in DELTA_KEYS}
    if "framed_postcheck" in arms and "base" in arms:
        deltas["framed_postcheck_minus_base"] = {
            k: _delta(metrics["framed_postcheck"][k], metrics["base"][k]) for k in DELTA_KEYS}
    if "framed_postcheck" in arms and "framed" in arms:
        deltas["framed_postcheck_minus_framed"] = {
            k: _delta(metrics["framed_postcheck"][k], metrics["framed"][k]) for k in DELTA_KEYS}
    label = decide_label(meta["llm_backend"], metrics)
    audit_metrics = {arm: aggregate_audit(per, arm) for arm in arms} if any("audit" in p for p in per) else None
    report = {"meta": {"n": len(per), "arms": arms, **meta, "judge_backend": "deterministic_rubric",
                       "frozen_thresholds": {"primary": _FROZEN.primary_match,
                                             "secondary": _FROZEN.secondary_match}},
              "metrics": metrics, "trace_completeness": metrics_tc, "deltas": deltas, "label": label}
    if audit_metrics:
        report["audit_metrics"] = audit_metrics

    print("=" * 74)
    print(f"PHASE 2 — FRAMED-ANSWER EVAL   llm_backend={meta['llm_backend']} "
          f"(production_valid={meta['production_valid']})  judge=deterministic_rubric")
    print(f"  frame backend={meta['semantic_frame_backend']}  n={len(per)}  arms={arms}  "
          f"thresholds=frozen {_FROZEN.primary_match}/{_FROZEN.secondary_match}")
    print("-" * 74)
    print("  metric".ljust(32) + "".join(a[:14].rjust(16) for a in arms))
    for k in RUBRIC_KEYS + ("postcheck_rewrite_rate",):
        row = "  " + k.ljust(30)
        for a in arms:
            v = metrics[a].get(k)
            row += ("n/a" if v is None else f"{v:.3f}").rjust(16)
        print(row)
    print(f"  {'trace_completeness'.ljust(30)}" + f"{metrics_tc:.3f}".rjust(16 * len(arms)))
    print("-" * 74)
    print("DELTAS (positive = framing helps; phoneme_overreach/must_not lower is better)")
    for name, d in deltas.items():
        print(f"  {name}: " + "  ".join(f"{k}={'n/a' if v is None else f'{v:+.3f}'}"
                                        for k, v in d.items()))
    if audit_metrics:
        print("-" * 74)
        print("PHASE 3 ANSWER AUDIT (opt-in; does not affect the Phase 2 scores above)")
        for k in ("audit_pass_rate", "rewrite_recommended_rate", "critical_findings_rate"):
            row = "  " + k.ljust(30)
            for a in arms:
                v = (audit_metrics.get(a) or {}).get(k)
                row += ("n/a" if v is None else f"{v:.3f}").rjust(16)
            print(row)
    print("-" * 74)
    print(f"LABEL: {label}")
    if label == "PHASE2_STUB_SMOKE_ONLY":
        print("  NOTE: stub LLM — validates harness/scoring/deltas, NOT real behavioral lift.")
    if explain:
        print("=" * 74 + "\nFAILURE EXPLAINER (framed arm)")
        for p in per:
            s = p["scores"].get("framed", {})
            probs = []
            if s.get("primary_frame_correct") == 0.0:
                probs.append("primary-miss")
            if s.get("rejected_domain_avoidance") == 0.0:
                probs.append(f"rejected:{s.get('_mentioned_rejected')}")
            if s.get("phoneme_overreach_rate"):
                probs.append("overreach")
            if (s.get("must_not_violation_rate") or 0) > 0:
                probs.append("must-not")
            if probs:
                print(f"  {p['id']:28} {probs}")
    if out:
        outp = Path(out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        blob = dict(report)
        if write_traces:
            blob["traces"] = per
        outp.write_text(json.dumps(blob, indent=2))
        print(f"\nwrote {outp}")
    return report


def rescore(traces_path, rows, explain, out):
    """Re-score saved answers with the CURRENT rubric — no LLM/frame re-run."""
    saved = json.loads(Path(traces_path).read_text())
    traces = saved.get("traces") or []
    if not traces:
        print(f"[error] {traces_path} has no traces (run the eval with --write-traces).")
        return 2
    by_id = {ex["id"]: ex for ex in rows}
    meta = saved.get("meta", {})
    arms = meta.get("arms", ["base", "framed", "framed_postcheck"])
    per = []
    for tr in traces:
        ex = by_id.get(tr["id"])
        if not ex:
            continue
        terms = ex.get("dominant_terms") or []
        per.append({"id": tr["id"], "category": ex.get("category"), "answers": tr["answers"],
                    "scores": {a: RB.score_answer(tr["answers"].get(a, ""), ex, terms) for a in arms},
                    "postcheck": tr.get("postcheck", {"needed_rewrite": False}),
                    "trace_complete": tr.get("trace_complete", 1.0)})
    print(f"[rescored {len(per)} examples from {traces_path} with the current rubric]")
    summarize(per, arms, {"llm_backend": meta.get("llm_backend", "stub"),
                          "llm_info": meta.get("llm_info", ""),
                          "production_valid": meta.get("production_valid", False),
                          "semantic_frame_backend": meta.get("semantic_frame_backend", "")},
              explain, out, write_traces=False)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(_DATA))
    ap.add_argument("--kb", default=str(EV._KB))
    ap.add_argument("--llm-backend", default="stub",
                    choices=["stub", "real", "local", "mistral", "hf"])
    ap.add_argument("--semantic-backend", default="hashing",
                    choices=["hashing", "lexical", "demo", "real"])
    ap.add_argument("--arms", default="base,framed,framed_postcheck")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--explain-failures", action="store_true")
    ap.add_argument("--write-traces", action="store_true")
    ap.add_argument("--audit-answers", action="store_true",
                    help="Phase 3: audit each arm's answer vs the frozen frame (default off)")
    ap.add_argument("--rewrite-mode", default="off", choices=["off", "suggest", "auto"],
                    help="Phase 3 rewrite policy (default off; 'auto' performs one rewrite)")
    ap.add_argument("--rescore", default=None,
                    help="re-score a saved --write-traces JSON with the current rubric (no LLM re-run)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = load_data(args.data)
    if args.rescore:
        return rescore(args.rescore, rows, args.explain_failures, args.out)
    if args.limit:
        rows = rows[: args.limit]
    kb = EV.load_kb(args.kb)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    llm, llm_info = LA.load_llm_adapter(args.llm_backend)
    adapter, provider, sem_info = build_frame_adapter(args.semantic_backend, kb)

    per, audit = [], {}
    for ex in rows:
        trace, terms = frame_for(ex, adapter, provider)
        answers, scores, pc = {}, {}, {"needed_rewrite": False, "reasons": []}
        for arm in arms:
            try:
                ans, pci = run_arm(arm, ex, trace, terms, llm)
            except Exception as exc:   # LLM backend failure (bad key, model API, OOM, network)
                import traceback
                print(f"[error] LLM backend '{llm.backend}' ({llm_info}) failed on {ex['id']}/{arm}: "
                      f"{type(exc).__name__}: {exc!r}")
                traceback.print_exc()
                print("  -> fix the backend (credentials/model), or use --llm-backend stub. "
                      "No partial report written.")
                return 2
            answers[arm] = ans
            scores[arm] = RB.score_answer(ans, ex, terms)
            if arm == "framed_postcheck":
                pc = pci
            if args.audit_answers:
                audit.setdefault(ex["id"], {})[arm] = audit_arm(ex, trace, ans, llm, args.rewrite_mode)
        complete = (all(a in answers and answers[a] for a in arms)
                    and bool(trace.scores) is not None)
        rec = {"id": ex["id"], "category": ex.get("category"), "query": ex["query"],
               "csr_trace": {"primary_domains": trace.primary_domains,
                             "secondary_domains": trace.secondary_domains,
                             "rejected_domains": trace.rejected_domains,
                             "scores": [s.domain + ":" + str(s.match) for s in trace.scores]},
               "answers": answers, "scores": scores, "postcheck": pc,
               "trace_complete": 1.0 if complete else 0.0}
        if args.audit_answers:
            rec["audit"] = audit[ex["id"]]
        per.append(rec)

    summarize(per, arms, {"llm_backend": llm.backend, "llm_info": llm_info,
                          "production_valid": llm.production_valid, "semantic_frame_backend": sem_info},
              args.explain_failures, args.out, args.write_traces)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
