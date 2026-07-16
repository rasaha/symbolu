#!/usr/bin/env bash
# KVPro V3 Step-0 — Part C: Nsight Compute per-kernel counters (RunPod, POD-ONLY, HW-UNTESTED).
# ncu on a full LLM generate is intractable (millions of launches), so we restrict to the int4 decode /
# attention kernels via --kernel-name regex and a small --launch-count, on a SHORT generation. Exports a
# metric CSV that 04_parse_profile.py rolls up. If ncu counters are blocked (perms), the run is marked
# UNAVAILABLE and downstream counter fields stay UNAVAILABLE — never estimated.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
PYBIN="${PYBIN:-python3}"; OUTDIR="${OUTDIR:-$HERE/runs}"; mkdir -p "$OUTDIR"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
BENCH="$ROOT/CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py"
CTX="${CTX:-16384}"; MAXTOK="${MAXTOK:-4}"; LAUNCHES="${LAUNCHES:-40}"
# kernels of interest: fused int4 decode-attention, gather/copy, unpack. Regex is permissive.
KRE="${KRE:-.*(int4|flash|decode_attn|splitk|gather|unpack|protect|dequant).*}"
METRICS="dram__bytes_read.sum,dram__bytes_write.sum,lts__t_sector_hit_rate.pct,\
smsp__sass_average_data_bytes_per_sector_mem_global_op_ld.pct,\
smsp__sass_average_data_bytes_per_sector_mem_global_op_st.pct,\
smsp__thread_inst_executed_per_inst_executed.ratio,\
sm__warps_active.avg.pct_of_peak_sustained_active,launch__registers_per_thread,\
launch__occupancy_limit_registers,smsp__inst_executed.avg.per_cycle_active"

if ! command -v ncu >/dev/null 2>&1; then
  echo "[UNAVAILABLE] ncu not on PATH — counter fields stay UNAVAILABLE."; exit 3; fi
if ! "$PYBIN" -c "from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache" 2>/dev/null; then
  echo "[BLOCKED] production int4 fork ABSENT — ncu cannot reach the production decode kernel."
  echo "          Use 03_profile_cuda_events.sh to time the in-repo Triton route-A kernel instead."; exit 4; fi

CSV="$OUTDIR/ncu_ctx${CTX}.csv"
echo "[ncu] profiling up to $LAUNCHES launches of /$KRE/ at ctx=$CTX ..."
if ncu --target-processes all --kernel-name-base function --kernel-name "regex:$KRE" \
       --launch-count "$LAUNCHES" --metrics "$METRICS" --csv --page raw \
       "$PYBIN" "$BENCH" --worker --cell eager --model "$MODEL" \
       --max-model-len "$CTX" --max-tokens "$MAXTOK" --output "$OUTDIR/ncu.worker.json" > "$CSV" 2>"$OUTDIR/ncu.err"; then
  echo "[ncu] -> $CSV"
  echo "[ncu] parse with: python3 04_parse_profile.py --ncu-csv $CSV"
else
  echo "[UNAVAILABLE] ncu run failed (often ERR_NVGPUCTRPERM — profiling not permitted)."
  echo "              Fix: set NVreg RmProfilingAdminOnly=0 (host) or run ncu as admin; see $OUTDIR/ncu.err"
  echo "              Counter-derived fields will remain UNAVAILABLE in the stage summary."
  exit 5
fi
