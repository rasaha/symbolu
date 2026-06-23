#!/usr/bin/env python3
"""Kosha K2 generation quality eval. Pre-reg: docs/KOSHA_K2_QUALITY_EVAL_PREREG.md.

Two arms, SAME base model + SAME C×R×S frame; the ONLY difference is the inserted Kosha depth block, so
any delta is attributable to Kosha:
  W   = base Mistral + C×R×S wrapper (kosha=None)        — validated baseline
  W+K = base Mistral + C×R×S wrapper + Kosha modifier    — enable_kosha
Scored by the SAME validated rubric_v2 (guardrails) + deterministic depth_conformance (against the
INTENDED depth label, not the selector's prediction). NO model-as-judge. Guardrail-first §9 gate; the
quality claim is bounded to depth-conformance/clarity (NOT human preference — that is a future K3).

CPU-SAFE: aggregate()/decide() are pure and unit-tested; `--dry-run` emits the skeleton. Real generation
needs a GPU + the cu121 stack + peft? (no peft needed here — base model only). Generations are cached.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CSR = _HERE.parent / "cg_wrapper_ablation"
for p in (str(_HERE.parent), str(_CSR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from conscious_generation import kosha_conformance as KC          # noqa: E402

ARMS = ("W", "WK")
LEVELS = ("annamaya", "pranamaya", "manomaya", "vijnanamaya", "anandamaya")
DECISIONS = ("CG_KOSHA_K2_ADDS_QUALITY", "CG_KOSHA_K2_SAFE_NO_QUALITY_GAIN",
             "CG_KOSHA_K2_FRAME_ONLY_BEST", "CG_KOSHA_K2_DEGRADES_FRAME",
             "CG_KOSHA_K2_DEGRADES_FACTUALITY", "CG_KOSHA_K2_DEGRADES_RECALL",
             "CG_KOSHA_K2_INSUFFICIENT_POWER", "CG_KOSHA_K2_ENV_UNAVAILABLE")
TOL_FRAME, TOL_RECALL, TOL_GUARD = 0.02, 0.03, 0.05


def rubric_example(q: dict) -> dict:
    """Map a K2 query row to a rubric_v2 scoring example (no false_claims authored -> factuality keys off
    answer length/term presence only; stated honestly in the pre-reg)."""
    return {"query": q["query"], "dominant_terms": [q["term"]],
            "expected_primary": [q["primary_domain"]],
            "expected_secondary": list(q.get("secondary_domains", [])),
            "expected_secondary_true_senses": [],
            "expected_rejected": list(q.get("rejected_domains", [])),
            "must_include": list(q.get("must_include", [])),
            "must_not_include": [], "false_claims": []}


# ---- aggregation (pure; CPU-testable) -----------------------------------------------------------
def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def aggregate(per_example: list) -> dict:
    """per_example: [{"slice","intended_depth","scores":{arm:{rubric_v2 + depth_conformance + terse +
    over_framing}}}]. Returns {arm: {metric: value}}."""
    out = {}
    for arm in ARMS:
        rows = [pe for pe in per_example if arm in pe.get("scores", {})]
        sc = [pe["scores"][arm] for pe in rows]
        out[arm] = {
            "primary_frame_correct": _mean([r["primary_frame_correct"] for r in sc]),
            "rejected_domain_avoidance": _mean([r["rejected_domain_avoidance"] for r in sc]),
            "factuality_preserved": _mean([r["factuality_preserved"] for r in sc]),
            "must_include_recall": _mean([r["must_include_recall"] for r in sc]),
            "clarity_usefulness": _mean([r["answer_clarity_proxy"] for r in sc]),
            "depth_conformance": _mean([r["depth_conformance"] for r in sc]),
            "terse_rate": _mean([r["terse"] for r in sc]),
            "over_framing_rate": _mean([r["over_framing"] for r in sc]),
            "answer_length": _mean([r.get("word_count") for r in sc]),
            "n": len(rows),
        }
    return out


def bootstrap_delta(per_example, metric, n_boot=2000, seed=0) -> dict:
    raw = {"clarity_usefulness": "answer_clarity_proxy"}.get(metric, metric)   # aggregated name -> raw key
    rows = [pe for pe in per_example if "W" in pe["scores"] and "WK" in pe["scores"]]
    if not rows:
        return {"delta": 0.0, "ci_low": 0.0, "ci_high": 0.0, "excludes_zero": False}
    wk = [pe["scores"]["WK"][raw] for pe in rows]
    w = [pe["scores"]["W"][raw] for pe in rows]
    n = len(rows); rng = random.Random(seed); deltas = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append(sum(wk[i] for i in idx) / n - sum(w[i] for i in idx) / n)
    deltas.sort()
    return {"delta": round(sum(wk) / n - sum(w) / n, 4),
            "ci_low": round(deltas[int(0.025 * n_boot)], 4),
            "ci_high": round(deltas[int(0.975 * n_boot)], 4),
            "excludes_zero": bool(deltas[int(0.025 * n_boot)] > 0.0)}


def slices_improved_depth(per_example) -> int:
    """# of Kosha-level slices where WK depth_conformance > W (per intended level)."""
    n = 0
    for lvl in LEVELS:
        rows = [pe for pe in per_example if pe.get("slice") == lvl
                and "W" in pe["scores"] and "WK" in pe["scores"]]
        if not rows:
            continue
        w = _mean([pe["scores"]["W"]["depth_conformance"] for pe in rows])
        wk = _mean([pe["scores"]["WK"]["depth_conformance"] for pe in rows])
        n += int(wk > w + 1e-9)
    return n


# ---- decision gate (pre-reg §9; pre-registered labels only) -------------------------------------
def decide(m: dict, *, conf_delta: dict, clarity_delta: dict, slices_improved: int) -> tuple:
    W, WK = m.get("W"), m.get("WK")
    if not (W and WK) or W["n"] < 8 or WK["n"] < 8:
        return "CG_KOSHA_K2_INSUFFICIENT_POWER", {"reason": "fewer than 8 scored per arm"}
    # guardrails first (any failure dominates, regardless of upside)
    if WK["primary_frame_correct"] < W["primary_frame_correct"] - TOL_FRAME \
            or WK["rejected_domain_avoidance"] < W["rejected_domain_avoidance"] - TOL_FRAME:
        return "CG_KOSHA_K2_DEGRADES_FRAME", {"pfc": (W["primary_frame_correct"], WK["primary_frame_correct"]),
                                              "rda": (W["rejected_domain_avoidance"], WK["rejected_domain_avoidance"])}
    if WK["factuality_preserved"] < W["factuality_preserved"] - TOL_FRAME:
        return "CG_KOSHA_K2_DEGRADES_FACTUALITY", {"fact": (W["factuality_preserved"], WK["factuality_preserved"])}
    if WK["must_include_recall"] < W["must_include_recall"] - TOL_RECALL:
        return "CG_KOSHA_K2_DEGRADES_RECALL", {"recall": (W["must_include_recall"], WK["must_include_recall"])}
    guard_ok = (WK["terse_rate"] <= W["terse_rate"] + TOL_GUARD
                and WK["over_framing_rate"] <= W["over_framing_rate"] + TOL_GUARD)
    quality_up = ((conf_delta["excludes_zero"] or clarity_delta["excludes_zero"])
                  and slices_improved >= 2 and guard_ok)
    r = {"depth_conformance_delta": conf_delta, "clarity_delta": clarity_delta,
         "slices_improved": slices_improved, "guard_ok": guard_ok}
    if quality_up:
        return "CG_KOSHA_K2_ADDS_QUALITY", r
    # guardrails pass but no significant quality gain
    if WK["depth_conformance"] + 1e-9 < W["depth_conformance"] and WK["clarity_usefulness"] + 1e-9 < W["clarity_usefulness"]:
        return "CG_KOSHA_K2_FRAME_ONLY_BEST", r
    return "CG_KOSHA_K2_SAFE_NO_QUALITY_GAIN", r


def run(per_example: list) -> dict:
    m = aggregate(per_example)
    conf_d = bootstrap_delta(per_example, "depth_conformance")
    clar_d = bootstrap_delta(per_example, "clarity_usefulness")
    si = slices_improved_depth(per_example)
    decision, reasons = decide(m, conf_delta=conf_d, clarity_delta=clar_d, slices_improved=si)
    from collections import Counter
    return {"n": len(per_example), "arm_metrics": m,
            "slice_counts": dict(Counter(pe.get("slice") for pe in per_example)),
            "depth_conformance_delta": conf_d, "clarity_delta": clar_d, "slices_improved": si,
            "decision": decision, "decision_reasons": reasons}


def to_markdown(rep) -> str:
    if rep.get("decision") in ("CG_KOSHA_K2_ENV_UNAVAILABLE", "dry_run"):
        return f"# Kosha K2 quality eval — {rep.get('decision')}\n\n- {rep.get('note', '')}\n"
    m = rep["arm_metrics"]
    L = ["# Kosha K2 — frame-only (W) vs frame+Kosha (W+K)", "",
         f"- n: **{rep['n']}**  ·  **DECISION: `{rep['decision']}`**", "",
         "| metric | W | W+K |", "|---|---|---|"]
    for k in ("depth_conformance", "clarity_usefulness", "primary_frame_correct",
              "rejected_domain_avoidance", "factuality_preserved", "must_include_recall",
              "terse_rate", "over_framing_rate", "answer_length"):
        L.append(f"| {k} | {m['W'][k]} | {m['WK'][k]} |")
    L += ["", f"- Δ depth_conformance (W+K−W): `{rep['depth_conformance_delta']}`",
          f"- Δ clarity (W+K−W): `{rep['clarity_delta']}`  ·  slices improved: **{rep['slices_improved']}**",
          f"- reasons: `{rep['decision_reasons']}`", "",
          "> Guardrail-first: any C×R×S/factuality/recall regression → DEGRADES_*. Quality claim is bounded",
          "> to depth-conformance/clarity (NOT human preference — that is a future K3). No model-as-judge."]
    return "\n".join(L) + "\n"


def gpu_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:                                     # noqa: BLE001
        return False


def _generate_and_score(queries, base_model, dtype="bf16", max_new=220):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from csr_match_filter import rubric as RB
    from csr_match_filter import prompts as P
    from csr_match_filter import kosha as K

    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    if dtype == "4bit":
        model = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto", load_in_4bit=True)
    else:
        model = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto",
                                                     torch_dtype=torch.bfloat16)

    def gen(prompt):
        inp = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inp, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        return tok.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    per = []
    for q in queries:
        ex = rubric_example(q)
        pri, sec, rej = [q["primary_domain"]], q.get("secondary_domains", []), q.get("rejected_domains", [])
        sel = K.select_kosha_depth(q["query"], primary_domain=q["primary_domain"])
        w_ans = gen(P.build_framed_prompt(q["query"], pri, sec, rej, kosha=None))
        wk_ans = gen(P.build_framed_prompt(q["query"], pri, sec, rej, kosha=sel))
        sc = {}
        for arm, ans in (("W", w_ans), ("WK", wk_ans)):
            r = dict(RB.score_answer_v2(ans, ex, [q["term"]]))
            r.update(KC.conformance_features(ans, q["intended_depth"]))
            r["answer"] = ans
            sc[arm] = r
        per.append({"id": q["id"], "slice": q["slice"], "intended_depth": q["intended_depth"],
                    "kosha_level": sel.level.value, "scores": sc})
    return per


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kosha K2 quality eval (W vs W+K).")
    ap.add_argument("--data", default="scripts/conscious_generation/data/kosha_k2_queries.json")
    ap.add_argument("--base-model", default="mistralai/Mistral-7B-Instruct-v0.3")
    ap.add_argument("--out", default="runs/kosha/k2_quality_eval.json")
    ap.add_argument("--report", default="runs/kosha/k2_quality_eval.md")
    ap.add_argument("--dtype", choices=("bf16", "4bit"), default="bf16")
    ap.add_argument("--from-cache", default=None)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.out).parent / "k2_per_example_cache.json"
    if args.from_cache:
        per = json.loads(Path(args.from_cache).read_text())["per_example"]
    elif not args.execute or not gpu_available():
        rep = {"decision": "CG_KOSHA_K2_ENV_UNAVAILABLE" if not gpu_available() else "dry_run",
               "note": "DRY-RUN: aggregate()/decide() wired; real generation needs a GPU pod.",
               "decision_labels": list(DECISIONS)}
        Path(args.out).write_text(json.dumps(rep, indent=2))
        Path(args.report).write_text(to_markdown(rep))
        print(f"DECISION: {rep['decision']} (dry-run; wrote {args.out})")
        return 0
    else:
        blob = json.loads(Path(args.data).read_text())
        queries = blob["queries"] if isinstance(blob, dict) else blob
        per = _generate_and_score(queries, args.base_model, dtype=args.dtype)
        cache_path.write_text(json.dumps({"per_example": per}, indent=2))
        print(f"[cached generations -> {cache_path}]")

    rep = run(per)
    Path(args.out).write_text(json.dumps(rep, indent=2))
    Path(args.report).write_text(to_markdown(rep))
    print(f"n={rep['n']} DECISION: {rep['decision']}")
    print(f"wrote {args.out} + {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
