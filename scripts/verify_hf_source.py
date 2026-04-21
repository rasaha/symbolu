#!/usr/bin/env python
"""Smoke test for `symbolu_bcvf_llm.sources.HuggingFaceSource`.

Runs against a small HuggingFace model (default `gpt2`, ~500 MB) to
verify the Source plumbing end-to-end before committing to a Llama
3.1 8B run:

  1. Constructor loads model + tokenizer (one-time cost).
  2. First `lookahead()` returns (L, V) fp32 probs and (L,) bool mask.
  3. Probabilities sum to ~1 per lookahead position.
  4. `commit(token)` advances context; next `lookahead()` reflects it.
  5. Teacher-forced scoring across §6's three scorers (vanilla, blend,
     trust) returns finite log-probs.
  6. Sanity cross-check: argmax of `lookahead()[0]` at l=0 matches the
     next token `model.generate(..., max_new_tokens=1, do_sample=False)`
     would emit — confirms the KV-cache amortization doesn't drift.

Prints a clear PASS/FAIL line per check. Exits 0 on all-pass, 1 on
any failure.

Typical RunPod usage (after `pip install torch transformers`):

    python scripts/verify_hf_source.py
    python scripts/verify_hf_source.py --model sshleifer/tiny-gpt2

If this passes, `HuggingFaceSource` plumbing works and you can move
on to `python -m symbolu_bcvf_llm.benchmark --benchmark truthfulqa
--smoke --model <your-target-model>`.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass
from typing import List

# Add the repo root to sys.path so `import symbolu_bcvf_llm` works when
# this script is run from anywhere.
import pathlib
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _print_result(r: CheckResult) -> None:
    mark = "PASS" if r.passed else "FAIL"
    msg = f"  [{mark}] {r.name}"
    if r.detail:
        msg += f" — {r.detail}"
    print(msg)


def _require(condition: bool, description: str, detail: str = "") -> CheckResult:
    return CheckResult(name=description, passed=condition, detail=detail)


def run_verification(model_name: str, L: int = 5, verbose: bool = True) -> int:
    """Returns 0 on all-pass, 1 on any failure."""
    results: List[CheckResult] = []

    print(f"Loading model `{model_name}` ...", flush=True)
    try:
        import numpy as np  # noqa: F401 — tested below
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        print(f"FATAL: missing ML stack ({exc}). Install with:")
        print("  pip install torch transformers")
        return 1

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        # Use fp32 on CPU, fp16/bf16 on GPU per §2.7.2 boundary rule.
        if torch.cuda.is_available():
            dtype = torch.float16
            device = "cuda"
        else:
            dtype = torch.float32
            device = "cpu"
        model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=dtype
        ).to(device)
        model.eval()
    except Exception:
        print("FATAL: could not load model / tokenizer:")
        traceback.print_exc()
        return 1

    print(f"Loaded (device={device}, dtype={dtype}).")
    print()

    from symbolu_bcvf_llm.sources.huggingface import HuggingFaceSource
    from symbolu_bcvf_llm.benchmark.scoring import (
        score_choice_blend,
        score_choice_trust,
        score_choice_vanilla,
    )

    prompt = "The capital of France is"
    # Compute a reference next-token id via model.generate for the
    # KV-cache cross-check (step 6).
    ref_inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.inference_mode():
        ref_out = model.generate(
            **ref_inputs, max_new_tokens=1, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    ref_next_token = int(ref_out[0, -1])

    # -------------------------------------------------------------- #
    # Check 1 — constructor
    # -------------------------------------------------------------- #
    print("Running checks ...")
    try:
        src = HuggingFaceSource(
            model=model, tokenizer=tokenizer, prompt=prompt, L=L
        )
        results.append(_require(
            True, "1. HuggingFaceSource constructor",
            f"vocab_size={src.vocab_size}, L={src.L}"
        ))
    except Exception as exc:
        results.append(_require(False, "1. HuggingFaceSource constructor", str(exc)))
        for r in results: _print_result(r)
        return 1

    # -------------------------------------------------------------- #
    # Check 2 — first lookahead shape + dtype + mask
    # -------------------------------------------------------------- #
    try:
        probs, mask = src.lookahead()
        ok_shape = probs.shape == (L, src.vocab_size) and mask.shape == (L,)
        ok_dtype = probs.dtype.name == "float32" and mask.dtype.name == "bool"
        results.append(_require(
            ok_shape and ok_dtype,
            "2. lookahead() shape + dtype (fp32)",
            f"probs.shape={probs.shape}, probs.dtype={probs.dtype}, "
            f"mask.shape={mask.shape}, mask.dtype={mask.dtype}",
        ))
    except Exception as exc:
        results.append(_require(False, "2. lookahead() shape + dtype (fp32)", str(exc)))
        for r in results: _print_result(r)
        return 1

    # -------------------------------------------------------------- #
    # Check 3 — probabilities sum to ~1 per position
    # -------------------------------------------------------------- #
    import numpy as np
    row_sums = probs.sum(axis=-1)
    max_abs_dev = float(np.max(np.abs(row_sums - 1.0)))
    results.append(_require(
        max_abs_dev < 1e-4,
        "3. Σ p per lookahead position ≈ 1",
        f"max|Σp - 1| = {max_abs_dev:.2e}",
    ))

    # -------------------------------------------------------------- #
    # Check 4 — argmax(l=0) matches model.generate reference
    # -------------------------------------------------------------- #
    hf_next_token = int(np.argmax(probs[0]))
    results.append(_require(
        hf_next_token == ref_next_token,
        "4. argmax(lookahead[l=0]) matches model.generate",
        f"HF Source: {hf_next_token} ({tokenizer.decode([hf_next_token])!r}); "
        f"model.generate: {ref_next_token} ({tokenizer.decode([ref_next_token])!r})",
    ))

    # -------------------------------------------------------------- #
    # Check 5 — commit advances context
    # -------------------------------------------------------------- #
    try:
        probs_before_commit, _ = src.lookahead()
        src.commit(hf_next_token)
        probs_after_commit, _ = src.lookahead()
        # After committing a token, the new lookahead[l=0] should equal the
        # previous lookahead[l=1] (modulo fp32 rounding from the roll +
        # the advance forward-pass re-emitting the same position's logits).
        # Weaker but sufficient sanity: the two arrays should differ.
        differs = not np.array_equal(probs_before_commit, probs_after_commit)
        results.append(_require(
            differs,
            "5. commit(token) advances context",
            "post-commit lookahead differs from pre-commit",
        ))
    except Exception as exc:
        results.append(_require(False, "5. commit(token) advances context", str(exc)))

    # -------------------------------------------------------------- #
    # Check 6 — teacher-forced scoring via all three §6 scorers
    # -------------------------------------------------------------- #
    # Reset by building a fresh triple of sources; score a short choice.
    def make_three_sources():
        return [
            HuggingFaceSource(model, tokenizer, prompt, L=L) for _ in range(3)
        ]

    # Choose a 2-token target string; tokenize it.
    target_text = " Paris"
    target_tokens = tokenizer.encode(target_text, add_special_tokens=False)[:2]
    if not target_tokens:
        target_tokens = [ref_next_token]

    for scorer_name, scorer_fn in [
        ("vanilla", score_choice_vanilla),
        ("blend", score_choice_blend),
        ("trust", score_choice_trust),
    ]:
        try:
            srcs = make_three_sources()
            score = scorer_fn(srcs, target_tokens)
            is_finite = np.isfinite(score)
            results.append(_require(
                bool(is_finite) and score < 0,
                f"6.{scorer_name}. teacher-forced score_choice_{scorer_name}",
                f"log P({target_text!r}) = {score:.3f}",
            ))
        except Exception as exc:
            traceback.print_exc()
            results.append(_require(
                False,
                f"6.{scorer_name}. teacher-forced score_choice_{scorer_name}",
                str(exc),
            ))

    # -------------------------------------------------------------- #
    # Report
    # -------------------------------------------------------------- #
    print()
    for r in results:
        _print_result(r)
    print()
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"Summary: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Smoke test HuggingFaceSource against a small model."
    )
    parser.add_argument(
        "--model",
        default="gpt2",
        help="HuggingFace model name (default gpt2 ~500 MB, CPU-viable). "
             "For a smaller footprint try sshleifer/tiny-gpt2.",
    )
    parser.add_argument("--L", type=int, default=5)
    args = parser.parse_args(argv)
    return run_verification(model_name=args.model, L=args.L)


if __name__ == "__main__":
    raise SystemExit(main())
