#!/usr/bin/env bash
# Video-DiT reused-feature-cache compression — POD orchestration (Stage B capture -> Stage A analyze).
# Bounded feasibility study; see docs/VIDEO_DIT_FEATURE_CACHE_COMPRESSION_FEASIBILITY_PLAN.md.
# Does NOT modify KVPro. Captures ONLY tensors reused across denoising steps.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export HF_HOME=${HF_HOME:-/workspace/hf_cache} HF_HUB_ENABLE_HF_TRANSFER=0 HF_HUB_DISABLE_XET=1
MODEL="${MODEL:-THUDM/CogVideoX-2b}"          # PRIMARY (plan §5); Wan2.1 T2V-1.3B is the secondary
PROMPT="${PROMPT:-A cat playing piano on a city street at night.}"
DIR=scripts/kvpro_video_dit_cache
OUT=artifacts/video_dit_cache/capture

pip install -U "diffusers>=0.31" transformers accelerate imageio imageio-ffmpeg numpy >/dev/null

# 0. verify model card (license/gated) before download — same discipline as the Mistral/VLM runs
python -c "from huggingface_hub import model_info as mi; i=mi('$MODEL'); print('gated',i.gated,'license',(i.cardData or {}).get('license'))"

# 1. STAGE B capture: read-only forward taps -> cross-step cache tensors + systems counters (GPU)
python "$DIR/capture_dit_cache.py" --model "$MODEL" --prompt "$PROMPT" \
  --num-frames 49 --steps 50 --cache-steps 8,16,24,32,40 \
  --save-layers 0,7,15,23,29 --out-dir "$OUT"

# 2. STAGE A analyze: compressibility + provisional verdict (CPU; caps at representation feasibility)
python "$DIR/analyze_cache_compressibility.py" --cache "$OUT" \
  --out-json artifacts/video_dit_cache/stageA_verdict.json \
  --out-csv  artifacts/video_dit_cache/stageA_metrics.csv

echo "verdict  -> artifacts/video_dit_cache/stageA_verdict.json"
echo "systems  -> $OUT/systems_metrics.json (several fields REQUIRE GPU PROFILER)"
echo "NEXT: run the calibration phase and FREEZE thresholds (verdict.freeze) before evaluating C-F."
