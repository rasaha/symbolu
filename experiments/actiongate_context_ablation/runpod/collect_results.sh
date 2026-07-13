#!/usr/bin/env bash
# Verify completeness, score/report via frozen logic, manifest, checksums, archive.
# Excludes model weights and secrets from the archive.
set -euo pipefail
cd "$(dirname "$0")"

export RESULTS_ROOT="${RESULTS_ROOT:-/workspace/results/actiongate-context-qwen}"
RUN_ID="${RUN_ID:-primary_qwen7b}"
RUN_DIR="${RESULTS_ROOT}/${RUN_ID}"

echo "[collect] verifying completeness + integrity"
python3 verify_results.py
echo "[collect] building reports (results.json, results.csv, REAL_LLM_RESULTS.md, plots)"
python3 collect.py
echo "[collect] writing run manifest"
python3 run_manifest.py

echo "[collect] checksums"
( cd "${RUN_DIR}" && find . -type f ! -name 'SHA256SUMS' -print0 | sort -z \
    | xargs -0 sha256sum > SHA256SUMS )

ARCHIVE="${RESULTS_ROOT}/${RUN_ID}.tar.gz"
echo "[collect] archiving -> ${ARCHIVE} (excludes weights + secrets)"
tar --exclude='*.safetensors' --exclude='*.bin' --exclude='*token*' --exclude='.env' \
    -czf "${ARCHIVE}" -C "${RESULTS_ROOT}" "${RUN_ID}"
sha256sum "${ARCHIVE}" > "${ARCHIVE}.sha256"
echo "[collect] archive ready: ${ARCHIVE}"
cat "${ARCHIVE}.sha256"
