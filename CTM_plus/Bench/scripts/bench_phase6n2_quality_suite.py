"""Phase 6N.2 — extended quality suite for int4_protected (large-N MMLU + HumanEval
+ LongBench), with a per-question AGREEMENT diagnostic vs bf16.

Extends Phase 6N (200-Q MMLU, 0.0pt delta) along three axes the brief still lists
as pending. The headline gain over 6N is the **agreement diagnostic**: aggregate
accuracy parity (63.5%=63.5%) can hide compensating per-question flips; this
suite reports, for each eval, the fraction of questions where bf16 and int4 give
the *same* answer — a far finer fidelity signal than the aggregate.

Three evals (run any subset via --evals):
  mmlu       large-N multiple-choice accuracy + bf16/int4 agreement (greedy A-D)
  humaneval  code-generation pass@1 (GENERATE-ONLY by default; see SECURITY)
  longbench  long-context QA, substring/F1 score + agreement (a few subtasks)

Each eval reports per-cell score AND:
  - delta (int4 - bf16)
  - agreement_pct: fraction of items where int4's answer == bf16's answer
  - (mmlu) flip breakdown: bf16-right/int4-wrong vs bf16-wrong/int4-right
The acceptance gate is per-eval: |delta| <= tol AND agreement >= agree_floor.

⚠ SECURITY (humaneval): pass@1 requires EXECUTING model-generated Python. That is
  arbitrary code execution. This script DEFAULTS TO GENERATE-ONLY (no execution) —
  it writes the completions to JSON for you to score with the official HumanEval
  harness in a sandbox. Pass --execute ONLY in a throwaway/sandboxed container;
  it runs each completion in a subprocess with a timeout, which is NOT a real
  security boundary. Do not --execute on a pod with credentials/network you care about.

⚠ MASK: int4 quality is only meaningful with a full-context-calibrated mask
  (mml=8192). A collapsed mask tanks every eval — the gate will flag it.

CPU-testable: all scorers (MMLU parse/agreement, HumanEval extract, LongBench F1)
are pure functions with --selftest (no GPU/model/dataset/execution).

Usage:
  python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py --selftest
  python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py --dry-run --evals mmlu,humaneval,longbench
  # GPU (good mask required):
  python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py \
      --evals mmlu --num-questions 1000 --cells bf16,protected \
      --out bench_out/phase6n2/mmlu_1k.json
  python CTM_plus/Bench/scripts/bench_phase6n2_quality_suite.py \
      --evals humaneval --num-questions 164 --out bench_out/phase6n2/humaneval_gen.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break

# Reuse the validated MMLU prompt/parse from Phase 6N (single source of truth).
_SCR = Path(__file__).resolve().parent
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))
import bench_phase6n_mmlu_quality as p6n   # build_prompt, parse_answer, LETTERS

LETTERS = p6n.LETTERS
DEFAULT_TOL_PCT = 1.0
DEFAULT_AGREE_FLOOR = 95.0   # bf16/int4 must agree on >= this % of items


# ===========================================================================
# MMLU (reuses 6N prompt/parse) + agreement diagnostic
# ===========================================================================
def mmlu_agreement(bf16_preds: List[Optional[int]],
                   int4_preds: List[Optional[int]],
                   answers: List[int]) -> Dict[str, object]:
    """Per-question agreement + flip breakdown between the two cells."""
    n = len(answers)
    agree = sum(1 for b, i in zip(bf16_preds, int4_preds) if b == i)
    bf_right_int_wrong = sum(
        1 for b, i, a in zip(bf16_preds, int4_preds, answers)
        if b == a and i != a)
    bf_wrong_int_right = sum(
        1 for b, i, a in zip(bf16_preds, int4_preds, answers)
        if b != a and i == a)
    return {
        "n": n,
        "agreement_pct": round(100.0 * agree / n, 2) if n else 0.0,
        "n_agree": agree,
        "bf16_right_int4_wrong": bf_right_int_wrong,
        "bf16_wrong_int4_right": bf_wrong_int_right,
        "net_flips": bf_wrong_int_right - bf_right_int_wrong,
    }


# ===========================================================================
# HumanEval — code completion (pass@1). GENERATE-ONLY by default.
# ===========================================================================
def humaneval_prompt(problem: Dict) -> str:
    """HumanEval gives a function signature + docstring; model completes the body."""
    return problem["prompt"]


def extract_completion(prompt: str, raw: str) -> str:
    """Take the model's continuation and stop at the first line that dedents to
    column 0 after the function body (a heuristic the official harness also uses
    via stop tokens). Returns prompt + body for execution."""
    # Strip a leading copy of the prompt if the model echoed it.
    body = raw
    if raw.startswith(prompt):
        body = raw[len(prompt):]
    # Cut at common stop markers (next def/class at col 0, or markdown fence).
    stops = ["\nclass ", "\ndef ", "\n#", "\nif __name__", "\nprint(", "\n```"]
    cut = len(body)
    for s in stops:
        idx = body.find(s)
        if idx != -1:
            cut = min(cut, idx)
    return prompt + body[:cut]


def _run_one_completion(full_src: str, test_src: str, entry_point: str,
                        timeout_s: float = 6.0) -> bool:
    """Execute prompt+completion+tests in a subprocess. NOT a security boundary —
    only call when --execute is set in a sandbox."""
    import subprocess, tempfile, textwrap
    harness = full_src + "\n\n" + test_src + "\n\n" + f"check({entry_point})\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(harness)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True,
                           timeout=timeout_s)
        return r.returncode == 0
    except Exception:
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ===========================================================================
# LongBench — substring + token-F1 score (the standard cheap scorer)
# ===========================================================================
def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def token_f1(prediction: str, ground_truth: str) -> float:
    """Standard SQuAD/LongBench token-level F1."""
    pred = normalize_text(prediction).split()
    gt = normalize_text(ground_truth).split()
    if not pred or not gt:
        return 1.0 if pred == gt else 0.0
    common = Counter(pred) & Counter(gt)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(gt)
    return 2 * precision * recall / (precision + recall)


def longbench_score(prediction: str, answers: List[str]) -> float:
    """Max F1 over the acceptable answers (LongBench allows multiple)."""
    return max((token_f1(prediction, a) for a in answers), default=0.0)


# ===========================================================================
# Acceptance
# ===========================================================================
def acceptance(eval_name: str, bf16_score: float, int4_score: float,
               agreement_pct: Optional[float], tol_pct: float,
               agree_floor: float) -> Dict[str, object]:
    delta = round(int4_score - bf16_score, 2)
    within = abs(delta) <= tol_pct
    agree_ok = agreement_pct is None or agreement_pct >= agree_floor
    collapse = (bf16_score - int4_score) > 15.0 or (
        agreement_pct is not None and agreement_pct < 50.0 and bf16_score > 50.0)
    if collapse:
        status = "COLLAPSE_SUSPECTED"
    elif within and agree_ok:
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "eval": eval_name,
        "bf16_score": bf16_score, "int4_score": int4_score, "delta": delta,
        "agreement_pct": agreement_pct, "tolerance_pct": tol_pct,
        "agreement_floor": agree_floor,
        "within_tolerance": within, "agreement_ok": agree_ok,
        "collapse_suspected": collapse, "status": status,
    }


# ===========================================================================
# Dataset loaders (GPU path)
# ===========================================================================
def _load(eval_name: str, n: int) -> List[Dict]:
    from datasets import load_dataset
    if eval_name == "mmlu":
        ds = load_dataset("cais/mmlu", "all", split="test")
        return [{"q": r["question"], "choices": r["choices"],
                 "answer": int(r["answer"])} for r in ds.select(range(min(n, len(ds))))]
    if eval_name == "humaneval":
        ds = load_dataset("openai_humaneval", split="test")
        return [{"task_id": r["task_id"], "prompt": r["prompt"],
                 "test": r["test"], "entry_point": r["entry_point"]}
                for r in ds.select(range(min(n, len(ds))))]
    if eval_name == "longbench":
        # A few short English subtasks; F1-scored. The HF config names + the need
        # for trust_remote_code vary by datasets version, so try a few spellings
        # and SURFACE the last error if every subtask fails (don't silently
        # return [] -> downstream ZeroDivision).
        out: List[Dict] = []
        last_err = None
        per_sub = max(1, n // 3 + 1)
        for sub in ("narrativeqa", "qasper", "hotpotqa", "multifieldqa_en"):
            ds = None
            # datasets>=3.0 BANS script datasets (THUDM/LongBench ships
            # LongBench.py). Try, in order: (1) HF's auto-Parquet conversion at
            # the refs/convert/parquet revision (bypasses the script -- the most
            # likely-to-work path on new datasets), (2) plain load (works only on
            # datasets<3.0). NOTE: the auto-Parquet revision may not exist for
            # every config; if all fail we surface the real error.
            for kw in ({"revision": "refs/convert/parquet"}, {}):
                try:
                    ds = load_dataset("THUDM/LongBench", sub, split="test", **kw)
                    break
                except Exception as e:
                    last_err = e
            if ds is None:
                continue
            feats = set(getattr(ds, "features", {}) or {})
            for r in ds.select(range(min(per_sub, len(ds)))):
                prompt = r.get("input") or r.get("context") or r.get("question") or ""
                ans = r.get("answers") or r.get("answer") or []
                if isinstance(ans, str):
                    ans = [ans]
                if not prompt or not ans:
                    continue
                out.append({"prompt": prompt, "context": r.get("context", ""),
                            "answers": ans, "subtask": sub})
                if len(out) >= n:
                    break
            if len(out) >= n:
                break
        if not out:
            raise SystemExit(
                "LongBench loaded 0 usable items. THUDM/LongBench is a SCRIPT "
                "dataset (LongBench.py); datasets>=3.0 bans those, and the "
                "refs/convert/parquet auto-conversion fallback also failed. Last "
                f"error: {type(last_err).__name__ if last_err else 'none'}: "
                f"{str(last_err)[:200]}. Fix options: a Parquet LongBench mirror "
                "(--evals stays the same, just point the loader at it), or an "
                "ISOLATED datasets<3.0 venv. MMLU works on this stack and is the "
                "load-bearing quality result. (Dataset-loading issue, NOT int4.)")
        return out[:n]
    raise ValueError(eval_name)


# ===========================================================================
# Self-test (pure CPU)
# ===========================================================================
def _selftest() -> int:
    # --- MMLU agreement ---
    ans = [0, 1, 2, 3]
    # identical preds -> 100% agreement, 0 net flips
    ag = mmlu_agreement([0, 1, 2, 3], [0, 1, 2, 3], ans)
    assert ag["agreement_pct"] == 100.0 and ag["net_flips"] == 0, ag
    # one compensating swap: same aggregate accuracy, but agreement < 100
    ag = mmlu_agreement([0, 1, 2, 3], [0, 1, 3, 2], ans)  # int4 flips q2,q3
    assert ag["agreement_pct"] == 50.0, ag
    assert ag["bf16_right_int4_wrong"] == 2 and ag["bf16_wrong_int4_right"] == 0
    print(f"  mmlu_agreement (catches hidden flips: 50% agree, +0 acc): PASS")

    # --- HumanEval completion extraction ---
    prompt = "def add(a, b):\n    \"\"\"add\"\"\"\n"
    raw = prompt + "    return a + b\n\ndef other():\n    pass\n"
    full = extract_completion(prompt, raw)
    assert full.startswith(prompt) and "return a + b" in full
    assert "def other" not in full, full   # stopped at next def
    print("  humaneval extract_completion (stops at next def): PASS")

    # --- LongBench F1 ---
    assert abs(token_f1("the cat sat", "cat sat") - 1.0) < 1e-9  # articles stripped
    assert token_f1("dog", "cat") == 0.0
    f = token_f1("paris france", "paris")
    assert 0.0 < f < 1.0, f
    assert longbench_score("the answer is Paris", ["Paris", "France"]) > 0.0
    print("  longbench token_f1 + max-over-answers: PASS")

    # --- acceptance ---
    a = acceptance("mmlu", 63.5, 63.5, 99.0, 1.0, 95.0)
    assert a["status"] == "PASS", a
    # same aggregate but LOW agreement -> FAIL (the diagnostic earns its keep)
    a = acceptance("mmlu", 63.5, 63.5, 80.0, 1.0, 95.0)
    assert a["status"] == "FAIL" and not a["agreement_ok"], a
    print("  acceptance: parity+high-agree PASS, parity+low-agree FAIL: PASS")
    # real regression
    a = acceptance("humaneval", 60.0, 55.0, None, 1.0, 95.0)
    assert a["status"] == "FAIL", a
    # collapse
    a = acceptance("mmlu", 65.0, 28.0, 30.0, 1.0, 95.0)
    assert a["status"] == "COLLAPSE_SUSPECTED", a
    print("  acceptance: regression FAIL, collapse flagged: PASS")

    print("\nself-test: 5/5 PASS")
    return 0


# ===========================================================================
# GPU / dry-run drivers
# ===========================================================================
def _build_llm(cell: str, model: str, mml: int, gpu_util: float):
    import torch  # noqa
    for k, v in p6n._cell_env(cell).items():
        os.environ[k] = v
    if cell == "bf16":
        from vllm import LLM
        return LLM(model=model, max_model_len=mml, gpu_memory_utilization=gpu_util,
                   dtype="bfloat16", max_num_seqs=8)
    from kv_policy.int4_protected import Int4ProtectedLLM
    return Int4ProtectedLLM(model=model, max_model_len=mml,
                            gpu_memory_utilization=gpu_util, max_num_seqs=8)


def _gen(llm, prompts: List[str], max_tokens: int):
    from vllm import SamplingParams
    sp = SamplingParams(temperature=0.0, max_tokens=max_tokens)
    return [o.outputs[0].text for o in llm.generate(prompts, sp)]


def _run_eval_gpu(eval_name: str, items: List[Dict], cells: List[str],
                  model: str, mml: int, gpu_util: float, execute: bool) -> Dict:
    raw_by_cell: Dict[str, List[str]] = {}
    for cell in cells:
        llm = _build_llm(cell, model, mml, gpu_util)
        if eval_name == "mmlu":
            prompts = [p6n.build_prompt(it["q"], it["choices"]) for it in items]
            raw_by_cell[cell] = _gen(llm, prompts, 4)
        elif eval_name == "humaneval":
            prompts = [humaneval_prompt(it) for it in items]
            raw_by_cell[cell] = _gen(llm, prompts, 512)
        elif eval_name == "longbench":
            prompts = [it["prompt"] for it in items]
            raw_by_cell[cell] = _gen(llm, prompts, 64)
        del llm
    return _score_eval(eval_name, items, raw_by_cell, execute)


def _score_eval(eval_name: str, items: List[Dict],
                raw_by_cell: Dict[str, List[str]], execute: bool) -> Dict:
    if not items:
        # Defensive: a bad dataset load must not divide-by-zero downstream.
        return {"eval": eval_name, "n": 0, "cells": {},
                "error": "no items to score (dataset loaded empty)"}
    result: Dict[str, object] = {"eval": eval_name, "n": len(items), "cells": {}}
    preds_by_cell: Dict[str, List] = {}

    if eval_name == "mmlu":
        answers = [it["answer"] for it in items]
        for cell, raws in raw_by_cell.items():
            preds = [p6n.parse_answer(r) for r in raws]
            preds_by_cell[cell] = preds
            result["cells"][cell] = p6n.score(preds, answers)
        if "bf16" in preds_by_cell and "protected" in preds_by_cell:
            result["agreement"] = mmlu_agreement(
                preds_by_cell["bf16"], preds_by_cell["protected"], answers)

    elif eval_name == "humaneval":
        for cell, raws in raw_by_cell.items():
            comps = [extract_completion(it["prompt"], r) for it, r in zip(items, raws)]
            preds_by_cell[cell] = comps
            if execute:
                passed = sum(_run_one_completion(c, it["test"], it["entry_point"])
                             for c, it in zip(comps, items))
                result["cells"][cell] = {"n": len(items), "passed": passed,
                                         "pass_at_1_pct": round(100.0 * passed / len(items), 2)}
            else:
                result["cells"][cell] = {"n": len(items), "passed": None,
                                         "pass_at_1_pct": None,
                                         "note": "GENERATE-ONLY (pass --execute in a sandbox to score)"}
        # agreement = identical generated completion (exact string)
        if "bf16" in preds_by_cell and "protected" in preds_by_cell:
            same = sum(1 for a, b in zip(preds_by_cell["bf16"], preds_by_cell["protected"]) if a == b)
            result["agreement"] = {"n": len(items),
                                   "exact_completion_agreement_pct": round(100.0 * same / len(items), 2)}

    elif eval_name == "longbench":
        for cell, raws in raw_by_cell.items():
            scores = [longbench_score(r, it["answers"]) for r, it in zip(raws, items)]
            preds_by_cell[cell] = raws
            result["cells"][cell] = {"n": len(items),
                                     "mean_f1_pct": round(100.0 * sum(scores) / len(items), 2) if items else 0.0}
        if "bf16" in preds_by_cell and "protected" in preds_by_cell:
            same = sum(1 for a, b in zip(preds_by_cell["bf16"], preds_by_cell["protected"])
                       if normalize_text(a) == normalize_text(b))
            result["agreement"] = {"n": len(items),
                                   "normalized_output_agreement_pct": round(100.0 * same / len(items), 2)}
    return result


def _run_eval_dry(eval_name: str, n: int) -> Dict:
    """Fake-model driver: bf16 'correct', int4 ~2% perturbed. Schema check only."""
    import random
    rng = random.Random(0)
    if eval_name == "mmlu":
        items = [{"q": f"Q{i}", "choices": ["a", "b", "c", "d"], "answer": i % 4}
                 for i in range(n)]
        bf = [p6n.LETTERS[it["answer"]] for it in items]
        pr = [p6n.LETTERS[it["answer"]] if rng.random() > 0.02
              else p6n.LETTERS[(it["answer"] + 1) % 4] for it in items]
        return _score_eval("mmlu", items, {"bf16": bf, "protected": pr}, False)
    if eval_name == "humaneval":
        items = [{"task_id": f"t{i}", "prompt": f"def f{i}(x):\n    \"\"\"d\"\"\"\n",
                  "test": "def check(f): assert True", "entry_point": f"f{i}"}
                 for i in range(n)]
        raws = [it["prompt"] + "    return x\n" for it in items]
        return _score_eval("humaneval", items, {"bf16": raws, "protected": raws}, False)
    if eval_name == "longbench":
        items = [{"prompt": f"ctx{i}", "answers": ["paris"]} for i in range(n)]
        raws = ["the answer is paris" for _ in items]
        return _score_eval("longbench", items, {"bf16": raws, "protected": raws}, False)
    raise ValueError(eval_name)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 6N.2 extended quality suite")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--evals", default="mmlu",
                    help="comma: mmlu,humaneval,longbench")
    ap.add_argument("--cells", default="bf16,protected")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--num-questions", type=int, default=1000)
    ap.add_argument("--tol-pct", type=float, default=DEFAULT_TOL_PCT)
    ap.add_argument("--agree-floor", type=float, default=DEFAULT_AGREE_FLOOR)
    ap.add_argument("--execute", action="store_true",
                    help="HumanEval: EXECUTE generated code to score pass@1. "
                         "ARBITRARY CODE EXECUTION — sandbox/throwaway pod ONLY.")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    evals = [e.strip() for e in args.evals.split(",") if e.strip()]
    cells = [c.strip() for c in args.cells.split(",") if c.strip()]

    if args.execute and not args.dry_run:
        print("⚠ --execute set: will run model-generated code in subprocesses. "
              "Ensure this is a sandboxed/throwaway pod.", file=sys.stderr)

    report: Dict[str, object] = {"model": args.model, "dry_run": bool(args.dry_run),
                                 "evals": {}}
    overall_pass = True
    for ev in evals:
        if args.dry_run:
            res = _run_eval_dry(ev, min(args.num_questions, 12))
        else:
            items = _load(ev, args.num_questions)
            res = _run_eval_gpu(ev, items, cells, args.model,
                                args.max_model_len, args.gpu_util, args.execute)
        # build per-eval acceptance
        cellscores = res["cells"]
        def _score_of(c):
            d = cellscores.get(c, {})
            return d.get("accuracy_pct") or d.get("pass_at_1_pct") or d.get("mean_f1_pct")
        bf, pr = _score_of("bf16"), _score_of("protected")
        agree = None
        ag = res.get("agreement", {})
        if ag:
            agree = (ag.get("agreement_pct") or ag.get("exact_completion_agreement_pct")
                     or ag.get("normalized_output_agreement_pct"))
        if bf is not None and pr is not None:
            res["acceptance"] = acceptance(ev, bf, pr, agree, args.tol_pct, args.agree_floor)
            if res["acceptance"]["status"] != "PASS":
                overall_pass = False
        report["evals"][ev] = res

    print(json.dumps(report, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to: {args.out}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
