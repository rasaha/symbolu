#!/usr/bin/env bash
# Phase 8a — Eviction remeasurement scaffold.
#
# DO NOT RUN until Phase 8b is GREEN. Day 5b's bridge composition
# cell must show non-zero attention reaching the evictor before this
# script's results are meaningful — otherwise you're just re-running
# v5 with the audit's gap intact and proving the -20% tax again.
#
# 8a runs FOUR cells (~$0.50 inclusive):
#
#   1. lru_baseline.json
#      vLLM LRU, no CTM+. Both 8a runs use --enable-prefix-caching
#      (forced ON by CTM+ anyway — see run_streaming.py:83-86) so
#      the cache regime is symmetric (audit risk #1 mitigation).
#
#   2. ctm_plus_phase3.json
#      CTM+ Phase 4 evictor + Phase 3 attention forwarding (the
#      BRIDGE cell). real attention sums reach forward_block_attention.
#      No INT4. This is the cell that tests whether bridging closes
#      the -20% Python-dispatch tax.
#
#   3. ctm_plus_phase4_trig.json
#      CTM+ Phase 4 evictor + Phase 4 trig scoring (calibration JSON).
#      No INT4. This is v5's measurement vehicle for the -11%
#      swap_out algorithm win, now with PER-LAYER calibration.
#      Phase 3 and Phase 4 are mutex (runner_vllm_streaming.py:601-606
#      enforces "competing hypotheses; run in separate cells").
#
#   4. ctm_plus_phase4_trig_int4.json
#      All three: CTM+ + Phase 4 trig + INT4 route-A. The
#      combined-stack operating point. Phase 4 trig is the empirically
#      stronger algorithm (v5's -11%), so the combined cell uses it
#      rather than Phase 3.
#
# Comparison logic:
#   Cell 2 vs Cell 1     : did the bridge close the -20% throughput tax?
#   Cell 3 vs Cell 1     : did per-layer recalibration preserve the
#                          -11% swap_out algorithm win?
#   Cell 4 vs Cell 1     : combined-stack partner-relevant operating point
#
# Outputs:
#   Bench/bench_out/PHASE8A/<cell>/streaming_summary.json
#   Bench/bench_out/PHASE8A/PHASE8A_REPORT.md

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"
cd "$REPO_ROOT"

OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/PHASE8A}"
mkdir -p "$OUT_ROOT"

# ----- Prerequisites -----
BRIDGE_RESULT="${BRIDGE_RESULT:-./Bench/bench_out/PHASE8B_GPU/day5b/streaming_summary.json}"
CALIBRATION="${CALIBRATION:-./Bench/calibration/qwen25_7b_per_layer.json}"

python -c "
import json, sys, pathlib
br = pathlib.Path('$BRIDGE_RESULT')
if not br.exists():
    print(f'PRECONDITION FAIL: {br} missing. Run phase8b_route_a_gpu_smoke.sh first.')
    sys.exit(2)
r = json.load(open(br))
agg = r.get('attention_aggregator_stats') or {}
ev = r.get('ctm_evictor_stats') or {}
samples = agg.get('samples_recorded', 0)
flushed = agg.get('blocks_flushed', 0)
nz = ev.get('forward_block_attention_nonzero_sum_calls', None)

if samples == 0 or flushed == 0:
    print('PRECONDITION FAIL: bridge composition reported zero attention samples/flushes.')
    print('The Phase 3 path is broken. Re-running 8a will reproduce the')
    print('-20% tax and tell us nothing new. See PHASE8B_ROUTE_A_BRIDGE_PLAN.md.')
    sys.exit(2)

if nz is None:
    print('PRECONDITION WARN: forward_block_attention_nonzero_sum_calls counter missing.')
    print('Add the counter in CTMEvictorModern.forward_block_attention before 8a so')
    print('partner-credible reporting can show non-zero attention reached the evictor.')
    print('Proceeding on samples_recorded/flushed evidence; 8a results will still be valid.')
elif nz == 0:
    print('PRECONDITION FAIL: forward_block_attention received only attention_sum==0.')
    print('Capture extracted samples but they zeroed during aggregation. Inspect')
    print('AttentionAggregator + _capture_attention_to_aggregator on real GPU args.')
    sys.exit(2)
else:
    print(f'Bridge check PASSED: nonzero-sum attention calls = {nz}')

cal = pathlib.Path('$CALIBRATION')
if not cal.exists():
    print(f'PRECONDITION FAIL: per-layer calibration JSON missing at {cal}.')
    print('Pooled-layer MRL was 0.221 (below 0.3 bar). v5 used pooled-layer;')
    print('this remeasurement must use per-layer to be method-credible.')
    print('Generate via the calibration runbook (one-shot, ~$0.05).')
    sys.exit(2)
print(f'Per-layer calibration found: {cal}')
"

# ----- Workload (v5 replicate) -----
BENCH_MODEL="${BENCH_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
WORKLOAD="${WORKLOAD:-chat_32k}"

PROMPT_LENGTH_CHOICES="${PROMPT_LENGTH_CHOICES:-8000,16000,24000,30000}"
MAX_DECODE_TOKENS="${MAX_DECODE_TOKENS:-2048}"
MAX_WALL_SECONDS="${MAX_WALL_SECONDS:-60}"
MAX_REQUESTS="${MAX_REQUESTS:-30}"
ARRIVAL_RATE="${ARRIVAL_RATE:-6.0}"
ARRIVAL_ALPHA="${ARRIVAL_ALPHA:-1.5}"

GPU_UTIL="${GPU_UTIL:-0.26}"
SWAP_GB="${SWAP_GB:-16}"

# CTM+ forces --enable-prefix-caching ON (runner enforces this because
# CTM+ patches PrefixCachingBlockAllocator). To keep cells apples-to-
# apples, the LRU baseline ALSO sets --enable-prefix-caching explicitly.
# Audit risk #1: v5 had CTM+ at 99% peak KV vs LRU at 57% — different
# cache regimes. Forcing both ON makes the comparison policy-only.
PREFIX_FLAG=(--enable-prefix-caching)

# ----- Cell 1: LRU baseline -----
echo "[PHASE8A] Cell 1 — LRU baseline (prefix caching ON for symmetry)"
CELL1="$OUT_ROOT/lru_baseline"
mkdir -p "$CELL1"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL_SECONDS" \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  "${PREFIX_FLAG[@]}" \
  --output-dir "$CELL1"

# ----- Cell 2: CTM+ + Phase 3 attention (BRIDGE cell) -----
echo "[PHASE8A] Cell 2 — CTM+ + Phase 3 attention (bridge cell, no INT4)"
CELL2="$OUT_ROOT/ctm_plus_phase3"
mkdir -p "$CELL2"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL_SECONDS" \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --ctm-plus --phase3-attention \
  --output-dir "$CELL2"

# ----- Cell 3: CTM+ + Phase 4 trig + per-layer calibration -----
echo "[PHASE8A] Cell 3 — CTM+ + Phase 4 trig (per-layer cal, no INT4)"
CELL3="$OUT_ROOT/ctm_plus_phase4_trig"
mkdir -p "$CELL3"

# Phase 4 fast hooks + Cython evictor are the v9/v10 latency-recovery
# levers; include them so the comparison is apples-to-apples with the
# audit's "v9+v10 still showed -20%" finding. If they're absent here
# but were absent in the audit too, we're measuring the same baseline.
python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL_SECONDS" \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --ctm-plus \
  --phase4-trig-calibration "$CALIBRATION" \
  --phase4-cython-evictor --phase4-fast-hooks \
  --output-dir "$CELL3"

# ----- Cell 4: Combined stack -----
echo "[PHASE8A] Cell 4 — Combined: CTM+ + Phase 4 trig + INT4 route-A"
CELL4="$OUT_ROOT/ctm_plus_phase4_trig_int4"
mkdir -p "$CELL4"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL_SECONDS" \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --ctm-plus \
  --phase4-trig-calibration "$CALIBRATION" \
  --phase4-cython-evictor --phase4-fast-hooks \
  --int4-kv-route-a \
  --int4-kv-k-group-size 32 --int4-kv-v-group-size 32 \
  --int4-kv-bits 4 --int4-kv-sink-size 4 \
  --output-dir "$CELL4"

# ----- Window-pruning trigger rate check (audit risk #3) -----
python -c "
import json, pathlib
r3 = json.load(open('$CELL3/streaming_summary.json'))
# Counter name per runner_vllm_streaming.py:124 +.
trig_total = r3.get('phase4_trig_score_computes')
trig_lookups = r3.get('phase4_trig_score_lookups')
trig_evicts = r3.get('phase4_trig_blend_evict_calls')
wall = r3.get('actual_wall_seconds') or $MAX_WALL_SECONDS
print(f'Phase 4 trig: score_computes={trig_total}, lookups={trig_lookups}, blend_evict_calls={trig_evicts}, wall={wall}s')
if trig_total is None or trig_evicts is None:
    print('  WARN: trig counters missing; audit risk #3 (window-pruning starvation) cannot be checked')
else:
    per_60s = trig_total * (60.0 / max(wall, 1e-9))
    blend_per_60s = trig_evicts * (60.0 / max(wall, 1e-9))
    print(f'  Normalized to 60s: score_computes={per_60s:.0f}, blend_evict_calls={blend_per_60s:.0f}')
    if per_60s < 500:
        print(f'  TRIG WARN: rate too low ({per_60s:.0f}/60s) — possible post-v6 regression')
    elif per_60s > 6000:
        print(f'  TRIG WARN: rate too high ({per_60s:.0f}/60s) — possible over-firing on prefill')
    else:
        print(f'  Trig signal rate OK (in expected 1000-5000/60s band)')
"

# ----- Report -----
python -c "
import json, pathlib
root = pathlib.Path('$OUT_ROOT')

def load(name):
    p = root / name / 'streaming_summary.json'
    return json.load(open(p)) if p.exists() else None

c1 = load('lru_baseline')
c2 = load('ctm_plus_phase3')
c3 = load('ctm_plus_phase4_trig')
c4 = load('ctm_plus_phase4_trig_int4')

def tps(r):
    if not r: return None
    return r.get('throughput_tokens_per_second') or r.get('decode_tokens_per_second')

def swap_per_decode(r):
    if not r: return None
    s = r.get('total_swap_out_blocks') or r.get('cumulative_swap_out_blocks') or 0
    d = r.get('total_decode_tokens') or r.get('decode_tokens') or 0
    return (s/d) if d else None

def pct(a, b):
    if a is None or b is None or b == 0: return 'n/a'
    return f'{(a/b - 1)*100:+.1f}%'

lines = ['# Phase 8a — Eviction remeasurement report (post-bridge)', '']
lines.append('## Throughput (tokens/sec)')
lines.append(f'  Cell 1 LRU baseline               : {tps(c1)}')
lines.append(f'  Cell 2 CTM+ + Phase 3 (bridge)    : {tps(c2)}  ({pct(tps(c2), tps(c1))} vs LRU)')
lines.append(f'  Cell 3 CTM+ + Phase 4 trig        : {tps(c3)}  ({pct(tps(c3), tps(c1))} vs LRU)')
lines.append(f'  Cell 4 Combined (P4 trig + INT4)  : {tps(c4)}  ({pct(tps(c4), tps(c1))} vs LRU)')
lines.append('')
lines.append('## Eviction quality (swap_out / decode_token)')
lines.append(f'  Cell 1 LRU baseline               : {swap_per_decode(c1)}')
lines.append(f'  Cell 2 CTM+ + Phase 3             : {swap_per_decode(c2)}  ({pct(swap_per_decode(c2), swap_per_decode(c1))} vs LRU)')
lines.append(f'  Cell 3 CTM+ + Phase 4 trig        : {swap_per_decode(c3)}  ({pct(swap_per_decode(c3), swap_per_decode(c1))} vs LRU)')
lines.append(f'  Cell 4 Combined                   : {swap_per_decode(c4)}  ({pct(swap_per_decode(c4), swap_per_decode(c1))} vs LRU)')
lines.append('')
lines.append('## Decision matrix (see PHASE8A_REMEASUREMENT_SCAFFOLD.md):')
lines.append('  * Cell 2 vs Cell 1 TPS  -> Did the bridge close the -20% tax?')
lines.append('  * Cell 3 vs Cell 1 swap -> Did per-layer cal preserve -11% algorithm win?')
lines.append('  * Cell 4 TPS vs Cell 1  -> Partner-relevant combined-stack number')
lines.append('')
lines.append('DO NOT update INT4_PROTECTED_VC_BRIEF.md until these are reviewed.')
(root/'PHASE8A_REPORT.md').write_text('\n'.join(lines) + '\n')
print(open(root/'PHASE8A_REPORT.md').read())
"

echo "[PHASE8A] done. Report at $OUT_ROOT/PHASE8A_REPORT.md"
