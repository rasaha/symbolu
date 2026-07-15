#!/usr/bin/env bash
# Combine reconstruction + attention-error (+ optional end-to-end) into the pre-registered verdict.
# Emits verdict.json + a CSV summary. RECON=, ATTN=, E2E= override the run-dir defaults.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"
cpu_gate_or_die
RUN="$(kvv3_run_dir)"
RECON="${RECON:-$RUN/reconstruction_metrics.json}"
ATTN="${ATTN:-$RUN/attention_error_metrics.json}"
E2E="${E2E:-$RUN/e2e_quality.json}"
MODEL="${GATE_MODEL:-qwen}"
section "Decision gate (pre-registered)"
args=(--out "$RUN/verdict.json" --model "$MODEL")
[[ -f "$RECON" ]] && args+=(--recon "$RECON") || note "no reconstruction JSON ($RECON) — NOT RUN"
[[ -f "$ATTN"  ]] && args+=(--attn  "$ATTN")  || note "no attention JSON ($ATTN) — NOT RUN"
[[ -f "$E2E"   ]] && args+=(--e2e   "$E2E")   || note "no end-to-end JSON ($E2E) — NOT RUN (needs pod fake-quant)"
run_step "verdict" "$RUN/gate.log" python3 "$KVV3_LIB_DIR/gates.py" "${args[@]}"
# CSV summary from the verdict JSON.
python3 - "$RUN/verdict.json" "$RUN/verdict_summary.csv" <<'PY' || true
import json, sys
v = json.load(open(sys.argv[1]))
with open(sys.argv[2], "w") as f:
    f.write("candidate,quality_offline,quality_e2e,systems_pass,pct_reduction\n")
    for c, p in v["per_candidate"].items():
        f.write(f"{c},{p['quality_offline']},{p['quality_e2e']},{p['systems_pass']},{p['pct_reduction']}\n")
    f.write(f"# VERDICT,{v['verdict']},,,\n")
print("VERDICT:", v["verdict"], "-> verdict.json + verdict_summary.csv")
PY
cat "$RUN/gate.log" | tail -8
ok "-> $RUN/verdict.json  |  $RUN/verdict_summary.csv"
