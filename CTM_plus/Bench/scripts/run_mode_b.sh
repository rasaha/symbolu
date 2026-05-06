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
#   ./scripts/run_mode_b.sh [--quick] [--full] [--rag-only] \
#                           [--agentic-only] [--heavy-spillover]
#
# Time estimates (single A100):
#   --quick           ~5 min   (1 workload × 2 policies × 1 seed = 2 cells)
#   --rag-only        ~25 min  (1 workload × 2 policies × 3 seeds = 6 cells)
#   --agentic-only    ~25 min  (1 workload × 2 policies × 3 seeds = 6 cells)
#   --full            ~75 min  (3 workloads × 2 policies × 3 seeds = 18 cells)
#   --heavy-spillover ~25 min  (1 workload × 2 policies × 3 seeds = 6 cells,
#                               at tighter GPU_MEM_UTIL to engage HBF tier)
#
# Mode A's tightest-spillover regime (oversub 0.025) found the 52%
# latency-cut headline on chat_32k. --heavy-spillover targets the
# real-model analog by lowering GPU_MEM_UTIL to 0.22 (default for
# A100-80GB) so vLLM's KV budget squeezes hard enough to engage
# the CPU-pinned + NVMe-mmap'd swap_space tier on every decode
# step. This is the cell where HBF would matter most in production;
# Mode B can't model the HBF tier directly (no HBF on a real GPU
# yet) but can validate that CTM+'s containment property holds
# under heavy real-model pressure.
#
# NOTE: --heavy-spillover's GPU_MEM_UTIL default of 0.22 assumes
# A100-80GB. For A100-40GB use GPU_MEM_UTIL_HEAVY=0.42; for
# H100-80GB use 0.22 unchanged; for RTX 4090 (24GB) try 0.92 and
# expect partial-only spillover. See MODE_B_RUNBOOK.md §4 for the
# tuning math.
#
# What "winning" looks like in the output:
#   * RAG  : CTM+ slow_tier_B/tok < LRU slow_tier_B/tok by ≥ 50%
#            (Mode A showed -100%; real-model attention may
#            soften this but the directional sign should hold)
#   * AGENTIC_CLUSTERED : CTM+ slow_tier_B/tok within 30% of LRU
#            (Mode A showed +22% gap at α=0.20; if the gap
#            blows out to >50% on a real model, the production
#            default change is not safe and should be reverted.)
#   * CHAT (--full) : CTM+ ≤ LRU at parity. Failure here would
#            be a real-model-specific regression the harness
#            missed.
#   * CHAT (--heavy-spillover) : CTM+ slow_tier_B/tok ≤ 70% of
#            LRU's. Mode A showed CTM+ at 61% of LRU
#            (657 MB vs 1.08 GB per token) — the
#            "containment" effect that delivered the 52% latency
#            cut when stacked with HBF.

set -euo pipefail

# ----- Configuration ----------------------------------------------- #

# Defaults — override via env vars before invocation.
MODEL=${MODEL:-meta-llama/Llama-3.1-8B-Instruct}
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.30}                # forces some KV-cache spillover
GPU_MEM_UTIL_HEAVY=${GPU_MEM_UTIL_HEAVY:-0.22}    # --heavy-spillover override
SWAP_SPACE_GB=${SWAP_SPACE_GB:-8}
SWAP_SPACE_GB_HEAVY=${SWAP_SPACE_GB_HEAVY:-16}    # double swap budget under heavy pressure
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
        # Target the Mode A oversub-0.025 regime where the 52%
        # latency cell lives. Tighten GPU_MEM_UTIL so vLLM's KV
        # budget engages CPU-pinned + NVMe-mmap'd swap on every
        # decode step. Bigger swap_space so blocks have room to
        # land. Workload is chat_32k (where the cell exists).
        WORKLOADS=("${WORKLOADS_CHAT[@]}")
        GPU_MEM_UTIL="$GPU_MEM_UTIL_HEAVY"
        SWAP_SPACE_GB="$SWAP_SPACE_GB_HEAVY"
        ;;
    full)
        WORKLOADS=("${WORKLOADS_FULL[@]}")
        ;;
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
echo "==> Next steps (depending on which mode you ran):"
echo "  --rag-only        : verify CTM+ slow_tier_B/tok is at least 50%"
echo "                      below LRU's. Mode A predicted -100%."
echo "  --agentic-only    : verify CTM+ regression vs LRU is within +30%."
echo "                      Mode A predicted +12.5% to +29% at oversub 0.10."
echo "  --heavy-spillover : verify CTM+ slow_tier_B/tok is at most 70% of"
echo "                      LRU's. Mode A predicted CTM+ at 61% of LRU"
echo "                      (657 MB vs 1.08 GB per token) — the containment"
echo "                      effect that delivers the 52% latency cut when"
echo "                      stacked with HBF in production."
echo "  --full            : all three workloads at moderate spillover."
echo
echo "If predictions hold across the modes you ran, the production default"
echo "change (attention_ema_alpha=0.2) is validated against real attention"
echo "weights. Update bench_out/RESULTS.md §0 banner from \"Mode A only\""
echo "to \"Mode A + Mode B validated\" and append a §11 section with the"
echo "Mode B numbers. Reproducer-citation template in MODE_B_RUNBOOK.md §5."
echo
echo "If predictions break (RAG < 25% reduction OR agentic > +50% regression"
echo "OR chat regression under heavy spillover), see MODE_B_RUNBOOK.md §3"
echo "Step 7 for the git revert recipe."
