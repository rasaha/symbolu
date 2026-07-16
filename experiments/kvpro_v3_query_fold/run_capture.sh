#!/usr/bin/env bash
# Phase B — capture real metadata for ONE model (pod). Usage:
#   ./run_capture.sh --model Qwen/Qwen2.5-7B-Instruct --mask <m.pt> --out qwen_capture.pt
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PYBIN="${PYBIN:-python3}"
[ -f /workspace/venv-vllm/bin/activate ] && . /workspace/venv-vllm/bin/activate
exec "$PYBIN" "$HERE/capture_metadata.py" "$@"
