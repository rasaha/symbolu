"""Phase 6 v2 Option B-1 — graph capture smoke test.

Tries to enable vLLM's CUDA graph capture for the int4_protected
backend by setting `enforce_eager=False` on Int4ProtectedLLM. Captures
the outcome:

  1. CLEAN PASS  — captures, generates correct output, big speedup.
                   Land it and lock the win.
  2. WRONG OUT   — captures, but output diverges from eager baseline
                   (slot-baking bug expected per OPTION_B_PREFLIGHT.md
                   §B-pre-4). Tells us we need pre-capture hoist.
  3. CRASH       — capture rejects something in our impl. The error
                   message + traceback scopes the next fix.
  4. NO CAPTURE  — vLLM 0.7.3 V0 silently doesn't capture (no error,
                   no speedup). Need to check vLLM internals.

The smoke test measures:
  - Whether generate even completes.
  - Whether output matches the eager baseline (correctness).
  - Wall time vs eager (early signal of capture benefit).

This is intentionally NOT a full bench — we just want to know what
happens when we flip the flag. The real perf measurement comes after
correctness is locked.

Run on the pod:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/smoke_phase6_b1_graph_capture.py
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


PROMPT_A = (
    "The secret code is XYZ123. Repeat the secret code in the next "
    "sentence. Make sure to include it verbatim."
)
PROMPT_B = "Roses are red, violets are"


def _run_one_config(*, enforce_eager: bool, label: str, max_tokens: int):
    """Build an Int4ProtectedLLM with the given config, generate a
    couple of prompts, return wall time + outputs."""
    import torch
    from vllm import SamplingParams
    import kv_policy.int4_protected
    from kv_policy.int4_protected import Int4ProtectedLLM

    print(f"\n{'=' * 78}")
    print(f"CONFIG: {label}  (enforce_eager={enforce_eager})")
    print(f"{'=' * 78}")

    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'."); return None

    sampling = SamplingParams(temperature=0.0, max_tokens=max_tokens)

    print(f"  Building Int4ProtectedLLM (enforce_eager={enforce_eager})...")
    t_load0 = time.perf_counter()
    try:
        llm = Int4ProtectedLLM(
            model="Qwen/Qwen2.5-7B-Instruct",
            max_model_len=4096,
            gpu_memory_utilization=0.5,
            enforce_eager=enforce_eager,
        )
    except Exception as e:
        print(f"  CRASH during construction: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"label": label, "status": "construct_crash", "error": str(e)}
    t_load = time.perf_counter() - t_load0
    print(f"  Constructed in {t_load:.1f}s.")

    print(f"  Warmup (B=1)...")
    try:
        llm.generate([PROMPT_A], sampling)
    except Exception as e:
        print(f"  CRASH during warmup: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"label": label, "status": "warmup_crash",
                "error": f"{type(e).__name__}: {e}"}

    print(f"  Batched run (B=2, max_tokens={max_tokens})...")
    try:
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        outs = llm.generate([PROMPT_A, PROMPT_B], sampling)
        torch.cuda.synchronize()
        wall = time.perf_counter() - t0
    except Exception as e:
        print(f"  CRASH during generate: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"label": label, "status": "generate_crash",
                "error": f"{type(e).__name__}: {e}"}

    texts = [o.outputs[0].text for o in outs]
    n_tokens = sum(len(o.outputs[0].token_ids) for o in outs)
    agg_tps = n_tokens / wall if wall > 0 else 0.0
    print(f"  Wall: {wall:.3f}s  n_out_total: {n_tokens}  agg_tps: {agg_tps:.1f}")
    print(f"  A: {texts[0][:100]!r}")
    print(f"  B: {texts[1][:100]!r}")
    return {
        "label":   label,
        "status":  "ok",
        "wall":    wall,
        "n_tokens": n_tokens,
        "agg_tps": agg_tps,
        "texts":   texts,
    }


def main():
    print("=" * 78)
    print("Phase 6 v2 B-1 smoke test — try enabling CUDA graph capture")
    print("=" * 78)

    # First the eager baseline (current ship), then the captured candidate.
    # Single process; vLLM cleans up between LLM constructions but it can
    # be flaky — if the second build fails, that's a known multi-instance
    # issue, not a capture issue.
    results = []

    r_eager = _run_one_config(
        enforce_eager=True, label="EAGER (baseline)", max_tokens=24,
    )
    results.append(r_eager)

    r_captured = _run_one_config(
        enforce_eager=False, label="CAPTURED (enforce_eager=False)",
        max_tokens=24,
    )
    results.append(r_captured)

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    for r in results:
        if r is None:
            print(f"  (skipped — missing mask?)")
            continue
        if r["status"] != "ok":
            print(f"  {r['label']:<36} {r['status']}: {r.get('error', '')}")
        else:
            print(f"  {r['label']:<36} wall={r['wall']:.3f}s  "
                  f"agg_tps={r['agg_tps']:.1f}")

    # Verdict.
    print()
    if r_eager and r_eager.get("status") == "ok" and r_captured:
        if r_captured["status"] == "ok":
            # Correctness check.
            match = r_eager["texts"] == r_captured["texts"]
            speedup = (r_captured["agg_tps"] / r_eager["agg_tps"]
                       if r_eager["agg_tps"] > 0 else 0.0)
            print(f"  Output match across configs: {match}")
            print(f"  Speedup (captured / eager): {speedup:.2f}×")
            if match and speedup > 1.5:
                print()
                print("  VERDICT: CLEAN PASS. Graph capture works, big win.")
                print("           Lock the new ship.")
                return 0
            elif not match:
                print()
                print("  VERDICT: WRONG OUTPUT. Graph captured, but output")
                print("           diverges from eager baseline. Likely the")
                print("           slot-baking bug — slot_indices_for() ran")
                print("           at capture time and baked stale values.")
                print("           Fix: hoist slot resolution to pre-capture.")
                return 1
            elif speedup < 1.1:
                print()
                print("  VERDICT: NO CAPTURE BENEFIT. Output correct but")
                print("           no speedup. Either capture didn't fire,")
                print("           or it's capturing the same work without")
                print("           amortizing the launch overhead. Check")
                print("           vLLM logs for 'capturing model' messages.")
                return 1
            else:
                print()
                print(f"  VERDICT: MODEST WIN ({speedup:.2f}×). Capture")
                print("           working but not delivering the expected")
                print("           2-3×. Investigate which phase dominates.")
                return 0
        else:
            print(f"  VERDICT: CAPTURE FAILED. Status: {r_captured['status']}.")
            print(f"           Error: {r_captured.get('error', '?')}")
            print("           The error message scopes the next fix.")
            return 1
    print("  VERDICT: INCONCLUSIVE — one or more configs didn't run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
