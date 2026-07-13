#!/usr/bin/env bash
# Resume an interrupted run: same RUN_ID + config. Skips completed keys, rejects any
# changed model revision / prompts / frozen fingerprint / run kind.
set -euo pipefail
cd "$(dirname "$0")"

: "${RUN_ID:?set RUN_ID to the interrupted run id}"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
export ALLOW_MOCK="${ALLOW_MOCK:-0}"
echo "[resume] resuming RUN_ID=${RUN_ID} under ${RESULTS_ROOT}"
PROBE_REQUIRE_GPU="${PROBE_REQUIRE_GPU:-1}" PROBE_REQUIRE_MODEL=1 python3 probe_environment.py
python3 run_benchmark.py
echo "[resume] done"
