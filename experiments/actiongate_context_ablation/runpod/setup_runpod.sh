#!/usr/bin/env bash
# Install the pinned CUDA inference stack and validate the environment.
set -euo pipefail
cd "$(dirname "$0")"

TORCH_VERSION="${TORCH_VERSION:-2.4.1}"
CUDA_INDEX="${CUDA_INDEX:-https://download.pytorch.org/whl/cu121}"

echo "[setup] python: $(python3 --version)"
echo "[setup] installing torch==${TORCH_VERSION} from ${CUDA_INDEX}"
python3 -m pip install --upgrade pip
python3 -m pip install "torch==${TORCH_VERSION}" --index-url "${CUDA_INDEX}"
echo "[setup] installing pinned inference deps"
python3 -m pip install -r requirements-runpod.txt

echo "[setup] probing environment (GPU required; model not required yet)"
PROBE_REQUIRE_GPU=1 PROBE_REQUIRE_MODEL=0 python3 probe_environment.py
echo "[setup] done"
