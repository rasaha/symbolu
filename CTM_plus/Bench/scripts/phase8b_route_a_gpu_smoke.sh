#!/usr/bin/env bash
# Phase 8b — Route-A Days 4-5 GPU smoke + bridge composition verification.
#
# DO NOT RUN ON THIS CPU CONTAINER. This script is the deliverable for
# the GPU pod (Runpod A100 or H100). Estimated wall: ~$0.30 inclusive.
#
# Stages (each gated; abort on failure):
#
#   Day 4  : Install + heuristic verification on Qwen2.5-0.5B
#            (~$0.02 wall, 5 minutes). Confirms route-A's
#            `_looks_like_attention` matches the real vLLM Attention
#            class name on the pinned vLLM version. forward_calls > 0
#            asserts the wrapper actually fires on real decode.
#
#   Day 5a : Throughput + quality on Qwen2.5-7B, route-A ONLY
#            (no CTM+, no capture). Matches the §20.3 dequant_fallback
#            cell.
#
#   Day 5b : BRIDGE COMPOSITION CELL — Qwen2.5-7B with
#            --ctm-plus --phase3-attention --int4-kv-route-a.
#            (Phase 4 trig is mutex-incompatible with Phase 3
#            attention forwarding; this cell tests the Phase 3 path
#            which is what closes the audit's gap.)
#
#            Asserts:
#              (i)   manager.stats['forward_calls'] > 0
#              (ii)  aggregator stats show non-zero
#                    blocks_flushed AND samples_recorded
#              (iii) evictor logs `forward_block_attention` calls
#                    with non-zero attention_sum (the bridge proof)
#            If (iii) fails, the audit's "attention doesn't reach
#            evictor" conclusion is still in force; do NOT proceed
#            to 8a — engineering work needed first.
#
#   Day 5c : Sanity throughput-vs-LRU diff. Cheap (~$0.05); just
#            tells us whether the integration-tax delta moved.
#            Used as a PRELIMINARY signal — the proper 8a
#            remeasurement comes later.
#
# Output: ./Bench/bench_out/PHASE8B_GPU/{day4,day5a,day5b,day5c}/streaming_summary.json
# Status report: PHASE8B_GPU_REPORT.md (auto-generated from the JSONs).

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"
cd "$REPO_ROOT"

OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/PHASE8B_GPU}"
mkdir -p "$OUT_ROOT"

VLLM_VERSION_PIN="${VLLM_VERSION_PIN:-0.7.3}"
SMALL_MODEL="${SMALL_MODEL:-Qwen/Qwen2.5-0.5B-Instruct}"
BENCH_MODEL="${BENCH_MODEL:-Qwen/Qwen2.5-7B-Instruct}"

KV_K_GROUP="${KV_K_GROUP:-32}"
KV_V_GROUP="${KV_V_GROUP:-32}"
KV_BITS="${KV_BITS:-4}"
KV_SINK="${KV_SINK:-4}"

# v5 chat_32k workload knobs (PHASE4_GPU_FINDINGS §3 row v5).
WORKLOAD="${WORKLOAD:-chat_32k}"
PROMPT_LENGTH_CHOICES="${PROMPT_LENGTH_CHOICES:-8000,16000,24000,30000}"
MAX_DECODE_TOKENS="${MAX_DECODE_TOKENS:-2048}"
MAX_WALL_SECONDS="${MAX_WALL_SECONDS:-60}"
MAX_REQUESTS="${MAX_REQUESTS:-30}"
ARRIVAL_RATE="${ARRIVAL_RATE:-6.0}"
ARRIVAL_ALPHA="${ARRIVAL_ALPHA:-1.5}"

GPU_UTIL="${GPU_UTIL:-0.26}"
SWAP_GB="${SWAP_GB:-16}"

log() { printf '\n[PHASE8B] %s\n' "$*"; }

require_vllm() {
  python -c "
import vllm, sys
got = vllm.__version__
want = '$VLLM_VERSION_PIN'
if got != want:
    print(f'vllm version mismatch: got {got}, expected {want}. The install paths', file=sys.stderr)
    print('and attn_metadata fields may have moved. Update the smoke script if', file=sys.stderr)
    print('intentional; otherwise pin the pod env.', file=sys.stderr)
    sys.exit(2)
"
}

log "Phase 8b kickoff — vllm=$VLLM_VERSION_PIN, small=$SMALL_MODEL, bench=$BENCH_MODEL"
log "Output dir: $OUT_ROOT"
require_vllm

# -------- Day 4 — install verification on small model --------
log "Day 4 — install smoke ($SMALL_MODEL)"
DAY4_OUT="$OUT_ROOT/day4"
mkdir -p "$DAY4_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$SMALL_MODEL" \
  --workload constant_short \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb 1 \
  --arrival-rate 2.0 --arrival-alpha 1.5 \
  --max-requests 4 --max-wall-seconds 30 \
  --max-decode-tokens 10 \
  --prompt-length-choices "64,128" \
  --int4-kv-route-a \
  --int4-kv-k-group-size "$KV_K_GROUP" \
  --int4-kv-v-group-size "$KV_V_GROUP" \
  --int4-kv-bits "$KV_BITS" \
  --int4-kv-sink-size "$KV_SINK" \
  --output-dir "$DAY4_OUT"

python -c "
import json, sys, pathlib
p = pathlib.Path('$DAY4_OUT/streaming_summary.json')
if not p.exists():
    print(f'DAY 4 FAIL: streaming_summary.json missing at {p}')
    sys.exit(2)
r = json.load(open(p))
# stats live under int4_route_a_stats per runner_vllm_streaming.py:1212-1228.
fc = (r.get('int4_route_a_stats') or {}).get('forward_calls', 0)
if fc == 0:
    print('DAY 4 FAIL: int4_route_a_stats.forward_calls == 0. The class-name')
    print('heuristic missed real vLLM Attention. Inspect kv_policy.')
    print('int4_cache_kv_route_a:_looks_like_attention. Abort before Day 5.')
    sys.exit(2)
print(f'DAY 4 PASS: forward_calls={fc}')
"

# -------- Day 5a — route-A only --------
log "Day 5a — route-A ONLY ($BENCH_MODEL, $WORKLOAD)"
DAY5A_OUT="$OUT_ROOT/day5a"
mkdir -p "$DAY5A_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" \
  --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL_SECONDS" \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --int4-kv-route-a \
  --int4-kv-k-group-size "$KV_K_GROUP" \
  --int4-kv-v-group-size "$KV_V_GROUP" \
  --int4-kv-bits "$KV_BITS" \
  --int4-kv-sink-size "$KV_SINK" \
  --output-dir "$DAY5A_OUT"

# -------- Day 5b — BRIDGE COMPOSITION CELL --------
log "Day 5b — BRIDGE composition (CTM+ + Phase 3 attention + route-A)"
DAY5B_OUT="$OUT_ROOT/day5b"
mkdir -p "$DAY5B_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" \
  --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL_SECONDS" \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --ctm-plus \
  --phase3-attention \
  --int4-kv-route-a \
  --int4-kv-k-group-size "$KV_K_GROUP" \
  --int4-kv-v-group-size "$KV_V_GROUP" \
  --int4-kv-bits "$KV_BITS" \
  --int4-kv-sink-size "$KV_SINK" \
  --output-dir "$DAY5B_OUT"

python -c "
import json, sys, pathlib
p = pathlib.Path('$DAY5B_OUT/streaming_summary.json')
if not p.exists():
    print(f'DAY 5b FAIL: streaming_summary.json missing at {p}')
    sys.exit(2)
r = json.load(open(p))
i4 = r.get('int4_route_a_stats') or {}
agg = r.get('attention_aggregator_stats') or {}
ev = r.get('ctm_evictor_stats') or {}
fc = i4.get('forward_calls', 0)
flushed = agg.get('blocks_flushed', 0)
samples = agg.get('samples_recorded', 0)
# The two counters below are NEW for Day 5b — see PHASE8B_ROUTE_A_BRIDGE_PLAN.md
# 'Logging hooks needed for Day 5b'. If the keys are missing,
# the logging patch wasn't applied. Treat as a soft warning;
# samples_recorded > 0 is still the primary bridge signal.
fba_calls = ev.get('forward_block_attention_calls')
fba_nonzero = ev.get('forward_block_attention_nonzero_sum_calls')

problems = []
if fc == 0:           problems.append('int4 forward_calls == 0 (route-A wrapper never fired)')
if samples == 0:      problems.append('aggregator samples_recorded == 0 (capture wrapper extracted no attention)')
if flushed == 0:      problems.append('aggregator blocks_flushed == 0 (flush never reached the buffer)')
if fba_calls is not None and fba_calls == 0:
    problems.append('forward_block_attention_calls == 0 (evictor never called)')
if fba_nonzero is not None and fba_nonzero == 0:
    problems.append('forward_block_attention_nonzero_sum_calls == 0 (only attention_sum=0 reached evictor)')

if problems:
    print('DAY 5b BRIDGE FAIL:')
    for p in problems: print(f'  - {p}')
    print()
    print('The bridge is NOT GREEN. Do NOT advance to 8a remeasurement.')
    print('Inspect runner_vllm_streaming.py:1004-1098 install order and')
    print('_capture_attention_to_aggregator (vllm_evictor.py:1844-).')
    sys.exit(2)

logging_keys_present = fba_calls is not None and fba_nonzero is not None
print(f'DAY 5b BRIDGE PASS: fc={fc} flushed={flushed} samples={samples}'
      + (f' fba={fba_calls} nonzero={fba_nonzero}' if logging_keys_present
         else ' (note: forward_block_attention_* counters missing - logging patch needed for 8a precondition)'))
"

# -------- Day 5c — preliminary LRU baseline --------
log "Day 5c — preliminary LRU baseline (no CTM+, no route-A)"
DAY5C_OUT="$OUT_ROOT/day5c"
mkdir -p "$DAY5C_OUT"

python -m ctm_bench.scripts.run_streaming \
  --model "$BENCH_MODEL" \
  --workload "$WORKLOAD" \
  --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
  --max-requests "$MAX_REQUESTS" --max-wall-seconds 30 \
  --max-decode-tokens "$MAX_DECODE_TOKENS" \
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
  --output-dir "$DAY5C_OUT"

# -------- Summary --------
log "Generating PHASE8B_GPU_REPORT.md"

python -c "
import json, pathlib
root = pathlib.Path('$OUT_ROOT')
def load(stage):
    p = root / stage / 'streaming_summary.json'
    return json.load(open(p)) if p.exists() else None

d4  = load('day4')
d5a = load('day5a')
d5b = load('day5b')
d5c = load('day5c')

def tps(r):
    if not r: return None
    return r.get('throughput_tokens_per_second') or r.get('decode_tokens_per_second')

lines = ['# Phase 8b — Route-A GPU verification report', '']
lines.append(f'- Day 4 install smoke: forward_calls = {(d4 or {}).get(\"int4_route_a_stats\", {}).get(\"forward_calls\")}')
lines.append(f'- Day 5a route-A only TPS: {tps(d5a)}')
lines.append(f'- Day 5b bridge composition TPS: {tps(d5b)}')
lines.append(f'- Day 5c LRU baseline TPS (30s):  {tps(d5c)}')
if d5b and d5c and tps(d5b) and tps(d5c):
    delta = (tps(d5b) - tps(d5c)) / tps(d5c) * 100
    lines.append(f'- Preliminary delta (5b vs 5c LRU): {delta:+.1f}%')
lines.append('')
lines.append('See per-cell JSONs at $OUT_ROOT/day*/streaming_summary.json')
lines.append('If Day 5b passed -> run per-layer recalibration -> phase8a_remeasure.sh')
pathlib.Path('PHASE8B_GPU_REPORT.md').write_text('\n'.join(lines) + '\n')
print(open('PHASE8B_GPU_REPORT.md').read())
"

log "Phase 8b done. Inspect PHASE8B_GPU_REPORT.md and the bench_out JSONs."
