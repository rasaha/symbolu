#!/usr/bin/env bash
# Phase 4 trig diagnosis sweep — bounded.
#
# Question to answer: why does Phase 4 trig change 99% of eviction picks
# but produce no swap_out improvement (vs LRU, at 180s wall)?
#
# Three hypotheses, each isolated by a sweep cell:
#
#   H1: Trig blend in evict() is the culprit. The candidate-count knob
#       controls how many candidates evict() re-ranks with trig.
#       candidate_count=1 effectively DISABLES trig in evict() (only
#       window_pruning_pass uses it). If swap_out approaches LRU at
#       candidate=1, evict()'s trig usage was hurting.
#
#   H2: Window-pruning is the culprit. window_interval=128 (default)
#       runs window_pruning_pass every 128 decode tokens. Bump to 512
#       to slow it 4x. If swap_out improves vs T3, window pruning was
#       making poor decisions.
#
#   H3: Both. window=512 + candidate=1 is the minimum-trig
#       configuration. If swap_out STILL doesn't beat LRU, Phase 4
#       trig has no quality contribution at all and should be
#       retired from the VC narrative.
#
# All sweep cells run at 180s wall to match T3's CI level. Reuses
# the existing LRU 180s and T3 180s from PHASE8A_TIGHTENING/.
#
# Cost: 4 cells x $0.20 = ~$0.80, ~10 minutes.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"
cd "$REPO_ROOT"

OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/PHASE8A_TRIG_SWEEP}"
mkdir -p "$OUT_ROOT"

PER_LAYER_CAL="${PER_LAYER_CAL:-./Bench/calibration/qwen25_7b_per_layer.json}"
if [[ ! -f "$PER_LAYER_CAL" ]]; then
  echo "PREREQ FAIL: $PER_LAYER_CAL missing."
  exit 2
fi

BENCH_MODEL="${BENCH_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
WORKLOAD="${WORKLOAD:-chat_32k}"
PROMPT_LENGTH_CHOICES="${PROMPT_LENGTH_CHOICES:-8000,16000,24000,30000}"
MAX_DECODE_TOKENS="${MAX_DECODE_TOKENS:-2048}"
MAX_REQUESTS="${MAX_REQUESTS:-30}"
ARRIVAL_RATE="${ARRIVAL_RATE:-6.0}"
ARRIVAL_ALPHA="${ARRIVAL_ALPHA:-1.5}"
GPU_UTIL="${GPU_UTIL:-0.26}"
SWAP_GB="${SWAP_GB:-16}"
MAX_WALL="${MAX_WALL:-180}"

run_cell () {
  local cell_name="$1"
  local window_interval="$2"
  local blend_count="$3"
  local out_dir="$OUT_ROOT/$cell_name"
  mkdir -p "$out_dir"
  echo "[SWEEP] $cell_name: window=$window_interval, blend_candidates=$blend_count"

  python -m ctm_bench.scripts.run_streaming \
    --model "$BENCH_MODEL" --workload "$WORKLOAD" \
    --gpu-memory-utilization "$GPU_UTIL" --swap-space-gb "$SWAP_GB" \
    --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA" \
    --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL" \
    --max-decode-tokens "$MAX_DECODE_TOKENS" \
    --prompt-length-choices "$PROMPT_LENGTH_CHOICES" \
    --enable-prefix-caching \
    --ctm-plus \
    --phase4-trig-calibration "$PER_LAYER_CAL" \
    --phase4-window-interval "$window_interval" \
    --phase4-trig-blend-candidate-count "$blend_count" \
    --phase4-cython-evictor --phase4-fast-hooks \
    --output-dir "$out_dir"
}

# ----- Sweep -----
run_cell "s1_window256_candidate4"  256  4    # H2: slower window pruning
run_cell "s2_window128_candidate1"  128  1    # H1: disable trig in evict()
run_cell "s3_window512_candidate1"  512  1    # H3: minimum trig
run_cell "s4_window128_candidate2"  128  2    # H1 intermediate

# ----- Report -----
python -c "
import json, pathlib

sweep_root = pathlib.Path('$OUT_ROOT')
tightening_root = pathlib.Path('./Bench/bench_out/PHASE8A_TIGHTENING')

cells = [
    ('LRU 180s (ref)',           tightening_root / 't_lru_180s'),
    ('T3 default (w=128,c=4)',   tightening_root / 't3_phase4_trig_per_layer_180s'),
    ('s1 w=256, c=4',            sweep_root / 's1_window256_candidate4'),
    ('s2 w=128, c=1 (no evict-blend)',  sweep_root / 's2_window128_candidate1'),
    ('s3 w=512, c=1 (min trig)', sweep_root / 's3_window512_candidate1'),
    ('s4 w=128, c=2',            sweep_root / 's4_window128_candidate2'),
]

def load(path):
    p = path / 'streaming_summary.json'
    return json.load(open(p)) if p.exists() else None

lines = ['# Phase 4 trig diagnosis sweep report', '']
lines.append('All cells: Qwen2.5-7B, chat_32k, 180s wall, 30 reqs,')
lines.append('prefix caching ON, per-layer calibration.')
lines.append('')

# --- Throughput + swap quality ---
lines.append('## Throughput + swap quality')
lines.append('')
lines.append('| Cell | TPS | Completed | Decode tokens | swap_out | swap/completed | Preempt |')
lines.append('|---|---:|---:|---:|---:|---:|---:|')
for label, path in cells:
    r = load(path)
    if r is None:
        lines.append(f'| {label} | MISSING | | | | | |'); continue
    tps = r.get('tokens_per_second', 0.0)
    completed = r.get('n_requests_completed', 0) or 0
    decode = r.get('n_decode_tokens', 0)
    swap = r.get('swap_out_blocks', 0)
    spc = (swap / completed) if completed else None
    preempt = r.get('preemption_events', 0)
    spc_str = f'{spc:.0f}' if spc is not None else 'n/a'
    lines.append(
        f'| {label} | {tps:.1f} | {completed} | {decode} | {swap} | {spc_str} | {preempt} |'
    )

# --- Trig firing internals ---
lines.append('')
lines.append('## Trig firing internals (per cell, raw counters)')
lines.append('')
lines.append('| Cell | window_pruning_invocations | trig_score_computes | trig_score_lookups | cache hit % | blend_evict_calls | changed_pick | changed % |')
lines.append('|---|---:|---:|---:|---:|---:|---:|---:|')
for label, path in cells:
    r = load(path)
    if r is None:
        lines.append(f'| {label} | | | | | | | |'); continue
    wp = r.get('phase4_window_pruning_invocations', 0)
    computes = r.get('phase4_trig_score_computes', 0)
    lookups = r.get('phase4_trig_score_lookups', 0)
    hit_pct = ((lookups - computes) / lookups * 100) if lookups > 0 else 0
    blend = r.get('phase4_trig_blend_evict_calls', 0)
    changed = r.get('phase4_trig_changed_pick', 0)
    chg_pct = (changed / blend * 100) if blend > 0 else 0
    lines.append(
        f'| {label} | {wp} | {computes} | {lookups} | {hit_pct:.1f}% | {blend} | {changed} | {chg_pct:.1f}% |'
    )

# --- Deltas vs LRU 180s ---
lru = load(tightening_root / 't_lru_180s')
if lru:
    lines.append('')
    lines.append('## Deltas vs LRU 180s')
    lines.append('')
    lines.append('| Cell | TPS delta | swap/completed delta |')
    lines.append('|---|---:|---:|')
    lru_tps = lru.get('tokens_per_second', 1.0) or 1.0
    lru_completed = lru.get('n_requests_completed') or 1
    lru_spc = (lru.get('swap_out_blocks', 0) / lru_completed) if lru_completed else 1.0
    for label, path in cells:
        if label.startswith('LRU'): continue
        r = load(path)
        if r is None: continue
        tps = r.get('tokens_per_second', 0.0)
        completed = r.get('n_requests_completed') or 0
        spc = (r.get('swap_out_blocks', 0) / completed) if completed else None
        tps_d = (tps / lru_tps - 1) * 100
        if spc is not None and lru_spc:
            spc_d = (spc / lru_spc - 1) * 100
            spc_str = f'{spc_d:+.1f}%'
        else:
            spc_str = 'n/a'
        lines.append(f'| {label} | {tps_d:+.1f}% | {spc_str} |')

(sweep_root/'REPORT.md').write_text('\n'.join(lines) + '\n')
print(open(sweep_root/'REPORT.md').read())
"

echo "[SWEEP] Done. Report at $OUT_ROOT/REPORT.md"
