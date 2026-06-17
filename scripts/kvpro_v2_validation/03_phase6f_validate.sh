#!/usr/bin/env bash
# 03 — Phase 6F (int4 read-path dequant-prep fusion) validation.
#   1. CPU byte-equivalence tests (fused == reference)            [MEASURED, no GPU needed]
#   2. GPU fused-vs-nonfused: ONLY if the fusion is wired into the decode path.
#      If not wired -> INCOMPLETE with the EXACT integration point (no fake A/B).
#   3. before/after decode throughput at PHASE6F_FUSED_READ=0 and =1 (when wired).
# Emits a CSV summary. Decode recovery ceiling ~0.27-0.30x, NEVER parity.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

RUN="$(kvpro_run_dir)"; CSV="$RUN/phase6f_summary.csv"
B6="$REPO/CTM_plus/Bench/scripts"
TEST="$REPO/CTM_plus/KVPolicy/tests/test_phase6f_read_fusion_cpu.py"
BACKEND="$REPO/CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
TPUT_MML="${TPUT_MML:-4096}"; TPUT_BATCHES="${TPUT_BATCHES:-1,8}"

echo "phase,test,mode,status,value,unit,label,notes" >"$CSV"
csv() { echo "6F,$1,$2,$3,${4:-},${5:-},${6:-},${7:-}" >>"$CSV"; }

section "Phase 6F — CPU byte-equivalence (fused == reference)"
if run_step "cpu byte-eq (test_phase6f_read_fusion_cpu)" "$RUN/phase6f_cpu.log" python3 "$TEST"; then
  csv "cpu_byte_equivalence" "cpu" "PASS" "" "" "MEASURED" "fused==reference for K/V/prep"
else
  csv "cpu_byte_equivalence" "cpu" "FAIL" "" "" "MEASURED" "see phase6f_cpu.log"
fi

section "Phase 6F — GPU A/B (gated on integration being wired)"
WIRED=0
if grep -qE 'PHASE6F_FUSED_READ|fused_read_dequant_prep|phase6f_read_fusion' "$BACKEND" 2>/dev/null; then
  WIRED=1
fi

if [[ "$WIRED" -eq 0 ]]; then
  warn "Phase 6F is NOT wired into the live decode path yet — GPU A/B would be a NO-OP."
  warn "EXACT integration point required before the throughput A/B is meaningful:"
  echo  "    File : CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py"
  echo  "    Func : _read_decode_packed_batched (and B=1: _read_decode_packed_one)"
  echo  "    Wire : replace the staged get_packed_view_batched -> _splice -> dequant with"
  echo  "           kv_policy.phase6f_read_fusion.fused_read_dequant_prep(view, BS=...),"
  echo  "           honoring env PHASE6F_FUSED_READ (0=reference, 1=fused) for the A/B gate."
  echo  "    Oracle: tests/test_phase6f_read_fusion_cpu.py already pins fused==reference."
  csv "gpu_fused_vs_nonfused" "gpu" "INCOMPLETE" "" "" "NOT-MEASURED" "fusion not wired; see integration point above"
  csv "gpu_throughput_ab" "gpu" "INCOMPLETE" "" "" "NOT-MEASURED" "A/B skipped — would be a no-op until wired"
else
  env_gate_or_die
  ceiling_note
  # GPU kernel correctness oracle, if the GPU test exists.
  if [[ -f "$B6/kernel_6c_gpu_test.py" ]]; then
    if run_step "gpu fused kernel correctness (kernel_6c_gpu_test)" "$RUN/phase6f_gpu_correct.log" \
          python3 "$B6/kernel_6c_gpu_test.py"; then
      csv "gpu_fused_vs_nonfused" "gpu" "PASS" "" "" "MEASURED" "kernel_6c_gpu_test"
    else
      csv "gpu_fused_vs_nonfused" "gpu" "FAIL" "" "" "MEASURED" "see phase6f_gpu_correct.log"
    fi
  fi
  # A/B throughput: same bench, PHASE6F_FUSED_READ=0 then =1.
  for flag in 0 1; do
    PHASE6F_FUSED_READ="$flag" run_step "throughput PHASE6F_FUSED_READ=$flag" "$RUN/phase6f_tput_$flag.log" \
        python3 "$B6/bench_phase6_batched_throughput.py" --model "$MODEL" \
          --max-model-len "$TPUT_MML" --batch-sizes "$TPUT_BATCHES" || true
  done
  python3 - "$RUN" "$CSV" <<'PY' || true
import re, sys, glob, os
run, csvf = sys.argv[1:3]
def best_tps(p):
    t=None
    for ln in open(p, errors="ignore"):
        m=re.search(r'agg_tps[=\s:]+([0-9.]+)', ln) or re.search(r'\|\s*([0-9.]+)\s*\|\s*[0-9.]+\s*\|\s*[0-9.]+×', ln)
        if m:
            try: t=max(t or 0.0, float(m.group(1)))
            except: pass
    return t
f0=best_tps(os.path.join(run,"phase6f_tput_0.log"))
f1=best_tps(os.path.join(run,"phase6f_tput_1.log"))
with open(csvf,"a") as f:
    f.write(f"6F,gpu_throughput_ab,gpu,{'MEASURED' if (f0 and f1) else 'PARTIAL'},,,MEASURED,reference_agg_tps={f0}\n")
    f.write(f"6F,gpu_throughput_ab_fused,gpu,{'MEASURED' if f1 else 'PARTIAL'},{f1 or ''},tok/s,MEASURED,fused_agg_tps; ceiling<=~0.30x vs full precision\n")
print("A/B agg_tps: reference(=0)=",f0," fused(=1)=",f1)
PY
fi

section "Phase 6F validation complete"
ok "CSV summary: $CSV"
note "Decode recovery ceiling stays ~0.27-0.30x; full-precision parity is NOT claimed."
