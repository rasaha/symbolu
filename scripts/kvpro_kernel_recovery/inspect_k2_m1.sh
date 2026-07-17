#!/usr/bin/env bash
# K2-M1 Phase F — static-resource gate for the built K2-M1 kernel.
# Reports regs/thread, stack, local, shared, text size, and SASS spill traffic (LDL/STL)
# for the M1 target symbol, and applies the PRE-REGISTERED static gate. Register count is a
# SIGNAL, not the verdict — the gate is measured latency (Phase H). POD-ONLY.
#
#   bash scripts/kvpro_kernel_recovery/inspect_k2_m1.sh
set -u
PY="${PYBIN:-python3}"; command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python3 || true)"
# Pre-registered static gate (from the task):
GATE_PREFERRED=128; GATE_MIN_USEFUL=160

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
[ -n "${SO:-}" ] && [ -f "$SO" ] || { echo "[UNAVAILABLE] .so not found — build K2-M1 first"; exit 3; }
command -v cuobjdump >/dev/null 2>&1 || { echo "[UNAVAILABLE] cuobjdump (export PATH=\$PATH:/usr/local/cuda/bin)"; exit 3; }
echo "[.so] $SO"

echo; echo "== static resources — int4kv_packed splitkv target (demangled) =="
HAVE_FILT=0; command -v c++filt >/dev/null 2>&1 && HAVE_FILT=1
cuobjdump -res-usage "$SO" 2>/dev/null | "$PY" - "$HAVE_FILT" "$GATE_PREFERRED" "$GATE_MIN_USEFUL" <<'PY'
import sys, subprocess, re
have_filt = sys.argv[1]=="1"; PREF=int(sys.argv[2]); MINU=int(sys.argv[3])
def dm(s):
    if not have_filt: return s
    try: return subprocess.run(["c++filt", s], capture_output=True, text=True).stdout.strip()
    except Exception: return s
cur=None; tgt=[]
for ln in sys.stdin.read().splitlines():
    m=re.search(r"Function\s+(\S+)", ln)
    if m: cur=m.group(1); continue
    m=re.search(r"REG:(\d+).*STACK:(\d+).*SHARED:(\d+)", ln)
    if m and cur:
        d=dm(cur)
        if "flash_fwd_splitkv_kernel" in d and (re.search(r"true,\s*true>\s*\(", d) or d.rstrip().endswith("true, true>")):
            tgt.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), d))
if not tgt:
    print("  (no int4kv_packed symbol matched — check c++filt / that KVPRO_K2_M1 variant was built)"); raise SystemExit(0)
worst=max(t[0] for t in tgt)
for reg,stack,sh,d in tgt:
    occ=int(65536/(reg*32)); print(f"  REG={reg} STACK={stack} SHARED={sh}  occ={occ}/64={100*occ/64:.0f}%  {d[:110]}")
print()
verdict = ("PASS-preferred (<=%d)"%PREF if worst<=PREF else
           "PASS-min-useful (<=%d)"%MINU if worst<=MINU else
           "OVER-160 — NOT a fail by itself: only fails if measured latency ALSO misses the gate")
print(f"STATIC GATE: worst target REG={worst} -> {verdict}")
print("REMINDER: register count cannot produce GO/NO-GO. The verdict is Phase H latency (>=20% @16K,32K).")
PY

echo; echo "== text size (target) =="
cuobjdump -res-usage "$SO" 2>/dev/null | grep -iE "splitkv" -A1 | grep -iE "text|size" | head -6 || echo "  (text-size line not in -res-usage on this toolkit; use 'cuobjdump -elf' if needed)"

echo; echo "== SASS spill evidence — LDL/STL (the real proof; STACK alone is not) =="
cuobjdump -sass "$SO" 2>/dev/null | awk '
  /\.text\._ZN5flash24flash_fwd_splitkv_kernel/ {f=$NF; ldl[f]=0; stl[f]=0; seen[f]=1}
  /LDL/ {ldl[f]++} /STL/ {stl[f]++}
  END {for (k in seen) printf "  LDL=%-5d STL=%-5d  %s\n", ldl[k], stl[k], substr(k,1,80)}' | sort || true
echo "  (compare LDL/STL against the production baseline from extract_target_kernel.sh section 3:"
echo "   fewer LDL/STL on the M1 symbol = spill reduced. This is the honest spill metric.)"
