#!/usr/bin/env bash
# =============================================================================
# Single reproducible GPU training run for the clean-softmax Symbol-U model.
# RunPod-compatible. The model/algorithms are FROZEN — this only launches them
# at GPU scale and saves logs / checkpoints / config / samples / diagnostics.
#
# ONE-COMMAND USAGE (after cloning the repo on a GPU pod):
#     bash scripts/run_gpu_training.sh
#
# Override any setting via env vars, e.g.:
#     STEPS=10000 BATCH=96 DMODEL=768 LAYERS=12 bash scripts/run_gpu_training.sh
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."          # repo root

EXP="${EXP:-symbolu_gpu_full}"
OUT="runs/${EXP}"
# --- training hyperparameters (A100/H100 defaults) ---
ABLATION="${ABLATION:-full}"     # full = typed-heads + refinement + memory
MODE="${MODE:-combined}"         # combined = contribution + residual-reg + entropy-cal
STEPS="${STEPS:-5000}"
BATCH="${BATCH:-64}"
GRAD_ACCUM="${GRAD_ACCUM:-1}"
LR="${LR:-3e-4}"
BLOCK="${BLOCK:-512}"
DMODEL="${DMODEL:-512}"
LAYERS="${LAYERS:-8}"
HEADS="${HEADS:-8}"
CKPT_EVERY="${CKPT_EVERY:-1000}"
EVAL_EVERY="${EVAL_EVERY:-500}"
LOG_EVERY="${LOG_EVERY:-50}"
CONTRIB_EVERY="${CONTRIB_EVERY:-4}"
GEN_TOKENS="${GEN_TOKENS:-400}"
SEED="${SEED:-0}"

echo "=================================================================="
echo " Symbol-U clean-softmax GPU training :: experiment=$EXP"
echo "=================================================================="
mkdir -p "$OUT"

# ---- 1) verify CUDA + print GPU information ----
python - <<'PY'
import torch
print("torch:", torch.__version__)
ok = torch.cuda.is_available()
print("cuda available:", ok)
if ok:
    i = torch.cuda.current_device()
    p = torch.cuda.get_device_properties(i)
    print(f"GPU[{i}]: {p.name} | VRAM {p.total_memory/1e9:.1f} GB | "
          f"compute {p.major}.{p.minor} | bf16={torch.cuda.is_bf16_supported()}")
else:
    print("WARNING: no CUDA detected — this will run on CPU. Use a GPU pod for the real run.")
PY
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi || echo "(nvidia-smi not available)"

# ---- 2) install missing dependencies ----
python -c "import torch"  2>/dev/null || pip install --quiet torch
python -c "import numpy"  2>/dev/null || pip install --quiet numpy

# ---- 3) prepare dataset (idempotent) ----
[ -f data/clean_lm/corpus.txt ] || \
  python -m symbolu_neural.clean_softmax.prepare_data --out data/clean_lm/corpus.txt

# ---- 4) launch training (saves logs, ckpts, config, samples, diagnostics) ----
python -m symbolu_neural.clean_softmax.train_gpu \
  --corpus data/clean_lm/corpus.txt --ablation "$ABLATION" --mode "$MODE" \
  --steps "$STEPS" --batch-size "$BATCH" --grad-accum "$GRAD_ACCUM" --lr "$LR" \
  --block "$BLOCK" --d-model "$DMODEL" --layers "$LAYERS" --heads "$HEADS" \
  --amp --ckpt-every "$CKPT_EVERY" --eval-every "$EVAL_EVERY" --log-every "$LOG_EVERY" \
  --contrib-every "$CONTRIB_EVERY" --gen-tokens "$GEN_TOKENS" --seed "$SEED" \
  --out "$OUT" 2>&1 | tee "$OUT/train_console.log"

# ---- 5) explicitly run generate.py on the final checkpoint (validates loading) ----
python -m symbolu_neural.clean_softmax.generate --ckpt "$OUT/ckpt.pt" \
  --prompt "The model " --max-new-tokens "$GEN_TOKENS" --temperature 0.8 --top-k 40 \
  --seed "$SEED" 2>&1 | tee "$OUT/generate_cli.txt"

# ---- 6) token-change instrumentation / contribution activity on final ckpt ----
python -m symbolu_neural.clean_softmax.inspect_generation --ckpt "$OUT/ckpt.pt" \
  --prompt "The model " --n 120 --temperature 0.8 --top-k 40 --seed "$SEED" \
  2>&1 | tee "$OUT/activity.txt" || echo "(inspect_generation skipped)"

echo "=================================================================="
echo " DONE — outputs in $OUT/"
echo "   config.json  train_log.jsonl  ckpt.pt  ckpt_step*.pt"
echo "   metrics.json samples.txt      generate_cli.txt activity.txt"
echo "=================================================================="
ls -la "$OUT" || true
