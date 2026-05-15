#!/usr/bin/env bash
# §20.4 long-context decode-stability diagnostic sprint — one-command driver.
#
# Runs the three diagnostic cells from DIAGNOSTIC_SPRINT_LONG_CONTEXT_RUNBOOK.md
# back-to-back on the 16k needle-in-haystack setup:
#
#   1. Sink sweep      — sink_size in {0,4,16,32,64,128}     (6 cells)
#   2. K/V ablation    — K-only INT4, V-only INT4            (2 cells)
#   3. INT5            — bits=5, base config                 (1 cell)
#
# Every cell uses the SAME 16k needle setup (depths 0.1/0.5/0.9, 3 samples,
# 64 decoded tokens, perplexity skipped) so the only moving part per cell is
# the knob under test. Each cell writes its own JSON; the harness logs needle
# success, first-stutter position, repeated-token rate, decode entropy (mean/
# min + collapse flag), cache memory footprint, and decode tokens/sec.
#
# Scope is intentionally bounded: route-A and the fused Marlin kernel are NOT
# touched here. This sprint only decides whether INT4 long-context is
# salvageable (sink / INT5 / adaptive-precision) or whether FP8 becomes the
# long-context default.
#
# Usage:
#   bash scripts/diagnostic_sprint_long_context.sh
#   MODEL=Qwen/Qwen2.5-7B-Instruct OUTDIR=bench_out/diag_sprint \
#       bash scripts/diagnostic_sprint_long_context.sh
#
# Run from CTM_plus/Bench/ inside the venv-hf environment (transformers >= 5,
# torch 2.5.1+cu124). A100 40 GB; ~15-20 min wall (model reloads per cell).

set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
DTYPE="${DTYPE:-float16}"
DEVICE="${DEVICE:-auto}"
OUTDIR="${OUTDIR:-bench_out/diag_sprint}"
CTX="${CTX:-16000}"
DEPTHS="${DEPTHS:-0.1,0.5,0.9}"
SAMPLES="${SAMPLES:-3}"
DECODE_TOKENS="${DECODE_TOKENS:-64}"

mkdir -p "${OUTDIR}"

# Common args for every cell — the fixed 16k needle setup.
COMMON=(
  --model "${MODEL}"
  --dtype "${DTYPE}"
  --device "${DEVICE}"
  --context-lengths "${CTX}"
  --needle-depths "${DEPTHS}"
  --needle-samples "${SAMPLES}"
  --needle-decode-tokens "${DECODE_TOKENS}"
  --skip-perplexity
)

run_cell () {
  local label="$1"; shift
  echo "================================================================"
  echo "  §20.4 diagnostic cell: ${label}"
  echo "================================================================"
  python -m ctm_bench.scripts.track_e_long_context "${COMMON[@]}" "$@"
}

# ---- Cell group 1: sink sweep ----
for SINK in 0 4 16 32 64 128; do
  run_cell "sink_size=${SINK}" \
    --sink-size "${SINK}" \
    --output "${OUTDIR}/sink_${SINK}.json"
done

# ---- Cell group 2: K/V ablation (base config, sink=0) ----
run_cell "K-only INT4 (V passes through FP16)" \
  --no-quantize-v \
  --output "${OUTDIR}/k_only.json"

run_cell "V-only INT4 (K passes through FP16)" \
  --no-quantize-k \
  --output "${OUTDIR}/v_only.json"

# ---- Cell group 3: INT5 (base config, sink=0) ----
run_cell "INT5 (bits=5)" \
  --bits 5 \
  --output "${OUTDIR}/int5.json"

echo
echo "================================================================"
echo "  Diagnostic sprint complete. 9 cell JSONs in ${OUTDIR}/"
echo "================================================================"
echo "Read the 'int4 decode:' line printed under each cell's needle row,"
echo "or grep the aggregates:"
echo
echo "  python - <<'PY'"
echo "  import json, glob"
echo "  for f in sorted(glob.glob('${OUTDIR}/*.json')):"
echo "      d = json.load(open(f))"
echo "      for k, b in d.get('deltas', {}).get('per_context_length', {}).items():"
echo "          print(f, b.get('int4_needle_accuracy'),"
echo "                b.get('int4_first_stutter_earliest'),"
echo "                b.get('int4_repeated_token_rate_mean'),"
echo "                b.get('int4_entropy_collapse_rate'))"
echo "  PY"
