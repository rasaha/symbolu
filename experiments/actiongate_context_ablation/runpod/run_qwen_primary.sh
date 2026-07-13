#!/usr/bin/env bash
# Preregistered PRIMARY benchmark: Qwen2.5-7B, full corpus, 4 methods, budgets 20/30/40%.
set -euo pipefail
cd "$(dirname "$0")"

export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-7B-Instruct}"
export MODEL_DIR="${MODEL_DIR:-/workspace/models/Qwen2.5-7B-Instruct}"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
export RUN_KIND="PRIMARY"
export RUN_ID="${RUN_ID:-primary_qwen7b}"
export BUDGETS="${BUDGETS:-0.2,0.3,0.4}"
export METHODS="${METHODS:-original,structural_only,protected,protection_unaware}"
export MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-64}"
export DTYPE="${DTYPE:-auto}"
export DEVICE="${DEVICE:-cuda}"
export MIN_VRAM_GB="${MIN_VRAM_GB:-24}"
export ALLOW_MOCK=0        # PRIMARY must never use the mock reader

echo "[primary] downloading 7B model"
python3 download_model.py
echo "[primary] probing (GPU + model required, >=${MIN_VRAM_GB}GB VRAM)"
PROBE_REQUIRE_GPU=1 PROBE_REQUIRE_MODEL=1 python3 probe_environment.py
echo "[primary] running PRIMARY benchmark (durable, resumable)"
python3 run_benchmark.py
echo "[primary] collecting results + verdict"
./collect_results.sh
echo "[primary] PASS"
