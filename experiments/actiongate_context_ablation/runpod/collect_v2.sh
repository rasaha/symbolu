#!/usr/bin/env bash
# Verify (V2 expected keys) -> V2 score/report -> manifest -> checksums -> archive.
set -euo pipefail
cd "$(dirname "$0")"
export BENCHMARK_VERSION=v2
export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-7B-Instruct}"
export RUN_ID="${RUN_ID:-absolute_utility_v2_$(basename "${MODEL_ID}")}"
export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
RUN_DIR="${RESULTS_ROOT}/${RUN_ID}"

echo "[v2-collect] verifying completeness + integrity"
python3 verify_results.py
echo "[v2-collect] building V2 reports (results.json, results.csv, ABSOLUTE_UTILITY_V2_RESULTS.md)"
python3 collect_v2.py
echo "[v2-collect] writing run manifest"
python3 run_manifest.py

echo "[v2-collect] checksums"
( cd "${RUN_DIR}" && find . -type f ! -name 'SHA256SUMS' -print0 | sort -z \
    | xargs -0 sha256sum > SHA256SUMS )

ARCHIVE="${RESULTS_ROOT}/${RUN_ID}.tar.gz"
echo "[v2-collect] archiving -> ${ARCHIVE} (excludes weights + secrets)"
tar --exclude='*.safetensors' --exclude='*.bin' --exclude='*token*' --exclude='.env' \
    -czf "${ARCHIVE}" -C "${RESULTS_ROOT}" "${RUN_ID}"
sha256sum "${ARCHIVE}" > "${ARCHIVE}.sha256"
echo "[v2-collect] archive ready: ${ARCHIVE}"
