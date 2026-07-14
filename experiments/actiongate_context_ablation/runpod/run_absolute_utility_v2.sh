#!/usr/bin/env bash
# V2 absolute-utility benchmark run. Changing MODEL_ID is the only requirement; the
# benchmark surface (V2 tasks/scoring/prompt/fingerprint) is selected by BENCHMARK_VERSION=v2.
# V1 and V2 never share a run dir: the default RUN_ID is absolute_utility_v2_<model>.
set -euo pipefail
cd "$(dirname "$0")"

export BENCHMARK_VERSION=v2
export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-7B-Instruct}"
export RUN_ID="${RUN_ID:-absolute_utility_v2_$(basename "${MODEL_ID}")}"
export RUN_KIND="${RUN_KIND:-PRIMARY}"
export BUDGETS="${BUDGETS:-0.2,0.3,0.4}"
export METHODS="${METHODS:-original,structural_only,protected,protection_unaware}"
export MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-64}"
export DTYPE="${DTYPE:-auto}"
export DEVICE="${DEVICE:-cuda}"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
export ALLOW_MOCK="${ALLOW_MOCK:-0}"

echo "[v2] BENCHMARK_VERSION=v2 MODEL_ID=${MODEL_ID} RUN_ID=${RUN_ID} BUDGETS=${BUDGETS}"
if [[ "${SKIP_DOWNLOAD:-0}" != "1" ]]; then python3 download_model.py; fi
PROBE_REQUIRE_GPU="${PROBE_REQUIRE_GPU:-1}" PROBE_REQUIRE_MODEL=1 python3 probe_environment.py
python3 run_benchmark.py
echo "[v2] done — run ./collect_v2.sh (with the same RUN_ID) to score/report"
