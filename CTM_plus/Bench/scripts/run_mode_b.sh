#!/usr/bin/env bash
# CTM+ Mode B (real-model via vLLM) — GPU validation run script.
#
# Validates the production default change (attention_ema_alpha
# 0.1 → 0.2) on a real model. Mode A's directional finding —
# CTM+ wins decisively on RAG, regression on agentic-clustered
# eliminated by alpha=0.20 — needs to be confirmed against real
# attention weights before the production change is fully
# trusted.
#
# Requirements:
#   * NVIDIA GPU with >= 24GB VRAM (A100 / H100 / RTX 4090)
#   * Python 3.10+
#   * CUDA 12.1+
#   * Free NVMe partition with >= 50GB (for swap_space backing)
#
# Usage:
#   ./scripts/run_mode_b.sh [--quick] [--full] [--rag-only] [--agentic-only]
#
# Time estimates (single A100):
#   --quick           ~5 min   (smoke run on small workload)
#   --rag-only        ~25 min  (1 model × 2 policies × 1 workload × 3 seeds)
#   --agentic-only    ~25 min  (1 model × 2 policies × 1 workload × 3 seeds)
#   --full            ~75 min  (1 model × 2 policies × 3 workloads × 3 seeds)
#
# What "winning" looks like in the output:
#   * RAG  : CTM+ slow_tier_B/tok < LRU slow_tier_B/tok by ≥ 50%
#            (Mode A showed -100%; real-model attention may
#            soften this but the directional sign should hold)
#   * AGENTIC_CLUSTERED : CTM+ slow_tier_B/tok within 30% of LRU
#            (Mode A showed +22% gap at α=0.20; if the gap
#            blows out to >50% on a real model, the production
#            default change is not safe and should be reverted.)
#   * CHAT : CTM+ ≤ LRU at parity. Failure here would be a
#            real-model-specific regression the harness missed.

set -euo pipefail

# ----- Configuration ----------------------------------------------- #

# Defaults — override via env vars before invocation.
MODEL=${MODEL:-meta-llama/Llama-3.1-8B-Instruct}
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.30}     # forces KV-cache spillover
SWAP_SPACE_GB=${SWAP_SPACE_GB:-8}
SEEDS=(42 137 271)
OUT_DIR=${OUT_DIR:-bench_out/mode_b_$(date +%Y%m%d_%H%M%S)}

WORKLOADS_RAG=(rag_128k)
WORKLOADS_AGENTIC=(agentic_clustered_64k)
WORKLOADS_CHAT=(chat_32k)
WORKLOADS_FULL=(rag_128k agentic_clustered_64k chat_32k)

POLICIES=(lru ctm_plus)

# ----- Argparse ---------------------------------------------------- #

MODE="full"
case ${1:-} in
    --quick)        MODE="quick" ;;
    --rag-only)     MODE="rag_only" ;;
    --agentic-only) MODE="agentic_only" ;;
    --full|"")      MODE="full" ;;
    -h|--help)
        sed -n '2,/^set -euo/p' "$0" | sed 's/^# \?//'
        exit 0
        ;;
    *)
        echo "ERROR: unknown argument $1" >&2
        echo "Usage: $0 [--quick|--rag-only|--agentic-only|--full]" >&2
        exit 2
        ;;
esac

case "$MODE" in
    quick)         WORKLOADS=("${WORKLOADS_RAG[@]}"); SEEDS=(42) ;;
    rag_only)      WORKLOADS=("${WORKLOADS_RAG[@]}") ;;
    agentic_only)  WORKLOADS=("${WORKLOADS_AGENTIC[@]}") ;;
    full)          WORKLOADS=("${WORKLOADS_FULL[@]}") ;;
esac

# ----- Pre-flight checks ------------------------------------------- #

echo "==> Pre-flight checks"

if ! command -v python3 >/dev/null; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi

if ! python3 -c "import vllm" 2>/dev/null; then
    echo "ERROR: vLLM not installed. Run: pip install vllm" >&2
    exit 1
fi

if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "ERROR: CUDA not available. This script requires a GPU." >&2
    exit 1
fi

if ! python3 -c "import kv_policy" 2>/dev/null; then
    echo "WARN: kv_policy not on import path. Attempting to add CTM_plus/KVPolicy."
    KV_POLICY_DIR="$(cd "$(dirname "$0")/.." && pwd)/KVPolicy"
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
if [[ "$PROD_ALPHA" != "0.2" ]]; then
    echo "WARN: production default is $PROD_ALPHA, expected 0.2 (Round 4 recommendation)."
    echo "      If you want to test the OLD default, set PROD_ALPHA=0.1 explicitly."
fi

mkdir -p "$OUT_DIR"
echo "==> Output directory: $OUT_DIR"
echo "==> Model: $MODEL"
echo "==> Workloads: ${WORKLOADS[*]}"
echo "==> Policies: ${POLICIES[*]}"
echo "==> Seeds: ${SEEDS[*]}"
echo "==> GPU memory utilization: $GPU_MEM_UTIL (forces spillover)"
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
import glob
from pathlib import Path

out_dir = Path("$OUT_DIR")
all_cells = []
for summary_path in sorted(out_dir.glob("**/vllm_summary.json")):
    with open(summary_path) as f:
        data = json.load(f)
    all_cells.extend(data["cells"])

with open(out_dir / "all_cells.json", "w") as f:
    json.dump({"cells": all_cells}, f, indent=2, sort_keys=True)

# Render a compact table.
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

# Pairwise reduction vs LRU per (workload, seed).
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
echo "==> Next steps:"
echo "  1. Verify CTM+ wins on RAG (slow_tier_B/tok much lower than LRU)."
echo "  2. Verify CTM+ regression on agentic_clustered is < 30% of LRU."
echo "  3. If both hold, the production default change (alpha=0.20) is"
echo "     validated against real attention weights. Update RESULTS.md §4"
echo "     with the Mode B numbers and consider promoting CTM+ to STABLE_API."
echo "  4. If either fails, capture the failure mode + revert the production"
echo "     default in a follow-up commit."
