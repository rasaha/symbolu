#!/usr/bin/env bash
# setup.sh — RunPod environment setup for the CG-wrapper generation-quality ablation.
#
# RESEARCH track only (generation quality). Installs NO governance dependencies.
# Run from the repo root:  bash scripts/cg_wrapper_ablation/setup.sh
set -euo pipefail

echo "== CG wrapper ablation :: setup =="

# --- Core deps (the wrapper + generation path only) ---------------------------
python -m pip install --upgrade pip
python -m pip install \
  "torch" \
  "transformers>=4.44" \
  "accelerate>=0.33" \
  "sentencepiece" \
  "numpy" \
  "pytest"

# --- Optional: 4/8-bit quantized backbone (set DTYPE=4bit/8bit to use) --------
if [[ "${INSTALL_BNB:-1}" == "1" ]]; then
  python -m pip install "bitsandbytes>=0.46.1" || \
    echo "[warn] bitsandbytes install failed; run full-precision (DTYPE=bf16) instead."
fi

# --- Optional: flash-attention-2 (wrapper falls back to sdpa if absent) -------
if [[ "${INSTALL_FLASH:-0}" == "1" ]]; then
  python -m pip install flash-attn --no-build-isolation || \
    echo "[warn] flash-attn install failed; wrapper will use sdpa."
fi

echo "== environment =="
python - <<'PY'
import torch, transformers
print("torch       :", torch.__version__)
print("cuda avail  :", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu         :", torch.cuda.get_device_name(0))
print("transformers:", transformers.__version__)
PY

echo "== CPU sanity tests (must pass before the GPU run) =="
python -m pytest tests/test_cg_wrapper_ablation.py -q

echo "== setup complete =="
echo "Next: configure env vars then run smoke_generate.py (see README.md)."
