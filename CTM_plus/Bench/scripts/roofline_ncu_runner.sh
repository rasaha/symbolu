#!/usr/bin/env bash
# Phase 6M.5 — Roofline runbook (Test 1, THE GATE). RUN ON THE POD.
#
# This is the single command the USER runs on an ncu-unlocked GPU pod to
# produce the roofline split for the int4 decode-attention kernel. It:
#   1. Runs the §9 ncu unlock probe and ABORTS if counters are locked
#      (ERR_NVGPUCTRPERM) — get a privileged pod before booking GPU time.
#   2. Profiles the int4_captured and bf16_stock attention kernels with ncu
#      (SpeedOfLight + Memory/Compute WorkloadAnalysis + Occupancy + LaunchStats)
#      at the saturation operating point (mml=8192, B=48, long context).
#   3. Exports CSVs and runs analyze_phase6m5_roofline.py to print the verdict.
#
# NOTHING here changes a kernel or a quant setting — it is pure measurement.
#
# Usage (on the pod):
#   source /workspace/venv-vllm/bin/activate
#   bash CTM_plus/Bench/scripts/roofline_ncu_runner.sh
#
# Then paste BOTH the printed verdict AND the contents of
#   $OUT/PHASE_6M5_roofline_report.txt
# back into the session so the findings doc can be finalized.
#
# Env overrides: OUT, NCU, DRIVER, MML, BATCH, MAXTOK, PROMPT_FRAC, LAUNCH_COUNT.
set -uo pipefail

# --- locate tools / repo (handle both pod and local layouts) --------------
NCU="${NCU:-$(command -v ncu || echo /usr/local/cuda/bin/ncu)}"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRIVER="${DRIVER:-$SCRIPTS_DIR/bench_phase6_d_profile_gpu.py}"
ANALYZER="$SCRIPTS_DIR/analyze_phase6m5_roofline.py"
OUT="${OUT:-$SCRIPTS_DIR/../bench_out/phase6m5_roofline}"
mkdir -p "$OUT"

# --- saturation operating point (matches 6M.4 / the plan) -----------------
MML="${MML:-8192}"
BATCH="${BATCH:-48}"
MAXTOK="${MAXTOK:-96}"
PROMPT_FRAC="${PROMPT_FRAC:-0.95}"
# ncu replays each kernel many times (multi-pass counter collection) — so we
# scope to the attention kernels only (-k regex) and cap how many launches are
# profiled. 28 layers ≈ one decode step's worth of attention kernels.
LAUNCH_COUNT="${LAUNCH_COUNT:-28}"
KERNEL_REGEX="${KERNEL_REGEX:-regex:flash_fwd|fwd_kvcache|kvcache_int4}"

SECTIONS=(--section SpeedOfLight
          --section MemoryWorkloadAnalysis
          --section ComputeWorkloadAnalysis
          --section Occupancy
          --section LaunchStats)

echo "=================================================================="
echo "Phase 6M.5 roofline — ncu=$NCU"
echo "  operating point: mml=$MML B=$BATCH max_tokens=$MAXTOK frac=$PROMPT_FRAC"
echo "  out dir: $OUT"
echo "=================================================================="

# --- STEP 0: §9 ncu unlock probe (HARD PREREQ) ----------------------------
echo
echo "### STEP 0: ncu unlock probe (§9) ###"
PROBE_OUT="$("$NCU" --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed \
    python -c "import torch; x=torch.randn(4096,4096,device='cuda'); torch.cuda.synchronize(); (x@x).sum().item(); torch.cuda.synchronize()" 2>&1)"
echo "$PROBE_OUT" | tail -8
if echo "$PROBE_OUT" | grep -q "ERR_NVGPUCTRPERM"; then
    echo
    echo "!!! ABORT: ERR_NVGPUCTRPERM — GPU perf counters are LOCKED on this pod."
    echo "!!! ncu cannot collect SpeedOfLight here. Get a privileged pod"
    echo "!!! (NVreg_RestrictProfilingToAdminUsers=0) BEFORE booking Test 1 GPU time."
    exit 3
fi
if ! echo "$PROBE_OUT" | grep -qi "sm__throughput"; then
    echo
    echo "!!! WARN: probe did not show the sm__throughput metric table."
    echo "!!! ncu may be misconfigured — inspect the output above before proceeding."
    exit 4
fi
echo ">>> ncu counters UNLOCKED — Test 1 is runnable. Proceeding."

# --- helper: profile one cell ---------------------------------------------
profile_cell () {
    local cell="$1"; shift
    local extra=("$@")
    local rep="$OUT/${cell}_ncu.ncu-rep"
    local csv="$OUT/${cell}_ncu.csv"
    echo
    echo "### Profiling cell=$cell (ncu) ###"
    "$NCU" --nvtx --nvtx-include "phase6d_step/" \
        -k "$KERNEL_REGEX" \
        --launch-count "$LAUNCH_COUNT" \
        "${SECTIONS[@]}" \
        --export "$rep" --force-overwrite \
        python "$DRIVER" --cell "$cell" \
            --max-model-len "$MML" --batch-size "$BATCH" \
            --max-tokens "$MAXTOK" --prompt-frac "$PROMPT_FRAC" \
            "${extra[@]}"
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        echo "!!! ncu run for cell=$cell exited $rc — see output above." >&2
    fi
    # Export the details page to CSV for the analyzer.
    "$NCU" --import "$rep" --csv --page details > "$csv" 2>>"$OUT/${cell}_import.log" \
        || "$NCU" --import "$rep" --csv > "$csv" 2>>"$OUT/${cell}_import.log"
    echo ">>> wrote $csv"
}

profile_cell int4_captured
profile_cell bf16_stock --bf16-eager

# --- STEP 3: analyze ------------------------------------------------------
echo
echo "### Analyzing roofline split ###"
python "$ANALYZER" \
    --int4-csv "$OUT/int4_captured_ncu.csv" \
    --bf16-csv "$OUT/bf16_stock_ncu.csv" \
    --int4-kernel-substr fwd_kvcache \
    --bf16-kernel-substr flash_fwd \
    --out "$OUT/PHASE_6M5_roofline_report.txt"

echo
echo "=================================================================="
echo "DONE. Paste back:"
echo "  1. the VERDICT block printed above"
echo "  2. $OUT/PHASE_6M5_roofline_report.txt"
echo "  3. (if the kernel substring missed) the kernel names in"
echo "     $OUT/int4_captured_ncu.csv  — grep 'Kernel Name'"
echo "Artifacts (commit with git add -f; bench_out/ is gitignored):"
echo "  $OUT/*.csv  $OUT/PHASE_6M5_roofline_report.txt"
echo "=================================================================="
