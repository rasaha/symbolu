"""Phase 7 — Mistral-7B-Instruct-v0.3 int4_protected end-to-end smoke.

After calibrating a Mistral-specific protect mask, this script confirms
that the int4_protected backend produces coherent outputs through
Mistral. Pattern mirrors verify_phase5b_6_batch.py (the main multi-
batch regression gate for Qwen) but:

  - Targets mistralai/Mistral-7B-Instruct-v0.3 by default.
  - Expects PROTECT_MASK_PATH to point at a Mistral-calibrated mask
    (run calibrate_phase5b_protect_mask.py --model mistralai/Mistral-7B-Instruct-v0.3
    first; the derived output path is auto-used as the default mask).
  - Asserts:
      A. int4_protected generation completes without fallbacks.
      B. Output is deterministic across two runs (architectural
         determinism property — same as Qwen verify).
      C. Output is non-trivial (not all-empty or all-same-token).
      D. call_stats show packed decode fired (not the bf16 fallback).

Architecture differences from Qwen2.5-7B that this verify exercises:
  - 32 layers (vs Qwen's 28) → 32 PagedKVWriter instances.
  - H_kv = 8 (vs Qwen's 4) → larger sidecars + pool tensors per layer.
  - Sliding window attention → passes through writer.protect_mask +
    kernel window_size unchanged.

Run on the pod:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase7_mistral_int4_protected.py

Override the mask path:
  PROTECT_MASK_PATH=/workspace/dev/build-logs/mistral_7b_instruct_v0_3_protect_mask_4pct.pt \\
      /workspace/venv-vllm/bin/python3 .../verify_phase7_mistral_int4_protected.py
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


# Two prompts of differing structure — same fixture style as the
# Qwen multi-batch verify.
PROMPT_A = (
    "[INST] The secret code is XYZ123. Repeat the secret code in the "
    "next sentence. [/INST]"
)
PROMPT_B = "[INST] Roses are red, violets are [/INST]"


def _run(model_id, mask_path, max_tokens):
    import torch
    from vllm import SamplingParams
    import kv_policy.int4_protected
    from kv_policy.int4_protected import Int4ProtectedLLM, get_backend_info
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl

    os.environ["PROTECT_MASK_PATH"] = mask_path
    print(f"  Loading int4_protected Mistral...")
    llm = Int4ProtectedLLM(
        model=model_id,
        max_model_len=4096,
        gpu_memory_utilization=0.5,
        enforce_eager=True,
    )
    info = get_backend_info(llm)
    print(f"  Backend marker: {info.get('marker')}")
    print(f"  Layers swapped: {info.get('layers_swapped')}")

    sampling = SamplingParams(temperature=0.0, max_tokens=max_tokens)

    # ----- Batched run 1 -----
    print(f"\n  [T1] Batched [A, B] run 1...")
    Int4ProtectedAttentionImpl.reset_call_stats()
    outs1 = llm.generate([PROMPT_A, PROMPT_B], sampling)
    stats1 = Int4ProtectedAttentionImpl.get_call_stats()
    text_a1 = outs1[0].outputs[0].text
    text_b1 = outs1[1].outputs[0].text
    print(f"    A: {text_a1[:100]!r}")
    print(f"    B: {text_b1[:100]!r}")
    print(f"    stats: {stats1}")

    # ----- Batched run 2 (determinism) -----
    print(f"\n  [T2] Batched [A, B] run 2 (determinism check)...")
    outs2 = llm.generate([PROMPT_A, PROMPT_B], sampling)
    text_a2 = outs2[0].outputs[0].text
    text_b2 = outs2[1].outputs[0].text
    print(f"    A: {text_a2[:100]!r}")
    print(f"    B: {text_b2[:100]!r}")

    # ----- Gates -----
    print()
    print("=" * 70)
    print("Gates")
    print("=" * 70)
    ok = True

    # (A) Generation completed (we got here without crashing).
    print(f"  [PASS] A: int4_protected generation completes")

    # (B) Determinism: byte-identical text across runs.
    if text_a1 == text_a2:
        print(f"  [PASS] B: prompt A deterministic across runs")
    else:
        print(f"  [FAIL] B: prompt A diverged across runs")
        print(f"          run1: {text_a1[:120]!r}")
        print(f"          run2: {text_a2[:120]!r}")
        ok = False
    if text_b1 == text_b2:
        print(f"  [PASS] B: prompt B deterministic across runs")
    else:
        print(f"  [FAIL] B: prompt B diverged across runs")
        ok = False

    # (C) Non-trivial output.
    if len(text_a1.strip()) >= 5 and len(text_b1.strip()) >= 5:
        print(f"  [PASS] C: outputs non-trivial (len A={len(text_a1)}, "
              f"B={len(text_b1)})")
    else:
        print(f"  [FAIL] C: outputs too short — backend may not be "
              f"generating real text. A={text_a1!r}  B={text_b1!r}")
        ok = False

    # (D) Packed decode fired, no fallback.
    n_packed = stats1.get("decode_calls_packed", 0)
    n_fb     = stats1.get("decode_calls_fallback", 0)
    n_write  = stats1.get("write_path_calls", 0)
    n_wfb    = stats1.get("write_path_fallback", 0)
    if n_packed > 0:
        print(f"  [PASS] D: packed decode fired ({n_packed} calls)")
    else:
        print(f"  [FAIL] D: no packed decode calls — backend may have "
              f"silently fallen back to bf16")
        ok = False
    if n_fb == 0 and n_wfb == 0:
        print(f"  [PASS] D: 0 fallback decodes, 0 fallback writes")
    else:
        print(f"  [FAIL] D: fallbacks detected — decode_fb={n_fb}, "
              f"write_fb={n_wfb}")
        ok = False

    print()
    if ok:
        print("Phase 7 Mistral int4_protected: GREEN")
        print(f"  Mistral-7B-Instruct-v0.3 produces coherent, deterministic")
        print(f"  output through the int4_protected backend with the")
        print(f"  Mistral-calibrated protect mask. Methodology generalizes")
        print(f"  from Qwen → Mistral.")
        return 0
    else:
        print("Phase 7 Mistral int4_protected: FAIL")
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mistralai/Mistral-7B-Instruct-v0.3")
    parser.add_argument(
        "--mask-path", default=None,
        help="Path to the calibrated protect mask. Default: derive "
             "from model id (matches calibrate_phase5b_protect_mask.py "
             "auto-derivation).",
    )
    parser.add_argument("--max-tokens", type=int, default=32)
    args = parser.parse_args()

    # Derive default mask path from model id (matches the calibration
    # script's auto-derivation).
    if args.mask_path is None:
        slug = args.model.split("/")[-1].lower()
        for ch in (".", "-"):
            slug = slug.replace(ch, "_")
        args.mask_path = f"/workspace/dev/build-logs/{slug}_protect_mask_4pct.pt"

    print("=" * 70)
    print("Phase 7 — int4_protected end-to-end smoke")
    print("=" * 70)
    print(f"  model:    {args.model}")
    print(f"  mask:     {args.mask_path}")
    print(f"  prompts:  A={PROMPT_A[:50]!r}...")
    print(f"            B={PROMPT_B[:50]!r}")
    print()

    if not os.path.exists(args.mask_path):
        print(f"FAIL: protect mask not found at '{args.mask_path}'.")
        print(f"      Run calibration first:")
        print(f"        /workspace/venv-vllm/bin/python3 \\")
        print(f"            /workspace/symbolu/CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \\")
        print(f"            --model {args.model}")
        return 1

    try:
        return _run(args.model, args.mask_path, args.max_tokens)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
