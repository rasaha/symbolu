#!/usr/bin/env bash
# Phase 6M — Tier-1 operating-point sweep (no ncu, no code change). RUN ON POD.
#
# Finds the BEST throughput ratio int4_protected already achieves, by sweeping
# the capacity demo across batch sizes and generation lengths and tabulating the
# protected/bf16 aggregate-tps ratio at each point. This is PURE MEASUREMENT —
# no kernel/quant change, no profiling counters needed — so it runs on any GPU
# pod (including the ncu-locked ones). It explains why we saw 0.22x at one point
# and 0.32x at another: the ratio is operating-point-sensitive, and this finds
# the sweet spot you already have for free.
#
# It does NOT improve the kernel (that's Test 3 / 6F). It only locates the best
# existing config — useful for "deploy at the config that minimizes the tax".
#
# Usage (on the pod):
#   source /workspace/venv-vllm/bin/activate
#   bash CTM_plus/Bench/scripts/phase6m_operating_point_sweep.sh
#
# Env: MML, B_LIST, GEN_LIST, PROMPT_FRAC, OUT, MODEL.
#   B_LIST   batch sizes to sweep (default "48,72,96,128")
#   GEN_LIST generation lengths to sweep (default "128,512")
#
# PRECONDITIONS (this session's hard lessons):
#   - kernels rebuilt + byte-eq GREEN (preflight_gpu_pod.sh)
#   - protect mask present AND valid — a bad/short-context mask makes int4
#     output collapse; throughput numbers stay valid but DON'T quote quality.
#   - export HF_HUB_ENABLE_HF_TRANSFER=0 ; HF_HOME=/workspace/.cache/huggingface
set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAP="$SCRIPTS_DIR/phase6l_capacity_demo.py"
PY="${PYTHON:-python}"
OUT="${OUT:-$SCRIPTS_DIR/../bench_out/phase6m_opsweep}"
mkdir -p "$OUT"

MML="${MML:-8192}"
B_LIST="${B_LIST:-48,72,96,128}"
GEN_LIST="${GEN_LIST:-128,512}"
PROMPT_FRAC="${PROMPT_FRAC:-0.95}"

echo "=================================================================="
echo "Phase 6M Tier-1 operating-point sweep (no ncu, no code change)"
echo "  mml=$MML  b_list=$B_LIST  gen_list=$GEN_LIST  frac=$PROMPT_FRAC"
echo "  out: $OUT"
echo "=================================================================="

IFS=',' read -ra GENS <<< "$GEN_LIST"
SUMMARY="$OUT/opsweep_summary.tsv"
echo -e "gen\tb_list\tbf16_agg_tps\tprot_agg_tps\tagg_ratio\tnet_density\tprot_live" > "$SUMMARY"

for GEN in "${GENS[@]}"; do
    RUN_OUT="$OUT/gen${GEN}"
    mkdir -p "$RUN_OUT"
    echo
    echo "### sweep: max_tokens=$GEN ###"
    "$PY" "$CAP" --compare --mml "$MML" --max-tokens "$GEN" \
        --prompt-frac "$PROMPT_FRAC" --b-list "$B_LIST" --out-dir "$RUN_OUT" \
        || echo "!!! gen=$GEN run returned nonzero (claim not demonstrated or error)"
    # Pull the headline ratio out of the report.json for the summary table.
    REPORT="$RUN_OUT/report.json"
    if [[ -f "$REPORT" ]]; then
        "$PY" - "$REPORT" "$GEN" "$B_LIST" >> "$SUMMARY" <<'PY'
import json, sys
report, gen, blist = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(report))
tp = d.get("throughput") or {}
dn = d.get("density") or {}
def g(x, default="NA"):
    v = tp.get(x);  return f"{v}" if v is not None else default
row = [gen, blist,
       g("bf16_agg_tps"), g("protected_agg_tps"), g("aggregate_tps_ratio"),
       f"{dn.get('net_density_ratio','NA')}",
       f"{(d.get('analysis',{}).get('by_cell',{}).get('protected',{}) or {}).get('demonstrated_live','NA')}"]
print("\t".join(str(x) for x in row))
PY
    fi
done

echo
echo "=================================================================="
echo "SWEEP SUMMARY (best agg_ratio = the config to deploy at):"
echo "=================================================================="
column -t -s $'\t' "$SUMMARY" 2>/dev/null || cat "$SUMMARY"
echo
echo "Artifacts (commit with git add -f; bench_out gitignored):"
echo "  $SUMMARY"
echo "  $OUT/gen*/report.json"
echo
echo "REMINDER: this finds the best EXISTING config (no code change). It does NOT"
echo "remove the gather tax — that is Test 3 / 6F (see estimate_phase6m_headroom.py"
echo "for the bounded ceiling). Density + quality unchanged; quote throughput only"
echo "if the protect mask is valid (no collapse)."
echo "=================================================================="
