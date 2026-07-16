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

echo "== classify =="
CLASSIFY_ARGS=(--probe "$PROBE_JSON" --out "$VERDICT_JSON")
[ -n "${PEAK_HBM_GBPS:-}" ] && CLASSIFY_ARGS+=(--peak-hbm-gbps "$PEAK_HBM_GBPS")
[ -n "${PEAK_FP32_TFLOPS:-}" ] && CLASSIFY_ARGS+=(--peak-fp32-tflops "$PEAK_FP32_TFLOPS")
"$PYBIN" "$HERE/08_classify_unzip_bound.py" "${CLASSIFY_ARGS[@]}"

echo
echo "artifacts: $PROBE_JSON ; $VERDICT_JSON"
echo "commit (from repo root): git add -f scripts/kvpro_v3_profile/runs/unzip_bound*.json"
