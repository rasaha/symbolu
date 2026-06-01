#!/usr/bin/env bash
# =============================================================================
# preflight_gpu_pod.sh — get a GPU pod ready to benchmark the int4_protected
# KV-cache project, and tell you EXACTLY what (if anything) needs rebuilding.
# =============================================================================
#
# Run this FIRST on any GPU pod, whether you:
#   (A) re-attached / migrated the /workspace volume (venv + dev/ already there),
#   (B) booted a fresh pod with the volume but a DIFFERENT GPU/driver, or
#   (C) want to confirm a pod is benchmark-ready before spending GPU-billed time.
#
# It is READ-ONLY by default: it checks each layer (GPU -> torch -> vLLM ->
# flash-attn -> int4 kernel -> model) and prints a GREEN/REBUILD verdict per
# layer. It does NOT rebuild unless you pass --rebuild (which just calls the
# canonical rebuild_all_kernels.sh).
#
# Usage:
#   source /workspace/venv-vllm/bin/activate
#   bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh            # check only
#   bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh --rebuild  # check + rebuild kernels if needed
#   bash CTM_plus/Bench/scripts/preflight_gpu_pod.sh --fetch-model  # also pre-download Qwen-7B
#
# Env: HF_HOME (default /workspace/.cache/huggingface), HF_TOKEN (for downloads),
#      MODEL (default Qwen/Qwen2.5-7B-Instruct),
#      VENV (default /workspace/venv-vllm), VLLM_FA_DIR (default /workspace/dev/vllm-flash-attn-dev).
#
# This script does NOT build the venv from nothing — see the FRESH-POD section
# in PREP_NEW_POD.md for that (rare; only if the volume itself is gone).
set -uo pipefail

VENV="${VENV:-/workspace/venv-vllm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYMBOLU_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
VLLM_FA_DIR="${VLLM_FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
export HF_HOME="${HF_HOME:-/workspace/.cache/huggingface}"

DO_REBUILD=0; DO_FETCH=0
for a in "$@"; do case "$a" in
    --rebuild) DO_REBUILD=1 ;;
    --fetch-model) DO_FETCH=1 ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown flag: $a"; exit 2 ;;
esac; done

GREEN=0; NEEDS_REBUILD=0; HARD_FAIL=0
say()  { printf '%s\n' "$*"; }
ok()   { printf '  [GREEN]   %s\n' "$*"; GREEN=$((GREEN+1)); }
warn() { printf '  [REBUILD] %s\n' "$*"; NEEDS_REBUILD=$((NEEDS_REBUILD+1)); }
bad()  { printf '  [FAIL]    %s\n' "$*"; HARD_FAIL=$((HARD_FAIL+1)); }

say "================================================================"
say "Preflight — int4_protected GPU pod"
say "  venv:   $VENV"
say "  HF_HOME:$HF_HOME"
say "  model:  $MODEL"
say "================================================================"

# --- 0. venv present + active --------------------------------------------
say; say "### 0. virtualenv ###"
if [[ ! -d "$VENV" ]]; then
    bad "venv missing at $VENV — the volume may not be attached, or this is a"
    bad "  fresh pod with no volume. See PREP_NEW_POD.md (FRESH-POD section)."
    echo; say "PREFLIGHT ABORTED — no venv."; exit 3
fi
if [[ "${VIRTUAL_ENV:-}" != "$VENV" ]]; then
    warn "venv not active in this shell. Run: source $VENV/bin/activate"
else
    ok "venv active: $VIRTUAL_ENV"
fi
PY="$VENV/bin/python"

# --- 1. GPU + driver ------------------------------------------------------
say; say "### 1. GPU / driver ###"
if command -v nvidia-smi &>/dev/null && nvidia-smi -L &>/dev/null; then
    nvidia-smi --query-gpu=name,compute_cap,driver_version,memory.total --format=csv,noheader \
        | sed 's/^/  GPU: /'
    CC="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d ' ')"
    case "$CC" in
        8.0) ok "compute_cap 8.0 (A100) — matches the kernels' build target." ;;
        9.0) warn "compute_cap 9.0 (H100/H200) — kernels built for sm_80 will NOT"
             warn "  load; a rebuild on THIS pod is REQUIRED (see --rebuild)." ;;
        "")  bad "could not read compute_cap." ;;
        *)   warn "compute_cap $CC — differs from A100 sm_80; rebuild likely needed." ;;
    esac
else
    bad "no GPU detected (nvidia-smi missing or no devices). This is a CPU pod —"
    bad "  the kernels import in Python-fallback but NO benchmark will run."
fi

# --- 2. torch + CUDA ------------------------------------------------------
say; say "### 2. torch / CUDA runtime ###"
TORCH_OUT="$("$PY" - <<'PY' 2>&1
try:
    import torch
    print("OK", torch.__version__, torch.version.cuda, torch.cuda.is_available())
except Exception as e:
    print("ERR", repr(e))
PY
)"
say "  $TORCH_OUT"
case "$TORCH_OUT" in
    "OK"*True*) ok "torch imports and sees CUDA." ;;
    "OK"*False*) warn "torch imports but cuda.is_available()=False (driver/libcuda not"
                 warn "  attached). On a GPU pod this means the runtime isn't wired up." ;;
    *) bad "torch failed to import — venv may be corrupt or torch/CUDA mismatched." ;;
esac

# --- 3. vLLM + its compiled _C -------------------------------------------
say; say "### 3. vLLM (expect 0.7.3) + vllm._C ###"
VLLM_OUT="$("$PY" - <<'PY' 2>&1
try:
    import vllm; print("VER", vllm.__version__)
except Exception as e:
    print("VER_ERR", repr(e))
try:
    import vllm._C; print("C_OK")
except Exception as e:
    print("C_ERR", repr(e))
PY
)"
say "$VLLM_OUT" | sed 's/^/  /'
echo "$VLLM_OUT" | grep -q "C_OK" \
    && ok "vllm._C loaded (libcuda present)." \
    || warn "vllm._C failed (usually libcuda.so.1 missing -> no GPU/driver, or a"
echo "$VLLM_OUT" | grep -q "C_OK" || warn "  vLLM/torch mismatch). Fix the GPU/driver first; rebuild if it persists."

# --- 4. vendored flash-attn (the fork) -----------------------------------
say; say "### 4. vendored vllm_flash_attn (the fork) ###"
FA_OUT="$("$PY" - <<'PY' 2>&1
try:
    import torch  # must precede the vendored .so
    import vllm.vllm_flash_attn as m
    print("OK", m.__file__)
except Exception as e:
    print("ERR", repr(e))
PY
)"
say "  $FA_OUT"
case "$FA_OUT" in
    OK*) ok "vllm.vllm_flash_attn loads." ;;
    *)   warn "vendored flash-attn failed to load -> rebuild + reinstall the wheel"
         warn "  over the vendored slot (rebuild_all_kernels.sh handles this)." ;;
esac

# --- 5. int4_protected_C custom kernel -----------------------------------
say; say "### 5. int4_protected_C (Phase 6E fused kernels) ###"
INT4_OUT="$("$PY" - <<'PY' 2>&1
try:
    import torch  # MUST be first (the .so needs libc10/libtorch loaded)
    import int4_protected_C as m
    print("OK", [s for s in dir(m) if not s.startswith('_')])
except Exception as e:
    print("ERR", repr(e))
PY
)"
say "  $INT4_OUT"
case "$INT4_OUT" in
    OK*) ok "int4_protected_C loaded (compiled kernel present)." ;;
    *ImportError*|*ERR*) warn "int4_protected_C not loaded -> Python fallback only. Rebuild with"
                         warn "  --rebuild if you need the fused CUDA writer for benchmarking." ;;
esac

# --- 6. model cache -------------------------------------------------------
say; say "### 6. model cache ($MODEL) ###"
SNAP="$HF_HOME/hub/models--${MODEL//\//--}/snapshots"
if compgen -G "$SNAP/*/model-00001-of-*.safetensors" >/dev/null 2>&1; then
    ok "model weights present in cache (no download needed)."
elif [[ -d "$SNAP" ]]; then
    warn "model dir exists but weights look incomplete — will re-download on use."
else
    warn "model NOT cached — first load downloads ~15G (set HF_TOKEN; needs network)."
fi

# --- optional: rebuild ----------------------------------------------------
if [[ "$DO_REBUILD" == "1" ]]; then
    say; say "### REBUILD requested -> calling rebuild_all_kernels.sh --clean ###"
    if [[ "${VIRTUAL_ENV:-}" != "$VENV" ]]; then
        # shellcheck disable=SC1091
        source "$VENV/bin/activate"
    fi
    bash "$SCRIPT_DIR/rebuild_all_kernels.sh" --clean --verify-source
fi

# --- optional: fetch model ------------------------------------------------
if [[ "$DO_FETCH" == "1" ]]; then
    say; say "### FETCH-MODEL requested -> downloading $MODEL (safetensors only) ###"
    if [[ -z "${HF_TOKEN:-}" ]]; then
        warn "HF_TOKEN not set. Qwen-7B is public so this may still work; export"
        warn "  HF_TOKEN=hf_... first if the download 401s."
    fi
    "$PY" -m huggingface_hub.commands.huggingface_cli download "$MODEL" \
        --exclude "*.pth" "original/*" 2>&1 | tail -5 \
      || "$VENV/bin/huggingface-cli" download "$MODEL" --exclude "*.pth" "original/*" 2>&1 | tail -5
fi

# --- verdict --------------------------------------------------------------
say; say "================================================================"
say "PREFLIGHT SUMMARY:  GREEN=$GREEN  REBUILD=$NEEDS_REBUILD  FAIL=$HARD_FAIL"
say "================================================================"
if [[ "$HARD_FAIL" -gt 0 ]]; then
    say "RESULT: NOT READY — hard failures above (GPU/torch/venv). Fix those first."
    exit 1
elif [[ "$NEEDS_REBUILD" -gt 0 ]]; then
    say "RESULT: NEEDS WORK — re-run with --rebuild (and --fetch-model if uncached),"
    say "        then re-run this preflight. Final gate before benchmarking:"
    say "          bash $SCRIPT_DIR/verify_phase6e_byte_eq.sh --cuda   # must PASS"
    exit 2
else
    say "RESULT: READY. Final correctness gate before booking benchmark time:"
    say "          bash $SCRIPT_DIR/verify_phase6e_byte_eq.sh --cuda   # expect PASS"
    say "        Then run Test 1 (roofline): roofline_ncu_runner.sh (ncu-unlocked pod)."
    exit 0
fi
