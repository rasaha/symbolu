#!/usr/bin/env bash
# K0 — fresh-pod reproducible build orchestrator for the production INT4 decode kernel.
# Chains the repo's proven scripts (rebuild_all_kernels.sh, smoke_test_fa_install.sh) with
# idempotent prerequisite checks + the K0 gates. Delegates the ACTUAL kernel build to
# rebuild_all_kernels.sh — this wrapper only does the fresh-pod setup + gates. Read
# K0_BUILD_RUNBOOK.md for the manual step-by-step. POD-ONLY (A100, sm_80).
#
#   FA_TARBALL=/workspace/vllm-flash-attn-dev-src.tar.gz bash k0_build.sh
#
# Env: SYMBOLU (default /workspace/symbolu), VENV (/workspace/venv-vllm),
#      FA_DIR (/workspace/dev/vllm-flash-attn-dev), FA_TARBALL, MAX_JOBS, TORCH_INDEX.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU="${SYMBOLU:-/workspace/symbolu}"
VENV="${VENV:-/workspace/venv-vllm}"
FA_DIR="${FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
FA_TARBALL="${FA_TARBALL:-/workspace/vllm-flash-attn-dev-src.tar.gz}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu121}"
STATUS="$HERE/runs/k0_build_status.json"; mkdir -p "$HERE/runs"
PY="$VENV/bin/python3"
declare -A S=()
step() { echo; echo "== K0 $1 =="; }
mark() { S["$1"]="$2"; echo "   [$2] $1"; }
finish() {
  { echo "{"; local first=1
    for k in "${!S[@]}"; do [ $first -eq 1 ] && first=0 || echo ","; printf '  "%s": "%s"' "$k" "${S[$k]}"; done
    echo; echo "}"; } > "$STATUS"
  echo; echo "K0 status -> $STATUS"; cat "$STATUS"
  echo; echo "commit: git add -f scripts/kvpro_kernel_recovery/runs/k0_build_status.json"
}
trap finish EXIT

# --- Phase 0: environment ---
step "0 — environment"
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L | head -1 && mark gpu present || mark gpu NOT_FOUND
python3.12 --version >/dev/null 2>&1 && mark python312 present || mark python312 NOT_FOUND

# --- Phase 1: venv + pinned stack (idempotent) ---
step "1 — venv + pinned stack (vllm 0.7.3, torch 2.5.1, py3.12)"
if [ ! -x "$PY" ]; then
  python3.12 -m venv "$VENV" || { mark venv FAILED; exit 1; }
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
PY="$VENV/bin/python3"
if ! "$PY" -c "import vllm" 2>/dev/null; then
  pip install --upgrade pip wheel setuptools packaging >/dev/null 2>&1
  pip install --no-deps --force-reinstall torch==2.5.1 --index-url "$TORCH_INDEX" || { mark stack FAILED_torch; exit 1; }
  pip install vllm==0.7.3 || { mark stack FAILED_vllm; exit 1; }
  # PIN transformers/tokenizers to the vLLM-0.7.3-compatible versions (unpinned pulls a 5.x
  # whose lazy imports break vLLM 0.7.3: "Could not import module 'ProcessorMixin'").
  pip install transformers==4.48.3 tokenizers==0.21.1 || { mark stack FAILED_transformers; exit 1; }
  pip install accelerate huggingface_hub numpy tqdm ninja cmake pybind11 >/dev/null 2>&1
  pip install -e "$SYMBOLU/CTM_plus/KVPolicy/" >/dev/null 2>&1
fi
"$PY" -c "import vllm,torch;print('vllm',vllm.__version__,'torch',torch.__version__)" \
  && mark stack ok || { mark stack FAILED_import; exit 1; }

# --- Phase 2: fork source (tarball preferred; else reconstruct from base @ 720c948) ---
step "2 — INT4-patched fork source"
if [ -d "$FA_DIR/csrc" ]; then
  mark fork_source present_reuse
elif [ -f "$FA_TARBALL" ]; then
  mkdir -p "$(dirname "$FA_DIR")"; tar xzf "$FA_TARBALL" -C "$(dirname "$FA_DIR")" \
    && mark fork_source untarred || { mark fork_source FAILED_untar; exit 1; }
else
  echo "   no tarball at $FA_TARBALL — reconstructing from base @ 720c948 + in-repo patches"
  mkdir -p "$(dirname "$FA_DIR")"
  git clone https://github.com/vllm-project/flash-attention "$FA_DIR" || { mark fork_source FAILED_clone; exit 1; }
  git -C "$FA_DIR" checkout 720c94869cf2e0ff5a706e9c7f1dce0939686ade || { mark fork_source FAILED_checkout; exit 1; }
  mkdir -p /workspace/dev/build-logs
  VEND="$("$PY" -c 'import os,vllm.vllm_flash_attn as m;print(os.path.dirname(m.__file__))' 2>/dev/null || true)"
  [ -n "$VEND" ] && cp -r "$VEND" /workspace/dev/build-logs/vllm_flash_attn_vendored_backup 2>/dev/null || true
  ok=1
  for p in apply_phase1 apply_phase2_1 apply_phase2_2 apply_phase2_3 apply_phase2_5 \
           apply_phase3 apply_phase4 apply_phase2_4_1a; do
    bash "$SYMBOLU/CTM_plus/Bench/scripts/$p.sh" || { echo "   FAILED at $p"; ok=0; break; }
  done
  [ $ok -eq 1 ] && mark fork_source reconstructed || { mark fork_source FAILED_patch; exit 1; }
fi

# --- Phase 3: build + install (delegate to the canonical builder) ---
step "3 — build + install (rebuild_all_kernels.sh --clean --verify-source)"
TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.0}" MAX_JOBS="${MAX_JOBS:-16}" NVCC_THREADS="${NVCC_THREADS:-2}" \
  bash "$SYMBOLU/CTM_plus/Bench/scripts/rebuild_all_kernels.sh" --clean --verify-source \
  && mark build ok || { mark build FAILED; echo "   read /workspace/dev/build-logs/ for the full log"; exit 1; }

# --- Phase 4: K0 gates ---
step "4 — K0 gates (import / hash / smoke / contract)"
"$PY" -c "import torch,vllm.vllm_flash_attn as m; assert hasattr(m,'flash_attn_with_int4_kvcache'); assert hasattr(torch.ops._vllm_fa2_C,'fwd_kvcache_int4')" \
  && mark gate_import ok || mark gate_import FAILED
PYBIN="$PY" "$PY" "$HERE/02_hash_installed_kernel.py" >/dev/null 2>&1 && mark gate_hash recorded || mark gate_hash FAILED
"$PY" "$HERE/test_contract_cpu.py" >/dev/null 2>&1 && mark gate_contract ok_16_16 || mark gate_contract FAILED
echo "   running A100 smoke (may take a few min)..."
bash "$SYMBOLU/CTM_plus/Bench/scripts/smoke_test_fa_install.sh" && mark gate_smoke ok || mark gate_smoke CHECK_MANUALLY
PYBIN="$PY" bash "$HERE/run_recovery_audit.sh" >/dev/null 2>&1 && mark recovery_verdict recorded || mark recovery_verdict CHECK
echo; echo "== K0 done — review gates above; K0 GREEN needs import+hash+contract ok and smoke within tolerance =="
