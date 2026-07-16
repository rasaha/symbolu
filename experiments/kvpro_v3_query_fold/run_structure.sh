#!/usr/bin/env bash
# Phase C/D — scale + xmin structural audit for ONE captured manifest (CPU-OK). Usage:
#   ./run_structure.sh <capture.pt> <tag> [outdir]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PYBIN="${PYBIN:-python3}"
MAN="${1:?capture.pt required}"; TAG="${2:?tag required}"; OUT="${3:-$HERE/out}"; mkdir -p "$OUT"
"$PYBIN" "$HERE/analyze_scale_structure.py" --manifest "$MAN" --out-json "$OUT/${TAG}_scale_structure.json" --out-csv "$OUT/${TAG}_scale_structure.csv"
"$PYBIN" "$HERE/analyze_xmin_structure.py"  --manifest "$MAN" --out-json "$OUT/${TAG}_xmin_structure.json"  --out-csv "$OUT/${TAG}_xmin_structure.csv"
