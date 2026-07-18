#!/usr/bin/env bash
# Cross-model replication sweep. Runs the IDENTICAL frozen benchmark for each model;
# changing MODEL_ID is the only requirement. Unavailable models are skipped honestly.
set -euo pipefail
cd "$(dirname "$0")"

export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"

# Weights are large and disk is a fixed per-session quota. By default, delete each
# model's weights after its run (results are already persisted under RESULTS_ROOT),
# so a multi-model sweep stays under quota. Set KEEP_WEIGHTS=1 to retain them.
KEEP_WEIGHTS="${KEEP_WEIGHTS:-0}"

DEFAULT_MODELS="Qwen/Qwen2.5-14B-Instruct,meta-llama/Llama-3.1-8B-Instruct,google/gemma-2-9b-it,mistralai/Mistral-7B-Instruct-v0.3"
IFS=',' read -ra MODELS <<< "${MODELS:-$DEFAULT_MODELS}"

for MODEL_ID in "${MODELS[@]}"; do
  echo "=================================================================="
  echo "[xmodel] $MODEL_ID"
  echo "=================================================================="
  RUN_ID="xmodel_$(basename "$MODEL_ID")"
  MODEL_DIR="/workspace/models/$(basename "$MODEL_ID")"
  if MODEL_ID="$MODEL_ID" RUN_ID="$RUN_ID" bash run_qwen_matrix.sh \
       && RUN_ID="$RUN_ID" bash collect_results.sh; then
    echo "[xmodel] OK $MODEL_ID"
  else
    echo "[xmodel] SKIP $MODEL_ID (download/probe/run failed — e.g. gated model, OOM, disk quota, or no access). Continuing honestly; no fabricated result."
  fi
  if [[ "$KEEP_WEIGHTS" != "1" && -d "$MODEL_DIR" ]]; then
    echo "[xmodel] freeing weights to stay under disk quota: $MODEL_DIR"
    rm -rf "$MODEL_DIR"
  fi
done

echo "[xmodel] sweep complete — aggregating"
./analyze_cross_model.sh
