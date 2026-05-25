#!/usr/bin/env python3
"""verify_phase5b_5_needle.py — Phase 5B.5 quality acceptance.

Needle-in-haystack retrieval test for the int4_protected backend.

Pattern: plant a unique unmistakable code (e.g., "QM7-K3F-9XZ") inside
a filler-text context of varying length. Ask the model to recall the
code. Repeat across context lengths and needle positions. Compare
retrieval rate to stock vLLM at the same prompts.

For each trial:
  - Build prompt: [intro] [filler_before] [needle line] [filler_after] [question]
  - Decode <= max_tokens tokens
  - Check if needle code appears anywhere in the decoded text
  - Stock and int4 use the SAME prompts so the comparison is apples-to-apples

Test matrix:
  - 5 unique needle codes
  - 3 context lengths: ~200, ~600, ~1200 filler-token total
  - For each (code, length): one trial with needle in the MIDDLE of the
    filler (worst case — both prefixes and suffixes to attend through)
  = 15 trials total

Gate: int4 retrieval rate >= stock retrieval rate - 0.10 (within 10%
absolute of stock). Stock should be ~100% on this fixture; we accept
modest int4 degradation. Lock protect_fraction (currently 4% by
artifact name) if int4 retrieval rate >= 80% in absolute terms.

Args:
  --protect-mask-path  override $PROTECT_MASK_PATH
  --max-tokens         decode length cap (default 64)
  --max-model-len      vLLM max context (default 4096)
  --num-needles        prompts per length bucket (default 5)
  --lengths            comma-separated filler-token budgets (default 200,600,1200)
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
import random
import string
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


# Filler corpus — varied factual / declarative sentences that don't
# coincidentally contain alphanumeric codes resembling needles.
FILLER_SENTENCES = [
    "The river flowed gently through the valley, past forests of pine and oak.",
    "Many travelers had crossed this bridge over the centuries.",
    "The library held thousands of books in dozens of languages.",
    "Mountain peaks rose above the clouds in the distant west.",
    "Each morning the baker started work before the first light of dawn.",
    "Ancient ruins stood at the edge of the meadow, half-covered in moss.",
    "The marketplace bustled with vendors selling fruits and spices.",
    "Quiet streams fed into a wide lake that mirrored the autumn sky.",
    "Old maps in the museum showed cities that no longer existed.",
    "Stone walls separated the gardens from the orchards beyond.",
    "Lanterns along the path glowed softly after the sun had set.",
    "The harbor was full of ships preparing for the evening tide.",
    "Birds returned to the same trees each spring for many years.",
    "A long road stretched eastward toward the snow-capped highlands.",
    "Workshops in the village specialized in pottery and woodwork.",
    "Children gathered in the square to listen to the storyteller.",
    "Wild herbs grew along the cliff path overlooking the bay.",
    "The clocktower struck the hour and crows scattered from the roof.",
    "Light snow began to fall over the rooftops of the old town.",
    "A small inn at the crossroads welcomed weary travelers each night.",
]


def _make_needle(rng: random.Random) -> str:
    """Make a unique alphanumeric code unlikely to occur in filler."""
    chars = string.ascii_uppercase + string.digits
    return f"{''.join(rng.choices(chars, k=3))}-{''.join(rng.choices(chars, k=3))}-{''.join(rng.choices(chars, k=3))}"


def _build_prompt(needle: str, filler_target_tokens: int, rng: random.Random) -> str:
    """Build a needle-in-haystack prompt with the needle in the middle of
    `filler_target_tokens` worth of filler sentences (rough estimate via
    char count: 1 token ~ 4 chars).
    """
    half_chars = filler_target_tokens * 4 // 2
    before, after = [], []
    while sum(len(s) for s in before) < half_chars:
        before.append(rng.choice(FILLER_SENTENCES))
    while sum(len(s) for s in after) < half_chars:
        after.append(rng.choice(FILLER_SENTENCES))

    prompt = (
        "Read the following passage carefully. There is a special code "
        "hidden somewhere in the middle. Remember it.\n\n"
        + " ".join(before) + "\n\n"
        + f"SPECIAL CODE: {needle}\n\n"
        + " ".join(after) + "\n\n"
        + "Question: What was the SPECIAL CODE in the passage?\n"
        + "Answer: The special code is"
    )
    return prompt


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    raise RuntimeError("Could not locate the inner nn.Module.")


def _gen_stock(prompts: List[str], args) -> List[str]:
    import torch
    from vllm import LLM, SamplingParams
    print("[1/2] Stock vLLM (kv_cache_dtype=auto)...")
    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        block_size=args.block_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
    outs = llm.generate(prompts, sampling)
    texts = [o.outputs[0].text for o in outs]
    del llm; gc.collect(); torch.cuda.empty_cache()
    return texts


def _gen_int4(prompts: List[str], args) -> Tuple[List[str], Dict[str, int]]:
    import torch
    from vllm import LLM, SamplingParams
    from kv_policy.phase5b_backend_install import (
        enable_int4_protected_backend, install_int4_protected_backend,
        Int4ProtectedAttentionImpl,
    )

    print("[2/2] int4_protected backend...")
    enable_int4_protected_backend()
    Int4ProtectedAttentionImpl.reset_call_stats()
    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        kv_cache_dtype="int4_protected",
        block_size=args.block_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    model = _find_inner_model(llm)
    install_int4_protected_backend(model)
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    texts: List[str] = []
    for i, p in enumerate(prompts, 1):
        print(f"  int4 prompt {i}/{len(prompts)} ({len(p)} chars)...")
        with torch.inference_mode():
            for _, sub in model.named_modules():
                impl = getattr(sub, "impl", None)
                if isinstance(impl, Int4ProtectedAttentionImpl):
                    w = getattr(impl, "_phase5b_paged_writer", None)
                    if w is not None:
                        # Phase 7 fix: reset ALL seqs (not just default) so
                        # stale SeqStates from prior prompts don't carry
                        # accumulated seq_pos into a new prompt. vLLM
                        # recycles block_ids across generate calls; on
                        # models with tight KV-cache budgets (e.g.
                        # Qwen2.5-14B with ~3.6K blocks) collisions happen
                        # within 5-10 prompts and cause bf16-backing
                        # overflow. `reset_sequence("all")` evicts every
                        # SeqState (per B-pre-1 fix `1f04819`); next write
                        # to any seq_id lazily allocates a fresh slot.
                        w.reset_sequence("all")
        out = llm.generate([p], sampling)
        texts.append(out[0].outputs[0].text)

    stats = Int4ProtectedAttentionImpl.get_call_stats()
    del llm, model; gc.collect(); torch.cuda.empty_cache()
    return texts, stats


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",          type=int,   default=4096)
    parser.add_argument("--max-tokens",             type=int,   default=64)
    parser.add_argument("--block-size",             type=int,   default=32)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--num-needles",            type=int,   default=5,
                        help="number of needle prompts per length bucket")
    parser.add_argument("--lengths",                default="200,600,1200",
                        help="comma-separated filler-token-budget values")
    parser.add_argument("--seed",                   type=int,   default=42)
    parser.add_argument("--protect-mask-path",      default=None,
                        help="override $PROTECT_MASK_PATH")
    parser.add_argument("--protect-fraction",       type=float, default=0.04,
                        help="protect_fraction encoded in the mask filename "
                             "(only affects auto-derivation of the default "
                             "mask path when --protect-mask-path is not set)")
    parser.add_argument("--abs-pass-threshold",     type=float, default=0.80,
                        help="absolute retrieval-rate gate for int4")
    parser.add_argument("--rel-pass-margin",        type=float, default=0.10,
                        help="int4 must be within this margin of stock retrieval rate")
    args = parser.parse_args(argv)

    if args.block_size != 32:
        print(f"FAIL: block-size must be 32 (got {args.block_size})."); return 1

    try:
        import torch
        from vllm import SamplingParams
    except ImportError as e:
        print(f"FAIL: import error ({e})."); return 1

    if args.protect_mask_path:
        os.environ["PROTECT_MASK_PATH"] = args.protect_mask_path
    # Phase 7: derive default mask path from --model id (slug match with
    # calibrate_phase5b_protect_mask.py auto-derivation), so this verify
    # works on any calibrated model without manually setting the env var.
    if "PROTECT_MASK_PATH" not in os.environ:
        slug = args.model.split("/")[-1].lower()
        for ch in (".", "-"):
            slug = slug.replace(ch, "_")
        pct = int(round(args.protect_fraction * 100))
        os.environ["PROTECT_MASK_PATH"] = (
            f"/workspace/dev/build-logs/{slug}_protect_mask_{pct}pct.pt"
        )
    mask_path = os.environ["PROTECT_MASK_PATH"]
    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'.")
        print(f"      Run calibration first:")
        print(f"        /workspace/venv-vllm/bin/python3 \\")
        print(f"            /workspace/symbolu/CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \\")
        print(f"            --model {args.model} --protect-fraction {args.protect_fraction}")
        return 1

    print("=" * 78)
    print("Phase 5B.5 — needle-in-haystack quality acceptance")
    print("=" * 78)
    print(f"  model:             {args.model}")
    print(f"  max_model_len:     {args.max_model_len}")
    print(f"  max_tokens:        {args.max_tokens}")
    print(f"  block_size:        {args.block_size}")
    print(f"  protect_mask path: {mask_path}")
    print(f"  num_needles:       {args.num_needles}")
    print(f"  lengths:           {args.lengths}")
    print()

    rng = random.Random(args.seed)
    lengths = [int(x) for x in args.lengths.split(",")]

    # Build the trial corpus.
    trials: List[Dict[str, Any]] = []
    for L in lengths:
        for k in range(args.num_needles):
            needle = _make_needle(rng)
            prompt = _build_prompt(needle, L, rng)
            trials.append({
                "id":          f"L{L}_n{k}",
                "needle":      needle,
                "filler_tgt":  L,
                "prompt_chars": len(prompt),
                "prompt":      prompt,
            })
    prompts = [t["prompt"] for t in trials]
    print(f"  built {len(trials)} trial prompts; "
          f"sizes {min(len(p) for p in prompts)}-{max(len(p) for p in prompts)} chars")
    print()

    stock_texts = _gen_stock(prompts, args)
    int4_texts, call_stats = _gen_int4(prompts, args)

    # Score retrieval per trial.
    print()
    print("=" * 78)
    print("Per-trial results")
    print("=" * 78)
    print(f"  {'trial':<14} {'needle':<13} {'stock?':<8} {'int4?':<8} agreement")
    per_trial: List[Dict[str, Any]] = []
    for t, stk, i4 in zip(trials, stock_texts, int4_texts):
        s_hit = t["needle"] in stk
        i_hit = t["needle"] in i4
        agree = "yes" if s_hit == i_hit else "DIVERGE"
        per_trial.append({
            "id": t["id"], "needle": t["needle"], "filler_tgt": t["filler_tgt"],
            "stock_hit": s_hit, "int4_hit": i_hit,
            "stock_text": stk, "int4_text": i4,
        })
        print(f"  {t['id']:<14} {t['needle']:<13} "
              f"{'HIT' if s_hit else 'miss':<8} "
              f"{'HIT' if i_hit else 'miss':<8} {agree}")

    # Aggregate.
    n = len(per_trial)
    stock_rate = sum(1 for p in per_trial if p["stock_hit"]) / n
    int4_rate  = sum(1 for p in per_trial if p["int4_hit"])  / n
    n_agree    = sum(1 for p in per_trial if p["stock_hit"] == p["int4_hit"])

    # By length bucket
    by_len: Dict[int, Tuple[int, int, int]] = {}
    for p in per_trial:
        L = p["filler_tgt"]
        s, i, total = by_len.get(L, (0, 0, 0))
        by_len[L] = (s + int(p["stock_hit"]), i + int(p["int4_hit"]), total + 1)

    print()
    print("=" * 78)
    print("Aggregate")
    print("=" * 78)
    print(f"  total trials:           {n}")
    print(f"  stock retrieval rate:   {stock_rate*100:5.1f}%  ({sum(1 for p in per_trial if p['stock_hit'])}/{n})")
    print(f"  int4  retrieval rate:   {int4_rate*100:5.1f}%  ({sum(1 for p in per_trial if p['int4_hit'])}/{n})")
    print(f"  agreement:              {n_agree*100/n:5.1f}%  ({n_agree}/{n})")
    print()
    print("  by length bucket:")
    print(f"    {'L (filler tok)':<18} {'stock':<10} {'int4':<10}")
    for L in sorted(by_len.keys()):
        s_hits, i_hits, total = by_len[L]
        print(f"    {L:<18} {s_hits}/{total} ({100*s_hits/total:3.0f}%)  "
              f"{i_hits}/{total} ({100*i_hits/total:3.0f}%)")
    print()
    print("  int4_protected call stats:")
    for k, v in call_stats.items():
        print(f"    {k}: {v}")

    # ----- Gates -----
    print()
    print("=" * 78)
    print("Gates")
    print("=" * 78)
    gates = []
    gates.append((
        f"int4 retrieval >= {args.abs_pass_threshold*100:.0f}% absolute",
        int4_rate >= args.abs_pass_threshold,
    ))
    gates.append((
        f"int4 retrieval >= stock - {args.rel_pass_margin*100:.0f}% (relative)",
        int4_rate >= stock_rate - args.rel_pass_margin,
    ))
    gates.append((
        "0 packed-decode fallbacks",
        call_stats.get("decode_calls_fallback", 0) == 0,
    ))
    gates.append((
        "0 write fallbacks",
        call_stats.get("write_path_fallback", 0) == 0,
    ))

    ok = True
    for label, passed in gates:
        marker = "PASS" if passed else "FAIL"
        if not passed: ok = False
        print(f"  [{marker}] {label}")

    print()
    if ok:
        print("Phase 5B.5 needle: GREEN")
        print(f"  protect_mask at '{mask_path}' holds quality at the gate.")
        return 0
    print("Phase 5B.5 needle: FAIL")
    print(f"  protect_mask at '{mask_path}' insufficient. Consider calibrating")
    print(f"  at a higher protect_fraction (e.g., 6% or 8%) and re-running with")
    print(f"  --protect-mask-path /path/to/qwen2_5_7b_protect_mask_8pct.pt")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
