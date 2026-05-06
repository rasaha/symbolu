#!/usr/bin/env bash
# Mode B on a vLLM 0.4.x pinned environment — validation roadmap #2.
#
# This is the "real-model CTM+ vs LRU on a frozen-vLLM-version stack"
# path. It uses the existing CTM+ evictor patch (which targets the
# BlockSpaceManagerV1 + Evictor ABC interface that exists only in
# vLLM ≤ 0.4.x). Newer vLLM versions removed that hook and the patch
# raises NotImplementedError on 0.5+.
#
# This script is a sibling to run_mode_b.sh, NOT a replacement.
# run_mode_b.sh works on any vLLM version but only runs the LRU
# baseline on 0.5+; this script runs both LRU and CTM+ but requires
# vLLM 0.4.x.
#
# Caveat (must be flagged in any partner conversation citing this
# script's output):
#   * vLLM 0.4.x is not the version anyone runs in production. Any
#     numbers from this script are real-model evidence on a
#     historical stack — defensible as a calibration check on
#     CTM+'s scoring math against real attention, but NOT a claim
#     about modern vLLM serving performance.
#
# Requirements:
#   * NVIDIA GPU with >= 24GB VRAM (A100 / H100 / RTX 4090)
#   * Python 3.10+
#   * CUDA 12.1+ (vLLM 0.4.3 supports CUDA 11.8 + 12.1)
#   * vLLM == 0.4.3 (or another 0.4.x release; verified via
#     ctm_bench.scripts.vllm_version_check)
#
# Models known to load on vLLM 0.4.x:
#   * meta-llama/Llama-2-7b-chat-hf  (tested by upstream)
#   * mistralai/Mistral-7B-Instruct-v0.1  (tested by upstream)
#   Newer architectures (Llama-3, Qwen2.5) may not be supported on
#   vLLM 0.4.x. Use Llama-2 or Mistral for the validation run.
#
# Usage:
#   ./scripts/run_mode_b_vllm04.sh [--quick] [--full] [--rag-only] \
#                                  [--agentic-only] [--heavy-spillover]
#
# Time / cost estimates same as run_mode_b.sh (single A100):
#   --quick           ~5 min   (1 workload × 2 policies × 1 seed)
#   --rag-only        ~25 min  (1 workload × 2 policies × 3 seeds)
#   --agentic-only    ~25 min  (1 workload × 2 policies × 3 seeds)
#   --full            ~75 min  (3 workloads × 2 policies × 3 seeds)
#   --heavy-spillover ~25 min  (1 workload × 2 policies × 3 seeds)

set -euo pipefail

# ----- Configuration ----------------------------------------------- #

# vLLM 0.4.x compatibility: default to a model known to load on the
# 0.4.x line. Override via env var if you want to try a different
# model (e.g. internal fine-tune that builds against vLLM 0.4).
MODEL=${MODEL:-mistralai/Mistral-7B-Instruct-v0.1}
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.30}
GPU_MEM_UTIL_HEAVY=${GPU_MEM_UTIL_HEAVY:-0.22}
SWAP_SPACE_GB=${SWAP_SPACE_GB:-8}
SWAP_SPACE_GB_HEAVY=${SWAP_SPACE_GB_HEAVY:-16}
SEEDS=(42 137 271)
OUT_DIR=${OUT_DIR:-bench_out/mode_b_vllm04_$(date +%Y%m%d_%H%M%S)}

WORKLOADS_RAG=(rag_128k)
WORKLOADS_AGENTIC=(agentic_clustered_64k)
WORKLOADS_CHAT=(chat_32k)
WORKLOADS_FULL=(rag_128k agentic_clustered_64k chat_32k)

# Both policies — that's the point of #2. Modern run_mode_b.sh
# can only do LRU on vLLM 0.5+.
POLICIES=(lru ctm_plus)

# ----- Argparse ---------------------------------------------------- #

MODE="full"
case ${1:-} in
    --quick)            MODE="quick" ;;
    --rag-only)         MODE="rag_only" ;;
    --agentic-only)     MODE="agentic_only" ;;
    --heavy-spillover)  MODE="heavy_spillover" ;;
    --full|"")          MODE="full" ;;
    -h|--help)
        sed -n '2,/^set -euo/p' "$0" | sed 's/^# \?//'
        exit 0
        ;;
    *)
        echo "ERROR: unknown argument $1" >&2
        echo "Usage: $0 [--quick|--rag-only|--agentic-only|--heavy-spillover|--full]" >&2
        exit 2
        ;;
esac

case "$MODE" in
    quick)
        WORKLOADS=("${WORKLOADS_RAG[@]}")
        SEEDS=(42)
        ;;
    rag_only)
        WORKLOADS=("${WORKLOADS_RAG[@]}")
        ;;
    agentic_only)
        WORKLOADS=("${WORKLOADS_AGENTIC[@]}")
        ;;
    heavy_spillover)
        WORKLOADS=("${WORKLOADS_CHAT[@]}")
        GPU_MEM_UTIL="$GPU_MEM_UTIL_HEAVY"
        SWAP_SPACE_GB="$SWAP_SPACE_GB_HEAVY"
        ;;
    full)
        WORKLOADS=("${WORKLOADS_FULL[@]}")
        ;;
esac

# ----- Pre-flight checks ------------------------------------------- #

echo "==> Pre-flight checks (vLLM 0.4.x pin path — roadmap #2)"

if ! command -v python3 >/dev/null; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi

# Run the version check first — fails loud with actionable advice
# if vLLM is missing or wrong version. Must succeed (exit 0) or we
# stop here.
if ! python3 -m ctm_bench.scripts.vllm_version_check; then
    echo
    echo "ABORT: vLLM version check failed. See message above for the"
    echo "       recommended fix (typically: pip install 'vllm==0.4.3')."
    exit 1
fi

if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "ERROR: CUDA not available. This script requires a GPU." >&2
    exit 1
fi

if ! python3 -c "import kv_policy" 2>/dev/null; then
    echo "WARN: kv_policy not on import path. Attempting to add CTM_plus/KVPolicy."
    KV_POLICY_DIR="$(cd "$(dirname "$0")/../.." && pwd)/KVPolicy"
    if [[ -d "$KV_POLICY_DIR" ]]; then
        export PYTHONPATH="${KV_POLICY_DIR}:${PYTHONPATH:-}"
        if ! python3 -c "import kv_policy" 2>/dev/null; then
            echo "ERROR: still cannot import kv_policy after adding $KV_POLICY_DIR" >&2
            exit 1
        fi
    else
        echo "ERROR: $KV_POLICY_DIR does not exist" >&2
        exit 1
    fi
fi

GPU_INFO=$(python3 -c "
import torch
i = 0
print(f'GPU: {torch.cuda.get_device_name(i)}')
print(f'VRAM: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.1f} GB')
")
echo "$GPU_INFO"

PROD_ALPHA=$(python3 -c "
from kv_policy.attention_evictor import KVCachePolicy
import inspect
sig = inspect.signature(KVCachePolicy.__init__)
print(sig.parameters['attention_ema_alpha'].default)
")
echo "Production attention_ema_alpha default: $PROD_ALPHA"

mkdir -p "$OUT_DIR"
echo "==> Output directory: $OUT_DIR"
echo "==> Model: $MODEL  (vLLM 0.4.x compatible models: Llama-2, Mistral-v0.1)"
echo "==> Workloads: ${WORKLOADS[*]}"
echo "==> Policies: ${POLICIES[*]}"
echo "==> Seeds: ${SEEDS[*]}"
echo "==> GPU memory utilization: $GPU_MEM_UTIL"
echo "==> Swap space: ${SWAP_SPACE_GB} GB"
echo

# ----- Run sweep --------------------------------------------------- #

CELL_COUNT=$(( ${#WORKLOADS[@]} * ${#POLICIES[@]} * ${#SEEDS[@]} ))
echo "==> Total cells: $CELL_COUNT"
CELL_IDX=0

for workload in "${WORKLOADS[@]}"; do
    for policy in "${POLICIES[@]}"; do
        for seed in "${SEEDS[@]}"; do
            CELL_IDX=$((CELL_IDX + 1))
            CELL_NAME="${workload}_${policy}_seed${seed}"
            CELL_OUT="$OUT_DIR/$CELL_NAME"
            echo "[$CELL_IDX/$CELL_COUNT] Running $CELL_NAME"
            python3 -m ctm_bench.runner_vllm \
                --model "$MODEL" \
                --workload "$workload" \
                --policy "$policy" \
                --gpu-memory-utilization "$GPU_MEM_UTIL" \
                --swap-space "$SWAP_SPACE_GB" \
                --seed "$seed" \
                --output-dir "$CELL_OUT" \
                2>&1 | tee "$CELL_OUT.log"
        done
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
for summary_path in sorted(out_dir.glob("**/vllm_summary.json")):
    with open(summary_path) as f:
        data = json.load(f)
    all_cells.extend(data["cells"])

with open(out_dir / "all_cells.json", "w") as f:
    json.dump({"cells": all_cells}, f, indent=2, sort_keys=True)

print()
print(f"{'Workload':<22s} {'Policy':<10s} {'Seed':>5s}  "
      f"{'slow_B/tok':>12s}  {'avg_lat_ns':>12s}  {'hbm_hit':>8s}  {'wall':>7s}")
for c in sorted(all_cells, key=lambda x: (x["workload_name"], x["policy_name"], x["seed"])):
    print(
        f"{c['workload_name']:<22s} {c['policy_name']:<10s} "
        f"{c['seed']:>5d}  {c['slow_tier_bytes_per_decode_token']:>12,.0f}  "
        f"{c['avg_access_latency_ns']:>12,.0f}  "
        f"{c['hbm_hit_rate']*100:>7.2f}%  "
        f"{c['wall_clock_seconds']:>6.1f}s"
    )

print()
print("==> CTM+ vs LRU reduction (negative = improvement):")
by_key = {}
for c in all_cells:
    by_key[(c["workload_name"], c["policy_name"], c["seed"])] = c

for (wl, pol, seed), cell in sorted(by_key.items()):
    if pol != "ctm_plus":
        continue
    base = by_key.get((wl, "lru", seed))
    if base is None:
        continue
    base_v = base["slow_tier_bytes_per_decode_token"]
    cur_v = cell["slow_tier_bytes_per_decode_token"]
    if base_v == 0:
        pct = "n/a (LRU=0)"
    else:
        pct = f"{((base_v - cur_v) / base_v) * 100:+.1f}%"
    print(f"  {wl:<22s} seed={seed:<3d}  CTM+ vs LRU: {pct}")

print()
print(f"==> Wrote {out_dir / 'all_cells.json'}")
PYEOF

echo
echo "==> Done."
echo "==> Summary: $OUT_DIR/all_cells.json"
echo "==> Logs:    $OUT_DIR/*.log"
echo
echo "==> IMPORTANT — partner-conversation framing:"
echo "  These numbers are real-model evidence on a vLLM 0.4.x pinned"
echo "  stack. They are defensible as a calibration check on CTM+'s"
echo "  scoring math against real attention, but they are NOT a claim"
echo "  about modern (vLLM 0.5+, 0.7+) serving performance — that"
echo "  remains gated on validation roadmap #3 (allocator-architecture"
echo "  rewrite) or partner-specific Path B integration."
echo
echo "  Cite this run as: 'CTM+ vs LRU on Mistral-7B + vLLM 0.4.3, single"
echo "  A100, three workloads, three seeds — historical-stack calibration"
echo "  evidence. See PARTNER_VALIDATION_NOTE.md §4 for the modern-stack"
echo "  validation gate.'"
