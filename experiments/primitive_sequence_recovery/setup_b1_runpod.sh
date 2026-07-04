#!/usr/bin/env bash
# One-shot, idempotent B1 RunPod environment setup + verify.
# Reproduces the known-good stack for running run_b1_generation.py against the frozen B0 baseline.
# NOT a frozen artifact. Safe to re-run. Does NOT run a model or unblock anything.
#
#   bash experiments/primitive_sequence_recovery/setup_b1_runpod.sh
#
# Assumes a GPU pod whose driver supports CUDA >= 12.8 (nvidia-smi "CUDA Version: 12.8" or higher).
# For a different driver, set CU=cu124|cu126|cu130 to match before running.
set -euo pipefail

CU="${CU:-cu128}"                       # torch wheel build; override for a different driver
TORCH="2.8.0"; TV="0.23.0"; TA="2.8.0"  # matched trio for cu128 / torch 2.8

echo "== 0. driver check =="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi | sed -n '3p'
else
  echo "WARN: nvidia-smi not found — are you on the GPU pod (not the git/prep VM)?"
fi

echo "== 1. torch trio ($CU, matched) =="
pip install --index-url "https://download.pytorch.org/whl/${CU}" \
    "torch==${TORCH}" "torchvision==${TV}" "torchaudio==${TA}"

echo "== 2. locked backend + companions =="
# resolve requirements file relative to this script
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pip install -r "${HERE}/b1_runpod_requirements.txt"

echo "== 3. cmudict corpus (true G2P) =="
python3 -c "import nltk; nltk.download('cmudict', quiet=True); from nltk.corpus import cmudict; cmudict.dict(); print('cmudict ok')"

echo "== 4. verify stack =="
python3 - <<'PY'
import torch, torchvision, torchaudio, transformers, tokenizers, accelerate
assert torch.cuda.is_available(), "cuda False — driver/torch mismatch; set CU= to match the driver"
assert transformers.__version__ == "5.13.0", f"transformers {transformers.__version__} != locked 5.13.0"
assert tokenizers.__version__ == "0.22.2", f"tokenizers {tokenizers.__version__} != locked 0.22.2"
print(f"torch {torch.__version__} | tv {torchvision.__version__} | ta {torchaudio.__version__} "
      f"| cuda {torch.cuda.is_available()} | transformers {transformers.__version__} "
      f"| tokenizers {tokenizers.__version__} | accelerate {accelerate.__version__}")
PY

echo "== 5. runner integrity gate (no model call) =="
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -c "import sys; sys.path.insert(0, '${HERE}'); import run_b1_generation as G; G.verify_frozen_or_abort(); print('frozen integrity ok')"

echo
echo "ENV READY. Next (from the repo root):"
echo "  cd \"\$(git rev-parse --show-toplevel)\""
echo "  python3 experiments/primitive_sequence_recovery/run_b1_generation.py --limit 3 --out /tmp/b1_smoke.jsonl   # smoke"
echo "  python3 experiments/primitive_sequence_recovery/run_b1_generation.py --out experiments/primitive_sequence_recovery/b1_raw_outputs.jsonl --resume   # full 3600"
echo
echo "Reminder: do NOT 'pip install vllm' in this env — it drags torch back to cu130 and breaks CUDA."
