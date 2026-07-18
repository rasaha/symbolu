#!/usr/bin/env bash
# Permission-free occupancy probe for the int4 decode-attention kernel (ncu is
# ERR_NVGPUCTRPERM-blocked). cuobjdump reads STATIC resource usage (registers /
# shared mem per kernel) straight from the installed .so — no HW counters, no
# elevated perms, no GPU run. Low theoretical occupancy (register- or smem-limited)
# is the most likely cause of the roofline's "2% bandwidth, latency-bound" verdict.
# POD-ONLY (needs the built _vllm_fa2_C .so + cuobjdump from the CUDA toolkit).
#
#   bash cuobjdump_occupancy.sh
set -u
PY="${PYBIN:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python3 || true)"

# A100 sm_80 per-SM limits
REGS_SM=65536; THREADS_SM=2048; WARP=32; SMEM_SM=166912   # 163 KiB opt-in

echo "== locate the int4 kernel .so =="
SO="$("$PY" - <<'PY' 2>/dev/null || true
import os
try:
    import vllm.vllm_flash_attn as m
    d = os.path.dirname(m.__file__)
    for f in os.listdir(d):
        if f.startswith("_vllm_fa2_C") and f.endswith(".so"):
            print(os.path.join(d, f)); break
except Exception:
    pass
PY
)"
[ -n "${SO:-}" ] && [ -f "$SO" ] || { echo "[UNAVAILABLE] _vllm_fa2_C .so not found — build/install the kernel first"; exit 3; }
echo "  .so: $SO ($(du -h "$SO" | cut -f1))"

command -v cuobjdump >/dev/null 2>&1 || { echo "[UNAVAILABLE] cuobjdump not on PATH — add \$CUDA_HOME/bin"; exit 3; }

echo; echo "== per-kernel static resource usage (int4 decode attention) =="
# The decode kernel is the split-KV int4 path; the demangled symbol carries
# 'splitkv' + 'int4'. Show reg/smem for the matching kernels.
cuobjdump -res-usage "$SO" 2>/dev/null \
  | grep -iE "splitkv|int4|fwd_kvcache" -A2 \
  | grep -iE "splitkv|int4|reg|smem|stack" \
  | head -60

echo; echo "== theoretical occupancy from registers (A100 sm_80: ${REGS_SM} reg/SM, ${THREADS_SM} thr/SM) =="
echo "  paste the REG count above; occupancy = min(32 warps, floor(${REGS_SM}/(regs*${WARP})), floor(${THREADS_SM}/${WARP}))/32"
"$PY" - "$REGS_SM" "$THREADS_SM" <<'PY'
import sys
regs_sm, threads_sm = int(sys.argv[1]), int(sys.argv[2])
warp, max_warps = 32, threads_sm // 32
print(f"  {'regs/thread':>12} {'warps/SM (reg-lim)':>20} {'occupancy':>12}")
for regs in (64, 96, 128, 160, 168, 192, 224, 255):
    reg_warps = (regs_sm // (regs * warp))
    occ = min(max_warps, reg_warps) / max_warps
    flag = "  <-- low" if occ < 0.5 else ""
    print(f"  {regs:>12} {min(max_warps, reg_warps):>20} {occ*100:>10.0f}%{flag}")
print("\n  (>=64 regs/thread already caps occupancy on A100; a flash+dequant+splice")
print("   kernel commonly runs 160-255 regs -> 12-25% occupancy -> the latency-bound tell.)")
PY

echo; echo "next: if occupancy is low, the K2 kernel rewrite target is register pressure"
echo "      (vectorized nibble load, fewer live temporaries, smem staging) — NOT the gather."
