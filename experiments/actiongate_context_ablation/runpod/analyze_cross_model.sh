#!/usr/bin/env bash
# Aggregate all available per-model results into CROSS_MODEL_RESULTS.md + plots + json.
set -euo pipefail
cd "$(dirname "$0")"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
python3 analyze_cross_model.py
