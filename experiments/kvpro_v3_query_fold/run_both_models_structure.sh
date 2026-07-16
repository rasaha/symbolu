#!/usr/bin/env bash
# Phase A-H both models: explore Qwen + Llama, then the natural-structure verdict.
# Usage: ./run_both_models_structure.sh --qwen-mask <m.pt> --llama-mask <m.pt> [--outdir out]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PYBIN="${PYBIN:-python3}"
QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen2.5-7B-Instruct}"; LLAMA_MODEL="${LLAMA_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
QMASK=""; LMASK=""; OUTDIR="$HERE/out"
while [ $# -gt 0 ]; do case "$1" in
  --qwen-mask) QMASK="$2"; shift 2;; --llama-mask) LMASK="$2"; shift 2;;
  --outdir) OUTDIR="$2"; shift 2;; *) echo "unknown arg $1"; exit 2;; esac; done
: "${QMASK:?--qwen-mask required}"; : "${LMASK:?--llama-mask required}"; mkdir -p "$OUTDIR"
bash "$HERE/run_metadata_explore.sh" --model "$QWEN_MODEL"  --mask "$QMASK" --tag qwen  --outdir "$OUTDIR" || exit 1
bash "$HERE/run_metadata_explore.sh" --model "$LLAMA_MODEL" --mask "$LMASK" --tag llama --outdir "$OUTDIR" || exit 1
echo "== NATURAL-STRUCTURE VERDICT =="
"$PYBIN" "$HERE/decide_structure.py" --results-dir "$OUTDIR" --models qwen,llama --out-json "$OUTDIR/structure_verdict.json"
echo "commit artifacts: git add -f $OUTDIR"
