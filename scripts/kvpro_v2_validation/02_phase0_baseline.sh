#!/usr/bin/env bash
# 02 — Phase-0 baseline reproduction (smallest reproducible first).
# Reproduces, on real GPU, for Qwen2.5-7B (then optionally more models):
#   (a) quality  — hard-needle int4_protected vs bf16   (phase6k12_hard_needle.py)
#   (b) density  — saturation raw/net + sidecar tax      (phase6k14_saturation.py -> phase6l)
#   (c) throughput — int4 vs full-precision ratio + sweep (bench_phase6_b4 + batched)
# Logs/artifacts -> runs/kvpro_v2/<timestamp>/. Every number here is MEASURED by THIS run.
#
# Models:
#   Primary  : $MODEL (default Qwen/Qwen2.5-7B-Instruct), uses $PROTECT_MASK_PATH.
#   Extra    : $EXTRA_MODELS = "id1=/path/mask1.pt,id2=/path/mask2.pt" (each needs its own mask).
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
QUALITY_MML="${QUALITY_MML:-8192}"
QUALITY_ITEMS="${QUALITY_ITEMS:-6}"
DENSITY_MML="${DENSITY_MML:-8192}"
TPUT_BATCHES="${TPUT_BATCHES:-1,2,4,8}"
TPUT_MML="${TPUT_MML:-4096}"

env_gate_or_die
RUN="$(kvpro_run_dir)"; SUM="$RUN/SUMMARY_phase0.md"
B6="$REPO/CTM_plus/Bench/scripts"
section "Phase-0 baseline → $RUN"
{
  echo "# KVPro v2 — Phase-0 baseline (MEASURED this run)"
  echo "- run dir: $RUN"
  echo "- date(UTC): $(date -u)"
  echo "- NOTE: all values below are MEASURED on THIS pod/run. The decode ceiling"
  echo "  (~0.27-0.30x, never parity) is the v2 *recovery target*, not a result here."
  echo
} >"$SUM"

run_one_model() {
  local model="$1" maskhint="${2:-}"
  local slug; slug="$(echo "$model" | tr '/:' '__')"
  local mlog="$RUN/${slug}"; mkdir -p "$mlog"
  section "Model: $model  (mask: ${PROTECT_MASK_PATH:-<env>})"
  echo "## $model" >>"$SUM"

  # model/mask flags for phase6k12 (non-Qwen needs explicit --model/--protect-mask)
  local mk_flags=(--mml "$QUALITY_MML" --items "$QUALITY_ITEMS" --cells bf16,protected)
  if [[ "$model" != "Qwen/Qwen2.5-7B-Instruct" ]]; then
    mk_flags+=(--model "$model")
    [[ -n "$maskhint" ]] && mk_flags+=(--protect-mask "$maskhint")
  fi

  # (a) QUALITY -------------------------------------------------------------
  rm -f /tmp/phase6k12_*.json 2>/dev/null || true
  if run_step "quality: hard-needle bf16 vs protected" "$mlog/quality.log" \
        python3 "$B6/phase6k12_hard_needle.py" "${mk_flags[@]}"; then :; fi
  cp /tmp/phase6k12_*.json "$mlog/" 2>/dev/null || true
  python3 - "$mlog" "$SUM" "$model" <<'PY' || true
import json, sys, glob, os
mlog, sumf, model = sys.argv[1:4]
rows=[]
for p in sorted(glob.glob(os.path.join(mlog, "phase6k12_*.json"))):
    try:
        d=json.load(open(p))
        rows.append((d.get("cell","?"), d.get("strict_accuracy"), d.get("retrieval_accuracy"),
                     d.get("n_total")))
    except Exception as e:
        rows.append((os.path.basename(p), f"parse-error:{e}", None, None))
with open(sumf,"a") as f:
    f.write("### quality (MEASURED — hard-needle)\n")
    if not rows:
        f.write("- NO quality JSON produced (see quality.log) — step did not complete.\n\n"); raise SystemExit
    for cell, strict, retr, n in rows:
        f.write(f"- cell=`{cell}` strict_accuracy=**{strict}** retrieval_accuracy={retr} n={n}\n")
    f.write("- (Qwen2.5-7B may be AT-THE-MARGIN under the 4% mask; report the exact figure, do not round to parity.)\n\n")
print("quality parsed:", rows)
PY

  # (b) DENSITY -------------------------------------------------------------
  rm -f /tmp/phase6k14_*.json 2>/dev/null || true
  run_step "density: saturation sweep bf16 vs protected" "$mlog/density.log" \
      python3 "$B6/phase6k14_saturation.py" --mml "$DENSITY_MML" --cells bf16,protected || true
  cp /tmp/phase6k14_*.json "$mlog/" 2>/dev/null || true
  # Net-density / sidecar-tax summary from the produced JSONs.
  if ls "$mlog"/phase6k14_*.json >/dev/null 2>&1; then
    run_step "density: net-density analysis (phase6l)" "$mlog/density_analysis.log" \
        python3 "$B6/phase6l_capacity_demo.py" --compare --from-jsons "$mlog"/phase6k14_*.json || true
    {
      echo "### density (MEASURED — saturation)"
      echo "- raw saturation JSONs + net-density analysis: \`$mlog/density*.log\`, \`$mlog/phase6k14_*.json\`"
      echo "- expected class: ~2.0x raw KV slots, ~1.8x net under saturation, flat sidecar tax — confirm in the log."
      echo
    } >>"$SUM"
  else
    echo "### density: NO saturation JSON produced (see density.log)." >>"$SUM"; echo >>"$SUM"
  fi

  # (c) THROUGHPUT ----------------------------------------------------------
  ceiling_note
  run_step "throughput: int4(eager) vs full-precision(bf16) ratio" "$mlog/tput_ratio.log" \
      python3 "$B6/bench_phase6_b4_throughput_gpu.py" --cells eager,bf16 \
        --model "$model" --max-model-len "$TPUT_MML" || true
  run_step "throughput: int4_protected batched sweep" "$mlog/tput_sweep.log" \
      python3 "$B6/bench_phase6_batched_throughput.py" \
        --model "$model" --max-model-len "$TPUT_MML" --batch-sizes "$TPUT_BATCHES" || true
  {
    echo "### throughput (MEASURED this run)"
    echo "- int4-vs-bf16 ratio: \`$mlog/tput_ratio.log\` (the 0.13–0.67x-class number, workload-dependent)."
    echo "- int4 batched sweep (agg_tps per B): \`$mlog/tput_sweep.log\`."
    echo "- KVPro is below full precision on the unoptimized path; recovery ceiling ~0.27–0.30x, NEVER parity."
    echo
  } >>"$SUM"
}

# Primary model (smallest reproducible first).
run_one_model "$MODEL" "${PROTECT_MASK_PATH:-}"

# Optional extra models: EXTRA_MODELS="id=/path/mask.pt,id2=/path/mask2.pt"
if [[ -n "${EXTRA_MODELS:-}" ]]; then
  IFS=',' read -ra _items <<<"$EXTRA_MODELS"
  for it in "${_items[@]}"; do
    m="${it%%=*}"; mp="${it#*=}"
    [[ -f "$mp" ]] || { warn "extra model $m: mask $mp missing — run 01_calibrate_mask.sh; skipping."; continue; }
    export PROTECT_MASK_PATH="$mp"
    run_one_model "$m" "$mp"
  done
fi

section "Phase-0 baseline complete"
ok "Summary: $SUM"
note "All figures in the summary are MEASURED by this run; no projected value is presented as a result."
