#!/usr/bin/env bash
# K2-M1 Phase A completion — extract the EXACT target kernel's pod-only context so the
# Phase D patch can be written correctly. Prints (for you to paste back):
#   1) the base flash_fwd_kernel.h loop context around the int4 K-load/transform site
#      (the fragment iteration + live state that HOSTS int4_packed_load_K_block);
#   2) the exact int4kv_packed splitkv symbol's static resources (regs/stack/local),
#      isolated from the stock/causal variants by demangling;
#   3) SASS local-spill evidence (LDL/STL counts) for that symbol — the real spill proof
#      (nonzero STACK alone is NOT proof of HBM spill).
# Read-only. POD-ONLY (needs /workspace/dev checkout + built .so + cuobjdump + c++filt).
set -u
PY="${PYBIN:-python3}"; command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python3 || true)"
FA_DIR="${FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
SRC="$FA_DIR/csrc/flash_attn/src"

echo "############################################################"
echo "# 1) BASE LOOP CONTEXT — flash_fwd_kernel.h (pod-only)"
echo "############################################################"
KH="$SRC/flash_fwd_kernel.h"
if [ -f "$KH" ]; then
  echo "[file] $KH"
  echo "--- call sites of the int4 packed loader + Is_int4kv_packed branch ---"
  grep -nE "int4_packed_load_K_block|int4_packed_load_V_block|Is_int4kv_packed|Is_int4kv" "$KH" || echo "(no hits?)"
  echo
  echo "--- context (±22 lines) around each int4_packed_load_K_block call ---"
  # print surrounding lines so I can see tKsK/tKVcKV partition + live state at the site
  grep -nE "int4_packed_load_K_block" "$KH" | cut -d: -f1 | while read -r ln; do
    a=$((ln>22 ? ln-22 : 1)); b=$((ln+22))
    echo "===== lines $a..$b ====="
    sed -n "${a},${b}p" "$KH"
    echo
  done
  echo "--- how tKsK / tKVcKV (the transform's output tile + coord tensor) are partitioned ---"
  grep -nE "tKsK|tKVcKV|partition_.*sK|Tensor.*sK|make_tiled_copy" "$KH" | head -40 || true
else
  echo "[UNAVAILABLE] $KH not found. Fresh pod? reconstruct the dev tree first:"
  echo "  FA_TARBALL=/workspace/vllm-flash-attn-dev-src.tar.gz bash scripts/kvpro_kernel_recovery/k0_build.sh"
fi

echo
echo "############################################################"
echo "# 2) EXACT TARGET SYMBOL — int4kv_packed splitkv resources"
echo "############################################################"
SO="$("$PY" - <<'PY' 2>/dev/null || true
import os
try:
    import vllm.vllm_flash_attn as m
    d=os.path.dirname(m.__file__)
    for f in os.listdir(d):
        if f.startswith("_vllm_fa2_C") and f.endswith(".so"): print(os.path.join(d,f)); break
except Exception: pass
PY
)"
if [ -n "${SO:-}" ] && [ -f "$SO" ] && command -v cuobjdump >/dev/null 2>&1; then
  echo "[.so] $SO"
  HAVE_FILT=0; command -v c++filt >/dev/null 2>&1 && HAVE_FILT=1
  # Pair each Function symbol with its REG/STACK/LOCAL line, demangle, and keep only the
  # flash_fwd_splitkv_kernel instantiations whose LAST TWO template bools are true,true
  # (Is_int4kv=true, Is_int4kv_packed=true) — the production packed target.
  cuobjdump -res-usage "$SO" 2>/dev/null | "$PY" - "$HAVE_FILT" <<'PY'
import sys, subprocess, re
have_filt = sys.argv[1] == "1"
lines = sys.stdin.read().splitlines()
def demangle(sym):
    if not have_filt: return sym
    try: return subprocess.run(["c++filt", sym], capture_output=True, text=True).stdout.strip()
    except Exception: return sym
cur=None; rows=[]
for ln in lines:
    m=re.search(r"Function\s+(\S+)", ln)
    if m: cur=m.group(1); continue
    m=re.search(r"REG:(\d+).*STACK:(\d+).*(?:SHARED:(\d+)).*", ln)
    if m and cur: rows.append((cur, int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)))
print(f"{'REG':>4} {'STACK':>6} {'SHARED':>7}  demangled (int4kv_packed target = ends ', true, true>')")
tgt=[]
for sym,reg,stack,sh in rows:
    d=demangle(sym)
    if "flash_fwd_splitkv_kernel" not in d: continue
    is_pkd = bool(re.search(r"true,\s*true>\s*\(", d)) or d.rstrip().endswith("true, true>")
    tag = "  <== TARGET (int4kv,packed)" if is_pkd else ""
    if is_pkd: tgt.append((sym,reg,stack,sh))
    print(f"{reg:>4} {stack:>6} {sh:>7}  {d[:150]}{tag}")
print()
if tgt:
    for sym,reg,stack,sh in tgt:
        print(f"TARGET SYMBOL: {sym}")
        print(f"  REG={reg} STACK={stack} SHARED={sh} -> occupancy {int(65536/(reg*32))}/64 warps "
              f"= {100*int(65536/(reg*32))/64:.0f}%")
else:
    print("(no int4kv_packed instantiation matched; c++filt missing? falling back: inspect the "
          "flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.o object directly.)")
PY
else
  echo "[UNAVAILABLE] need the venv .so + cuobjdump (export PATH=\$PATH:/usr/local/cuda/bin)."
fi

echo
echo "############################################################"
echo "# 3) SASS SPILL EVIDENCE — LDL/STL per function (real spill proof)"
echo "############################################################"
if [ -n "${SO:-}" ] && [ -f "$SO" ] && command -v cuobjdump >/dev/null 2>&1; then
  echo "LDL/STL (local load/store = register spill traffic) and LDS/STS (shared) per splitkv function:"
  cuobjdump -sass "$SO" 2>/dev/null | awk '
    /\.text\._ZN5flash24flash_fwd_splitkv_kernel/ {f=$NF; ldl[f]=0; stl[f]=0; lds[f]=0; sts[f]=0; seen[f]=1}
    /LDL/ {ldl[f]++} /STL/ {stl[f]++} /LDS/ {lds[f]++} /STS/ {sts[f]++}
    END {for (k in seen) printf "  LDL=%-5d STL=%-5d LDS=%-5d STS=%-5d  %s\n", ldl[k], stl[k], lds[k], sts[k], substr(k,1,80)}
  ' | sort || true
  echo "(LDL/STL > 0 on the target symbol = confirmed register spill to local memory. If LDL/STL=0"
  echo " despite nonzero STACK, the STACK is call-frame/alloca, NOT a hot-path spill — report that honestly.)"
else
  echo "[UNAVAILABLE] (same prerequisites as section 2)"
fi

echo
echo "== NEXT: paste sections 1–3. Section 1 lets me write the Phase D M1A.2 (late-unpack) patch"
echo "   against the real base loop; section 2/3 give the exact baseline regs+spill for the gate. =="
