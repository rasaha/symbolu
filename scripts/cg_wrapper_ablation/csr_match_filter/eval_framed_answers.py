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


def _delta(a, b):
    return None if (a is None or b is None) else round(a - b, 4)


def decide_label(llm_backend, m):
    if llm_backend != "real":
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(_DATA))
    ap.add_argument("--kb", default=str(EV._KB))
    ap.add_argument("--llm-backend", default="stub", choices=["stub", "real"])
    ap.add_argument("--semantic-backend", default="hashing",
                    choices=["hashing", "lexical", "demo", "real"])
    ap.add_argument("--arms", default="base,framed,framed_postcheck")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--explain-failures", action="store_true")
    ap.add_argument("--write-traces", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = load_data(args.data)
    if args.limit:
        rows = rows[: args.limit]
    kb = EV.load_kb(args.kb)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    llm, llm_info = LA.load_llm_adapter(args.llm_backend)
    adapter, provider, sem_info = build_frame_adapter(args.semantic_backend, kb)

    per = []
    for ex in rows:
        trace, terms = frame_for(ex, adapter, provider)
        answers, scores, pc = {}, {}, {"needed_rewrite": False, "reasons": []}
        for arm in arms:
            ans, pci = run_arm(arm, ex, trace, terms, llm)
            answers[arm] = ans
            scores[arm] = RB.score_answer(ans, ex, terms)
            if arm == "framed_postcheck":
                pc = pci
        complete = (all(a in answers and answers[a] for a in arms)
                    and bool(trace.scores) is not None)
        per.append({"id": ex["id"], "category": ex.get("category"), "query": ex["query"],
                    "csr_trace": {"primary_domains": trace.primary_domains,
                                  "secondary_domains": trace.secondary_domains,
                                  "rejected_domains": trace.rejected_domains,
                                  "scores": [s.domain + ":" + str(s.match) for s in trace.scores]},
                    "answers": answers, "scores": scores, "postcheck": pc,
                    "trace_complete": 1.0 if complete else 0.0})

    metrics = {arm: aggregate(per, arm) for arm in arms}
    metrics_tc = _mean([p["trace_complete"] for p in per])
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

    label = decide_label(args.llm_backend, metrics)
    report = {"meta": {"n": len(per), "arms": arms, "llm_backend": llm.backend,
                       "llm_info": llm_info, "production_valid": llm.production_valid,
                       "judge_backend": "deterministic_rubric", "semantic_frame_backend": sem_info,
                       "frozen_thresholds": {"primary": _FROZEN.primary_match,
                                             "secondary": _FROZEN.secondary_match}},
              "metrics": metrics, "trace_completeness": metrics_tc, "deltas": deltas, "label": label}

    # ---- report ----
    print("=" * 74)
    print(f"PHASE 2 — FRAMED-ANSWER EVAL   llm_backend={llm.backend} "
          f"(production_valid={llm.production_valid})  judge=deterministic_rubric")
    print(f"  frame backend={sem_info}  n={len(per)}  arms={arms}  thresholds=frozen "
          f"{_FROZEN.primary_match}/{_FROZEN.secondary_match}")
    print("-" * 74)
    hdr = "  metric".ljust(32) + "".join(a[:14].rjust(16) for a in arms)
    print(hdr)
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
    print("-" * 74)
    print(f"LABEL: {label}")
    if label == "PHASE2_STUB_SMOKE_ONLY":
        print("  NOTE: stub LLM — validates harness/scoring/deltas, NOT real behavioral lift.")

    if args.explain_failures:
        print("=" * 74)
        print("FAILURE EXPLAINER (framed arm)")
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

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        blob = dict(report)
        if args.write_traces:
            blob["traces"] = per
        outp.write_text(json.dumps(blob, indent=2))
        print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
