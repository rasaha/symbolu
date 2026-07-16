#!/usr/bin/env bash
# Phase H — quality for surviving candidates on ONE model (pod). Usage:
#   ./run_quality.sh --model <m> --mask <m.pt> --candidates QF1,QF2 --out qwen_quality.json
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PYBIN="${PYBIN:-python3}"
[ -f /workspace/venv-vllm/bin/activate ] && . /workspace/venv-vllm/bin/activate
exec "$PYBIN" "$HERE/run_quality.py" "$@"
