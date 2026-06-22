#!/usr/bin/env bash
# Reproducible env for the CSR Phase 2B real-Mistral run on RunPod.
# Base image: a RunPod "PyTorch 2.x / CUDA 12.1" template is ideal (torch + GPU work out of the box).
# Requires an NVIDIA driver >= CUDA 12.1 (12.4 is fine). Run from the repo root: bash scripts/setup_runpod_phase2b.sh
set -euo pipefail

echo "[setup] torch/torchvision (cu121 — matches a CUDA 12.1+ driver) ..."
pip install --index-url https://download.pytorch.org/whl/cu121 torch==2.4.1 torchvision==0.19.1

echo "[setup] transformers stack + tokenizer deps ..."
pip install "transformers>=4.40,<4.46" accelerate sentence-transformers sentencepiece protobuf

echo "[setup] verifying torch + GPU + transformers + sentence-transformers ..."
python - <<'PY'
import torch, transformers, sentence_transformers  # noqa: F401
from transformers import AutoModelForCausalLM  # noqa: F401  (forces the torch-backed import path)
print("torch", torch.__version__, "| cuda_available", torch.cuda.is_available(),
      "| transformers", transformers.__version__)
assert torch.cuda.is_available(), \
    "CUDA not available — driver too old for this torch build (need driver >= CUDA 12.1)."
print("[setup] ENV OK")
PY

echo "[setup] done."
echo "[setup] Mistral-7B-Instruct-v0.3 may be gated — if downloads fail, accept the license on HF and:"
echo "        export HF_TOKEN=hf_xxxx && huggingface-cli login --token \$HF_TOKEN"
echo "[setup] validate with a REAL run (must print production_valid=True, primary ~0.609/0.764):"
echo "        bash scripts/setup_runpod_phase2b.sh --validate    # or run the eval command in docs/RUNPOD_SETUP.md"

if [[ "${1:-}" == "--validate" ]]; then
  export CSR_LLM_MODEL="${CSR_LLM_MODEL:-mistralai/Mistral-7B-Instruct-v0.3}"
  python scripts/cg_wrapper_ablation/csr_match_filter/eval_framed_answers_robustness.py \
    --data   scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_eval_v2_rubricv2.jsonl \
    --rubric scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_rubric_v2.yaml \
    --answer-backends mistral --judge-backend deterministic --semantic-backend real \
    --arms base,framed --write-traces --out robustness_eval_v2.json
fi
