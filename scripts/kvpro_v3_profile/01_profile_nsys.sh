#!/usr/bin/env bash
# KVPro V3 Step-0 — Part C: Nsight Systems timeline + kernel-summary (RunPod, POD-ONLY, HW-UNTESTED).
# Wraps the EXISTING throughput bench (eager cell = real int4 decode path, NO CUDA graph) under nsys and
# exports a kernel-summary CSV that 04_parse_profile.py maps to pipeline stages. Skips cleanly (marks the
# run UNAVAILABLE) if nsys or the production int4 fork is absent — it does NOT fabricate a profile.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
PYBIN="${PYBIN:-python3}"; OUTDIR="${OUTDIR:-$HERE/runs}"; mkdir -p "$OUTDIR"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
BENCH="$ROOT/CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py"
# workload regimes (Part C): latency B=1, low-batch B=4/8 (bench sweeps batch internally); ctx + gen here
CONTEXTS="${CONTEXTS:-4096 16384 32768}"; MAXTOK="${MAXTOK:-32}"; CELL="${CELL:-eager}"

if ! command -v nsys >/dev/null 2>&1; then
  echo "[UNAVAILABLE] nsys not on PATH — cannot collect a timeline. (run 00_env_gate.sh)"; exit 3; fi
if ! "$PYBIN" -c "from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache" 2>/dev/null; then
  echo "[BLOCKED] production int4 fork (vllm.vllm_flash_attn.flash_attn_with_int4_kvcache) ABSENT."
  echo "          The eager throughput bench cannot drive the production decode kernel. Options:"
  echo "          (a) install the forked vLLM wheel + apply CTM_plus/Bench/scripts/apply_phase*_patches.py,"
  echo "          (b) profile the in-repo Triton route-A kernel instead (03_profile_cuda_events.sh)."
  exit 4
fi

for CTX in $CONTEXTS; do
  TAG="nsys_${CELL}_ctx${CTX}_tok${MAXTOK}"; BASE="$OUTDIR/$TAG"
  echo "[nsys] $TAG ..."
  nsys profile --force-overwrite=true -o "$BASE" --trace=cuda,nvtx --sample=none \
    "$PYBIN" "$BENCH" --worker --cell "$CELL" --model "$MODEL" \
      --max-model-len "$CTX" --max-tokens "$MAXTOK" --output "$BASE.worker.json" \
    || { echo "[WARN] nsys run failed for $TAG (see above)"; continue; }
  # kernel summary CSV (column names drift across nsys versions; the parser is tolerant)
  nsys stats --report cuda_gpu_kern_sum --format csv --output "$BASE" "$BASE.nsys-rep" 2>/dev/null \
    || nsys stats --report gpukernsum --format csv --output "$BASE" "$BASE.nsys-rep" 2>/dev/null \
    || echo "[WARN] nsys stats export failed for $TAG"
  echo "[nsys] -> ${BASE}_cuda_gpu_kern_sum.csv (or *_gpukernsum.csv)"
done
echo "[nsys] done. Feed the *kern_sum*.csv to: python3 04_parse_profile.py --nsys-csv <csv>"
