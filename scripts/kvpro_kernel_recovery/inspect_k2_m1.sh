#!/usr/bin/env bash
# K2-M1 Phase F — static-resource gate for the built K2-M1 wheel (control + unroll sweep).
# The int kM1Unroll param makes each factor a distinct symbol in ONE wheel:
#   Lb1ELb1ELi0E = control (full unroll, freshly compiled)   <- the clean baseline
#   Lb1ELb1ELi{1,2,4}E = M1 unroll factors
# Reports REG/STACK/SHARED + SASS LDL/STL per factor and compares each M1 factor to the
# SAME-WHEEL control. Register count is a signal, not the verdict; runtime latency
# (bench_k2_m1_op.py, then the 16K/32K bench) is authoritative. POD-ONLY.
#
#   bash scripts/kvpro_kernel_recovery/inspect_k2_m1.sh
set -u
PY="${PYBIN:-python3}"; command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python3 || true)"
TMP="$(mktemp -d 2>/dev/null || echo /tmp)"

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

cuobjdump -res-usage "$SO" > "$TMP/res.txt" 2>/dev/null || true
cuobjdump -sass      "$SO" > "$TMP/sass.txt" 2>/dev/null || true

"$PY" - "$TMP/res.txt" "$TMP/sass.txt" <<'PY'
import re, sys
res = open(sys.argv[1]).read() if len(sys.argv) > 1 else ""
sass = open(sys.argv[2]).read() if len(sys.argv) > 2 else ""
# int4-packed target carries Lb1ELb1E (int4kv,packed) then Li<N>E (K2-M1 unroll factor).
TGT = re.compile(r"Lb1ELb1ELi(\d+)E.*?vNS_16Flash_fwd_params")

# --- static resources per factor (from -res-usage) ---
cur = None
res_by = {}
for ln in res.splitlines():
    m = re.search(r"Function\s+(\S+?):?\s*$", ln)
    if m: cur = m.group(1); continue
    m = re.search(r"REG:(\d+).*STACK:(\d+).*SHARED:(\d+)", ln)
    if m and cur and "flash_fwd_splitkv_kernel" in cur:
        t = TGT.search(cur)
        if t:
            res_by.setdefault(int(t.group(1)), []).append(
                (int(m.group(1)), int(m.group(2)), int(m.group(3))))

# --- LDL/STL per factor (from -sass) ---
sass_by = {}
cur = None; keep = False
for ln in sass.splitlines():
    m = re.search(r"Function :\s+(\S+)", ln)
    if m:
        cur = m.group(1); t = TGT.search(cur)
        keep = ("flash_fwd_splitkv_kernel" in cur) and bool(t)
        if keep: sass_by.setdefault(int(t.group(1)), []).append([0, 0])  # [ldl, stl]
        continue
    if keep and cur:
        if "LDL" in ln: sass_by[int(TGT.search(cur).group(1))][-1][0] += 1
        if "STL" in ln: sass_by[int(TGT.search(cur).group(1))][-1][1] += 1

if not res_by:
    print("  (no int4kv_packed Li<N> symbols — did KVPRO_K2_M1_BUILD compile? check the wheel)")
    raise SystemExit(0)

def rng(vals, i):
    xs = [v[i] for v in vals]
    return f"{min(xs)}-{max(xs)}" if xs else "-", (max(xs) if xs else 0)

print(f"\n{'factor':<10}{'#sym':>6}{'REG':>10}{'STACK':>12}{'SHARED':>9}{'LDL(max)':>12}{'STL(max)':>10}")
maxldl, maxstl = {}, {}
for f in sorted(res_by):
    rvals = res_by[f]
    reg_r, _ = rng(rvals, 0); stk_r, _ = rng(rvals, 1)
    shared = rvals[0][2] if rvals else 0
    svals = sass_by.get(f, [])
    ldl_r, ldl_max = rng(svals, 0); stl_r, stl_max = rng(svals, 1)
    maxldl[f] = ldl_max; maxstl[f] = stl_max
    name = "control" if f == 0 else f"U{f}"
    print(f"{name:<10}{len(rvals):>6}{reg_r:>10}{stk_r:>12}{shared:>9}{ldl_r:>12}{stl_r:>10}")

# --- gate: compare each M1 factor's worst spill to the same-wheel control (factor 0) ---
print("\n-- static gate (advisory; runtime latency is authoritative) --")
if 0 not in maxldl:
    print("  no control (Li0E) symbol found — cannot compute reduction"); raise SystemExit(0)
c_ldl, c_stl = maxldl[0], maxstl[0]
advance = []
for f in (1, 2, 4):
    if f not in maxldl:
        continue
    dl = (c_ldl - maxldl[f]) / c_ldl if c_ldl else 0.0
    ds = (c_stl - maxstl[f]) / c_stl if c_stl else 0.0
    ok = (dl >= 0.25) or (ds >= 0.25)
    print(f"  U{f}: max LDL {maxldl[f]} ({dl*100:+.0f}% vs control {c_ldl}), "
          f"max STL {maxstl[f]} ({ds*100:+.0f}% vs {c_stl})  -> "
          f"{'spill materially reduced' if ok else 'little static change'}")
    if ok: advance.append(f)
print()
if advance:
    print(f"STATIC: spill reduced for {['U'+str(f) for f in advance]} -> run bench_k2_m1_op.py to "
          "confirm on DECODE latency (the real gate).")
else:
    print("STATIC: no factor cut spill >=25%. Still run bench_k2_m1_op.py once — latency can move "
          "even at similar static counts; if it does not, that is a measured NO-GO.")
print("Next: python CTM_plus/Bench/scripts/bench_k2_m1_op.py --context-tokens 16000 --batch 8 --gen 64")
PY
