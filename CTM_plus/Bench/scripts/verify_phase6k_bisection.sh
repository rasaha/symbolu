#!/usr/bin/env bash
#
# Verify the Phase 6K kernel fix via N-bisection. Belt-and-suspenders
# version: runs the bisection in TWO configurations and reports both:
#
#   1. CONTROL: bf16 stock vLLM (no int4_protected). Confirms the
#      prompts themselves produce coherent output at all N values.
#      If bf16 fails on any N, the pod's vLLM install or model is
#      broken — NOT the int4 bug.
#
#   2. INT4 PROTECTED CAPTURED: the cell under test. Pre-fix this
#      produced garbage on N=8/30; post-fix should produce coherent
#      output for all four N values.
#
# Output: side-by-side comparison + a one-line PASS/FAIL verdict.
#
# Usage:
#   bash CTM_plus/Bench/scripts/verify_phase6k_bisection.sh
#
# Env:
#   QUICK=1 — run only int4 path (skip the bf16 control; faster).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

export PYTHONPATH="${SYMBOLU_ROOT}/CTM_plus/KVPolicy:${PYTHONPATH:-}"

QUICK="${QUICK:-0}"

echo "================================================================"
echo "Phase 6K verification — bisection (control vs int4)"
echo "================================================================"
echo

# Pre-flight: GPU available?
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'" || {
    echo "FAIL: CUDA not available. Cannot verify."
    exit 2
}

# Pre-flight: source patched?
KERNEL_H="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}/csrc/flash_attn/src/flash_fwd_kernel.h"
if [[ -f "${KERNEL_H}" ]]; then
    n_patched=$(grep -c "n_block \* Kernel_traits::kBlockN, binfo.actual_seqlen_k);" "${KERNEL_H}" || true)
    n_unpatched=$(grep -c "n_block \* Kernel_traits::kBlockN, params.seqlen_k);" "${KERNEL_H}" || true)
    echo "Source patched state: ${n_patched} patched / ${n_unpatched} unpatched call sites (expect 4/0 post-fix)."
fi
echo

if [[ "${QUICK}" != "1" ]]; then
    echo "----- CONTROL: bf16 stock vLLM -----"
    python <<'PY' || { echo "FAIL: bf16 control crashed."; exit 2; }
from vllm import LLM, SamplingParams
llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=8192,
          gpu_memory_utilization=0.5, max_num_seqs=8, dtype="bfloat16")
sampling = SamplingParams(temperature=0.0, max_tokens=24)
tests = [
    ("N=~12",  "List three primary colors and their names."),
    ("N=~20",  "Please write me a short list of three primary colors, with each color clearly named."),
    ("N=~32",  "Could you please write me a short detailed list of three primary colors that are typically used in additive color models, with each color clearly named for me?"),
    ("N=~50",  "Could you please write me a short detailed list of three primary colors that are typically used in additive color models with each color clearly named for me, and also briefly explain in one sentence what additive color mixing means in practice?"),
]
for label, prompt in tests:
    out = llm.generate([prompt], sampling)
    n_in = len(out[0].prompt_token_ids)
    print(f"  {label} (n={n_in}): {out[0].outputs[0].text!r}")
PY
    echo
fi

echo "----- TEST: int4_protected captured (Phase 6E fused) -----"
PHASE6E_FUSED_WRITER=1 python <<'PY' || { echo "FAIL: int4_protected crashed."; exit 2; }
import sys
from kv_policy.int4_protected import Int4ProtectedLLM
from vllm import SamplingParams

llm = Int4ProtectedLLM(
    model="Qwen/Qwen2.5-7B-Instruct", max_model_len=8192,
    gpu_memory_utilization=0.5, max_num_seqs=8,
)
sampling = SamplingParams(temperature=0.0, max_tokens=24)

tests = [
    ("N=~12",  "List three primary colors and their names."),
    ("N=~20",  "Please write me a short list of three primary colors, with each color clearly named."),
    ("N=~32",  "Could you please write me a short detailed list of three primary colors that are typically used in additive color models, with each color clearly named for me?"),
    ("N=~50",  "Could you please write me a short detailed list of three primary colors that are typically used in additive color models with each color clearly named for me, and also briefly explain in one sentence what additive color mixing means in practice?"),
]

# Collapse signatures we've seen pre-fix:
#   - "pérdida" token loop
#   - long runs of "a a a" or "the the"
#   - same token repeating > 5 times consecutively
import re
def is_garbage(text: str) -> bool:
    if not text.strip():
        return True
    if "pérdida" in text:
        return True
    # Repeat ratio: count tokens, distinct-token ratio < 0.3 = collapse.
    toks = re.findall(r"\b\w+\b", text)
    if len(toks) >= 6 and len(set(toks)) / max(1, len(toks)) < 0.30:
        return True
    return False

all_coherent = True
for label, prompt in tests:
    out = llm.generate([prompt], sampling)
    n_in = len(out[0].prompt_token_ids)
    text = out[0].outputs[0].text
    flag = "GARBAGE" if is_garbage(text) else "coherent"
    if is_garbage(text):
        all_coherent = False
    print(f"  {label} (n={n_in}) [{flag}]: {text!r}")

print()
print("=" * 64)
if all_coherent:
    print("VERDICT: ALL FOUR int4_protected prompts produced coherent output.")
    print("         Phase 6K fix is working.  ✓")
    print()
    print("Next: bash CTM_plus/Bench/scripts/verify_phase6e_byte_eq.sh")
    print("      then: PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6j_quality_gpu.py --smoke")
    sys.exit(0)
else:
    print("VERDICT: At least one prompt produced garbage.")
    print("         Phase 6K fix did NOT fully resolve the bug. Investigate further.")
    sys.exit(1)
PY
