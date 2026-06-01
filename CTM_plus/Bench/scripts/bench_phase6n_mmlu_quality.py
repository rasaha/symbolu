"""Phase 6N — MMLU quality bench for int4_protected (the cheap, high-value next step).

Broadens the int4_protected quality bar beyond needle + token-agreement to a
standard academic benchmark (**MMLU**), the #1 adoption-de-risker in the v2
roadmap. Runs bf16 (quality ceiling) vs int4_protected on the SAME held-out MMLU
questions and reports the accuracy delta + a pass/fail gate.

Why this is the cheapest high-value work:
  - No ncu, no profiling counters — runs on ANY GPU pod (incl. ncu-locked).
  - ~30-45 min on one A100; no multi-GPU, no kernel work.
  - Directly attacks the brief's "quality bench is needle+token-agreement only"
    gap, which de-risks customer adoption far more than bounded throughput work.

Method (greedy multiple-choice, the standard cheap MMLU protocol):
  For each question, build the prompt + 4 options, generate 1 token greedily,
  read which of A/B/C/D the model emits. Accuracy = fraction correct. Run on
  bf16 and protected; the gate is |bf16_acc - prot_acc| <= tolerance (default
  1.0 pt), matching the existing TurboQuant track-E gate convention.

⚠ Requires a VALID calibrated protect mask. A collapsed mask (e.g. the
  regenerated mml=1024 one) tanks int4 accuracy — that is a mask problem, NOT a
  method failure; the gate will correctly FAIL and flag it.

CPU-testable: the prompt builder + answer parser + scorer are pure functions
with a --selftest (no GPU, no model, no dataset). The GPU path is a thin driver.

Usage:
  # CPU self-test (no GPU/model/dataset):
  python CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py --selftest

  # CPU dry-run — exercises the full driver with a FAKE model (schema + plumbing):
  python CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py --dry-run

  # GPU run (on the pod; needs a valid protect mask):
  python CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py \
      --cells bf16,protected --num-questions 200 \
      --out bench_out/phase6n/mmlu_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

LETTERS = ["A", "B", "C", "D"]
# Default acceptance: int4 must stay within this many accuracy POINTS of bf16.
DEFAULT_TOL_PCT = 1.0

# A tiny built-in MMLU-style question set for --dry-run and --selftest (so the
# tooling is verifiable with no dataset download). The real run pulls MMLU via
# datasets (see _load_mmlu); these are paraphrased generic items, NOT MMLU rows.
_BUILTIN_QA = [
    {"q": "What is the capital of France?",
     "choices": ["Berlin", "Paris", "Rome", "Madrid"], "answer": 1},
    {"q": "2 + 2 equals what?",
     "choices": ["3", "4", "5", "22"], "answer": 1},
    {"q": "Water is chemically written as?",
     "choices": ["CO2", "O2", "H2O", "NaCl"], "answer": 2},
    {"q": "Which planet is closest to the Sun?",
     "choices": ["Venus", "Earth", "Mars", "Mercury"], "answer": 3},
]


# ---------------------------------------------------------------------------
# Pure functions (CPU-testable: no torch, no model)
# ---------------------------------------------------------------------------
def build_prompt(question: str, choices: List[str]) -> str:
    """Standard 4-choice MMLU prompt; model is asked to answer with a letter."""
    lines = [f"{question.strip()}", ""]
    for letter, choice in zip(LETTERS, choices):
        lines.append(f"{letter}. {choice}")
    lines.append("")
    lines.append("Answer with the single letter (A, B, C, or D) of the correct "
                 "choice.\nAnswer:")
    return "\n".join(lines)


def parse_answer(text: str) -> Optional[int]:
    """Extract the chosen option index (0-3) from a model's raw output.

    Accepts 'A', ' B.', 'The answer is C', '(D)', etc. Returns None if no
    clear letter is found (counts as wrong, not crash).

    Deliberately CONSERVATIVE: a bare A-D letter must be a STANDALONE token
    (surrounded by non-letters), so prose like \"I don't know\" does NOT parse
    as 'D'. We scan tokens left-to-right and take the first that is exactly a
    single A-D letter (optionally trailed by '.'/')'/':')."""
    if not text:
        return None
    up = text.upper()
    # An A-D letter flanked by non-letters (start/space/paren) and not glued to
    # more letters — e.g. "A", "(B)", "C.", "ANSWER: D" all match; "DON'T",
    # "ACID", "BEAD" do not.
    for m in re.finditer(r"(?<![A-Z])([ABCD])(?![A-Z])", up):
        # Reject if the matched letter is immediately followed by an apostrophe
        # (contraction like D'... is unlikely, but be safe) — the lookahead
        # above already excludes following letters, so this is sufficient.
        return LETTERS.index(m.group(1))
    return None


def score(predictions: List[Optional[int]], answers: List[int]) -> Dict[str, float]:
    """Accuracy + counts. predictions may contain None (unparseable)."""
    n = len(answers)
    correct = sum(1 for p, a in zip(predictions, answers) if p is not None and p == a)
    unparsed = sum(1 for p in predictions if p is None)
    return {
        "n": n,
        "correct": correct,
        "unparsed": unparsed,
        "accuracy_pct": round(100.0 * correct / n, 2) if n else 0.0,
    }


def acceptance(bf16_acc: float, prot_acc: float, tol_pct: float) -> Dict[str, object]:
    """Gate: int4 within tol_pct points of bf16 (and not a collapse)."""
    delta = round(prot_acc - bf16_acc, 2)
    within = abs(delta) <= tol_pct
    # A protected accuracy near chance (25%) when bf16 is well above flags a
    # likely mask collapse, not normal quantization loss.
    collapse_suspected = (bf16_acc - prot_acc) > 15.0 or prot_acc < 30.0 and bf16_acc > 50.0
    status = "PASS" if within else ("COLLAPSE_SUSPECTED" if collapse_suspected else "FAIL")
    return {
        "bf16_accuracy_pct": bf16_acc,
        "protected_accuracy_pct": prot_acc,
        "delta_pct": delta,
        "tolerance_pct": tol_pct,
        "within_tolerance": within,
        "collapse_suspected": collapse_suspected,
        "status": status,
    }


# ---------------------------------------------------------------------------
# GPU driver (thin; not exercised by --selftest)
# ---------------------------------------------------------------------------
def _load_mmlu(num_questions: int) -> List[Dict]:
    """Load MMLU via `datasets`. Falls back with a clear error if unavailable."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise SystemExit(f"`datasets` not installed (pip install datasets): {e}")
    # 'all' config, test split; flatten to our schema.
    ds = load_dataset("cais/mmlu", "all", split="test")
    out = []
    for row in ds:
        out.append({"q": row["question"], "choices": row["choices"],
                    "answer": int(row["answer"])})
        if len(out) >= num_questions:
            break
    return out


def _cell_env(cell: str) -> Dict[str, str]:
    if cell == "bf16":
        return {"PHASE6E_FUSED_WRITER": "0", "PHASE6J_NAIVE_FORCE_ZERO": "0"}
    if cell == "protected":
        return {"PHASE6E_FUSED_WRITER": "1", "PHASE6J_NAIVE_FORCE_ZERO": "0"}
    raise ValueError(f"unknown cell {cell!r}")


def _run_cell_gpu(cell: str, questions: List[Dict], model: str,
                  max_model_len: int, gpu_util: float) -> Dict:
    import torch  # noqa: F401
    from vllm import SamplingParams
    for k, v in _cell_env(cell).items():
        os.environ[k] = v
    if cell == "bf16":
        from vllm import LLM
        llm = LLM(model=model, max_model_len=max_model_len,
                  gpu_memory_utilization=gpu_util, dtype="bfloat16", max_num_seqs=8)
    else:
        from kv_policy.int4_protected import Int4ProtectedLLM
        llm = Int4ProtectedLLM(model=model, max_model_len=max_model_len,
                               gpu_memory_utilization=gpu_util, max_num_seqs=8)
    sp = SamplingParams(temperature=0.0, max_tokens=4)
    prompts = [build_prompt(q["q"], q["choices"]) for q in questions]
    outs = llm.generate(prompts, sp)
    preds = [parse_answer(o.outputs[0].text) for o in outs]
    answers = [q["answer"] for q in questions]
    s = score(preds, answers)
    s["cell"] = cell
    return s


def _run_cell_dry(cell: str, questions: List[Dict]) -> Dict:
    """Fake model: bf16 'knows' the answer; protected simulates ~2pt loss.
    Exercises the full schema/plumbing with no GPU."""
    import random
    rng = random.Random(0 if cell == "bf16" else 7)
    answers = [q["answer"] for q in questions]
    if cell == "bf16":
        preds = answers[:]  # perfect
    else:
        # drop ~1 in N to simulate small quant loss
        preds = [a if rng.random() > 0.05 else (a + 1) % 4 for a in answers]
    s = score(preds, answers)
    s["cell"] = cell
    return s


# ---------------------------------------------------------------------------
def _selftest() -> int:
    # build_prompt: contains the question, all 4 lettered choices, 'Answer:'.
    p = build_prompt("Capital of France?", ["Berlin", "Paris", "Rome", "Madrid"])
    assert "A. Berlin" in p and "B. Paris" in p and "D. Madrid" in p, p
    assert p.rstrip().endswith("Answer:"), p
    print("  build_prompt: PASS")

    # parse_answer: many formats.
    assert parse_answer("B") == 1
    assert parse_answer(" The answer is C.") == 2
    assert parse_answer("(D)") == 3
    assert parse_answer("A. Berlin") == 0
    assert parse_answer("") is None
    assert parse_answer("I don't know") is None  # no standalone A-D
    print("  parse_answer (A/B/C/D, prose, parens, empty): PASS")

    # score: counts correct + unparsed.
    s = score([0, 1, None, 3], [0, 2, 2, 3])
    assert s["n"] == 4 and s["correct"] == 2 and s["unparsed"] == 1
    assert abs(s["accuracy_pct"] - 50.0) < 1e-9, s
    print(f"  score (2/4 correct, 1 unparsed -> {s['accuracy_pct']}%): PASS")

    # acceptance PASS: within 1pt.
    a = acceptance(67.0, 66.5, DEFAULT_TOL_PCT)
    assert a["status"] == "PASS" and a["within_tolerance"], a
    print("  acceptance within tol -> PASS: PASS")

    # acceptance FAIL: 3pt drop, not collapse.
    a = acceptance(67.0, 64.0, DEFAULT_TOL_PCT)
    assert a["status"] == "FAIL" and not a["collapse_suspected"], a
    print("  acceptance 3pt drop -> FAIL: PASS")

    # acceptance COLLAPSE: protected near chance while bf16 high.
    a = acceptance(67.0, 26.0, DEFAULT_TOL_PCT)
    assert a["status"] == "COLLAPSE_SUSPECTED" and a["collapse_suspected"], a
    print("  acceptance near-chance -> COLLAPSE_SUSPECTED: PASS")

    # dry-run cells produce sane schema + bf16 perfect on built-ins.
    bf = _run_cell_dry("bf16", _BUILTIN_QA)
    pr = _run_cell_dry("protected", _BUILTIN_QA)
    assert bf["accuracy_pct"] == 100.0 and bf["cell"] == "bf16", bf
    assert 0.0 <= pr["accuracy_pct"] <= 100.0, pr
    print(f"  dry-run cells (bf16={bf['accuracy_pct']}% prot={pr['accuracy_pct']}%): PASS")

    print("\nself-test: 7/7 PASS")
    return 0


def _emit(report: Dict, out: Optional[Path]) -> None:
    print(json.dumps(report, indent=2))
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to: {out}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 6N MMLU quality bench (int4_protected)")
    ap.add_argument("--selftest", action="store_true",
                    help="CPU-only: test prompt/parse/score/acceptance (no GPU)")
    ap.add_argument("--dry-run", action="store_true",
                    help="CPU: run the full driver with a FAKE model (schema check)")
    ap.add_argument("--cells", default="bf16,protected",
                    help="comma-separated: bf16,protected")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--num-questions", type=int, default=200)
    ap.add_argument("--tol-pct", type=float, default=DEFAULT_TOL_PCT)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    cells = [c.strip() for c in args.cells.split(",") if c.strip()]

    if args.dry_run:
        questions = _BUILTIN_QA
        results = {c: _run_cell_dry(c, questions) for c in cells}
        n_used = len(questions)
        source = "BUILTIN (dry-run; NOT real MMLU)"
    else:
        questions = _load_mmlu(args.num_questions)
        n_used = len(questions)
        results = {c: _run_cell_gpu(c, questions, args.model,
                                    args.max_model_len, args.gpu_util)
                   for c in cells}
        source = f"cais/mmlu all/test [:{n_used}]"

    report = {
        "model": args.model, "n_questions": n_used, "source": source,
        "dry_run": bool(args.dry_run), "cells": results,
    }
    if "bf16" in results and "protected" in results:
        report["acceptance"] = acceptance(
            results["bf16"]["accuracy_pct"],
            results["protected"]["accuracy_pct"], args.tol_pct)
    _emit(report, args.out)
    # Exit nonzero if the gate did not pass (so CI/scripts can branch).
    acc = report.get("acceptance")
    return 0 if (acc is None or acc["status"] == "PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
