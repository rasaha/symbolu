#!/usr/bin/env bash
# Phase A-F for ONE model: capture metadata (pod) + run every CPU analyzer for scale & xmin.
# Usage: ./run_metadata_explore.sh --model <m> --mask <m.pt> --tag qwen [--outdir out] [--no-capture]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PYBIN="${PYBIN:-python3}"
[ -f /workspace/venv-vllm/bin/activate ] && . /workspace/venv-vllm/bin/activate
MODEL=""; MASK=""; TAG=""; OUTDIR="$HERE/out"; CAPTURE=1
while [ $# -gt 0 ]; do case "$1" in
  --model) MODEL="$2"; shift 2;; --mask) MASK="$2"; shift 2;; --tag) TAG="$2"; shift 2;;
  --outdir) OUTDIR="$2"; shift 2;; --no-capture) CAPTURE=0; shift;;
  *) echo "unknown arg $1"; exit 2;; esac; done
: "${TAG:?--tag required}"; mkdir -p "$OUTDIR"
MAN="$OUTDIR/${TAG}_meta.pt"
if [ "$CAPTURE" = 1 ]; then
  : "${MODEL:?--model required}"; : "${MASK:?--mask required}"
  echo "== $TAG: capture =="; "$PYBIN" "$HERE/metadata_explore.py" --model "$MODEL" --mask "$MASK" --out "$MAN" || exit 1
fi
for KIND in scale xmin; do
  echo "== $TAG/$KIND: entropy, temporal, clustering, variance, methods =="
  "$PYBIN" "$HERE/analyze_entropy.py"            --manifest "$MAN" --kind "$KIND" --out-json "$OUTDIR/${TAG}_${KIND}_entropy.json"  || exit 1
  "$PYBIN" "$HERE/analyze_temporal_stability.py" --manifest "$MAN" --kind "$KIND" --out-json "$OUTDIR/${TAG}_${KIND}_temporal.json" || exit 1
  "$PYBIN" "$HERE/analyze_clustering.py"         --manifest "$MAN" --kind "$KIND" --out-json "$OUTDIR/${TAG}_${KIND}_clustering.json" || exit 1
  "$PYBIN" "$HERE/analyze_variance_sources.py"   --manifest "$MAN" --kind "$KIND" --out-json "$OUTDIR/${TAG}_${KIND}_variance.json" || exit 1
  "$PYBIN" "$HERE/compare_structure_methods.py"  --manifest "$MAN" --kind "$KIND" --out-json "$OUTDIR/${TAG}_${KIND}_methods.json" --out-csv "$OUTDIR/${TAG}_${KIND}_methods.csv" || exit 1
done
echo "artifacts -> $OUTDIR (tag=$TAG)"
