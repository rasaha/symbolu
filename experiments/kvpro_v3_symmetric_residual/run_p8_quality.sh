#!/usr/bin/env bash
# KVPro V3 Step-0 — Part F runner: protected-INT8 (P8) quality gate (POD-ONLY, HARDWARE-UNTESTED).
# Cells: fp, affine (baseline = current shipped affine + EXACT/bf16 protected), P8sym, P8aff (int8 protected).
# Reuses the exact needle / hard-needle / MMLU protocol + drivers via --cells. Emits p8_verdict.json.
#   bash run_p8_quality.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --quick-quality
#   bash run_p8_quality.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --full-quality [--real-mmlu N]
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; source "$HERE/_lib.sh"

MODEL="Qwen/Qwen2.5-7B-Instruct"; MASK="${PROTECT_MASK_PATH:-}"; QUICK=0; REAL_MMLU=0; MMLU_N=0
# P8prod = production-faithful (needs k_min/k_max in the mask). Add P8aff,P8sym for experimental upper bounds.
CELLS="fp,affine,P8prod"
while [[ $# -gt 0 ]]; do case "$1" in
  --model) MODEL="$2"; shift 2;;
  --mask) MASK="$2"; shift 2;;
  --quick-quality) QUICK=1; shift;;
  --full-quality) QUICK=0; shift;;
  --real-mmlu) REAL_MMLU=1; MMLU_N="$2"; shift 2;;
  --cells) CELLS="$2"; shift 2;;
  -h|--help) sed -n '2,7p' "$0"; exit 0;;
  *) fail "unknown arg: $1"; exit 64;;
esac; done

RUN="$(kvv3_run_dir)"
section "KVPro V3 Step-0 P8 (protected-INT8) — model=$MODEL cells=$CELLS quick=$QUICK — run=$RUN"
pod_gate_or_die "$MASK"
DRV() { "$PY" "$HERE/$1" "${@:2}"; }

NDL=(--model "$MODEL" --mask "$MASK" --cells "$CELLS" --out "$RUN/p8_needle.json")
HN=(--model "$MODEL" --mask "$MASK" --cells "$CELLS" --out "$RUN/p8_hard_needle.json")
MM=(--model "$MODEL" --mask "$MASK" --cells "$CELLS" --out "$RUN/p8_knowledge.json")
if [[ "$QUICK" -eq 1 ]]; then
  NDL+=(--num-needles 2 --seeds 0); HN+=(--items-per-mode 2 --seeds 0); MM+=(--num-questions 8)
fi
if [[ "$REAL_MMLU" -eq 1 ]]; then MM+=(--real --num-questions "$MMLU_N"); fi

run_step "P8 hard-needle" "$RUN/p8_hard_needle.log" DRV hard_needle_driver.py "${HN[@]}" || true
run_step "P8 needle"      "$RUN/p8_needle.log"      DRV needle_driver.py "${NDL[@]}" || true
run_step "P8 MMLU"        "$RUN/p8_knowledge.log"   DRV mmlu_driver.py "${MM[@]}" || true

run_step "P8 verdict" "$RUN/p8_gate.log" DRV p8_gate.py \
  --needle "$RUN/p8_needle.json" --hard-needle "$RUN/p8_hard_needle.json" --mmlu "$RUN/p8_knowledge.json" \
  --out "$RUN/p8_verdict.json" || true

section "P8 complete"
ok "artifacts under: $RUN (p8_verdict.json)"
note "P8 changes ONLY protected-K precision vs affine; evaluate independently, do NOT combine with S2 yet."
note "Feed p8_verdict.json to the Step-0 decision matrix: scripts/kvpro_v3_profile/05_decision_matrix.py --p8 ..."
