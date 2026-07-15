#!/usr/bin/env bash
# KVPro V3 Gate-1 orchestrator (falsification study; fake-quant, no int4 fork needed).
#
#   ./run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --full-quality
#       full: capture -> recon + attn -> needle + hard-needle + MMLU + token-agreement -> verdict
#   ./run_all.sh --needle-only            # standard needle -> gate
#   ./run_all.sh --hard-needle-only       # hard-needle (MANDATORY gate) -> gate
#   ./run_all.sh --mmlu-only              # MMLU -> gate
#   ./run_all.sh --quick-quality          # small needle + hard-needle + builtin MMLU -> gate
#   ./run_all.sh --reconstruction-only    # offline recon (synthetic if no capture) — CPU-runnable
#   ./run_all.sh --quality-only           # offline attn + ppl e2e -> gate (no needle/mmlu)
#
# Quality drivers are POD-ONLY (GPU + model + mask). Fails loudly if those are missing.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/_lib.sh"

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"; MASK="${MASK:-${PROTECT_MASK_PATH:-}}"; MODE="full"
QUICK=0
while [[ $# -gt 0 ]]; do case "$1" in
  --model) MODEL="$2"; shift 2;;
  --mask)  MASK="$2";  shift 2;;
  --full-quality) MODE="full"; shift;;
  --needle-only) MODE="needle"; shift;;
  --hard-needle-only) MODE="hardneedle"; shift;;
  --mmlu-only) MODE="mmlu"; shift;;
  --quick-quality) MODE="full"; QUICK=1; shift;;
  --reconstruction-only) MODE="recon"; shift;;
  --quality-only) MODE="offline"; shift;;
  -h|--help) sed -n '2,18p' "$0"; exit 0;;
  *) fail "unknown arg: $1"; exit 64;;
esac; done
export MODEL MASK
RUN="$(kvv3_run_dir)"; export KVV3_RUN_DIR="$RUN"
GATE_MODEL=qwen; case "$MODEL" in *[Ll]lama*) GATE_MODEL=llama;; esac; export GATE_MODEL
section "KVPro V3 Gate-1 — mode=$MODE quick=$QUICK — model=$MODEL — run=$RUN"

DRV() { python3 "$HERE/$1" "${@:2}"; }
NDL_ARGS=(--model "$MODEL" --mask "$MASK" --out "$RUN/needle_results.json")
HN_ARGS=(--model "$MODEL" --mask "$MASK" --out "$RUN/hard_needle_results.json")
MM_ARGS=(--model "$MODEL" --mask "$MASK" --out "$RUN/knowledge_results.json")
if [[ "$QUICK" -eq 1 ]]; then
  NDL_ARGS+=(--num-needles 2 --seeds 0); HN_ARGS+=(--items-per-mode 2 --seeds 0); MM_ARGS+=(--num-questions 8)
fi

run_needle()  { pod_gate_or_die "$MASK"; run_step "standard needle"  "$RUN/needle.log"     DRV needle_driver.py "${NDL_ARGS[@]}"; }
run_hardn()   { pod_gate_or_die "$MASK"; run_step "hard-needle"      "$RUN/hard_needle.log" DRV hard_needle_driver.py "${HN_ARGS[@]}"; }
run_mmlu()    { pod_gate_or_die "$MASK"; run_step "MMLU/knowledge"   "$RUN/knowledge.log"  DRV mmlu_driver.py "${MM_ARGS[@]}"; }
run_tokagr()  { run_step "token agreement" "$RUN/token_agreement.log" \
                  DRV token_agreement.py --model "$MODEL" --mask "$MASK" --out "$RUN/token_agreement.json"; }
run_offline() {
  CAPTURE="${CAP:-}" bash "$HERE/run_reconstruction_eval.sh" || true
  CAPTURE="${CAP:-}" bash "$HERE/run_attention_error_eval.sh" || true
}
CAP=""
capture_if_pod() {
  if [[ "$(gpu_count)" -ge 1 ]] && mask_ok "$MASK"; then
    MODEL="$MODEL" MASK="$MASK" bash "$HERE/run_capture.sh" || true
    [[ -f "$RUN/CAPTURE_PATH" ]] && CAP="$(cat "$RUN/CAPTURE_PATH")"
  fi
}

case "$MODE" in
  recon)      capture_if_pod; CAPTURE="$CAP" bash "$HERE/run_reconstruction_eval.sh" || true ;;
  offline)    run_offline
              if [[ "$(gpu_count)" -ge 1 ]] && mask_ok "$MASK"; then
                run_step "ppl e2e" "$RUN/e2e.log" DRV fakequant_quality.py --model "$MODEL" --mask "$MASK" --out "$RUN/e2e_quality.json" || true
              fi
              bash "$HERE/run_quality_gate.sh" || true ;;
  needle)     run_needle || true; bash "$HERE/run_quality_gate.sh" || true ;;
  hardneedle) run_hardn  || true; bash "$HERE/run_quality_gate.sh" || true ;;
  mmlu)       run_mmlu   || true; bash "$HERE/run_quality_gate.sh" || true ;;
  full)
    capture_if_pod
    run_offline
    run_hardn  || true        # MANDATORY, Qwen2.5-7B first (the marginal model)
    run_needle || true
    run_mmlu   || true
    run_tokagr || true
    bash "$HERE/run_quality_gate.sh" || true ;;
esac

section "Gate-1 complete"
ok "artifacts under: $RUN"
note "GO requires needle + hard-needle + MMLU to PASS on the model under test; ppl/token-agreement/"
note "attention-proxy alone can never GO. See verdict.json + candidate_summary.csv."
