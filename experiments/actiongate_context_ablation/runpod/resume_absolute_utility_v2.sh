#!/usr/bin/env bash
# Resume an interrupted V2 run (same RUN_ID). The resume guard rejects V1 records, a
# changed model revision, changed prompts, or a changed V2 fingerprint.
set -euo pipefail
cd "$(dirname "$0")"
export BENCHMARK_VERSION=v2
export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-7B-Instruct}"
export RUN_ID="${RUN_ID:-absolute_utility_v2_$(basename "${MODEL_ID}")}"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
export SKIP_DOWNLOAD="${SKIP_DOWNLOAD:-1}"
echo "[v2-resume] RUN_ID=${RUN_ID}"
PROBE_REQUIRE_GPU="${PROBE_REQUIRE_GPU:-1}" PROBE_REQUIRE_MODEL=1 python3 probe_environment.py
python3 run_benchmark.py
