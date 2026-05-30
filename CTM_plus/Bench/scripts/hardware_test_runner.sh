#!/usr/bin/env bash
# Phase 6M.6 — Hardware test runbook (Test 2). RUN ON EACH GPU POD.
#
# Run this once per GPU (A100 baseline, then H100 and/or H200). It auto-detects
# the GPU, runs the capacity --compare at the saturation operating point, runs
# the 6D bucket profiler, and tags every artifact by GPU so
# analyze_phase6m6_hardware.py can build the per-GPU ratio table.
#
# NO code/kernel/quant change — same scripts, new hardware (plan §Test 2).
#
# Usage (on each pod):
#   source /workspace/venv-vllm/bin/activate
#   bash CTM_plus/Bench/scripts/hardware_test_runner.sh
#
# After running on all GPUs, copy each pod's $OUT/<GPU>_report.json back, then
# (on any machine — CPU only) attribute the axis with Test 1's verdict:
#   python CTM_plus/Bench/scripts/analyze_phase6m6_hardware.py \
#       --report A100=bench_out/phase6m6/A100_report.json \
#       --report H100=bench_out/phase6m6/H100_report.json \
#       --report H200=bench_out/phase6m6/H200_report.json \
#       --bound-verdict <Test-1 verdict> --out PHASE_6M6_hardware_report.txt
#
# Env overrides: OUT, GPU, MML, B_LIST, MAXTOK, PROMPT_FRAC, SKIP_PROFILE=1.
set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAP="$SCRIPTS_DIR/phase6l_capacity_demo.py"
PROF="$SCRIPTS_DIR/bench_phase6_d_profile_gpu.py"
ANALYZE6D="$SCRIPTS_DIR/analyze_phase6d_profile.py"
OUT="${OUT:-$SCRIPTS_DIR/../bench_out/phase6m6}"
mkdir -p "$OUT"

# --- detect GPU (override with GPU=...) -----------------------------------
if [[ -z "${GPU:-}" ]]; then
    GPU="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
    # Normalize "NVIDIA A100-SXM4-80GB" -> A100, "NVIDIA H100 80GB HBM3" -> H100, etc.
    case "$GPU" in
        *H200*) GPU=H200 ;;
        *H100*) GPU=H100 ;;
        *A100*) GPU=A100 ;;
        *)      GPU="${GPU// /_}" ;;
    esac
fi
echo "=================================================================="
echo "Phase 6M.6 hardware test — GPU=$GPU   out=$OUT"
echo "=================================================================="

# --- operating point (matches the plan §Test 2 method) --------------------
MML="${MML:-8192}"
B_LIST="${B_LIST:-96,128}"
MAXTOK="${MAXTOK:-512}"
PROMPT_FRAC="${PROMPT_FRAC:-0.95}"

# --- STEP 1: capacity --compare (the per-GPU 0.22× ratio) -----------------
echo
echo "### STEP 1: capacity --compare (does the 0.22× aggregate ratio improve?) ###"
GPU_OUT="$OUT/${GPU}_capacity"
mkdir -p "$GPU_OUT"
python "$CAP" --compare --mml "$MML" --max-tokens "$MAXTOK" \
    --prompt-frac "$PROMPT_FRAC" --b-list "$B_LIST" --out-dir "$GPU_OUT"
# Surface the headline report.json at a GPU-tagged top-level path.
if [[ -f "$GPU_OUT/report.json" ]]; then
    cp "$GPU_OUT/report.json" "$OUT/${GPU}_report.json"
    echo ">>> wrote $OUT/${GPU}_report.json"
else
    echo "!!! WARN: $GPU_OUT/report.json not found — capacity run may have failed." >&2
fi

# --- STEP 2: 6D bucket profiler (does the ~29% attn + ~19.5% gather shrink?) -
if [[ "${SKIP_PROFILE:-0}" != "1" ]]; then
    echo
    echo "### STEP 2: 6D kernel-bucket profile (long context) ###"
    PCFG="--max-model-len $MML --batch-size 128 --max-tokens 128 --prompt-frac $PROMPT_FRAC --gpu-memory-utilization 0.5 --n-warmup-runs 1"
    for CELL in int4_captured; do
        python "$PROF" --cell "$CELL" $PCFG \
            --torch-profile-csv "$OUT/${GPU}_${CELL}_kernels.csv"
    done
    python "$PROF" --cell bf16_stock $PCFG --bf16-eager \
        --torch-profile-csv "$OUT/${GPU}_bf16_stock_kernels.csv"
    python "$ANALYZE6D" \
        --int4-csv "$OUT/${GPU}_int4_captured_kernels.csv" \
        --bf16-csv "$OUT/${GPU}_bf16_stock_kernels.csv" \
        --out "$OUT/${GPU}_kernel_diff.txt"
    echo ">>> wrote $OUT/${GPU}_kernel_diff.txt"
fi

echo
echo "=================================================================="
echo "DONE for GPU=$GPU. Copy back (commit with git add -f):"
echo "  $OUT/${GPU}_report.json"
echo "  $OUT/${GPU}_kernel_diff.txt  (if profiled)"
echo "Then run analyze_phase6m6_hardware.py with --report ${GPU}=... and the"
echo "Test-1 --bound-verdict to attribute compute vs bandwidth."
echo "=================================================================="
