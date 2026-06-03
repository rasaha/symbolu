#!/usr/bin/env bash
# =============================================================================
# bootstrap_fresh_pod.sh — recreate the int4_protected GPU pod FROM SCRATCH.
# =============================================================================
#
# Use when NO existing pod/volume is available and you start from a bare GPU pod
# (empty /workspace). Encodes every lesson learned the hard way on 2026-06-01:
# the exact dependency pins (a kernel build silently swapped torch and cascaded
# through transformers/tokenizers/numpy/triton), the WHEEL + vendored-slot
# install (a plain `pip install -e .` left the int4 read symbol missing), the
# missing $TMPDIR (nvcc crash), and the FULL-CONTEXT mask recalibration (a
# short-context mask collapses int4 output).
#
# PREREQUISITES YOU MUST PROVIDE on the fresh pod before running:
#   1. The repo at /workspace/symbolu  (git clone or unzip your snapshot)
#   2. The flash-attn fork tarball at /workspace/vllm-flash-attn-dev-src.tar.gz
#      (NOT in the GitHub repo — it is a vendored working copy; you push+copy it)
#   3. A GPU attached (A100 80GB ideal; sm_80). Check: nvidia-smi
#   4. (optional) HF_TOKEN exported if any gated model is needed
#
# USAGE (run top-to-bottom; it is idempotent-ish and stops on first hard error):
#   bash /workspace/symbolu/CTM_plus/Bench/scripts/bootstrap_fresh_pod.sh
#
# Env overrides: REPO, VENV, FA_DIR, MODEL, PY_VER, SKIP_MASK=1, SKIP_AWQ=1.
# =============================================================================
set -uo pipefail

REPO="${REPO:-/workspace/symbolu}"
VENV="${VENV:-/workspace/venv-vllm}"
FA_TARBALL="${FA_TARBALL:-/workspace/vllm-flash-attn-dev-src.tar.gz}"
FA_DIR="${FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
PY_VER="${PY_VER:-3.12}"
export HF_HOME="${HF_HOME:-/workspace/.cache/huggingface}"
export HF_HUB_ENABLE_HF_TRANSFER=0
export TMPDIR="${TMPDIR:-/workspace/tmp}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.0}"   # A100; set 9.0 for H100/H200
export MAX_JOBS="${MAX_JOBS:-64}"

die() { echo "!!! FATAL: $*" >&2; exit 1; }
say() { echo; echo "=== $* ==="; }

# --- pinned versions (the cascade-safe set; vLLM 0.7.3 compatible) -----------
TORCH_SPEC="torch==2.5.1"
TORCH_INDEX="https://download.pytorch.org/whl/cu121"
declare -a RUNTIME_PINS=(
    "vllm==0.7.3"
    "transformers==4.48.3"
    "tokenizers==0.21.1"
    "numpy==1.26.4"
    "triton==3.1.0"
    "accelerate"
    "huggingface_hub"
)

say "0. Preconditions"
mkdir -p "$TMPDIR" /workspace/dev /workspace/dev/build-logs
[[ -d "$REPO" ]]        || die "repo missing at $REPO (clone/unzip it first)"
[[ -f "$FA_TARBALL" || -d "$FA_DIR" ]] || \
    die "flash-attn fork missing: need $FA_TARBALL (to untar) or $FA_DIR (already there)"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader \
    || echo "WARN: nvidia-smi not found — builds will work but nothing will RUN without a GPU"

say "1. System packages"
apt-get update -y && apt-get install -y build-essential git "python${PY_VER}-venv" unzip \
    || echo "WARN: apt-get failed (may already be present); continuing"

say "2. Python venv ($PY_VER) + base runtime (PINNED — order matters)"
if [[ ! -d "$VENV" ]]; then
    "python${PY_VER}" -m venv "$VENV" || die "venv creation failed"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate" || die "venv activate failed"
pip install --upgrade pip
# torch FIRST, from the cu121 index, with --no-deps so nothing else rides in:
pip install --no-deps --force-reinstall "$TORCH_SPEC" --index-url "$TORCH_INDEX" \
    || die "torch install failed"
# the rest of the runtime, pinned:
pip install "${RUNTIME_PINS[@]}" || die "runtime pin install failed"
# GUARD: confirm torch survived the vllm install (vllm can pull a different torch)
TORCH_NOW="$(python -c 'import torch; print(torch.__version__)')"
if [[ "$TORCH_NOW" != "2.5.1+cu121" ]]; then
    echo "torch drifted to $TORCH_NOW; restoring 2.5.1+cu121"
    pip install --no-deps --force-reinstall "$TORCH_SPEC" --index-url "$TORCH_INDEX"
fi
python -c "import torch, transformers, tokenizers, numpy, vllm; \
print('STACK:', 'torch', torch.__version__, '| tf', transformers.__version__, \
'| tok', tokenizers.__version__, '| np', numpy.__version__, '| vllm', vllm.__version__, \
'| cuda', torch.cuda.is_available())" || die "runtime import failed"

say "3. CTM+ python packages (editable, --no-deps so they cannot swap torch)"
(cd "$REPO" && pip install --no-deps -e CTM_plus/KVPolicy/) || die "KVPolicy install failed"
# ctm_bench is the benchmark harness ('python -m ctm_bench.scripts.run_streaming').
# Stdlib-only (install_requires=[]), so --no-deps is safe. Without this the
# runner fails with ModuleNotFoundError: No module named 'ctm_bench'.
(cd "$REPO" && pip install --no-deps -e CTM_plus/Bench/) || die "ctm_bench install failed"

say "4. Unpack the flash-attn fork (if not already present)"
if [[ ! -d "$FA_DIR" ]]; then
    (cd /workspace/dev && tar xzf "$FA_TARBALL") || die "fork untar failed"
fi
[[ -f "$FA_DIR/csrc/flash_attn/src/flash_fwd_kernel.h" ]] \
    || die "fork looks incomplete: missing flash_fwd_kernel.h under $FA_DIR"

say "5. Back up the STOCK vendored flash-attn slot (the install script needs this)"
FA_VENDORED="$(python -c 'import vllm,os;print(os.path.join(os.path.dirname(vllm.__file__),"vllm_flash_attn"))')"
BACKUP=/workspace/dev/build-logs/vllm_flash_attn_vendored_backup
if [[ -d "$FA_VENDORED" && ! -d "$BACKUP" ]]; then
    cp -r "$FA_VENDORED" "$BACKUP" && echo "backed up -> $BACKUP"
fi

say "6. Build BOTH kernels (wheel + vendored-slot install + symbol check)"
echo "    (TORCH_CUDA_ARCH_LIST=$TORCH_CUDA_ARCH_LIST MAX_JOBS=$MAX_JOBS; ~10-15 min)"
# The hardened rebuild script does: patch -> build fork WHEEL -> copy over vendored
# slot -> build int4_protected_C -> assert flash_attn_with_int4_kvcache present.
bash "$REPO/CTM_plus/Bench/scripts/rebuild_all_kernels.sh" --clean --verify-source \
    || die "kernel rebuild failed (see output above)"

say "7. Verify the kernel READ symbol is in the vendored slot (the gather fix)"
python -c "
import torch, vllm.vllm_flash_attn as m
assert hasattr(m, 'flash_attn_with_int4_kvcache'), 'int4 read symbol MISSING from vendored slot'
import int4_protected_C
print('KERNELS OK: vendored int4 symbol present; int4_protected_C exports',
      [s for s in dir(int4_protected_C) if not s.startswith('_')][:4], '...')" \
    || die "vendored int4 symbol missing — step 6 did not install the fork wheel correctly"

say "8. Download the model"
huggingface-cli download "$MODEL" --exclude "*.pth" "original/*" 2>&1 | tail -3 \
    || echo "WARN: model download issue (check HF_TOKEN / network); LLM() will retry"

say "9. Calibrate the protect mask AT FULL CONTEXT (mml=8192 — NOT 1024)"
if [[ "${SKIP_MASK:-0}" == "1" ]]; then
    echo "SKIPPED (SKIP_MASK=1) — ensure a valid mask exists at \$PROTECT_MASK_PATH"
else
    python "$REPO/CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py" \
        --output /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt \
        --protect-fraction 0.04 --max-model-len 8192 \
        || die "mask calibration failed"
fi

say "10. Correctness gate — byte-eq + needle (proves the pod is trustworthy)"
bash "$REPO/CTM_plus/Bench/scripts/verify_phase6e_byte_eq.sh" --cuda 2>&1 | tail -5 \
    || echo "WARN: byte-eq did not return clean; inspect before trusting int4 output"
CELL=protected ENFORCE_EAGER=1 PHASE6E_FUSED_WRITER=1 OUTPUT=/tmp/needle_boot.json \
    python "$REPO/CTM_plus/Bench/scripts/phase6k12_hard_needle.py" --worker --mml 8192 --items 1 \
    2>&1 | grep -E "strict=|COLLAPSE" || echo "WARN: needle check produced no summary line"

say "11. (optional) AWQ setup for Route 2 stacking test"
if [[ "${SKIP_AWQ:-0}" == "1" ]]; then
    echo "SKIPPED (SKIP_AWQ=1)"
else
    huggingface-cli download "${MODEL}-AWQ" --exclude "*.pth" 2>&1 | tail -2 \
        || echo "WARN: AWQ checkpoint download issue; Route 2 needs ${MODEL}-AWQ"
    python -c "from vllm.model_executor.layers.quantization import get_quantization_config; \
print('vLLM native AWQ:', get_quantization_config('awq'))" \
        || echo "NOTE: vLLM native AWQ probe failed; try 'pip install --no-deps autoawq'"
fi

say "DONE — fresh pod bootstrap complete"
cat <<EOF

Next steps:
  # confirm readiness (layer-by-layer):
  bash $REPO/CTM_plus/Bench/scripts/preflight_gpu_pod.sh

  # density + throughput:
  bash $REPO/CTM_plus/Bench/scripts/hardware_test_runner.sh

  # quality (needs the mask from step 9):
  python $REPO/CTM_plus/Bench/scripts/bench_phase6n_mmlu_quality.py --cells bf16,protected --num-questions 200

  # Route 2 stacking (needs the AWQ checkpoint from step 11):
  python $REPO/CTM_plus/Bench/scripts/bench_phase6o_weight_kv_stack.py \\
      --awq-model ${MODEL}-AWQ --mmlu 100 --out $REPO/CTM_plus/Bench/bench_out/phase6o/stack.json

Pins locked: torch 2.5.1+cu121 | transformers 4.48.3 | tokenizers 0.21.1 | numpy 1.26.4 | triton 3.1.0 | vllm 0.7.3
EOF
