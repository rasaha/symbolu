#!/usr/bin/env bash
# Combine attention proxy + standard-needle + hard-needle + MMLU into the pre-registered verdict.
# Emits verdict.json + candidate_summary.csv. Paths default to the run dir; override via env.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"
cpu_gate_or_die
RUN="$(kvv3_run_dir)"
ATTN="${ATTN:-$RUN/attention_error_metrics.json}"
NEEDLE="${NEEDLE:-$RUN/needle_results.json}"
HARDN="${HARDN:-$RUN/hard_needle_results.json}"
MMLU="${MMLU:-$RUN/knowledge_results.json}"
GATE_MODEL="${GATE_MODEL:-qwen}"

section "Decision gate (end-to-end quality REQUIRED for GO)"
args=(--out "$RUN/verdict.json" --model "$GATE_MODEL")
[[ -f "$ATTN"   ]] && args+=(--attn "$ATTN")            || note "attention proxy NOT RUN"
[[ -f "$NEEDLE" ]] && args+=(--needle "$NEEDLE")        || note "standard needle NOT RUN"
[[ -f "$HARDN"  ]] && args+=(--hard-needle "$HARDN")    || note "hard-needle NOT RUN (MANDATORY for GO)"
[[ -f "$MMLU"   ]] && args+=(--mmlu "$MMLU")            || note "MMLU NOT RUN"
run_step "verdict" "$RUN/gate.log" python3 "$KVV3_LIB_DIR/gates.py" "${args[@]}"

python3 - "$RUN/verdict.json" "$RUN/candidate_summary.csv" <<'PY' || true
import json, sys
v = json.load(open(sys.argv[1]))
with open(sys.argv[2], "w") as f:
    f.write("candidate,offline,needle,hard_needle,mmlu,full_quality,systems_pass,pct_reduction\n")
    for c, p in v["per_candidate"].items():
        f.write(f"{c},{p['quality_offline']},{p['needle']},{p['hard_needle']},{p['mmlu']},"
                f"{p['full_quality']},{p['systems_pass']},{p['pct_reduction']}\n")
    f.write(f"# VERDICT,{v['verdict']},benchmarks={v['benchmarks']},,,,,\n")
print("VERDICT:", v["verdict"], "| benchmarks:", v["benchmarks"])
PY
tail -10 "$RUN/gate.log"
ok "-> $RUN/verdict.json | $RUN/candidate_summary.csv"
