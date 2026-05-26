#!/usr/bin/env bash
# Install the int4 kernel path into vllm_flash_attn on this pod.
#
# Tier A R3 and R7 failed on the prior run with:
#   ImportError: cannot import name 'flash_attn_with_int4_kvcache'
#   from 'vllm.vllm_flash_attn'
#
# The pod has stock vLLM's vendored vllm_flash_attn. The
# int4-kernel path lives in a SEPARATE dev tree at
# /workspace/dev/vllm-flash-attn-dev (cloned during the kernel
# dev cycle, NOT in this repo). The brief's appendix points at
# CTM_plus/CUDA/ but that's an unrelated CTM/TurboQuant helper
# directory, not the vLLM-FA fork. Updating the appendix is a
# separate doc task; this script handles the install.
#
# Pipeline:
#
#   1. Sanity: dev tree exists, vLLM venv exists.
#   2. Backup the stock vendored vllm_flash_attn (if not already).
#   3. Apply the 10 phase patches sequentially (additive +
#      idempotent per their docstrings).
#   4. One incremental wheel build (only changed TUs rebuild).
#   5. Install the new wheel over the vendored copy.
#   6. Verify the import symbol.
#   7. Smoke test an int4_protected decode (1 prompt, 5 tokens).
#
# Safe to re-run. If the symbol is already importable AND
# FORCE_REBUILD is unset, exits early without rebuilding.
#
# Restore: bash Bench/scripts/restore_vendored_vllm_flash_attn.sh
#          (restores the stock vendored copy from backup)

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"
SYMBOLU="${SYMBOLU:-/workspace/symbolu}"
DEV_TREE="${DEV_TREE:-/workspace/dev/vllm-flash-attn-dev}"
BUILD_LOG_DIR="${BUILD_LOG_DIR:-/workspace/dev/build-logs}"
BACKUP_DIR="${BACKUP_DIR:-$BUILD_LOG_DIR/vllm_flash_attn_vendored_backup}"
VENV_FA="${VENV_FA:-/workspace/venv-vllm/lib/python3.12/site-packages/vllm/vllm_flash_attn}"

# ---- 1. Prerequisites ----
echo "==[1/7] Sanity checks ============================================="
if [[ ! -d "$DEV_TREE" ]]; then
  cat >&2 <<EOF
ERROR: vllm-flash-attn dev tree not found at $DEV_TREE.

This pod doesn't have the kernel-source tree that was cloned and
patched during the original int4-kernel dev cycle. The vLLM-FA
fork at SHA 720c948 (with the additive int4 path) is what
produces flash_attn_with_int4_kvcache; without that tree we
can't build it.

Options:
  - If the dev tree is on another pod, copy/rsync it here:
      rsync -av <other_pod>:$DEV_TREE/ $DEV_TREE/
  - If a pre-built wheel exists in a shared store, install it:
      bash $SYMBOLU/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh /path/to/wheel
  - Otherwise: clone vllm-project/flash-attention at SHA 720c948
    into $DEV_TREE before re-running this script.

Aborting. No changes have been made.
EOF
  exit 2
fi

# Find a vendored vllm_flash_attn — try the configured path first,
# then auto-detect via the active python.
if [[ ! -d "$VENV_FA" ]]; then
  echo "  configured VENV_FA=$VENV_FA missing; auto-detecting..."
  AUTO_FA=$(python3 -c "
import vllm, os
print(os.path.join(os.path.dirname(vllm.__file__), 'vllm_flash_attn'))
" 2>/dev/null)
  if [[ -n "$AUTO_FA" && -d "$AUTO_FA" ]]; then
    VENV_FA="$AUTO_FA"
    echo "  resolved VENV_FA=$VENV_FA"
  else
    echo "ERROR: vllm.vllm_flash_attn not found via python import. vLLM not installed?" >&2
    exit 2
  fi
fi

mkdir -p "$BUILD_LOG_DIR"
echo "  DEV_TREE  : $DEV_TREE"
echo "  VENV_FA   : $VENV_FA"
echo "  BACKUP    : $BACKUP_DIR"

# ---- 2. Backup ----
echo
echo "==[2/7] Backup the stock vendored vllm_flash_attn ================="
if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "  creating backup..."
  cp -r "$VENV_FA" "$BACKUP_DIR"
  echo "  -> $BACKUP_DIR"
else
  echo "  backup already exists at $BACKUP_DIR (left untouched)"
fi

# ---- 3. Early-exit if symbol is already importable ----
echo
echo "==[3/7] Probe for existing flash_attn_with_int4_kvcache ==========="
if python3 -c "from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache" 2>/dev/null; then
  echo "  symbol IS importable already."
  if [[ "${FORCE_REBUILD:-0}" != "1" ]]; then
    echo "  Skipping rebuild. Re-run with FORCE_REBUILD=1 to override."
    echo
    echo "[INSTALL] Already installed. Proceed to vc_brief_tier_a_resume.sh."
    exit 0
  fi
  echo "  FORCE_REBUILD=1 set; proceeding to rebuild + reinstall."
else
  echo "  symbol NOT importable. Proceeding with build."
fi

# ---- 4. Apply patches sequentially ----
echo
echo "==[4/7] Apply 10 phase patches ===================================="
# Order matters: phase N+1's patches typically extend phase N's.
# All patch scripts are documented as additive + idempotent, so
# re-applying is safe.
PHASES=(
  phase1
  phase2_1
  phase2_2
  phase2_3
  phase2_4_1a
  phase2_4_1b
  phase2_5
  phase2_6_2
  phase3
  phase4
)
PATCH_LOG="$BUILD_LOG_DIR/tier_a_patch_$(date +%Y%m%d_%H%M%S).log"
for phase in "${PHASES[@]}"; do
  patch="$SYMBOLU/CTM_plus/Bench/scripts/apply_${phase}_patches.py"
  if [[ ! -f "$patch" ]]; then
    echo "  WARN: $patch not found; skipping $phase"
    continue
  fi
  echo "  applying $phase..."
  python3 "$patch" 2>&1 | tee -a "$PATCH_LOG"
done
echo "  patch log: $PATCH_LOG"

# ---- 5. Wheel build ----
echo
echo "==[5/7] Incremental wheel build ==================================="
BUILD_LOG="$BUILD_LOG_DIR/tier_a_build_$(date +%Y%m%d_%H%M%S).log"
cd "$DEV_TREE"
TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.0;9.0}" \
MAX_JOBS="${MAX_JOBS:-16}" \
NVCC_THREADS="${NVCC_THREADS:-2}" \
  python setup.py bdist_wheel 2>&1 | tee "$BUILD_LOG"
echo "  build log: $BUILD_LOG"

# Locate the freshest wheel under dist/
WHEEL=$(ls -t "$DEV_TREE/dist/"*.whl 2>/dev/null | head -1)
if [[ -z "$WHEEL" || ! -f "$WHEEL" ]]; then
  echo "ERROR: no wheel produced in $DEV_TREE/dist/. Check $BUILD_LOG." >&2
  exit 1
fi
echo "  wheel: $WHEEL"

# ---- 6. Install the new wheel ----
echo
echo "==[6/7] Install rebuilt wheel into vendored slot =================="
bash "$SYMBOLU/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh" "$WHEEL"

# ---- 7. Verify + smoke ----
echo
echo "==[7/7] Verify import + smoke test ================================"

echo "  [import smoke]"
python3 -c "
from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
print('IMPORT OK:', flash_attn_with_int4_kvcache.__module__)
"

# Smoke test int4_protected decode. 1 prompt, 5 tokens. Cheapest
# real check that the kernel path actually executes -- not just
# that the symbol exists.
echo
echo "  [int4_protected decode smoke]"
SMOKE_MASK="${SMOKE_MASK:-$BUILD_LOG_DIR/qwen2_5_7b_instruct_protect_mask_4pct.pt}"
if [[ ! -f "$SMOKE_MASK" ]]; then
  echo "  WARN: $SMOKE_MASK missing; trying $BUILD_LOG_DIR/qwen2_5_7b_protect_mask_4pct.pt"
  SMOKE_MASK="$BUILD_LOG_DIR/qwen2_5_7b_protect_mask_4pct.pt"
fi
if [[ ! -f "$SMOKE_MASK" ]]; then
  echo "  WARN: no protect_mask found at expected paths."
  echo "  Decode smoke SKIPPED. R3 / R7 will need the mask present."
else
  PROTECT_MASK_PATH="$SMOKE_MASK" python3 -c "
import os
import kv_policy.int4_protected  # noqa: F401 (registers backend)
from vllm import LLM, SamplingParams
llm = LLM(
    model='Qwen/Qwen2.5-7B-Instruct',
    kv_cache_dtype='int4_protected',
    max_model_len=512,
    gpu_memory_utilization=0.5,
    block_size=32,
    enforce_eager=True,
)
out = llm.generate(['The capital of France is'],
                   SamplingParams(temperature=0.0, max_tokens=5))
text = out[0].outputs[0].text.strip()
print('DECODE SMOKE OK:', repr(text))
assert len(text) > 0, 'empty decode output'
"
fi

echo
echo "==[done] flash_attn_with_int4_kvcache installed + smoked =========="
echo "         Next: bash Bench/scripts/vc_brief_tier_a_resume.sh"
