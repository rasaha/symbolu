#!/usr/bin/env bash
# Phase 8a tightening runs — three follow-ups to disambiguate the
# May 2026 8a numbers before any VC framing.
#
# Context (from phase8a results):
#   * Cell 3 (CTM+ + Phase 4 trig + per-layer cal) -> TPS=102.4 vs
#     LRU Cell 1 TPS=102.4 ; swap_out=2177 vs 2205. The audit's
#     -20% throughput tax did NOT replicate and the v5 -11%
#     swap_out algorithm win shrank to -1.3%.
#
# This script runs three tightening cells:
#
#   T1 — Cell 3 with broadcast-pooled calibration. Reproduces v5's
#        methodology (pooled-layer Q-stats). If swap_out reduction
#        recovers toward -11%, the gap is methodology-driven.
#        If TPS drops below LRU, the -20% tax is real and was
#        per-layer-cal-fixed.
#
#   T2 — Cell 4 with 180s wall (3x the 60s wall used in 8a).
#        Tightens the partner-relevant combined-stack number's
#        confidence interval. Expected ~6-9 completions instead of
#        2-3, much less arrival-rate-shape noise.
#
#   T3 — Throughput sanity: re-run Cell 3 (per-layer cal) at 180s
#        wall. Confirms the "no -20% tax" finding holds at longer
#        wall + more completions. Adds the per-layer baseline at
#        the same 180s confidence level as T2.
#
# Outputs land at Bench/bench_out/PHASE8A_TIGHTENING/<cell>/streaming_summary.json
# Auto-emits Bench/bench_out/PHASE8A_TIGHTENING/REPORT.md.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"
cd "$REPO_ROOT"

OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/PHASE8A_TIGHTENING}"
mkdir -p "$OUT_ROOT"

PER_LAYER_CAL="${PER_LAYER_CAL:-./Bench/calibration/qwen25_7b_per_layer.json}"
POOLED_CAL="${POOLED_CAL:-./Bench/calibration/qwen25_7b_pooled.json}"

# ----- Sanity prerequisites -----
if [[ ! -f "$PER_LAYER_CAL" ]]; then
  echo "PREREQ FAIL: $PER_LAYER_CAL missing. Generate it first via calibrate_qcenters_vllm.py."
  exit 2
fi
PHASE8A_BRIDGE="${PHASE8A_BRIDGE:-./Bench/bench_out/PHASE8B_GPU/day5b/streaming_summary.json}"
if [[ ! -f "$PHASE8A_BRIDGE" ]]; then
  echo "PREREQ FAIL: $PHASE8A_BRIDGE missing. Phase 8b must have run first."
  exit 2
fi

# ----- Step 0: Derive broadcast-pooled cal (free, no GPU) -----
echo "[TIGHTENING] Deriving broadcast-pooled calibration from per-layer..."
python -m Bench.scripts.derive_pooled_cal \
  --input "$PER_LAYER_CAL" \
  --output "$POOLED_CAL" \
  || python Bench/scripts/derive_pooled_cal.py \
       --input "$PER_LAYER_CAL" \
       --output "$POOLED_CAL"

# ----- Workload (v5 replicate, same as phase8a_remeasure.sh) -----
BENCH_MODEL="${BENCH_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
WORKLOAD="${WORKLOAD:-chat_32k}"
PROMPT_LENGTH_CHOICES="${PROMPT_LENGTH_CHOICES:-8000,16000,24000,30000}"
MAX_DECODE_TOKENS="${MAX_DECODE_TOKENS:-2048}"
MAX_REQUESTS="${MAX_REQUESTS:-30}"
ARRIVAL_RATE="${ARRIVAL_RATE:-6.0}"
ARRIVAL_ALPHA="${ARRIVAL_ALPHA:-1.5}"
GPU_UTIL="${GPU_UTIL:-0.26}"
SWAP_GB="${SWAP_GB:-16}"

# ----- T1: Cell 3 with pooled calibration (60s, matches 8a wall) -----
echo "[TIGHTENING] T1: CTM+ + Phase 4 trig + POOLED cal (matches v5 methodology)"
T1_OUT="$OUT_ROOT/t1_phase4_trig_pooled_cal"
mkdir -p "$T1_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds 60 \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --enable-prefix-caching \
  --ctm-plus \
  --phase4-trig-calibration "$POOLED_CAL" \
  --phase4-cython-evictor --phase4-fast-hooks \
  --output-dir "$T1_OUT"

# ----- T2: Cell 4 (combined) at 180s wall -----
echo "[TIGHTENING] T2: Combined cell (Phase 4 trig + INT4 route-A) at 180s wall"
T2_OUT="$OUT_ROOT/t2_combined_180s"
mkdir -p "$T2_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds 180 \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --enable-prefix-caching \
  --ctm-plus \
  --phase4-trig-calibration "$PER_LAYER_CAL" \
  --phase4-cython-evictor --phase4-fast-hooks \
  --int4-kv-route-a \
  --int4-kv-k-group-size 32 --int4-kv-v-group-size 32 \
  --int4-kv-bits 4 --int4-kv-sink-size 4 \
  --output-dir "$T2_OUT"

# ----- T3: Cell 3 (per-layer cal) at 180s wall — sanity for "no -20% tax" -----
echo "[TIGHTENING] T3: CTM+ + Phase 4 trig (per-layer) at 180s wall"
T3_OUT="$OUT_ROOT/t3_phase4_trig_per_layer_180s"
mkdir -p "$T3_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds 180 \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --enable-prefix-caching \
  --ctm-plus \
  --phase4-trig-calibration "$PER_LAYER_CAL" \
  --phase4-cython-evictor --phase4-fast-hooks \
  --output-dir "$T3_OUT"

# ----- LRU baseline at 180s for T2/T3 comparison -----
echo "[TIGHTENING] LRU baseline at 180s wall (for apples-to-apples vs T2/T3)"
LRU_OUT="$OUT_ROOT/t_lru_180s"
mkdir -p "$LRU_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds 180 \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --enable-prefix-caching \
  --output-dir "$LRU_OUT"

# ----- Generate the comparison report -----
python -c "
import json, pathlib
root = pathlib.Path('$OUT_ROOT')

cells = {
    'LRU (180s)':            root / 't_lru_180s',
    'T1 Phase4 POOLED cal':  root / 't1_phase4_trig_pooled_cal',
    'T2 Combined (180s)':    root / 't2_combined_180s',
    'T3 Phase4 PER-LAYER 180s': root / 't3_phase4_trig_per_layer_180s',
}

def load(path):
    p = path / 'streaming_summary.json'
    return json.load(open(p)) if p.exists() else None

def pct(a, b):
    if a is None or b is None or b == 0: return 'n/a'
    return f'{(a/b - 1)*100:+.1f}%'

lines = ['# Phase 8a tightening runs report', '']
lines.append('## Configuration matrix')
lines.append('')
lines.append('| Cell | TPS | Completed | Decode tokens | swap_out | swap/decode | Preempt | Wall |')
lines.append('|---|---:|---:|---:|---:|---:|---:|---:|')

lru = load(cells['LRU (180s)'])

for label, path in cells.items():
    r = load(path)
    if r is None:
        lines.append(f'| {label} | MISSING | | | | | | |')
        continue
    tps = r.get('tokens_per_second')
    completed = r.get('n_requests_completed')
    decode = r.get('n_decode_tokens')
    swap = r.get('swap_out_blocks')
    swap_per_decode = (swap/decode) if decode else None
    preempt = r.get('preemption_events')
    wall = r.get('wall_clock_seconds')
    sd_str = f'{swap_per_decode:.3f}' if swap_per_decode is not None else 'n/a'
    lines.append(
        f'| {label} | {tps:.1f} | {completed} | {decode} | {swap} | '
        f'{sd_str} | {preempt} | {wall:.1f}s |'
    )
lines.append('')

if lru:
    lines.append('## Deltas vs LRU 180s')
    lines.append('')
    lines.append('| Cell | TPS delta | swap_out delta | swap/decode delta |')
    lines.append('|---|---:|---:|---:|')
    for label, path in cells.items():
        if label == 'LRU (180s)': continue
        r = load(path)
        if r is None: continue
        tps_d = pct(r.get('tokens_per_second'), lru.get('tokens_per_second'))
        swap_d = pct(r.get('swap_out_blocks'), lru.get('swap_out_blocks'))
        ds_r = (r.get('swap_out_blocks',0)/r.get('n_decode_tokens',1)) if r.get('n_decode_tokens') else None
        ds_l = (lru.get('swap_out_blocks',0)/lru.get('n_decode_tokens',1)) if lru.get('n_decode_tokens') else None
        ds_d = pct(ds_r, ds_l)
        lines.append(f'| {label} | {tps_d} | {swap_d} | {ds_d} |')

(root/'REPORT.md').write_text('\n'.join(lines) + '\n')
print(open(root/'REPORT.md').read())
"

echo "[TIGHTENING] Done. Report at $OUT_ROOT/REPORT.md"
