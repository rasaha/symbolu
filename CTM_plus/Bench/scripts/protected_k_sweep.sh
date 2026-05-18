#!/usr/bin/env bash
# §20.4.1 follow-on — outlier-protected K sweep (one-command driver).
#
# Tests whether protecting the top-magnitude K channels at FP16 (and
# leaving the rest INT4) recovers long-context quality — the path to
# ~3x compression *with* K-channel quality, instead of the ~2.3x that
# K-INT8 caps at.
#
# Runs on the SAME 16k needle setup as the §20.4 / §20.4.1 sprints:
#   fraction 0.000  — full INT4 K (the §20.4.1 RED anchor, ~29%)
#   fraction 0.005  — protect top 0.5% of K channels
#   fraction 0.010  — top 1%
#   fraction 0.020  — top 2%
#   fraction 0.040  — top 4%
# V is INT4 throughout; K is INT4 except the protected channels.
#
# PREREQUISITE: run the K-INT8 sanity check first (see
# DIAGNOSTIC_SPRINT_LONG_CONTEXT_RUNBOOK.md / the K-INT8 commands). This
# sweep only makes sense once K-INT8 has shown K precision can recover
# long-context behaviour at all.
#
# Usage (from CTM_plus/Bench/, venv-hf, A100):
#   bash scripts/protected_k_sweep.sh
#   SAMPLES=8 OUTDIR=bench_out/protected_k bash scripts/protected_k_sweep.sh
#
# Pod/disk/cache setup is identical to the K-INT8 run — see
# PROTECTED_K_SWEEP_RUNBOOK.md.

set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
DTYPE="${DTYPE:-float16}"
DEVICE="${DEVICE:-auto}"
OUTDIR="${OUTDIR:-bench_out/protected_k}"
CTX="${CTX:-16000}"
DEPTHS="${DEPTHS:-0.1,0.5,0.9}"
SAMPLES="${SAMPLES:-8}"
DECODE_TOKENS="${DECODE_TOKENS:-64}"

mkdir -p "${OUTDIR}"

COMMON=(
  --model "${MODEL}"
  --dtype "${DTYPE}"
  --device "${DEVICE}"
  --context-lengths "${CTX}"
  --needle-depths "${DEPTHS}"
  --needle-samples "${SAMPLES}"
  --needle-decode-tokens "${DECODE_TOKENS}"
  --skip-perplexity
  --k-bits 4
  --v-bits 4
)

for FRAC in 0.000 0.005 0.010 0.020 0.040; do
  echo "================================================================"
  echo "  protected-K sweep: k_protect_fraction=${FRAC}"
  echo "================================================================"
  python -m ctm_bench.scripts.track_e_long_context "${COMMON[@]}" \
    --k-protect-fraction "${FRAC}" \
    --output "${OUTDIR}/protect_${FRAC}.json"
done

echo
echo "================================================================"
echo "  Protected-K sweep complete. 5 cell JSONs in ${OUTDIR}/"
echo "================================================================"
python - <<PY
import json, glob
for f in sorted(glob.glob('${OUTDIR}/protect_*.json')):
    d = json.load(open(f))
    for _, b in d.get('deltas', {}).get('per_context_length', {}).items():
        print('%-22s' % f.split('/')[-1],
              'needle=%3.0f%%' % ((b.get('int4_needle_accuracy') or 0)*100),
              'first_stutter=%s' % b.get('int4_first_stutter_earliest'),
              'repeat=%.2f' % (b.get('int4_repeated_token_rate_mean') or 0),
              'collapse=%3.0f%%' % ((b.get('int4_entropy_collapse_rate') or 0)*100))
PY
