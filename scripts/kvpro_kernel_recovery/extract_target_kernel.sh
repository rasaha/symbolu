#!/usr/bin/env bash
# K2-M1 Phase A completion — extract the EXACT target kernel's pod-only context so the
# Phase D patch can be written correctly. Prints (for you to paste back):
#   1) base flash_fwd_kernel.h loop context around the int4 K-load/transform site;
#   2) the exact int4kv_packed splitkv symbol's static resources (regs/stack/local);
#   3) SASS local-spill evidence (LDL/STL) for that symbol — the real spill proof;
#   4) flash_api.cpp + flash.h int4-packed setup — where the KVPRO_K2_M1 runtime flag slots in.
# Read-only. POD-ONLY (needs /workspace/dev checkout + built .so + cuobjdump). c++filt optional
# (target is matched by mangled bool pattern Lb1ELb1EEE = Is_int4kv=Is_int4kv_packed=true).
set -u
PY="${PYBIN:-python3}"; command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python3 || true)"
FA_DIR="${FA_DIR:-/workspace/dev/vllm-flash-attn-dev}"
SRC="$FA_DIR/csrc/flash_attn/src"
API="$FA_DIR/csrc/flash_attn/flash_api.cpp"
TMP="$(mktemp -d 2>/dev/null || echo /tmp)"

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
  grep -nE "int4_packed_load_K_block" "$KH" | cut -d: -f1 | while read -r ln; do
    a=$((ln>22 ? ln-22 : 1)); b=$((ln+22))
    echo "===== lines $a..$b ====="; sed -n "${a},${b}p" "$KH"; echo
  done
  echo "--- how tKsK / tKVcKV are partitioned (the transform's output tile + coord tensor) ---"
  grep -nE "tKsK|tKVcKV|partition_.*sK|Tensor.*sK|make_tiled_copy" "$KH" | head -40 || true
else
  echo "[UNAVAILABLE] $KH not found. Reconstruct the dev tree first:"
  echo "  FA_TARBALL=/workspace/vllm-flash-attn-dev-src.tar.gz bash scripts/kvpro_kernel_recovery/k0_build.sh"
fi

# locate the built .so once
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

echo
echo "############################################################"
echo "# 2) EXACT TARGET SYMBOL — int4kv_packed splitkv resources"
echo "############################################################"
if [ -n "${SO:-}" ] && [ -f "$SO" ] && command -v cuobjdump >/dev/null 2>&1; then
  echo "[.so] $SO"
  # Dump to a FILE (do NOT pipe into 'python -' + heredoc: the heredoc replaces stdin, so
  # sys.stdin.read() would be empty — that was the bug). Parse the file via argv instead.
  cuobjdump -res-usage "$SO" > "$TMP/resusage.txt" 2>/dev/null || true
  HAVE_FILT=0; command -v c++filt >/dev/null 2>&1 && HAVE_FILT=1
  "$PY" - "$HAVE_FILT" "$TMP/resusage.txt" <<'PY'
import sys, subprocess, re
have_filt = sys.argv[1] == "1"
text = open(sys.argv[2]).read() if len(sys.argv) > 2 else ""
def dm(sym):
    if not have_filt: return sym
    try: return subprocess.run(["c++filt", sym], capture_output=True, text=True).stdout.strip()
    except Exception: return sym
# int4kv=true AND int4kv_packed=true == last two template bools true == mangled '...Lb1ELb1EEEvNS_16Flash_fwd_params'
PACKED = re.compile(r"Lb1ELb1EEEvNS_16Flash_fwd_params")
cur=None; rows=[]
for ln in text.splitlines():
    m=re.search(r"Function\s+(\S+?):?\s*$", ln)          # strip trailing ':'
    if m: cur=m.group(1); continue
    m=re.search(r"REG:(\d+).*STACK:(\d+).*SHARED:(\d+)", ln)
    if m and cur: rows.append((cur, int(m.group(1)), int(m.group(2)), int(m.group(3))))
if not rows:
    print("  (no Function/REG rows parsed — cuobjdump -res-usage empty? check toolkit)"); raise SystemExit(0)
print(f"{'REG':>4} {'STACK':>6} {'SHARED':>7}  symbol (splitkv only; TARGET = int4kv_packed)")
tgt=[]
for sym,reg,stack,sh in rows:
    if "flash_fwd_splitkv_kernel" not in sym: continue    # substring works on mangled too
    is_pkd = bool(PACKED.search(sym))
    if is_pkd: tgt.append((sym,reg,stack,sh))
    label = dm(sym) if have_filt else sym
    print(f"{reg:>4} {stack:>6} {sh:>7}  {label[:150]}{'  <== TARGET' if is_pkd else ''}")
print()
if tgt:
    for sym,reg,stack,sh in tgt:
        occ=int(65536/(reg*32))
        print(f"TARGET int4kv_packed: REG={reg} STACK={stack} SHARED={sh} -> occupancy {occ}/64 = {100*occ/64:.0f}%")
        print(f"  sym: {sym}")
else:
    print("(no int4kv_packed match. If ALL splitkv rows above are stock/causal, the packed kernel may")
    print(" be in a separate cubin — try: cuobjdump -res-usage \"$SO\" | grep -A1 int4kv_packed )")
PY
else
  echo "[UNAVAILABLE] need the venv .so + cuobjdump (export PATH=\$PATH:/usr/local/cuda/bin)."
fi

echo
echo "############################################################"
echo "# 3) SASS SPILL EVIDENCE — LDL/STL per splitkv function (real spill proof)"
echo "############################################################"
if [ -n "${SO:-}" ] && [ -f "$SO" ] && command -v cuobjdump >/dev/null 2>&1; then
  echo "LDL/STL = local load/store = register spill traffic; LDS/STS = shared. TARGET row is int4kv_packed."
  # cuobjdump -sass headers are 'Function : _ZN...'  (NOT .text._ZN...). Track that.
  cuobjdump -sass "$SO" 2>/dev/null | awk '
    /Function : / {f=$3; if (f ~ /flash_fwd_splitkv_kernel/) {cur=f; seen[cur]=1} else {cur=""}}
    cur!="" && /LDL/ {ldl[cur]++}
    cur!="" && /STL/ {stl[cur]++}
    cur!="" && /LDS/ {lds[cur]++}
    cur!="" && /STS/ {sts[cur]++}
    END {for (k in seen) {
           t = (k ~ /Lb1ELb1EEEvNS_16Flash_fwd_params/) ? "  <== TARGET int4kv_packed" : ""
           printf "  LDL=%-5d STL=%-5d LDS=%-6d STS=%-6d %s%s\n", ldl[k], stl[k], lds[k], sts[k], substr(k,1,60), t }}
  ' | sort -t= -k2 -n || true
  echo "(LDL/STL>0 on TARGET = confirmed spill to local memory. LDL/STL=0 with nonzero STACK ="
  echo " call-frame/alloca, NOT a hot-path spill — I will report that honestly, not as an HBM spill.)"
else
  echo "[UNAVAILABLE] (same prerequisites as section 2)"
fi

echo
echo "############################################################"
echo "# 4) FLAG-PLUMBING CONTEXT — flash_api.cpp + flash.h (for KVPRO_K2_M1)"
echo "############################################################"
if [ -f "$API" ]; then
  echo "[file] $API"
  echo "--- int4-packed dispatch / guard / params setup (where the getenv flag slots in) ---"
  grep -nE "Int4KvPackedGuard|packed_n_protect|k_packed|run_mha_fwd_splitkv_dispatch_int4kv_packed|getenv|k2m1|num_splits" "$API" | head -50 || echo "(no hits)"
  echo
  echo "--- context (±10 lines) around the packed guard/dispatch ---"
  grep -nE "Int4KvPackedGuard|run_mha_fwd_splitkv_dispatch_int4kv_packed" "$API" | cut -d: -f1 | head -4 | while read -r ln; do
    a=$((ln>10 ? ln-10 : 1)); b=$((ln+14)); echo "===== $API $a..$b ====="; sed -n "${a},${b}p" "$API"; echo
  done
else
  echo "[UNAVAILABLE] $API not found (dev tree missing)."
fi
FH="$SRC/flash.h"
if [ -f "$FH" ]; then
  echo "--- flash.h Flash_fwd_params int4-packed fields (where to add the k2m1 flag field) ---"
  grep -nE "packed|k_packed|n_protect|int4|struct Flash_fwd_params" "$FH" | head -40 || true
fi
echo
echo "== NEXT: paste sections 1–4. Then I write ONE complete Phase D patch (M1A: staged"
echo "   reconstruction in int4_packed_load_K_block + KVPRO_K2_M1 runtime flag, default OFF). =="
