#!/usr/bin/env bash
# Configurable matrix runner. Defaults reproduce the preregistered PRIMARY run.
set -euo pipefail
cd "$(dirname "$0")"

export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-7B-Instruct}"
export MODEL_DIR="${MODEL_DIR:-/workspace/models/$(basename "${MODEL_ID}")}"
export BUDGETS="${BUDGETS:-0.2,0.3,0.4}"
export METHODS="${METHODS:-original,structural_only,protected,protection_unaware}"
export RUN_ID="${RUN_ID:-matrix_$(basename "${MODEL_ID}")}"
export RUN_KIND="${RUN_KIND:-PRIMARY}"
export MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-64}"
export BATCH_SIZE="${BATCH_SIZE:-1}"
export DTYPE="${DTYPE:-auto}"
export DEVICE="${DEVICE:-cuda}"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
export ALLOW_MOCK="${ALLOW_MOCK:-0}"

echo "[matrix] MODEL_ID=${MODEL_ID} BUDGETS=${BUDGETS} METHODS=${METHODS} RUN_ID=${RUN_ID} DTYPE=${DTYPE} DEVICE=${DEVICE}"
if [[ "${SKIP_DOWNLOAD:-0}" != "1" ]]; then python3 download_model.py; fi
PROBE_REQUIRE_GPU="${PROBE_REQUIRE_GPU:-1}" PROBE_REQUIRE_MODEL=1 python3 probe_environment.py
python3 run_benchmark.py
echo "[matrix] done (run ./collect_results.sh to score/report)"
