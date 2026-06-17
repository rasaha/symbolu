#!/usr/bin/env bash
# 00 — Environment gate for the KVPro v2 RunPod validation harness.
# Verifies the pod can actually run int4_protected decode/serving BEFORE any
# decode test runs. Prints PASS/FAIL per check + an overall verdict, and exits
# non-zero on any HARD failure. No result here is "measured" — these are gates.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

section "KVPro v2 — environment gate"
HARD_FAIL=0

# 1) nvidia-smi + GPU count -------------------------------------------------
N_GPU="$(gpu_count)"
if [[ "$N_GPU" -ge 1 ]]; then
  ok "nvidia-smi present; GPUs visible: $N_GPU"
  nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader 2>/dev/null | sed 's/^/        /'
else
  fail "nvidia-smi not found or 0 GPUs — int4_protected needs a CUDA GPU."
  HARD_FAIL=1
fi

# 2) CUDA / nvcc ------------------------------------------------------------
if command -v nvcc >/dev/null 2>&1; then
  ok "nvcc: $(nvcc --version 2>/dev/null | grep -oE 'release [0-9.]+' | head -1)"
else
  warn "nvcc not on PATH (a built vLLM may still run; build steps would need it)."
fi
python3 - <<'PY'; CUDA_RC=$?
import sys
try:
    import torch
    print(f"        torch {torch.__version__}; torch.version.cuda={torch.version.cuda}")
    sys.exit(0 if torch.version.cuda else 3)
except Exception as e:
    print(f"        torch import failed: {e}"); sys.exit(3)
PY
if [[ "$CUDA_RC" -eq 0 ]]; then ok "torch built with CUDA"; else fail "torch missing/!CUDA"; HARD_FAIL=1; fi

# 3) torch CUDA runtime available ------------------------------------------
python3 - <<'PY'; TC_RC=$?
import sys
try:
    import torch
    sys.exit(0 if torch.cuda.is_available() else 4)
except Exception:
    sys.exit(4)
PY
if [[ "$TC_RC" -eq 0 ]]; then ok "torch.cuda.is_available() == True"; else fail "torch.cuda.is_available() == False"; HARD_FAIL=1; fi

# 4) vLLM 0.7.3 V0 ----------------------------------------------------------
python3 - <<'PY'; VLLM_RC=$?
import sys, os
try:
    import vllm
    v = getattr(vllm, "__version__", "?")
    print(f"        vllm {v}")
    if v != "0.7.3":
        print(f"        WARN: expected 0.7.3 (KVPro's validated vLLM); got {v}")
    # V0 engine: KVPro is a V0 backend. VLLM_USE_V1=1 forces V1 (incompatible).
    if os.environ.get("VLLM_USE_V1", "0") == "1":
        print("        FAIL: VLLM_USE_V1=1 set — KVPro is a V0 backend; unset it.")
        sys.exit(5)
    sys.exit(0)
except Exception as e:
    print(f"        vllm import failed: {e}"); sys.exit(5)
PY
if [[ "$VLLM_RC" -eq 0 ]]; then ok "vLLM importable, V0 path (see version note above)"; else fail "vLLM import / V0 check failed"; HARD_FAIL=1; fi

# 5) int4 flash-attn fork (HARD) -------------------------------------------
if have_int4_kernel; then
  ok "flash_attn_with_int4_kvcache importable (vllm.vllm_flash_attn) — int4 decode kernel present"
else
  fail "flash_attn_with_int4_kvcache NOT importable from vllm.vllm_flash_attn."
  fail "The int4 vllm-flash-attn fork is not built/installed. Decode + serving"
  fail "will fall over (only prefill works). BUILD THE FORK before any decode test."
  HARD_FAIL=1
fi

# 6) PROTECT_MASK_PATH ------------------------------------------------------
if mask_path_ok; then
  ok "PROTECT_MASK_PATH set and exists: $PROTECT_MASK_PATH"
else
  fail "PROTECT_MASK_PATH unset or missing — required to build Int4ProtectedLLM."
  print_mask_howto "Qwen/Qwen2.5-7B-Instruct" "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt"
  HARD_FAIL=1
fi

section "Gate verdict"
if [[ "$HARD_FAIL" -eq 0 ]]; then
  ok "ENVIRONMENT GATE: PASS — decode/serving tests may run."
  exit 0
else
  fail "ENVIRONMENT GATE: FAIL — fix the [FAIL] items above before decode tests."
  exit 1
fi
