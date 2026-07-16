#!/usr/bin/env bash
# KVPro V3 query-fold — orchestrator (POD). Structure gate FIRST; attention + quality
# run only with --full, and quality runs only for candidates that clear structure+
# attention+systems. Emits per-stage JSON + a final verdict. No kernel, no TPS claim.
#
#   ./run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask <m.pt> --structure-only
#   ./run_all.sh --model meta-llama/Llama-3.1-8B-Instruct --mask <m.pt> --structure-only
#   ./run_all.sh --both-models --full          # needs --qwen-mask & --llama-mask (or env)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYBIN="${PYBIN:-python3}"
[ -f /workspace/venv-vllm/bin/activate ] && . /workspace/venv-vllm/bin/activate
OUTDIR="${OUTDIR:-$HERE/out}"
QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
LLAMA_MODEL="${LLAMA_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
STRUCTURE_ONLY=0; FULL=0; BOTH=0; MODEL=""; MASK=""

while [ $# -gt 0 ]; do case "$1" in
  --model) MODEL="$2"; shift 2;;
  --mask) MASK="$2"; shift 2;;
  --qwen-mask) QWEN_MASK="$2"; shift 2;;
  --llama-mask) LLAMA_MASK="$2"; shift 2;;
  --structure-only) STRUCTURE_ONLY=1; shift;;
  --full) FULL=1; shift;;
  --both-models) BOTH=1; shift;;
  --outdir) OUTDIR="$2"; shift 2;;
  *) echo "unknown arg: $1"; exit 2;;
esac; done
mkdir -p "$OUTDIR"

tag_for() { case "$1" in *[Qq]wen*) echo qwen;; *[Ll]lama*) echo llama;; *) echo model;; esac; }

cap_struct_attn() {   # $1=model $2=mask $3=tag  -> capture + structure (+ attention if --full)
  local model="$1" mask="$2" tag="$3"
  echo "==== $tag: capture ===="
  "$PYBIN" "$HERE/capture_metadata.py" --model "$model" --mask "$mask" \
      --out "$OUTDIR/${tag}_capture.pt" || return 1
  echo "==== $tag: structure (scale + xmin) ===="
  "$PYBIN" "$HERE/analyze_scale_structure.py" --manifest "$OUTDIR/${tag}_capture.pt" \
      --out-json "$OUTDIR/${tag}_scale_structure.json" --out-csv "$OUTDIR/${tag}_scale_structure.csv" || return 1
  "$PYBIN" "$HERE/analyze_xmin_structure.py" --manifest "$OUTDIR/${tag}_capture.pt" \
      --out-json "$OUTDIR/${tag}_xmin_structure.json" --out-csv "$OUTDIR/${tag}_xmin_structure.csv" || return 1
  if [ "$FULL" = 1 ]; then
    echo "==== $tag: attention ===="
    "$PYBIN" "$HERE/evaluate_attention.py" --manifest "$OUTDIR/${tag}_capture.pt" \
        --out-json "$OUTDIR/${tag}_attention.json" || return 1
  fi
}

survivors() {   # combined survivors (structure+attention+systems) across $1=models-csv
  "$PYBIN" "$HERE/decide.py" --results-dir "$OUTDIR" --models "$1" --structure-only \
      --out-json "$OUTDIR/prelim_verdict.json" >/dev/null 2>&1 || true
  "$PYBIN" -c "import json;print(','.join(json.load(open('$OUTDIR/prelim_verdict.json')).get('survivors') or []))" 2>/dev/null
}

# --- run models ---
if [ "$BOTH" = 1 ]; then
  : "${QWEN_MASK:?--qwen-mask or QWEN_MASK required}"; : "${LLAMA_MASK:?--llama-mask or LLAMA_MASK required}"
  cap_struct_attn "$QWEN_MODEL" "$QWEN_MASK" qwen || exit 1
  cap_struct_attn "$LLAMA_MODEL" "$LLAMA_MASK" llama || exit 1
  MODELS="qwen,llama"
  Q_MASK="$QWEN_MASK"; L_MASK="$LLAMA_MASK"
else
  : "${MODEL:?--model required}"; : "${MASK:?--mask required}"
  TAG=$(tag_for "$MODEL"); cap_struct_attn "$MODEL" "$MASK" "$TAG" || exit 1
  MODELS="$TAG"
fi

# --- quality only for survivors (with --full) ---
if [ "$FULL" = 1 ]; then
  SURV=$(survivors "$MODELS")
  if [ -n "$SURV" ]; then
    echo "==== quality (survivors: $SURV) ===="
    if [ "$BOTH" = 1 ]; then
      "$PYBIN" "$HERE/run_quality.py" --model "$QWEN_MODEL"  --mask "$Q_MASK" --candidates "$SURV" \
          --out "$OUTDIR/qwen_quality.json"  --outdir "$OUTDIR/qwen_quality_raw"  || exit 1
      "$PYBIN" "$HERE/run_quality.py" --model "$LLAMA_MODEL" --mask "$L_MASK" --candidates "$SURV" \
          --out "$OUTDIR/llama_quality.json" --outdir "$OUTDIR/llama_quality_raw" || exit 1
    else
      "$PYBIN" "$HERE/run_quality.py" --model "$MODEL" --mask "$MASK" --candidates "$SURV" \
          --out "$OUTDIR/${MODELS}_quality.json" --outdir "$OUTDIR/${MODELS}_quality_raw" || exit 1
    fi
  else
    echo "  no candidate cleared structure+attention+systems -> skipping quality"
  fi
fi

# --- final verdict ---
echo "==== VERDICT ===="
FLAGS=""; [ "$STRUCTURE_ONLY" = 1 ] && FLAGS="--structure-only"
"$PYBIN" "$HERE/decide.py" --results-dir "$OUTDIR" --models "$MODELS" $FLAGS --out-json "$OUTDIR/verdict.json"
echo "artifacts in $OUTDIR ; commit with: git add -f $OUTDIR"
