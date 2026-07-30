#!/usr/bin/env bash
# KVPro x video-understanding feasibility — POD orchestration (Qwen2.5-VL).
# Phase 1: capture KV over video (GPU) -> analyze outlier structure (CPU) -> GO/NO-GO verdict.
set -euo pipefail
cd /workspace/symbolu
export HF_HOME=/workspace/hf_cache HF_HUB_ENABLE_HF_TRANSFER=0 HF_HUB_DISABLE_XET=1
MODEL=Qwen/Qwen2.5-VL-7B-Instruct
VIDEO=${1:?"usage: run_commands.sh <video.mp4>"}
OUT=artifacts/kvpro_video/capture
DIR=scripts/kvpro_video_understanding

pip install -U transformers accelerate qwen-vl-utils decord >/dev/null

# 0. verify model card (license/gated) before download — same discipline as the Mistral run
python -c "from huggingface_hub import model_info as mi; i=mi('$MODEL'); print('gated',i.gated,'license',(i.cardData or {}).get('license'))"

# 1. capture KV over increasing clip length (GPU); measures KV growth + dumps per-layer KV
python "$DIR/capture_vlm_kv.py" --model "$MODEL" --video "$VIDEO" \
  --frames 8,32,128 --save-layers 0,7,15,23,27 --out-dir "$OUT"

# 2. analyze the longest clip for outlier structure -> pre-registered GO/NO-GO (CPU)
python "$DIR/analyze_kv_outliers.py" --kv "$OUT/frames128" \
  --out-json artifacts/kvpro_video/feasibility_verdict.json \
  --out-csv  artifacts/kvpro_video/kv_outlier_metrics.csv

echo "verdict -> artifacts/kvpro_video/feasibility_verdict.json ; KV growth -> $OUT/kv_growth.json"
echo "GO*  -> proceed to Phase 2 video-QA quality (see the feasibility plan doc)."
