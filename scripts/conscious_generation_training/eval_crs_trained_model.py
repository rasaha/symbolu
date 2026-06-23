#!/usr/bin/env python3
"""T1 four-arm evaluation. Pre-reg: docs/CG_TRAINING_CRS_MISTRAL_PREREG.md.

MANDATORY four arms (the key question is value BEYOND the validated wrapper B, not just C>A):
  A: base Mistral, plain prompt            B: base Mistral + C×R×S wrapper (framed prompt)  [validated baseline]
  C: crs-lora Mistral, plain prompt        D: crs-lora Mistral + C×R×S wrapper (framed prompt)

Scoring reuses the SAME validated deterministic rubric (`rubric.score_answer_v2`) and the SAME prompt
builders as the validated eval — no new judge, no model-as-judge. CPU-SAFE: `--dry-run` emits the config/
skeleton; real generation needs a GPU + cu121 stack + peft. Decision uses ONLY the pre-registered labels.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ARMS = {
    "A": {"model": "base", "wrapper": False},
    "B": {"model": "base", "wrapper": True},
    "C": {"model": "crs_lora", "wrapper": False},
    "D": {"model": "crs_lora", "wrapper": True},
}
METRICS = ("primary_frame_correct", "rejected_domain_avoidance", "secondary_overpromotion_rate",
           "rejected_domain_leak_rate", "factuality_preserved", "clarity_usefulness",
           "must_include_recall", "answer_length", "generalization_to_unseen_terms",
           "generalization_to_unseen_domains")
SLICES = ("high_conf_primary", "ambiguous", "rejected_trap", "unseen_term", "domain_conflict",
          "negative_control", "per_domain")
DECISIONS = ("CG_TRAINING_CRS_ADDS_VALUE", "CG_TRAINING_CRS_NO_INCREMENTAL_VALUE",
             "CG_TRAINING_WRAPPER_STILL_BEST", "CG_TRAINING_DEGRADES_FACTUALITY",
             "CG_TRAINING_OVERFITS_FRAMES", "CG_TRAINING_INSUFFICIENT_DATA",
             "CG_TRAINING_ENV_UNAVAILABLE")


# ---- aggregation (pure; CPU-testable) ------------------------------------------------------------
def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def _pd_list(pe):
    """primary_domain may be a str or list; normalize to a list (avoids `list in set` TypeError)."""
    pd = pe.get("primary_domain")
    return pd if isinstance(pd, list) else ([pd] if pd else [])


def aggregate(per_example: list, unseen_domains=None) -> dict:
    """per_example: [{"slice": str, "primary_domain": str|list, "scores": {arm: rubric_v2_dict},
                      "answer_len": {arm: int}}]. Returns {arm: {metric: value}} for the §11 gate."""
    unseen_domains = set(unseen_domains or [])
    out = {}
    for arm in ARMS:
        rows = [pe for pe in per_example if arm in pe.get("scores", {})]
        sc = [pe["scores"][arm] for pe in rows]
        rda = _mean([r["rejected_domain_avoidance"] for r in sc])
        unseen_t = [pe["scores"][arm]["primary_frame_correct"]
                    for pe in rows if pe.get("slice") == "unseen_term"]
        unseen_d = [pe["scores"][arm]["primary_frame_correct"] for pe in rows
                    if any(d in unseen_domains for d in _pd_list(pe))]
        pf = _mean([r["primary_frame_correct"] for r in sc])
        out[arm] = {
            "primary_frame_correct": pf,
            "rejected_domain_avoidance": rda,
            "secondary_overpromotion_rate": _mean([r["rejected_domain_promotion"] for r in sc]),
            "rejected_domain_leak_rate": round(1.0 - rda, 4),
            "factuality_preserved": _mean([r["factuality_preserved"] for r in sc]),
            "clarity_usefulness": _mean([r["answer_clarity_proxy"] for r in sc]),
            "must_include_recall": _mean([r["must_include_recall"] for r in sc]),
            "answer_length": _mean([pe.get("answer_len", {}).get(arm) for pe in rows]),
            "generalization_to_unseen_terms": _mean(unseen_t) if unseen_t else pf,
            "generalization_to_unseen_domains": _mean(unseen_d) if unseen_d else pf,
            "n": len(rows),
        }
    return out


def bootstrap_delta(per_example, metric, arm_a, arm_b, n_boot=2000, seed=0):
    """Bootstrap CI of mean(metric[arm_a]) − mean(metric[arm_b]) over examples."""
    key = {"primary_frame_correct": "primary_frame_correct",
           "rejected_domain_avoidance": "rejected_domain_avoidance"}[metric]
    rows = [pe for pe in per_example if arm_a in pe["scores"] and arm_b in pe["scores"]]
    if not rows:
        return {"delta": 0.0, "ci_low": 0.0, "ci_high": 0.0, "excludes_zero": False}
    rng = random.Random(seed)
    a = [pe["scores"][arm_a][key] for pe in rows]
    b = [pe["scores"][arm_b][key] for pe in rows]
    n = len(rows)
    deltas = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append(sum(a[i] for i in idx) / n - sum(b[i] for i in idx) / n)
    deltas.sort()
    lo, hi = deltas[int(0.025 * n_boot)], deltas[int(0.975 * n_boot)]
    return {"delta": round(sum(a) / n - sum(b) / n, 4), "ci_low": round(lo, 4),
            "ci_high": round(hi, 4), "excludes_zero": bool(lo > 0.0)}


# ---- decision gate (pre-reg §11; pre-registered labels only) -------------------------------------
def decide(arm_metrics: dict, *, factuality_tol=0.02) -> tuple:
    A, B, C, D = (arm_metrics.get(k) for k in ("A", "B", "C", "D"))
    if not all((A, B, C, D)):
        return "CG_TRAINING_INSUFFICIENT_DATA", {"reason": "missing arm metrics"}
    r = {}
    c_beats_a = (C["primary_frame_correct"] > A["primary_frame_correct"]
                 and C["rejected_domain_avoidance"] > A["rejected_domain_avoidance"])
    r["c_beats_a"] = c_beats_a
    if C["factuality_preserved"] < A["factuality_preserved"] - factuality_tol \
            or C["clarity_usefulness"] < A["clarity_usefulness"] - factuality_tol:
        return "CG_TRAINING_DEGRADES_FACTUALITY", r
    generalizes = (C.get("generalization_to_unseen_terms", 0) > A.get("generalization_to_unseen_terms", 0)
                   and C.get("generalization_to_unseen_domains", 0) >= A.get("generalization_to_unseen_domains", 0))
    r["generalizes"] = generalizes
    if c_beats_a and not generalizes:
        return "CG_TRAINING_OVERFITS_FRAMES", r
    approaches_or_beats_b = any(C.get(m, 0) >= B.get(m, 0) for m in
                                ("primary_frame_correct", "rejected_domain_avoidance"))
    d_not_worse_than_b = (D["primary_frame_correct"] >= B["primary_frame_correct"] - factuality_tol
                          and D["rejected_domain_avoidance"] >= B["rejected_domain_avoidance"] - factuality_tol)
    r.update(approaches_or_beats_b=approaches_or_beats_b, d_not_worse_than_b=d_not_worse_than_b)
    if c_beats_a and generalizes and approaches_or_beats_b and d_not_worse_than_b:
        return "CG_TRAINING_CRS_ADDS_VALUE", r
    if B["primary_frame_correct"] >= max(C["primary_frame_correct"], D["primary_frame_correct"]):
        return "CG_TRAINING_WRAPPER_STILL_BEST", r
    return "CG_TRAINING_CRS_NO_INCREMENTAL_VALUE", r


def to_markdown(rep) -> str:
    if rep.get("decision") in ("CG_TRAINING_ENV_UNAVAILABLE", "dry_run"):
        return ("# Four-arm C×R×S-LoRA evaluation (T1) — DRY-RUN / ENV_UNAVAILABLE\n\n"
                f"- decision: {rep.get('decision')}\n- {rep.get('note', '')}\n")
    m = rep["arm_metrics"]
    L = ["# Four-arm C×R×S-LoRA evaluation (T1)", "",
         f"- n_test: **{rep['n_test']}**  ·  **DECISION: `{rep['decision']}`**",
         "- A=base · B=base+wrapper · C=LoRA · D=LoRA+wrapper", "",
         "| metric | A | B | C | D |", "|---|---|---|---|---|"]
    for k in ("primary_frame_correct", "rejected_domain_avoidance", "factuality_preserved",
              "clarity_usefulness", "secondary_overpromotion_rate", "must_include_recall",
              "generalization_to_unseen_terms"):
        L.append(f"| {k} | {m['A'][k]} | {m['B'][k]} | {m['C'][k]} | {m['D'][k]} |")
    L += ["", f"- ΔPFC C−B: `{rep['deltas'].get('C_minus_B_pfc')}`  ·  ΔPFC C−A: `{rep['deltas'].get('C_minus_A_pfc')}`",
          f"- reasons: `{rep['decision_reasons']}`", "",
          "> Self-distillation: targets are the wrapper's own audit-passing answers, so C cannot exceed",
          "> its teacher. T1 tests weight-internalization + generalization, not superiority over the wrapper."]
    return "\n".join(L) + "\n"


def gpu_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:                                     # noqa: BLE001
        return False


# ---- GPU generation path (pod only) --------------------------------------------------------------
def _generate_and_score(test_path, eval_data_path, base_model, lora_dir, seed=0, max_new=200,
                        dtype="bf16"):
    import sys
    _CSR = Path(__file__).resolve().parent.parent / "cg_wrapper_ablation"
    if str(_CSR) not in sys.path:
        sys.path.insert(0, str(_CSR))
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    from csr_match_filter import rubric as RB
    from csr_match_filter import prompts as P
    from csr_match_filter import eval_framed_answers as EF
    from csr_match_filter import eval_match_filter as EV

    by_id = {r["id"]: r for r in
             (json.loads(l) for l in Path(eval_data_path).read_text().splitlines() if l.strip())}
    test = [json.loads(l) for l in Path(test_path).read_text().splitlines() if l.strip()]
    kb = EV.load_kb(str(EV._KB))
    adapter, provider, sem = EF.build_frame_adapter("real", kb)

    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    # eval is NOT memory-bound on an 80GB card: bf16 is faster per-token than 4-bit. Use 4bit only to fit.
    if dtype == "4bit":
        base = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto", load_in_4bit=True)
    else:
        base = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto",
                                                    torch_dtype=torch.bfloat16)

    def gen(model, prompt):
        inp = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inp, max_new_tokens=max_new, do_sample=False,
                                  pad_token_id=tok.pad_token_id)
        return tok.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    def framed_prompt(ex):
        trace, terms = EF.frame_for(ex, adapter, provider)
        return P.build_framed_prompt(ex["query"], trace.primary_domains, trace.secondary_domains,
                                     trace.rejected_domains)

    per = []
    # base-model arms A/B first (before attaching LoRA)
    cache = []
    for t in test:
        ex = by_id[t["id"]]
        base_p, fr_p = P.build_base_prompt(ex["query"], ex["id"]), framed_prompt(ex)
        a_ans, b_ans = gen(base, base_p), gen(base, fr_p)
        cache.append((t, ex, base_p, fr_p, a_ans, b_ans))
    lora = PeftModel.from_pretrained(base, lora_dir)       # now adapter-active
    for (t, ex, base_p, fr_p, a_ans, b_ans) in cache:
        c_ans, d_ans = gen(lora, base_p), gen(lora, fr_p)
        terms = ex.get("dominant_terms") or None
        sc = {arm: RB.score_answer_v2(ans, ex, terms)
              for arm, ans in (("A", a_ans), ("B", b_ans), ("C", c_ans), ("D", d_ans))}
        per.append({"id": t["id"], "slice": t.get("slice", "high_conf_primary"),
                    "primary_domain": t.get("primary_domain"), "scores": sc,
                    "answer_len": {"A": len(a_ans.split()), "B": len(b_ans.split()),
                                   "C": len(c_ans.split()), "D": len(d_ans.split())}})
    return per, sem


def main(argv=None):
    ap = argparse.ArgumentParser(description="Four-arm C×R×S-LoRA evaluation (T1).")
    ap.add_argument("--data-dir", default="runs/cg_training/crs_sft")
    ap.add_argument("--eval-data", default="scripts/cg_wrapper_ablation/csr_match_filter/eval_data/"
                    "framed_answer_eval_v2_rubricv2.jsonl")
    ap.add_argument("--lora", default="runs/cg_training/crs_lora")
    ap.add_argument("--base-model", default="mistralai/Mistral-7B-Instruct-v0.3")
    ap.add_argument("--out", default="runs/cg_training/crs_eval/four_arm_eval.json")
    ap.add_argument("--report", default="runs/cg_training/crs_eval/four_arm_eval.md")
    ap.add_argument("--execute", action="store_true", help="run real generation (needs GPU + peft)")
    ap.add_argument("--dtype", choices=("bf16", "4bit"), default="bf16",
                    help="bf16 (faster, ~15GB; default for eval) or 4bit (slower, ~5GB)")
    ap.add_argument("--max-new-tokens", type=int, default=200)
    ap.add_argument("--from-cache", default=None,
                    help="re-score/decide from a saved per_example cache (skips GPU generation)")
    args = ap.parse_args(argv)

    test = Path(args.data_dir) / "test.jsonl"
    n_test = sum(1 for l in test.read_text().splitlines() if l.strip()) if test.exists() else 0
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    cache_path = Path(args.out).parent / "per_example_cache.json"
    if args.from_cache:                                   # re-aggregate from saved generations (no GPU)
        blob = json.loads(Path(args.from_cache).read_text())
        per, sem = blob["per_example"], blob.get("semantic_backend", "from_cache")
    elif not args.execute or not gpu_available():
        rep = {"arms": ARMS, "metrics": list(METRICS), "decision_labels": list(DECISIONS),
               "n_test": n_test, "decision": "CG_TRAINING_ENV_UNAVAILABLE" if not gpu_available() else "dry_run",
               "note": "DRY-RUN: four-arm config + §11 gate wired; real generation needs a GPU pod."}
        Path(args.out).write_text(json.dumps(rep, indent=2))
        Path(args.report).write_text(to_markdown(rep))
        print(f"DECISION: {rep['decision']} (dry-run; wrote {args.out})")
        return 0
    else:
        if n_test < 4:
            print("CG_TRAINING_INSUFFICIENT_DATA"); return 1
        per, sem = _generate_and_score(test, args.eval_data, args.base_model, args.lora,
                                       max_new=args.max_new_tokens, dtype=args.dtype)
        # persist the expensive GPU output IMMEDIATELY so a downstream error never wastes it
        cache_path.write_text(json.dumps({"per_example": per, "semantic_backend": sem}, indent=2))
        print(f"[cached generations -> {cache_path}]")
    holdout = {}
    meta = Path(args.data_dir) / "meta.json"
    if meta.exists():
        holdout = json.loads(meta.read_text()).get("holdout", {})
    arm_metrics = aggregate(per, unseen_domains=holdout.get("unseen_domains"))
    decision, reasons = decide(arm_metrics)
    deltas = {
        "C_minus_B_pfc": bootstrap_delta(per, "primary_frame_correct", "C", "B"),
        "C_minus_A_pfc": bootstrap_delta(per, "primary_frame_correct", "C", "A"),
        "C_minus_A_rda": bootstrap_delta(per, "rejected_domain_avoidance", "C", "A"),
    }
    rep = {"n_test": len(per), "semantic_backend": sem, "arm_metrics": arm_metrics,
           "deltas": deltas, "decision": decision, "decision_reasons": reasons,
           "per_example": per}
    Path(args.out).write_text(json.dumps(rep, indent=2))
    Path(args.report).write_text(to_markdown(rep))
    print(f"n_test={len(per)} DECISION: {decision}")
    print(f"wrote {args.out} + {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
