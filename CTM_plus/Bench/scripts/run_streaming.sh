#!/usr/bin/env bash
# Streaming Mode B (#3 Phase 1) — real-model swap-counter validation
# on modern vLLM (0.7+) using AsyncLLMEngine + preemption_mode=swap +
# Pareto-bursty arrivals.
#
# This is the runner that makes vLLM's swap path actually engage.
# Where the existing run_mode_b.sh (batch-mode) produces zero swap
# counters because FCFS doesn't preempt, this script puts sustained
# heavy-tailed pressure on the active set so the scheduler is forced
# to preempt + swap.
#
# Phase 1 is LRU-only — the CTM+ patch on vLLM 0.5+ remains gated on
# Phase 2 (a CpuGpuBlockAllocator-aware evictor patch). Use this
# script to:
#   * Validate that the swap path engages (counters > 0).
#   * Cross-check Mode A's LRU tier-cost predictions against real
#     swap traffic on real attention.
#
# What success looks like:
#   * swap_out_blocks > 0 across all cells.
#   * preemption_events > 0 across all cells.
#   * Per-(workload, seed) cell file: ``streaming_summary.json``.
#
# What "the swap path didn't engage" would mean (failure mode the
# Phase 1 work is specifically designed to prevent):
#   * swap_out_blocks == 0 — would indicate the Pareto schedule
#     wasn't aggressive enough OR vLLM's preemption_mode wasn't
#     actually applied. Stop and inspect the engine's
#     scheduler_config before retrying.
#
# Requirements:
#   * NVIDIA GPU with >= 24GB VRAM (A100 / H100 recommended for the
#     swap-pressure regime; smaller cards work but limit context).
#   * vLLM 0.7+ (for the AsyncLLMEngine with preemption-mode-swap;
#     older versions had a different scheduler API).
#   * Python 3.10+ with the venv from MODE_B_RUNBOOK.md §3.

set -euo pipefail

# ----- Configuration ----------------------------------------------- #

MODEL=${MODEL:-meta-llama/Llama-3.1-8B-Instruct}
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.30}
SWAP_SPACE_GB=${SWAP_SPACE_GB:-16}
SEEDS=(42 137 271)
OUT_DIR=${OUT_DIR:-bench_out/streaming_$(date +%Y%m%d_%H%M%S)}

# Pareto arrival shape — heavy-tailed; alpha=1.5 produces realistic
# burstiness. base_rate_per_sec is the long-run mean rate.
ARRIVAL_RATE=${ARRIVAL_RATE:-2.0}
ARRIVAL_ALPHA=${ARRIVAL_ALPHA:-1.5}

# Per-cell budget. Larger MAX_REQUESTS = more samples, more cost.
# 200 requests at 2/sec base rate is ~100s of arrivals + drain time.
MAX_REQUESTS=${MAX_REQUESTS:-200}
MAX_WALL_SECONDS=${MAX_WALL_SECONDS:-180}

WORKLOADS=(chat_32k rag_128k agentic_clustered_64k)

# ----- Argparse ---------------------------------------------------- #

MODE="full"
case ${1:-} in
    --quick)        MODE="quick" ;;
    --full|"")      MODE="full" ;;
    -h|--help)
        sed -n '2,/^set -euo/p' "$0" | sed 's/^# \?//'
        exit 0
        ;;
    *)
        echo "ERROR: unknown argument $1" >&2
        echo "Usage: $0 [--quick|--full]" >&2
        exit 2
        ;;
esac

case "$MODE" in
    quick)
        WORKLOADS=(chat_32k)
        SEEDS=(42)
        MAX_REQUESTS=20
        MAX_WALL_SECONDS=60
        ;;
esac

# ----- Pre-flight -------------------------------------------------- #

echo "==> Pre-flight checks (streaming Mode B — roadmap #3 Phase 1)"

if ! command -v python3 >/dev/null; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi

if ! python3 -c "import vllm" 2>/dev/null; then
    echo "ERROR: vLLM not installed. Run: pip install 'vllm>=0.7'" >&2
    exit 1
fi

# Check vLLM version is compatible with AsyncLLMEngine + preemption-
# mode-swap. The streaming runner targets 0.7+; lower versions may
# have different scheduler-config keys.
VLLM_VERSION=$(python3 -c "import vllm; print(vllm.__version__)")
echo "==> vLLM version: $VLLM_VERSION"
case "$VLLM_VERSION" in
    0.[01234].*)
        echo "WARN: vLLM $VLLM_VERSION is older than 0.5; this script"
        echo "      targets 0.7+. preemption_mode kwarg may not be"
        echo "      recognised. If this fails, pin a newer vLLM."
        ;;
esac

if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "ERROR: CUDA not available." >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

echo "==> Output directory:    $OUT_DIR"
echo "==> Model:               $MODEL"
echo "==> Workloads:           ${WORKLOADS[*]}"
echo "==> Seeds:               ${SEEDS[*]}"
echo "==> Arrival rate:        $ARRIVAL_RATE arrivals/sec (Pareto α=$ARRIVAL_ALPHA)"
echo "==> Max requests/cell:   $MAX_REQUESTS"
echo "==> Max wall/cell:       ${MAX_WALL_SECONDS}s"
echo "==> GPU memory util:     $GPU_MEM_UTIL"
echo "==> Swap space:          ${SWAP_SPACE_GB} GB"
echo

# ----- Run sweep --------------------------------------------------- #

CELL_COUNT=$(( ${#WORKLOADS[@]} * ${#SEEDS[@]} ))
echo "==> Total cells: $CELL_COUNT"
CELL_IDX=0

for workload in "${WORKLOADS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        CELL_IDX=$((CELL_IDX + 1))
        CELL_NAME="${workload}_lru_seed${seed}"
        CELL_OUT="$OUT_DIR/$CELL_NAME"
        mkdir -p "$CELL_OUT"
        echo "[$CELL_IDX/$CELL_COUNT] Running $CELL_NAME"
        python3 -m ctm_bench.scripts.run_streaming \
            --model "$MODEL" \
            --workload "$workload" \
            --seed "$seed" \
            --gpu-memory-utilization "$GPU_MEM_UTIL" \
            --swap-space-gb "$SWAP_SPACE_GB" \
            --arrival-rate "$ARRIVAL_RATE" \
            --arrival-alpha "$ARRIVAL_ALPHA" \
            --max-requests "$MAX_REQUESTS" \
            --max-wall-seconds "$MAX_WALL_SECONDS" \
            --output-dir "$CELL_OUT" \
            2>&1 | tee "$CELL_OUT.log"
    done
done

# ----- Aggregate --------------------------------------------------- #

echo
echo "==> Aggregating results"

python3 << PYEOF
import json
from pathlib import Path

out_dir = Path("$OUT_DIR")
all_cells = []
for summary_path in sorted(out_dir.glob("**/streaming_summary.json")):
    with open(summary_path) as f:
        all_cells.append(json.load(f))

with open(out_dir / "all_cells.json", "w") as f:
    json.dump({"cells": all_cells}, f, indent=2, sort_keys=True)

print()
print(f"{'Workload':<25s} {'Seed':>5s}  {'admitted':>9s} "
      f"{'completed':>10s} {'decode_tok':>11s} "
      f"{'swap_out':>9s} {'preempt':>8s} {'wall':>7s}")
print("-" * 100)
for c in sorted(all_cells, key=lambda x: (x.get("workload_name", ""), x.get("seed", 0))):
    print(
        f"{c.get('workload_name', ''):<25s} "
        f"{c.get('seed', 0):>5d}  "
        f"{c.get('n_requests_admitted', 0):>9d} "
        f"{c.get('n_requests_completed', 0):>10d} "
        f"{c.get('n_decode_tokens', 0):>11d} "
        f"{c.get('swap_out_blocks', 0):>9d} "
        f"{c.get('preemption_events', 0):>8d} "
        f"{c.get('wall_clock_seconds', 0):>6.1f}s"
    )

# Pass criterion for Phase 1: swap_out_blocks > 0 across cells.
total_swap_out = sum(c.get("swap_out_blocks", 0) for c in all_cells)
total_preempt = sum(c.get("preemption_events", 0) for c in all_cells)
print()
print(f"==> Total swap_out blocks: {total_swap_out}")
print(f"==> Total preemption events: {total_preempt}")
if total_swap_out == 0:
    print()
    print("WARN: zero swap_out across all cells. Phase 1's whole")
    print("      point is to make the swap path engage; if this is")
    print("      zero, the run did not validate what we wanted.")
    print("      Inspect the per-cell logs and consider:")
    print("      - Increasing arrival_rate (currently ${ARRIVAL_RATE}/sec)")
    print("      - Decreasing arrival_alpha for more bursts")
    print("      - Lowering gpu_memory_utilization to tighten KV budget")
PYEOF

echo
echo "==> Done."
echo "==> Summary: $OUT_DIR/all_cells.json"
echo
echo "==> What this run produces:"
echo "  * Real-model swap counters under sustained Pareto-bursty load."
echo "  * Per-(workload, seed) cells: streaming_summary.json"
echo "  * Phase 1 = LRU only. CTM+ on modern vLLM remains Phase 2."
echo
echo "==> Honest scope:"
echo "  These numbers calibrate Mode A's LRU tier-cost predictions"
echo "  against real swap traffic. They do NOT establish CTM+ vs LRU"
echo "  on modern vLLM — that's Phase 2. Cite this as 'real-model"
echo "  LRU swap-counter validation, vLLM 0.7+ + AsyncLLMEngine +"
echo "  preemption_mode=swap'."
