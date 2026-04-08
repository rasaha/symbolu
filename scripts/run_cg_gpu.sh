#!/usr/bin/env bash
# run_cg_gpu.sh — run inference_mistral.py --cg with real MistralCGAdapter
# on a GPU host.
#
# Usage:
#   HF_TOKEN=hf_xxx ./scripts/run_cg_gpu.sh                  # interactive REPL
#   HF_TOKEN=hf_xxx ./scripts/run_cg_gpu.sh demo             # multi-turn demo
#   HF_TOKEN=hf_xxx ./scripts/run_cg_gpu.sh "your query"     # single query
#
# Override defaults via env:
#   CG_MODEL      HuggingFace checkpoint id (default: mistralai/Mistral-7B-v0.3)
#   CG_QUANTIZE   "", "4bit", or "8bit"      (default: 4bit)
#   CG_DEVICE     device-map strategy        (default: auto)
#   HF_TOKEN      HF access token            (needed for gated checkpoints)
#
# This script exercises the REAL CG runtime path:
#   MistralCGAdapter -> CGToolDispatcher -> SafeMCPGateway
# See agentic/agentic_framework/docs/CG_RUNTIME_RUNBOOK.md.

set -euo pipefail

# ---- Config ---------------------------------------------------------
: "${CG_MODEL:=mistralai/Mistral-7B-v0.3}"
: "${CG_QUANTIZE:=4bit}"
: "${CG_DEVICE:=auto}"
: "${REPO_ROOT:=$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
: "${PY:=python}"

cd "$REPO_ROOT"

# ---- GPU sanity -----------------------------------------------------
echo "== GPU =="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv || {
    echo "nvidia-smi not found — are you on a GPU host?"; exit 1;
}

# ---- Dependencies ---------------------------------------------------
echo "== Installing inference stack =="
$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet \
    "torch" \
    "transformers>=4.40" \
    "accelerate" \
    "safetensors" \
    "sentencepiece"

if [[ "$CG_QUANTIZE" == "4bit" || "$CG_QUANTIZE" == "8bit" ]]; then
    $PY -m pip install --quiet "bitsandbytes"
fi

# ---- HuggingFace auth (gated checkpoints) ---------------------------
if [[ -n "${HF_TOKEN:-}" ]]; then
    $PY -c "from huggingface_hub import login; login('$HF_TOKEN')"
fi

# ---- Verify wiring with stub fallback first -------------------------
echo "== Wiring smoke (stub, no GPU work) =="
SYMBOLU_RUN_CG_SMOKE=1 $PY -m pytest -q \
    agentic/agentic_framework/tests/test_inference_mistral_cg_smoke.py

# ---- Real CG runtime ------------------------------------------------
echo "== Real CG runtime: $CG_MODEL (quantize=${CG_QUANTIZE:-none}, device=$CG_DEVICE) =="

QUANT_FLAG=()
if [[ -n "$CG_QUANTIZE" ]]; then
    QUANT_FLAG=(--cg-quantize "$CG_QUANTIZE")
fi

MODE="${1:-}"
case "$MODE" in
    demo)
        $PY -m agentic.agentic_framework.inference_mistral --cg \
            --cg-model "$CG_MODEL" \
            "${QUANT_FLAG[@]}" \
            --cg-device "$CG_DEVICE" \
            --demo --verbose
        ;;
    ""|interactive)
        $PY -m agentic.agentic_framework.inference_mistral --cg \
            --cg-model "$CG_MODEL" \
            "${QUANT_FLAG[@]}" \
            --cg-device "$CG_DEVICE" \
            --verbose
        ;;
    *)
        $PY -m agentic.agentic_framework.inference_mistral --cg \
            --cg-model "$CG_MODEL" \
            "${QUANT_FLAG[@]}" \
            --cg-device "$CG_DEVICE" \
            --verbose \
            --query "$MODE"
        ;;
esac
