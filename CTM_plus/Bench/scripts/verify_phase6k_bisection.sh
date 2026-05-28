#!/usr/bin/env bash
#
# Verify the Phase 6K kernel fix via the N-bisection script.
#
# Expected post-fix: all four N values produce coherent list-of-colors
# output. Pre-fix: N=8 / N=30 produce "pérdida pérdida..." garbage.
#
# Usage:
#   source /workspace/venv-vllm/bin/activate
#   cd /workspace/symbolu
#   bash CTM_plus/Bench/scripts/verify_phase6k_bisection.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

export PYTHONPATH="${SYMBOLU_ROOT}/CTM_plus/KVPolicy:${PYTHONPATH:-}"

echo "================================================================"
echo "Phase 6K verification — bisection across prompt lengths"
echo "================================================================"
echo "PYTHONPATH: ${PYTHONPATH}"
echo

PHASE6E_FUSED_WRITER=1 python <<'PY'
from kv_policy.int4_protected import Int4ProtectedLLM
from vllm import SamplingParams

llm = Int4ProtectedLLM(
    model="Qwen/Qwen2.5-7B-Instruct",
    max_model_len=8192,
    gpu_memory_utilization=0.5,
    max_num_seqs=8,
)
sampling = SamplingParams(temperature=0.0, max_tokens=24)

tests = [
    ("N=~12",  "List three primary colors and their names."),
    ("N=~20",  "Please write me a short list of three primary colors, with each color clearly named."),
    ("N=~32",  "Could you please write me a short detailed list of three primary colors that are typically used in additive color models, with each color clearly named for me?"),
    ("N=~50",  "Could you please write me a short detailed list of three primary colors that are typically used in additive color models with each color clearly named for me, and also briefly explain in one sentence what additive color mixing means in practice?"),
]
print()
print("Output (look for coherent 'Red, Blue, Yellow' content in ALL FOUR rows):")
print("-" * 78)
all_coherent = True
for label, prompt in tests:
    out = llm.generate([prompt], sampling)
    n_in = len(out[0].prompt_token_ids)
    text = out[0].outputs[0].text
    # Heuristic: garbage = repeated "pérdida" OR ratio of distinct tokens too low.
    is_garbage = ("pérdida" in text) or (text.count("a a a") > 0)
    flag = "GARBAGE" if is_garbage else "coherent"
    if is_garbage:
        all_coherent = False
    print(f"  {label} (actual={n_in} tokens) [{flag}]: {text!r}")
print("-" * 78)
print()
if all_coherent:
    print("VERDICT: All four prompts produced coherent output.")
    print("         Phase 6K fix appears to be working. Proceed with Phase 6J smoke.")
else:
    print("VERDICT: At least one prompt still produced garbage.")
    print("         The Phase 6K fix did not resolve the bug at the kernel level.")
    print("         Investigation continues — see PHASE_6K_FLASH_ATTN_OOB_FIX_FINDINGS.md.")
PY
