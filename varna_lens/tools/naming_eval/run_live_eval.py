#!/usr/bin/env python3
"""Live naming evaluation with real LLMs (Mistral / Qwen / OpenAI-compatible / Anthropic).

Runs the full outcome pipeline the deterministic harness could not: per-arm name GENERATION, blinded
multi-model JUDGING, per-arm quality, paired B−A / B−C / B−D effect sizes + CIs, cross-judge
disagreement, deterministic constraint satisfaction on the real names, optional explanation-honesty, and
token cost. Never fabricates — if no provider is configured it prints setup instructions and exits.

Setup (any one provider is enough; two+ judges recommended):
  export MISTRAL_API_KEY=...            # gen/judge with  mistral:mistral-large-latest
  export DASHSCOPE_API_KEY=...          # gen/judge with  qwen:qwen-max   (DashScope intl, OpenAI-compat)
  export LLM_BASE_URL=... LLM_API_KEY=...# any OpenAI-compatible endpoint via  compat:<model>

Examples:
  python run_live_eval.py --gen-model qwen:qwen-max --judge-models mistral:mistral-large-latest,qwen:qwen-max
  python run_live_eval.py --limit 6 --explanations           # small, cheaper smoke run
  python run_live_eval.py                                     # auto-pick configured providers
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent.parent
sys.path.insert(0, str(_HERE))
import corpus as C            # noqa: E402
import arms as A              # noqa: E402
import judge as J             # noqa: E402
import llm_client as L        # noqa: E402

RUBRIC = J.JUDGE_RUBRIC       # memorability, pronounceability, distinctiveness, professionalism, verbal_identity, fit_to_brief
CLAIM_PHRASES = ["this proves", "this reveals", "means the customer", "reveals the customer",
                 "proves that", "the name means", "decodes", "reveals that you", "this shows you are"]


# ---- robust helpers -------------------------------------------------------------------------------
def _names_from(text):
    out = []
    for ln in (text or "").splitlines():
        ln = ln.strip().lstrip("0123456789.)-•* \t").strip()
        if ln and len(ln) <= 40 and not ln.lower().startswith(("here", "sure", "option", "name")):
            out.append(ln.split(" — ")[0].split(":")[0].strip())
    return [n for n in out if n][:8]


def _first_json(text):
    depth = 0; start = None
    for i, ch in enumerate(text or ""):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:  # noqa: BLE001
                    start = None
    return {}


def _mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def _cohen_d_paired(diffs):
    if len(diffs) < 2:
        return float("nan")
    sd = statistics.pstdev(diffs)
    return (statistics.mean(diffs) / sd) if sd else float("inf") if statistics.mean(diffs) else 0.0


def _ci95(xs):
    if len(xs) < 2:
        return [None, None]
    m = statistics.mean(xs); h = 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)
    return [round(m - h, 3), round(m + h, 3)]


# ---- pipeline -------------------------------------------------------------------------------------
def judge_prompt(brief, labelled):
    return ("You are a branding expert. Score each naming OPTION from 1 (poor) to 5 (excellent) on: "
            + ", ".join(RUBRIC) + ".\nYou are blind to how each option was produced. Return ONLY JSON: "
            '{"opt_1": {"memorability": n, ...}, ...}.\n\n'
            f"BRIEF: {brief}\nOPTIONS:\n" + "\n".join(f"{lbl}: {name}" for lbl, name in labelled))


def check_constraints(name, cons):
    ok, checks = True, {}
    if "length" in cons and isinstance(cons["length"], str) and cons["length"].startswith("<="):
        lim = int(cons["length"][2:]); checks["length"] = len(name) <= lim; ok &= checks["length"]
    if cons.get("required_suffix"):
        checks["suffix"] = name.lower().endswith(cons["required_suffix"].lower()); ok &= checks["suffix"]
    if cons.get("required_prefix"):
        checks["prefix"] = name.lower().startswith(cons["required_prefix"].lower()); ok &= checks["prefix"]
    return ok, checks


def run(gen_model, judge_models, items, explanations, temperature):
    per_item = []
    for it in items:
        arms, c_src = A.all_arms(it, C.CORPUS)
        gen, usage = {}, {}
        for a, prompt in arms.items():
            text, u = L.chat(gen_model, prompt, temperature=temperature, max_tokens=400)
            gen[a] = _names_from(text); usage[a] = u
        # blind pool of ALL candidates across arms
        pool = [(a, n) for a in arms for n in gen[a]]
        order = sorted(range(len(pool)),
                       key=lambda i: __import__("hashlib").sha256((it["id"] + pool[i][1]).encode()).hexdigest())
        labelled = [(f"opt_{k+1}", pool[order[k]][1]) for k in range(len(pool))]
        lbl2arm = {f"opt_{k+1}": pool[order[k]][0] for k in range(len(pool))}
        # judge with each model
        judge_scores = {}
        for jm in judge_models:
            txt, _ = L.chat(jm, judge_prompt(it["brief"], labelled), temperature=0.0, max_tokens=1200)
            parsed = _first_json(txt)
            arm_q = {a: [] for a in arms}
            for lbl, scores in parsed.items():
                if lbl in lbl2arm and isinstance(scores, dict):
                    vals = [float(scores[m]) for m in RUBRIC if m in scores and isinstance(scores[m], (int, float))]
                    if vals:
                        arm_q[lbl2arm[lbl]].append(_mean(vals))
            judge_scores[jm] = {a: (_mean(v) if v else None) for a, v in arm_q.items()}
        # constraint satisfaction on real names
        cons_rate = {a: (sum(check_constraints(n, it["constraints"])[0] for n in gen[a]) / len(gen[a]))
                     if gen[a] else None for a in arms}
        rec = {"id": it["id"], "category": it["category"], "c_random_source": c_src,
               "n_candidates": {a: len(gen[a]) for a in arms}, "usage": usage,
               "judge_scores": judge_scores, "constraint_satisfaction": cons_rate, "gen": gen}
        if explanations:
            hon = {}
            for a, prompt in arms.items():
                ex, _ = L.chat(gen_model, prompt + "\n\nAlso add ONE sentence explaining your top pick.",
                               temperature=temperature, max_tokens=450)
                low = (ex or "").lower()
                hon[a] = sum(low.count(p) for p in CLAIM_PHRASES)
            rec["explanation_decode_claims"] = hon
        per_item.append(rec)
    return per_item


def aggregate(per_item, judge_models, arms=("A_baseline", "B_profile", "C_random", "D_minimal")):
    agg = {"per_judge": {}, "pooled": {}, "paired": {}, "cross_judge_disagreement": None,
           "constraint_satisfaction_mean": {}, "token_cost_mean": {}}
    # per-arm quality per judge + pooled
    for jm in judge_models:
        agg["per_judge"][jm] = {a: round(_mean([r["judge_scores"][jm][a] for r in per_item
                                                if r["judge_scores"].get(jm, {}).get(a) is not None]), 3)
                                for a in arms}
    def pooled_arm(r, a):
        vals = [r["judge_scores"][jm][a] for jm in judge_models if r["judge_scores"].get(jm, {}).get(a) is not None]
        return _mean(vals) if vals else None
    for a in arms:
        xs = [pooled_arm(r, a) for r in per_item]; xs = [x for x in xs if x is not None]
        agg["pooled"][a] = {"mean": round(_mean(xs), 3), "stdev": round(statistics.pstdev(xs), 3) if len(xs) > 1 else None,
                            "ci95": _ci95(xs), "n": len(xs)}
    # paired deltas vs B
    for other in ("A_baseline", "C_random", "D_minimal"):
        diffs = []
        for r in per_item:
            b = pooled_arm(r, "B_profile"); o = pooled_arm(r, other)
            if b is not None and o is not None:
                diffs.append(b - o)
        agg["paired"][f"B_minus_{other}"] = {
            "mean_delta": round(_mean(diffs), 3) if diffs else None,
            "cohen_d": round(_cohen_d_paired(diffs), 3) if len(diffs) > 1 else None,
            "ci95": _ci95(diffs), "n": len(diffs),
            "wins_B": sum(1 for d in diffs if d > 0), "ties": sum(1 for d in diffs if d == 0),
            "losses_B": sum(1 for d in diffs if d < 0)}
    # cross-judge disagreement: mean |judge_i(B) - judge_j(B)| over items (first two judges)
    if len(judge_models) >= 2:
        j1, j2 = judge_models[0], judge_models[1]
        d = [abs(r["judge_scores"][j1]["B_profile"] - r["judge_scores"][j2]["B_profile"])
             for r in per_item if r["judge_scores"].get(j1, {}).get("B_profile") is not None
             and r["judge_scores"].get(j2, {}).get("B_profile") is not None]
        agg["cross_judge_disagreement"] = {"metric": f"mean|{j1}−{j2}| on B", "value": round(_mean(d), 3) if d else None}
    # constraint satisfaction + token cost means
    for a in arms:
        cs = [r["constraint_satisfaction"][a] for r in per_item if r["constraint_satisfaction"].get(a) is not None]
        agg["constraint_satisfaction_mean"][a] = round(_mean(cs), 3) if cs else None
        pt = [r["usage"][a].get("prompt_tokens") for r in per_item if r["usage"][a].get("prompt_tokens")]
        ct = [r["usage"][a].get("completion_tokens") for r in per_item if r["usage"][a].get("completion_tokens")]
        agg["token_cost_mean"][a] = {"prompt": round(_mean(pt), 1) if pt else None,
                                     "completion": round(_mean(ct), 1) if ct else None}
    return agg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gen-model", default=None)
    ap.add_argument("--judge-models", default=None, help="comma-separated model specs")
    ap.add_argument("--limit", type=int, default=0, help="use first N corpus items (0 = all)")
    ap.add_argument("--explanations", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--out", default=str(_HERE / "naming_eval_live_results.json"))
    args = ap.parse_args()

    specs = L.available_specs()
    if not specs:
        print("No LLM provider configured. Set one of:\n"
              "  MISTRAL_API_KEY   (mistral:mistral-large-latest)\n"
              "  DASHSCOPE_API_KEY (qwen:qwen-max)\n"
              "  OPENAI_API_KEY    (openai:gpt-4o-mini)\n"
              "  LLM_BASE_URL + LLM_API_KEY (compat:<model>, e.g. OpenRouter/Together/vLLM/Ollama)\n"
              "  ANTHROPIC_API_KEY (anthropic:claude-opus-4-8)\n"
              "then re-run.  (No data is fabricated when unconfigured.)")
        return 2
    gen_model = args.gen_model or specs[0]
    judge_models = (args.judge_models.split(",") if args.judge_models else specs)
    items = C.CORPUS[:args.limit] if args.limit else C.CORPUS
    print(f"gen={gen_model}  judges={judge_models}  items={len(items)}  temp={args.temperature}")

    per_item = run(gen_model, judge_models, items, args.explanations, args.temperature)
    agg = aggregate(per_item, judge_models)
    result = {"config": {"gen_model": gen_model, "judge_models": judge_models, "n_items": len(items),
                         "temperature": args.temperature, "explanations": args.explanations},
              "per_item": per_item, "aggregate": agg}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n== Pooled per-arm quality (1-5) ==")
    for a, s in agg["pooled"].items():
        print(f"  {a:11} mean={s['mean']} ci95={s['ci95']} n={s['n']}")
    print("== Paired vs B (effect size) ==")
    for k, v in agg["paired"].items():
        print(f"  {k}: Δ={v['mean_delta']} d={v['cohen_d']} ci95={v['ci95']} "
              f"wins_B={v['wins_B']} ties={v['ties']} losses_B={v['losses_B']}")
    print("== Constraint satisfaction (mean) ==", agg["constraint_satisfaction_mean"])
    if agg["cross_judge_disagreement"]:
        print("== Cross-judge disagreement ==", agg["cross_judge_disagreement"])
    print(f"\nwrote {Path(args.out).relative_to(_REPO) if str(_REPO) in args.out else args.out}")
    print("NOTE: LLM judging is NOT equivalent to human validation; report cross-judge disagreement and "
          "treat as indicative only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
