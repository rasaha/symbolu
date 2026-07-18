#!/usr/bin/env bash
# KVPro V3 Step-0 — Part H: two-half-kernel unzip-bound probe (POD-ONLY, HARDWARE-UNTESTED).
# Answers "is the INT4 decode unzipper memory-bound or compute-bound?" WITHOUT ncu (counter
# perm blocked) by timing FETCH-only / MATH-only / FULL specialisations of the SAME unzip
# inner loop, then classifying + roofline cross-checking. Writes label=UNAVAILABLE (never
# fabricated) if GPU/Triton is missing.
#
#   CONTEXTS="4096 16384 32768" ITERS=100 ./07_unzip_bound_probe.sh
#
# Env knobs: CONTEXTS ITERS HKV HEAD_DIM BS VGROUP NPROTECT OUTDIR PEAK_HBM_GBPS PEAK_FP32_TFLOPS
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYBIN="${PYBIN:-python3}"
OUTDIR="${OUTDIR:-$HERE/runs}"; mkdir -p "$OUTDIR"
PROBE_JSON="$OUTDIR/unzip_bound.json"
VERDICT_JSON="$OUTDIR/unzip_bound_verdict.json"

echo "== KVPro V3 unzip-bound probe (fetch / math / full half-kernels) =="
"$PYBIN" "$HERE/unzip_bound_probe.py" \
    --contexts "${CONTEXTS:-4096 16384 32768}" \
    --iters "${ITERS:-100}" \
    --h-kv "${HKV:-4}" --head-dim "${HEAD_DIM:-128}" --bs "${BS:-32}" \
    --v-group-size "${VGROUP:-32}" --n-protect "${NPROTECT:-5}" \
    --out "$PROBE_JSON"
rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
    echo "[warn] probe exited $rc (non-UNAVAILABLE failure)"
fi

echo "== classify (Part H bound + 6F-A page-local gate) =="
CLASSIFY_ARGS=(--probe "$PROBE_JSON" --out "$VERDICT_JSON")
[ -n "${PEAK_HBM_GBPS:-}" ] && CLASSIFY_ARGS+=(--peak-hbm-gbps "$PEAK_HBM_GBPS")
[ -n "${PEAK_FP32_TFLOPS:-}" ] && CLASSIFY_ARGS+=(--peak-fp32-tflops "$PEAK_FP32_TFLOPS")
[ -n "${UNZIP_SHARE:-}" ] && CLASSIFY_ARGS+=(--unzip-share "$UNZIP_SHARE")
[ -n "${DECODE_ATTN_SHARE:-}" ] && CLASSIFY_ARGS+=(--decode-attn-share "$DECODE_ATTN_SHARE")
"$PYBIN" "$HERE/08_classify_unzip_bound.py" "${CLASSIFY_ARGS[@]}"

# --- 6F-A: if the >=20% read gate passed, immediately run the append feasibility spike ---
READ_PASS=$("$PYBIN" -c "import json;d=json.load(open('$VERDICT_JSON'));print(d.get('sixfa_pagelocal',{}).get('read_gate_pass'))" 2>/dev/null || echo "None")
echo
if [ "$READ_PASS" = "True" ]; then
    echo "== 6F-A read gate PASSED -> append feasibility spike =="
    "$PYBIN" "$HERE/09_append_feasibility_spike.py" \
        --context-len "${APPEND_CTX:-32768}" --batches "${BATCHES:-1 32 128 256}" \
        --iters "${APPEND_ITERS:-200}" --h-kv "${HKV:-4}" --head-dim "${HEAD_DIM:-128}" \
        --bs "${BS:-32}" --v-group-size "${VGROUP:-32}" --n-protect "${NPROTECT:-5}" \
        --probe "$PROBE_JSON" --out "$OUTDIR/append_spike.json"
else
    echo "== 6F-A read gate = $READ_PASS (not True) -> skipping append spike (rerun manually if desired) =="
fi

echo
echo "artifacts: $PROBE_JSON ; $VERDICT_JSON ; $OUTDIR/append_spike.json"
echo "commit (from repo root): git add -f scripts/kvpro_v3_profile/runs/unzip_bound*.json scripts/kvpro_v3_profile/runs/append_spike.json"
