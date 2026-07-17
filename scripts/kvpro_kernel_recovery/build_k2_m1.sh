#!/usr/bin/env bash
# K2-M1 Phase E — reproducible, ISOLATED build of the K2-M1 candidate kernel.
# Preserves the known-good production wheel/.so (rollback), applies the M1 patch on top of
# the recovered base tree, rebuilds ONE wheel that contains BOTH the production kernel
# (default) and the M1 variant (behind KVPRO_K2_M1=1 at runtime), and verifies import+symbol.
# The M1 patch (Phase D) is `apply_phase_k2m1a_patches.py`; this script FAILS LOUDLY if absent.
# POD-ONLY (A100, sm_80). Read K2_M1_TARGET_KERNEL.md first.
#
#   bash scripts/kvpro_kernel_recovery/build_k2_m1.sh
#   # rollback to production:  bash scripts/kvpro_kernel_recovery/build_k2_m1.sh --restore
set -u
SYMBOLU="${SYMBOLU:-/workspace/symbolu}"
VENV="${VENV:-/workspace/venv-vllm}"
FA_DIR="${FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
PY="$VENV/bin/python3"; command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python3 || true)"
BK="/workspace/dev/build-logs/k2m1_backup"; mkdir -p "$BK"
M1_PATCH="$SYMBOLU/CTM_plus/Bench/scripts/apply_phase_k2m1a_patches.py"   # Phase D deliverable

vendored_dir() { "$PY" -c 'import os,vllm.vllm_flash_attn as m;print(os.path.dirname(m.__file__))' 2>/dev/null; }

if [ "${1:-}" = "--restore" ]; then
  echo "== restore known-good production kernel =="
  if [ -f "$BK/prod_wheel.whl" ]; then
    pip install --force-reinstall --no-deps "$BK/prod_wheel.whl" && echo "restored from $BK/prod_wheel.whl"
  elif [ -d "$BK/vllm_flash_attn_prod" ]; then
    D="$(vendored_dir)"; [ -n "$D" ] && cp -rf "$BK/vllm_flash_attn_prod/." "$D/" && echo "restored .so into $D"
  else echo "[ERR] no backup found in $BK"; exit 1; fi
  exit 0
fi

# --- 0: the M1 patch must exist (Phase D) ---
if [ ! -f "$M1_PATCH" ]; then
  echo "[BLOCKED] Phase D patch not present: $M1_PATCH"
  echo "  Write it first (needs extract_target_kernel.sh section 1 — the base loop context)."
  echo "  This script intentionally does NOT build a silent no-op wheel."
  exit 2
fi

# --- 1: preserve the known-good production wheel/.so BEFORE touching anything ---
echo "== preserve known-good production kernel =="
if [ -z "$(ls -A "$BK" 2>/dev/null)" ]; then
  PRODW="$(ls -t /workspace/dev/**/dist/vllm_flash_attn-*.whl 2>/dev/null | head -1 || true)"
  if [ -n "${PRODW:-}" ]; then cp "$PRODW" "$BK/prod_wheel.whl" && echo "  backed up wheel -> $BK/prod_wheel.whl"; fi
  D="$(vendored_dir)"; [ -n "$D" ] && cp -r "$D" "$BK/vllm_flash_attn_prod" && echo "  backed up installed .so -> $BK/vllm_flash_attn_prod"
  "$PY" "$SYMBOLU/scripts/kvpro_kernel_recovery/02_hash_installed_kernel.py" > "$BK/prod_hashes.json" 2>/dev/null || true
else echo "  backup already present in $BK (not overwriting)"; fi

# --- 2: apply the M1 patch to the base dev tree (idempotent) ---
echo "== apply K2-M1 patch onto the recovered base tree =="
[ -d "$FA_DIR/csrc" ] || { echo "[ERR] base tree missing at $FA_DIR — run k0_build.sh first"; exit 1; }
( cd "$SYMBOLU" && "$PY" "$M1_PATCH" ) || { echo "[ERR] M1 patch failed to apply"; exit 1; }

# --- 3: build the isolated wheel (+k2m1 local version tag) ---
echo "== build (TORCH_CUDA_ARCH_LIST=8.0) — contains production + M1, M1 gated by KVPRO_K2_M1 =="
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.0}" MAX_JOBS="${MAX_JOBS:-16}" NVCC_THREADS="${NVCC_THREADS:-2}"
export VLLM_FA_LOCAL_VERSION="+k2m1"   # distinct wheel name so it can't be confused with prod
( cd "$FA_DIR" && "$PY" setup.py bdist_wheel ) || { echo "[ERR] build failed — see build log"; exit 1; }
NEWW="$(ls -t "$FA_DIR"/dist/vllm_flash_attn-*k2m1*.whl 2>/dev/null | head -1 || ls -t "$FA_DIR"/dist/*.whl | head -1)"
echo "  built: $NEWW"
sha256sum "$NEWW" | tee "$BK/k2m1_wheel.sha256"

# --- 4: install + verify import & BOTH ops present ---
echo "== install candidate + verify =="
pip install --force-reinstall --no-deps "$NEWW" || { echo "[ERR] install failed"; exit 1; }
"$PY" - <<'PY'
import torch, os, hashlib
import vllm.vllm_flash_attn as m
print("wrapper flash_attn_with_int4_kvcache:", hasattr(m, "flash_attn_with_int4_kvcache"))
print("op fwd_kvcache_int4:", hasattr(torch.ops._vllm_fa2_C, "fwd_kvcache_int4"))
so = [f for f in os.listdir(os.path.dirname(m.__file__)) if f.startswith("_vllm_fa2_C") and f.endswith(".so")]
if so:
    p = os.path.join(os.path.dirname(m.__file__), so[0])
    print("installed .so sha256:", hashlib.sha256(open(p,"rb").read()).hexdigest()[:16], f"({os.path.getsize(p)//(1024*1024)}M)")
print("NOTE: default path is production; KVPRO_K2_M1=1 selects M1 at runtime (verify with a decode call).")
PY
echo "== build done (control + unroll sweep {1,2,4} in ONE wheel; select via KVPRO_K2_M1=0|1|2|4)."
echo "   Next: inspect_k2_m1.sh (static spill per factor vs same-wheel control), then"
echo "         bench_k2_m1_op.py (op/decode latency + token-match) BEFORE any full-model work. =="
