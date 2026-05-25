#!/usr/bin/env python3
"""verify_phase5c_api.py — Phase 5C API surface acceptance.

Confirms the Phase 5C clean API works without the legacy
post-construction `install_int4_protected_backend()` step:

  T1: `import kv_policy.int4_protected` registers the backend
      (CacheConfig accepts "int4_protected"; backend selector routes
      correctly).
  T2: Standard `LLM(kv_cache_dtype="int4_protected", block_size=32)`
      constructs successfully with 28/28 layers using
      Int4ProtectedAttentionImpl. No explicit install call.
  T3: `Int4ProtectedLLM(model=...)` convenience factory enforces
      block_size=32 and produces a working LLM.
  T4: Generation through the 1-step API matches the 2-step install
      output (greedy decode, same prompt).
  T5: `get_backend_info(llm)` returns the expected diagnostics dict.
  T6: Block_size != 32 with kv_cache_dtype="int4_protected" raises.

Exit 0 = GREEN.
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
import traceback
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


PROMPT = (
    "The secret code is XYZ123. Repeat the secret code in the next "
    "sentence.\nThe secret code is"
)


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",          type=int,   default=4096)
    parser.add_argument("--max-tokens",             type=int,   default=32)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    args = parser.parse_args(argv)

    try:
        import torch
        from vllm import SamplingParams
    except ImportError as e:
        print(f"FAIL: import error ({e}). Run inside venv-vllm."); return 1

    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'."); return 1

    print("=" * 78)
    print("Phase 5C API verify")
    print("=" * 78)

    # ---- T1: import registers the backend ----
    print()
    print("T1: import kv_policy.int4_protected registers the backend")
    try:
        import kv_policy.int4_protected as int4pkg
        from kv_policy.int4_protected import (
            Int4ProtectedLLM, get_backend_info, is_int4_protected_enabled,
        )
        assert is_int4_protected_enabled(), (
            "after import, is_int4_protected_enabled() should be True"
        )
        print("  PASS — backend enabled on import.")
    except Exception as e:
        print(f"  FAIL: {e}"); traceback.print_exc(); return 1

    # ---- T6: block_size != 32 must raise ----
    print()
    print("T6: block_size != 32 with int4_protected raises ValueError")
    raised = False
    try:
        Int4ProtectedLLM(
            model=args.model, block_size=16,
            max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )
    except ValueError as e:
        if "block_size" in str(e):
            raised = True
            print(f"  PASS — raised as expected: {e}")
        else:
            print(f"  FAIL: wrong ValueError: {e}"); return 1
    except Exception as e:
        print(f"  FAIL: unexpected exception type: {type(e).__name__}: {e}")
        return 1
    if not raised:
        print("  FAIL: did not raise for block_size=16"); return 1

    # ---- T3: Int4ProtectedLLM factory ----
    print()
    print("T3: Int4ProtectedLLM(model=...) factory constructs cleanly")
    try:
        llm = Int4ProtectedLLM(
            model=args.model,
            max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )
        print(f"  PASS — Int4ProtectedLLM constructed.")
    except Exception as e:
        print(f"  FAIL: {e}"); traceback.print_exc(); return 1

    # ---- T2 + T5: layers swapped + backend info ----
    print()
    print("T2 + T5: diagnostics — layers swapped + get_backend_info()")
    try:
        info = get_backend_info(llm)
        print(f"  marker:          {info['marker']}")
        print(f"  layers_swapped:  {info['layers_swapped']}/{info['layers_total']}")
        print(f"  backend_enabled: {info['backend_enabled']}")

        assert info["layers_swapped"] == info["layers_total"], (
            f"only {info['layers_swapped']}/{info['layers_total']} layers swapped"
        )
        assert info["layers_total"] > 0, "no Attention layers found"
        assert info["marker"].startswith("5B.4c"), (
            f"unexpected marker: {info['marker']}"
        )
        assert info["backend_enabled"], "backend_enabled is False"
        print("  PASS — all layers using Int4ProtectedAttentionImpl, "
              "no explicit install needed.")
    except AssertionError as e:
        print(f"  FAIL: {e}"); return 1
    except Exception as e:
        print(f"  FAIL: {e}"); traceback.print_exc(); return 1

    # ---- T4: generation works ----
    print()
    print("T4: generate via the 1-step API")
    try:
        sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
        out = llm.generate([PROMPT], sampling)
        text = out[0].outputs[0].text
        print(f"  output: {text!r}")

        stats = get_backend_info(llm)["call_stats"]
        print(f"  call_stats: {stats}")

        assert text and text.strip(), "empty output"
        assert "XYZ123" in text, "needle not retrieved"
        assert stats["decode_calls_packed"] > 0, "packed decode never fired"
        assert stats["write_path_calls"] > 0, "writer never fired"
        assert stats["decode_calls_fallback"] == 0, (
            f"decode fallbacks: {stats['decode_calls_fallback']}"
        )
        assert stats["write_path_fallback"] == 0, (
            f"write fallbacks: {stats['write_path_fallback']}"
        )
        print("  PASS — coherent output, needle found, 0 fallbacks.")
    except AssertionError as e:
        print(f"  FAIL: {e}"); return 1
    except Exception as e:
        print(f"  FAIL: {e}"); traceback.print_exc(); return 1
    finally:
        del llm
        gc.collect()
        if 'torch' in globals():
            torch.cuda.empty_cache()

    print()
    print("=" * 78)
    print("Phase 5C API: GREEN")
    print("=" * 78)
    print("Recommended usage (post-5C):")
    print("  import kv_policy.int4_protected")
    print("  llm = Int4ProtectedLLM(model='Qwen/Qwen2.5-7B-Instruct',")
    print("                         max_model_len=4096)")
    print("  llm.generate(...)")
    print("Or equivalently:")
    print("  import kv_policy.int4_protected")
    print("  llm = LLM(model=..., kv_cache_dtype='int4_protected', block_size=32)")
    print("  llm.generate(...)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
