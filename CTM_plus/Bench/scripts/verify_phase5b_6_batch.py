#!/usr/bin/env python3
"""verify_phase5b_6_batch.py — Phase 5B.6 multi-batch acceptance.

Phase 5B.6 step 4: confirm batched decode produces the same output as
serial decode. Test plan:

  T1 — Serial baseline:
       Run prompt A alone (llm.generate([pA])). Capture text_A_serial.
       Reset writer state, run prompt B alone. Capture text_B_serial.

  T2 — Batched run:
       Run both prompts in one call (llm.generate([pA, pB])).
       Capture text_A_batched, text_B_batched.

  T3 — Compare:
       text_A_serial should equal text_A_batched (greedy invariance).
       text_B_serial should equal text_B_batched.

If any pair differs, the multi-seq read/write path is broken.

This script:
  - Uses the Phase 5C clean API (import kv_policy.int4_protected).
  - Resets the writer's SeqState between serial runs via
    `for impl: writer.reset_sequence("all")`.
  - Calls writer.evict_sequence(seq_id) on completion to release per-seq
    memory (best-effort; vLLM 0.7.3 doesn't have a clean hook for seq
    completion, so the verify works around it by tearing down the LLM
    between Test A and Test B).

Notes:
  - vLLM V0 engine with default config does prefill single-seq per
    forward call. So the WRITE path's "multi-seq prefill" branch
    isn't exercised here — only multi-seq decode.
  - For mixed prefill+decode batched (chunked prefill), see
    Phase 5B.7 (future).

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_6_batch.py
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


PROMPT_A = (
    "The secret code is XYZ123. Repeat the secret code in the next "
    "sentence.\nThe secret code is"
)
PROMPT_B = (
    "Roses are red, violets are"
)


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
    raise RuntimeError("Could not locate inner nn.Module.")


def _reset_all_seq_states(model):
    """Reset writer.reset_sequence('all') on every layer's impl. Run
    inside torch.inference_mode() because the writer's tensors are
    allocated under vLLM's inference_mode and can't be in-place
    modified outside it."""
    import torch
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    with torch.inference_mode():
        for _, sub in model.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    w.reset_sequence("all")


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-tokens",    type=int, default=32)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    args = parser.parse_args(argv)

    try:
        import torch
        from vllm import SamplingParams
        import kv_policy.int4_protected
        from kv_policy.int4_protected import Int4ProtectedLLM
        from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    except ImportError as e:
        print(f"FAIL: import error ({e})."); return 1

    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'."); return 1

    print("=" * 78)
    print("Phase 5B.6 batched-decode acceptance")
    print("=" * 78)
    print(f"  model:           {args.model}")
    print(f"  max_model_len:   {args.max_model_len}")
    print(f"  max_tokens:      {args.max_tokens}")
    print(f"  prompt A:        {PROMPT_A[:60]!r}...")
    print(f"  prompt B:        {PROMPT_B!r}")
    print()

    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    # --- Test 1: Serial baseline (separate LLM instances for clean state). ---
    print("[T1] Serial — prompt A alone")
    llm = Int4ProtectedLLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
    )
    out = llm.generate([PROMPT_A], sampling)
    text_A_serial = out[0].outputs[0].text
    print(f"  A_serial: {text_A_serial!r}")
    Int4ProtectedAttentionImpl.reset_call_stats()
    del llm; gc.collect(); torch.cuda.empty_cache()

    print()
    print("[T1] Serial — prompt B alone")
    llm = Int4ProtectedLLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
    )
    out = llm.generate([PROMPT_B], sampling)
    text_B_serial = out[0].outputs[0].text
    print(f"  B_serial: {text_B_serial!r}")
    del llm; gc.collect(); torch.cuda.empty_cache()

    # --- Test 2: Batched run (both prompts in one llm.generate). ---
    print()
    print("[T2] Batched — prompts [A, B] together")
    Int4ProtectedAttentionImpl.reset_call_stats()
    llm = Int4ProtectedLLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
    )
    outs = llm.generate([PROMPT_A, PROMPT_B], sampling)
    text_A_batched = outs[0].outputs[0].text
    text_B_batched = outs[1].outputs[0].text
    call_stats = Int4ProtectedAttentionImpl.get_call_stats()
    print(f"  A_batched: {text_A_batched!r}")
    print(f"  B_batched: {text_B_batched!r}")
    print(f"  call_stats: {call_stats}")
    del llm; gc.collect(); torch.cuda.empty_cache()

    # --- Test 3: Compare ---
    print()
    print("[T3] Compare")
    a_match = (text_A_serial == text_A_batched)
    b_match = (text_B_serial == text_B_batched)

    def _common_prefix(a: str, b: str) -> int:
        n = 0
        for ca, cb in zip(a, b):
            if ca != cb: return n
            n += 1
        return n

    cp_A = _common_prefix(text_A_serial, text_A_batched)
    cp_B = _common_prefix(text_B_serial, text_B_batched)
    print(f"  A: serial vs batched common-prefix {cp_A} chars "
          f"{'IDENTICAL' if a_match else f'(of {min(len(text_A_serial), len(text_A_batched))} shorter)'}")
    print(f"  B: serial vs batched common-prefix {cp_B} chars "
          f"{'IDENTICAL' if b_match else f'(of {min(len(text_B_serial), len(text_B_batched))} shorter)'}")

    # --- Gates ---
    print()
    print("=" * 78)
    print("Gates")
    print("=" * 78)
    gates = [
        ("A: serial == batched (bit-identical greedy)",  a_match),
        ("B: serial == batched (bit-identical greedy)",  b_match),
        ("0 fallback decodes",  call_stats.get("decode_calls_fallback", 0) == 0),
        ("0 fallback writes",   call_stats.get("write_path_fallback", 0) == 0),
        ("packed decode fired", call_stats.get("decode_calls_packed", 0) > 0),
    ]
    ok = True
    for label, passed in gates:
        marker = "PASS" if passed else "FAIL"
        if not passed: ok = False
        print(f"  [{marker}] {label}")

    print()
    if ok:
        print("Phase 5B.6 batch: GREEN")
        return 0
    print("Phase 5B.6 batch: FAIL")
    print()
    print("Diagnostic hints if A or B diverges:")
    print("  - Confirm Int4ProtectedAttentionImpl marker = '5B.4c.3'")
    print("    (multi-seq path was added in step 3).")
    print("  - Confirm decode_calls_packed > 0 (verifies packed kernel fired).")
    print("  - Confirm prefill ran single-seq (chunked_prefill must be False).")
    print("  - First-divergence character position in cp_A / cp_B narrows the")
    print("    timing: divergence at position 1+ = decode path; position 0 =")
    print("    write path.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
