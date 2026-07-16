#!/usr/bin/env bash
# KVPro V3 6F-A measurement #1 — alpha: what share of the decode path does the page-local
# (store-as-consumed) layout actually improve? Resolves the PROVISIONAL aggregate gate WITHOUT
# any 6F-C code. Times the standard-path permute-copy (native->head-major, whole KV, per step,
# int4_protected_k_cache.py:520-548) that page-local eliminates, the full in-repo decode kernel
# (oracle-checked), and the raw unzip read — median + p95, per context. Stops and reports after
# alpha. POD-ONLY; writes UNAVAILABLE if GPU/Triton/kernel is missing.
#
#   CONTEXTS="4096 16384 32768" ITERS=100 ./10_alpha_decode_share.sh
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYBIN="${PYBIN:-python3}"; OUTDIR="${OUTDIR:-$HERE/runs}"; mkdir -p "$OUTDIR"

echo "== KVPro V3 6F-A measurement #1: alpha (decode-path share) =="
"$PYBIN" "$HERE/10_alpha_decode_share.py" \
    --contexts "${CONTEXTS:-4096 16384 32768}" --iters "${ITERS:-100}" \
    --h-kv "${HKV:-4}" --head-dim "${HEAD_DIM:-128}" --gqa-g "${GQA_G:-7}" \
    --bs "${BS:-32}" --v-group-size "${VGROUP:-32}" --n-protect "${NPROTECT:-5}" \
    --out "$OUTDIR/alpha_decode_share.json"

echo
echo "artifact: $OUTDIR/alpha_decode_share.json"
echo "commit (from repo root): git add -f scripts/kvpro_v3_profile/runs/alpha_decode_share.json"
echo "STOP after alpha: if verdict=STRONG_RUN_BETA, run one nsys whole-step trace for beta before 6F-C."
