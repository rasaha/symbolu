#!/usr/bin/env bash
# train_cg_active.sh — train the Active-CG variant to produce a NON-INERT head for the ablation.
#
# Bakes in the analysis-driven config (see BOOTSTRAP_ANALYSIS.md):
#   --cg_bootstrap_mode active   (gate -1.0 + N(0,1e-3) adapter; escapes the inert fixed point)
#   --mistral_quantize none      (bf16 on A100 80GB; ablate with DTYPE=bf16 to match)
#   --no-stage8 equivalent       (Stage-8 synthesizer is ignored by the ablation; omitted)
#   CG_BOOTSTRAP_PROBE_EVERY     (logs gate / gate_grad / adapter_output_norm / corr-hidden ratio)
#
# Output: checkpoints_mistral_cg/best_model.pt  -> set CG_CHECKPOINT to it for the ablation.
#
# Usage:
#   PYTHONPATH=$PWD bash scripts/cg_wrapper_ablation/train_cg_active.sh
# Override via env: DATASET, MAX_STEPS, SEQ_LEN, BATCH, ACCUM, LR, EVAL_EVERY, SAVE_EVERY,
#                   WARMUP, CKPT_DIR, PROBE_EVERY.
#   e.g. SEQ_LEN=1024 BATCH=48 ACCUM=1 MAX_STEPS=3000 EVAL_EVERY=500 LR=3e-4 \
#        PYTHONPATH=$PWD bash scripts/cg_wrapper_ablation/train_cg_active.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
export PYTHONPATH="${PYTHONPATH:-$PWD}"

DATASET="${DATASET:-wikitext103}"
MAX_STEPS="${MAX_STEPS:-5000}"
SEQ_LEN="${SEQ_LEN:-2048}"
BATCH="${BATCH:-16}"
ACCUM="${ACCUM:-2}"
LR="${LR:-3e-4}"
EVAL_EVERY="${EVAL_EVERY:-1000}"
SAVE_EVERY="${SAVE_EVERY:-$EVAL_EVERY}"        # default: save whenever we eval (-> best_model.pt)
WARMUP="${WARMUP:-500}"
CKPT_DIR="${CKPT_DIR:-$PWD/checkpoints_mistral_cg}"
export CG_BOOTSTRAP_PROBE_EVERY="${PROBE_EVERY:-50}"

echo "== Active-CG training =="
echo "  dataset=$DATASET steps=$MAX_STEPS seq_len=$SEQ_LEN batch=${BATCH}x${ACCUM} lr=$LR"
echo "  eval_every=$EVAL_EVERY save_every=$SAVE_EVERY warmup=$WARMUP"
echo "  ckpt=$CKPT_DIR  probe_every=$CG_BOOTSTRAP_PROBE_EVERY"
echo "  NOTE: best_model.pt requires at least one eval -> keep EVAL_EVERY <= MAX_STEPS."
echo "  GATE CHECK: by ~step 1000 expect [CG-BOOTSTRAP] gate ~0.27 (parked is fine) and corr/hidden > ~0.05;"
echo "             if gate fell back to 0.1191 or corr/hidden < 1e-2, stop — the head is not active."

python train_unified_llm.py \
  --model_type mistral_cg \
  --mistral_model_name mistralai/Mistral-7B-v0.3 --mistral_quantize none \
  --cg_bootstrap_mode active \
  --dataset "$DATASET" --max_seq_len "$SEQ_LEN" \
  --max_steps "$MAX_STEPS" \
  --batch_size "$BATCH" --gradient_accumulation "$ACCUM" \
  --learning_rate "$LR" --warmup_steps "$WARMUP" \
  --eval_every "$EVAL_EVERY" --save_every "$SAVE_EVERY" --log_every 50 --sample_every "$EVAL_EVERY" \
  --mixed_precision bf16 \
  --enable_conscious_generation \
  --lambda_ont 0.01 --lambda_kosha_routing 0.01 --lambda_bliss_token 0.01 \
  --lambda_plausibility_token 0.005 --lambda_csr_token 0.005 \
  --lambda_vritti_token 0.005 --lambda_guna_token 0.005 \
  --enable_embedding_diagnostics --embedding_diag_interval 200 --embedding_diag_no_samples \
  --checkpoint_dir "$CKPT_DIR"

echo "== done. Next:"
echo "   export CG_CHECKPOINT=$CKPT_DIR/best_model.pt"
echo "   python - <<'PY'  # verify TRAINED"
echo "   import os,torch; from experiments.signal_gov.cg_checkpoint import unwrap_state_dict,verify_cg_state_dict"
echo "   print(verify_cg_state_dict(unwrap_state_dict(torch.load(os.environ['CG_CHECKPOINT'],map_location='cpu',weights_only=False))).summary)"
echo "   PY"
echo "   DTYPE=bf16 python scripts/cg_wrapper_ablation/smoke_generate.py 'Q: 6 rows of 8 apples. How many? A:'"
