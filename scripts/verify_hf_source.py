#!/usr/bin/env python
"""Smoke test for `symbolu_bcvf_llm.sources.HuggingFaceSource`.

Runs against a small HuggingFace model (default `gpt2`, ~500 MB) to
verify the Source plumbing end-to-end before committing to a Llama
3.1 8B run:

  1. Constructor loads model + tokenizer (one-time cost).
  2. First `lookahead()` returns (L, V) fp32 probs and (L,) bool mask.
  3. Probabilities sum to ~1 per lookahead position.
  4. Sanity cross-check: argmax of `lookahead()[0]` at l=0 matches the
     next token `model.generate(..., max_new_tokens=1, do_sample=False)`
     would emit — confirms the KV-cache amortization doesn't drift.
  5. `commit(token)` advances context; next `lookahead()` reflects it.
  6. Teacher-forced scoring across §6's three scorers (vanilla, blend,
     trust) returns finite log-probs.

Prints a clear PASS/FAIL line per check. Exits 0 on all-pass, 1 on
any failure.

Logging:
  - Console: human-readable PASS/FAIL + progress.
  - File log: full DEBUG including env + git + per-check shapes /
    dtypes / numeric values. Default location
    `docs/experiments/verify_hf_source_<model-slug>.log`.
  - Manifest JSON: env, args, per-check outcome, exception if any.

Typical RunPod usage (after `pip install torch transformers`):

    python scripts/verify_hf_source.py
    python scripts/verify_hf_source.py --model sshleifer/tiny-gpt2

If this passes, `HuggingFaceSource` plumbing works and you can move
on to `python -m symbolu_bcvf_llm.benchmark --benchmark truthfulqa
--smoke --model <your-target-model>`.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

# Add the repo root to sys.path so `import symbolu_bcvf_llm` works when
# this script is run from anywhere.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from symbolu_bcvf_llm.logging_util import (  # noqa: E402
    configure_logging,
    format_exception,
    log_environment,
    write_manifest,
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _slug(model_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_name).strip("_")


def run_verification(
    model_name: str,
    L: int,
    out_dir: pathlib.Path,
    verbose: bool,
) -> int:
    """Returns 0 on all-pass, 1 on any failure. All state is logged."""
    results: List[CheckResult] = []
    slug = _slug(model_name)
    log_path = out_dir / f"verify_hf_source_{slug}.log"
    manifest_path = out_dir / f"verify_hf_source_{slug}.json"

    logger = configure_logging(log_path=log_path, verbose=verbose)
    logger.info("=" * 72)
    logger.info("verify_hf_source.py starting — model=%s  L=%d", model_name, L)
    logger.info("=" * 72)
    env_info = log_environment(logger)

    manifest: Dict[str, Any] = {
        "script": "scripts/verify_hf_source.py",
        "args": {"model": model_name, "L": L, "verbose": verbose},
        "output_paths": {
            "run_log": str(log_path),
            "manifest_json": str(manifest_path),
        },
        **env_info,
        "checks": [],
        "outcome": "PENDING",
    }
    write_manifest(manifest_path, manifest)

    t_start = time.perf_counter()

    # -------------------------------------------------------------- #
    # Load ML stack + model
    # -------------------------------------------------------------- #
    try:
        import numpy as np
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer
        logger.info(
            "numpy=%s torch=%s transformers=%s (CUDA=%s)",
            np.__version__, torch.__version__,
            transformers.__version__, torch.cuda.is_available(),
        )
    except ImportError as exc:
        logger.error("Missing ML stack: %s", exc)
        logger.error("Install with: pip install torch transformers")
        manifest["outcome"] = "EXCEPTION"
        manifest["exception"] = format_exception(exc)
        write_manifest(manifest_path, manifest)
        return 1

    try:
        logger.info("Loading model `%s` ...", model_name)
        t_load = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(model_name)
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
        load_s = time.perf_counter() - t_load
        logger.info(
            "Loaded in %.1f s (device=%s, dtype=%s, vocab_size=%d)",
            load_s, device, dtype, tokenizer.vocab_size,
        )
        manifest["model"] = {
            "name": model_name,
            "device": str(device),
            "dtype": str(dtype),
            "vocab_size": int(tokenizer.vocab_size),
            "eos_token_id": (
                int(tokenizer.eos_token_id)
                if tokenizer.eos_token_id is not None else None
            ),
            "load_seconds": round(load_s, 2),
        }
        write_manifest(manifest_path, manifest)
    except Exception as exc:
        logger.error("Failed to load model / tokenizer:")
        logger.error(traceback.format_exc())
        manifest["outcome"] = "EXCEPTION"
        manifest["exception"] = format_exception(exc)
        write_manifest(manifest_path, manifest)
        return 1

    from symbolu_bcvf_llm.sources.huggingface import HuggingFaceSource
    from symbolu_bcvf_llm.benchmark.scoring import (
        score_choice_blend,
        score_choice_trust,
        score_choice_vanilla,
    )

    def add_check(name: str, ok: bool, detail: str = "") -> None:
        r = CheckResult(name=name, passed=ok, detail=detail)
        results.append(r)
        mark = "PASS" if ok else "FAIL"
        logger.info("[%s] %s — %s", mark, name, detail)
        manifest["checks"].append(asdict(r))
        write_manifest(manifest_path, manifest)

    prompt = "The capital of France is"
    logger.debug("Prompt: %r", prompt)

    # Reference next-token from model.generate for the KV-cache cross-check.
    ref_inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.inference_mode():
        ref_out = model.generate(
            **ref_inputs, max_new_tokens=1, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    ref_next_token = int(ref_out[0, -1])
    logger.debug(
        "model.generate reference next token: %d (%r)",
        ref_next_token, tokenizer.decode([ref_next_token]),
    )

    # -------------------------------------------------------------- #
    # Check 1 — constructor
    # -------------------------------------------------------------- #
    try:
        src = HuggingFaceSource(
            model=model, tokenizer=tokenizer, prompt=prompt, L=L
        )
        add_check(
            "1. HuggingFaceSource constructor",
            True,
            f"vocab_size={src.vocab_size}, L={src.L}, "
            f"eos_token_id={src.eos_token_id}",
        )
    except Exception as exc:
        logger.error(traceback.format_exc())
        add_check("1. HuggingFaceSource constructor", False, repr(exc))
        return _finalize(manifest, manifest_path, logger, t_start, results)

    # -------------------------------------------------------------- #
    # Check 2 — first lookahead shape + dtype + mask
    # -------------------------------------------------------------- #
    try:
        probs, mask = src.lookahead()
        ok_shape = probs.shape == (L, src.vocab_size) and mask.shape == (L,)
        ok_dtype = probs.dtype.name == "float32" and mask.dtype.name == "bool"
        add_check(
            "2. lookahead() shape + dtype (fp32)",
            ok_shape and ok_dtype,
            f"probs.shape={probs.shape}, probs.dtype={probs.dtype}, "
            f"mask.shape={mask.shape}, mask.dtype={mask.dtype}",
        )
    except Exception as exc:
        logger.error(traceback.format_exc())
        add_check("2. lookahead() shape + dtype (fp32)", False, repr(exc))
        return _finalize(manifest, manifest_path, logger, t_start, results)

    # -------------------------------------------------------------- #
    # Check 3 — probabilities sum to ~1 per position
    # -------------------------------------------------------------- #
    row_sums = probs.sum(axis=-1)
    max_abs_dev = float(np.max(np.abs(row_sums - 1.0)))
    add_check(
        "3. Σ p per lookahead position ≈ 1",
        max_abs_dev < 1e-4,
        f"max|Σp - 1| = {max_abs_dev:.2e}  (row_sums={row_sums.tolist()})",
    )

    # -------------------------------------------------------------- #
    # Check 4 — argmax(l=0) matches model.generate reference
    # -------------------------------------------------------------- #
    hf_next_token = int(np.argmax(probs[0]))
    add_check(
        "4. argmax(lookahead[l=0]) matches model.generate",
        hf_next_token == ref_next_token,
        f"HF Source: {hf_next_token} ({tokenizer.decode([hf_next_token])!r})  "
        f"vs  model.generate: {ref_next_token} "
        f"({tokenizer.decode([ref_next_token])!r})",
    )

    # -------------------------------------------------------------- #
    # Check 5 — commit advances context
    # -------------------------------------------------------------- #
    try:
        probs_before, _ = src.lookahead()
        src.commit(hf_next_token)
        probs_after, _ = src.lookahead()
        differs = not np.array_equal(probs_before, probs_after)
        add_check(
            "5. commit(token) advances context",
            differs,
            "post-commit lookahead differs from pre-commit",
        )
    except Exception as exc:
        logger.error(traceback.format_exc())
        add_check("5. commit(token) advances context", False, repr(exc))

    # -------------------------------------------------------------- #
    # Check 6 — teacher-forced scoring via all three §6 scorers
    # -------------------------------------------------------------- #
    def make_three() -> List[HuggingFaceSource]:
        return [
            HuggingFaceSource(model, tokenizer, prompt, L=L) for _ in range(3)
        ]

    target_text = " Paris"
    target_tokens = tokenizer.encode(target_text, add_special_tokens=False)[:2]
    if not target_tokens:
        target_tokens = [ref_next_token]
    logger.debug(
        "Teacher-forced target: %r → tokens %s",
        target_text, target_tokens,
    )

    for scorer_name, scorer_fn in [
        ("vanilla", score_choice_vanilla),
        ("blend", score_choice_blend),
        ("trust", score_choice_trust),
    ]:
        try:
            srcs = make_three()
            t0 = time.perf_counter()
            score = scorer_fn(srcs, target_tokens)
            elapsed = time.perf_counter() - t0
            ok = bool(np.isfinite(score)) and score < 0
            add_check(
                f"6.{scorer_name}. teacher-forced score_choice_{scorer_name}",
                ok,
                f"log P({target_text!r})={score:.3f}  "
                f"(scored in {elapsed * 1000:.1f} ms)",
            )
        except Exception as exc:
            logger.error(traceback.format_exc())
            add_check(
                f"6.{scorer_name}. teacher-forced score_choice_{scorer_name}",
                False, repr(exc),
            )

    return _finalize(manifest, manifest_path, logger, t_start, results)


def _finalize(
    manifest: Dict[str, Any],
    manifest_path: pathlib.Path,
    logger,
    t_start: float,
    results: List[CheckResult],
) -> int:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    duration_s = round(time.perf_counter() - t_start, 2)
    manifest["duration_s"] = duration_s
    manifest["outcome"] = "PASS" if passed == total and total > 0 else "FAIL"
    manifest["summary"] = {"passed": passed, "total": total}
    write_manifest(manifest_path, manifest)

    logger.info("")
    logger.info("Summary: %d/%d checks passed in %.1f s", passed, total, duration_s)
    logger.info("Run log:  %s", manifest["output_paths"]["run_log"])
    logger.info("Manifest: %s", manifest["output_paths"]["manifest_json"])
    return 0 if passed == total and total > 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Smoke test HuggingFaceSource against a small model."
    )
    parser.add_argument(
        "--model", default="gpt2",
        help="HuggingFace model name (default gpt2 ~500 MB, CPU-viable). "
             "For a smaller footprint try sshleifer/tiny-gpt2.",
    )
    parser.add_argument("--L", type=int, default=5)
    parser.add_argument(
        "--out-dir", type=pathlib.Path,
        default=_REPO_ROOT / "docs" / "experiments",
        help="destination for run log + manifest JSON",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="DEBUG on console (file log is always DEBUG)",
    )
    args = parser.parse_args(argv)
    try:
        return run_verification(
            model_name=args.model,
            L=args.L,
            out_dir=args.out_dir,
            verbose=args.verbose,
        )
    except Exception as exc:  # last-resort catch — logger may not be set up
        print(f"FATAL unhandled exception: {exc!r}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
