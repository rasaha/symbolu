#!/usr/bin/env bash
# ==========================================================================
# KVPro prot-int8 — Mistral real-model A/B/C run (POD-ONLY; requires GPU+weights)
# A = full BF16 KV            -> cell "fp"
# B = INT4 + BF16 protected   -> cell "affine"
# C = INT4 + INT8 protected   -> cell "P8prod"
# Primary causal comparison: C - B (identical machinery, only the protected sidecar dtype differs).
# NOTE: the quality path is FAKE-QUANT (reconstruct then HF attention), apples-to-apples for C-B,
#       but NOT the production vLLM int4 kernel. Label results accordingly.
# Secrets: NEVER put an HF token on a command line or in this file. Use `huggingface-cli login`
#          (writes to ~/.cache), only if the model turns out to be gated.
# ==========================================================================
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
EXP="$REPO_ROOT/experiments/kvpro_v3_symmetric_residual"
MODEL="mistralai/Mistral-7B-Instruct-v0.3"
export HF_HOME="${HF_HOME:-/workspace/hf_cache}"          # dedicated cache, OUTSIDE git
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
MASK="/workspace/hf_cache/mistral_v0_3_protect_mask_4pct_v2.pt"   # v2: WITH k_min/k_max (6N)
mkdir -p "$HF_HOME"

# --- 0. Hardware + disk sanity (report, do not proceed blindly) ------------
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv || { echo "NO GPU"; exit 1; }
df -h "$HF_HOME"

# --- 1. Deps (do NOT reinstall torch if the CUDA build already works) ------
python -c "import torch;assert torch.cuda.is_available()" || { echo "CUDA torch missing"; exit 1; }
python -m pip install -U transformers accelerate sentencepiece safetensors datasets evaluate huggingface_hub

# --- 2. VERIFY model BEFORE download: identifier, license, gating, config ---
#     Confirm Apache-2.0 (open source) vs MRL, gated=false, and CRITICALLY sliding_window==null.
python - "$MODEL" << 'PY'
import sys, json
from huggingface_hub import model_info
from transformers import AutoConfig
mid = sys.argv[1]
info = model_info(mid)                      # raises if the id does not exist / is inaccessible
cfg = AutoConfig.from_pretrained(mid)
lic = (info.cardData or {}).get("license") if info.cardData else getattr(info, "license", None)
out = {"id": mid, "gated": getattr(info, "gated", None), "license": lic,
       "sliding_window": getattr(cfg, "sliding_window", None),
       "num_key_value_heads": cfg.num_key_value_heads, "head_dim": getattr(cfg, "head_dim", None),
       "num_hidden_layers": cfg.num_hidden_layers, "num_attention_heads": cfg.num_attention_heads}
print(json.dumps(out, indent=2))
assert out["sliding_window"] in (None, 0), f"SWA ENABLED ({out['sliding_window']}) -> INCOMPATIBLE with the full-KV paged cache. STOP."
assert out["head_dim"] in (128, None), "head_dim != 128 -> check prot_int8/D assumptions."
print("[OK] compatibility gate passed (SWA disabled, head_dim=128).")
PY

# --- 3. Build the v2 protect mask for Mistral (WITH k_min/k_max for prot-int8) ---
python "$REPO_ROOT/CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py" \
    --model "$MODEL" --protect-fraction 0.04 --minmax-margin 1.1 \
    --max-model-len 2048 --output "$MASK"
export PROTECT_MASK_PATH="$MASK"

# --- 4. A/B/C QUALITY (fake-quant): greedy parity + logits + needle + hard-needle + MMLU ---
#     cells fp(A), affine(B), P8prod(C). Start with a quick sanity pass, then full.
cd "$EXP"
bash run_p8_quality.sh --model "$MODEL" --mask "$MASK" --cells fp,affine,P8prod --quick-quality
bash run_p8_quality.sh --model "$MODEL" --mask "$MASK" --cells fp,affine,P8prod --full-quality --real-mmlu 200
#   -> runs/<ts>/ : p8_needle.json p8_hard_needle.json p8_knowledge.json p8_verdict.json

# --- 5. Perplexity (small, established) — reuse the repo eval if present ----
#     e.g. wikitext-2-raw-v1; report exact n_samples + context_len in the CSV.
#     (Use the repo's perplexity/token-agreement stage under run_all.sh --reconstruction-only
#      or eval_lambada.py / eval_hellaswag.py as available for the chosen dataset.)

# --- 6. MEMORY + PERF (production path) — measure real torch.cuda + decode TPS -----
#     Use the production paged writer/backend (phase5b_backend_install) with and without
#     $INT4_PROTECTED_PROT_INT8 to get REAL allocated/reserved/peak + tokens/s for B vs C,
#     and confirm the int8->bf16 dequant materialization (IMPORTANT PATH CHECK).
#     INT4_PROTECTED_PROT_INT8 unset -> B ; =1 -> C. Keep every other knob identical.

# --- 7. Collect artifacts into artifacts/prot_int8_mistral/ (compact summaries only) ---
echo "Copy runs/<ts>/p8_verdict.json + summarized CSVs into artifacts/prot_int8_mistral/."
echo "DO NOT commit: model weights, HF cache ($HF_HOME), raw generations, profiler dumps."
