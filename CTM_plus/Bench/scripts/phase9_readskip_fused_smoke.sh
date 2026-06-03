#!/usr/bin/env bash
# =============================================================================
# phase9_readskip_fused_smoke.sh — P2c gate: does fused_v2 serving + read-skip
# even RUN end-to-end? Functional/plumbing smoke (not quality/throughput yet).
#
# Read-skip lives in the route-A fused_v2 decode path; the runner defaulted to
# dequant_fallback. This exercises the new --int4-kv-backend fused_v2 + the
# INT4_READSKIP_MODE switch on a tiny single-sequence workload.
#
# fused_v2 v1 is BATCH=1 single-sequence (decode num_tokens==1); concurrent
# decode falls back to dequant_fallback. So we drive it serialized (slow arrival,
# few requests) to actually hit the fused decode bypass + read-skip.
#
# Cells (small model, constant_short, ~$0.05):
#   A dequant_fallback (default)        — sanity that route-A still works.
#   B fused_v2 + READSKIP off           — does fused_v2 serving work at all?
#   C fused_v2 + READSKIP retention     — does the read-skip path execute?
#
# PASS = forward_calls>0 all cells; B/C fused_v2_decodes>0 (fused path fired);
#        C readskip_calls>0 + readskip_controllers>0 (retention executed).
# This does NOT assert quality/throughput — that's the next harness (real needle).
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$PWD}"; cd "$REPO_ROOT"
OUT="${OUT:-./Bench/bench_out/PHASE9_READSKIP_FUSED}"
mkdir -p "$OUT"
MODEL="${MODEL:-Qwen/Qwen2.5-0.5B-Instruct}"
MML="${MML:-2048}"
COMMON=(--model "$MODEL" --workload constant_short
        --gpu-memory-utilization 0.30 --swap-space-gb 1
        --arrival-rate 0.5 --arrival-alpha 1.5
        --max-requests 3 --max-wall-seconds 45 --max-decode-tokens 32
        --prompt-length-choices "64,96" --max-model-len "$MML"
        --int4-kv-route-a --int4-kv-k-group-size 32 --int4-kv-v-group-size 32
        --int4-kv-bits 4 --int4-kv-sink-size 4)
log() { printf '\n[P2C] %s\n' "$*"; }

assert_cell() {  # $1=dir $2=require_fused(0/1) $3=require_readskip(0/1)
  python - "$1" "$2" "$3" <<'PY'
import json, sys, pathlib
d, req_fused, req_rs = sys.argv[1], sys.argv[2] == "1", sys.argv[3] == "1"
p = pathlib.Path(d) / "streaming_summary.json"
if not p.exists():
    print(f"FAIL: {p} missing"); sys.exit(2)
r = json.load(open(p)); st = r.get("int4_route_a_stats") or {}
fc = st.get("forward_calls", 0)
fd = st.get("fused_v2_decodes", 0)
rc = st.get("readskip_calls", 0); rk = st.get("readskip_controllers", 0)
print(f"  forward_calls={fc} fused_v2_decodes={fd} backend={st.get('kernel_backend')} "
      f"readskip_mode={st.get('readskip_mode')} readskip_calls={rc} controllers={rk} "
      f"completed={r.get('completed')}")
probs = []
if fc == 0: probs.append("forward_calls==0 (route-A never fired)")
if req_fused and fd == 0:
    probs.append("fused_v2_decodes==0 (fused decode bypass never fired — batch>1 "
                 "fallback, or fused_v2 serving broken)")
if req_rs and rc == 0:
    probs.append("readskip_calls==0 (retention path never executed)")
if probs:
    print("  FAIL: " + "; ".join(probs)); sys.exit(2)
print("  PASS")
PY
}

log "Cell A — dequant_fallback (sanity)"
INT4_READSKIP_MODE=off python -m ctm_bench.scripts.run_streaming "${COMMON[@]}" \
  --int4-kv-backend dequant_fallback --output-dir "$OUT/a_dequant"
assert_cell "$OUT/a_dequant" 0 0

log "Cell B — fused_v2 + read-skip OFF (does fused_v2 serve?)"
INT4_READSKIP_MODE=off python -m ctm_bench.scripts.run_streaming "${COMMON[@]}" \
  --int4-kv-backend fused_v2 --int4-kv-max-seq-len "$MML" \
  --output-dir "$OUT/b_fused_off"
assert_cell "$OUT/b_fused_off" 1 0

log "Cell C — fused_v2 + read-skip RETENTION (does the skip path execute?)"
INT4_READSKIP_MODE=retention INT4_READSKIP_RECENT=256 INT4_READSKIP_BUDGET=256 \
INT4_READSKIP_SINK=64 INT4_READSKIP_OBSERVE=4 \
  python -m ctm_bench.scripts.run_streaming "${COMMON[@]}" \
  --int4-kv-backend fused_v2 --int4-kv-max-seq-len "$MML" \
  --output-dir "$OUT/c_fused_retention"
assert_cell "$OUT/c_fused_retention" 1 1

log "P2c smoke complete. If all PASS, fused_v2 serving + read-skip run end-to-end."
log "Next: a real-needle harness for the byte-eq (off==retain_all) + quality gates."
