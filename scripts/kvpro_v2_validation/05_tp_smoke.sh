#!/usr/bin/env bash
# 05 — Tensor-parallel smoke (multi-GPU only).
#   - Skips clearly if < 2 GPUs.
#   - Builds int4_protected at TP=1 and TP=2 (separate processes), compares greedy output
#     (correctness) and rank-0 writer geometry (sidecar/pool sharding signal).
# NOTE: tensor_parallel_size is NOT yet wired for int4_protected (single-GPU validated only).
# This smoke MEASURES what actually happens: a TP=2 construction/correctness failure is the
# real, honest result (TP not yet supported), printed with the gap — never faked as PASS.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

N_GPU="$(gpu_count)"
section "TP smoke (need >= 2 GPUs; have $N_GPU)"
if [[ "$N_GPU" -lt 2 ]]; then
  note "SKIP: fewer than 2 GPUs visible — tensor-parallel smoke not applicable here."
  exit 0
fi

env_gate_or_die
RUN="$(kvpro_run_dir)"; SUM="$RUN/SUMMARY_tp.md"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
DRV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_tp_smoke.py"
{ echo "# int4_protected TP smoke (MEASURED this run)"; echo "- GPUs: $N_GPU · model: $MODEL"; echo; } >"$SUM"

run_step "TP=1 baseline generate" "$RUN/tp1.log" \
    python3 "$DRV" --tp 1 --model "$MODEL" --out "$RUN/tp1.json" || true
run_step "TP=2 generate" "$RUN/tp2.log" \
    python3 "$DRV" --tp 2 --model "$MODEL" --out "$RUN/tp2.json" || true

python3 - "$RUN/tp1.json" "$RUN/tp2.json" "$SUM" <<'PY'
import json, os, sys
p1, p2, sumf = sys.argv[1:4]
def load(p):
    return json.load(open(p)) if os.path.exists(p) else {"ok": False, "error": "no output (process crashed before writing)"}
a, b = load(p1), load(p2)
lines = ["## verdict (MEASURED)"]
if not a.get("ok"):
    lines.append(f"- TP=1 FAILED: {a.get('error')} — baseline could not be established.")
if not b.get("ok"):
    lines.append(f"- **TP=2 FAILED (MEASURED): {b.get('error')}**")
    lines.append("- => Tensor parallelism is NOT validated for int4_protected. Likely gap: the")
    lines.append("  KVPro sidecars/staging pools (k_scale_ext/k_xmin_ext/v_*/k_protect_ext/_k_stage_pool)")
    lines.append("  are per-layer and not sharded/all-reduced across TP ranks. This is the integration")
    lines.append("  work to do; single-GPU remains the validated configuration.")
elif a.get("ok"):
    same = a.get("output_text") == b.get("output_text")
    lines.append(f"- TP=2 constructed and generated: OK")
    lines.append(f"- greedy output TP1==TP2 (correctness): **{'PASS' if same else 'FAIL'}** (MEASURED)")
    g1, g2 = a.get("writer_geometry", {}), b.get("writer_geometry", {})
    h1, h2 = g1.get("H_per_rank"), g2.get("H_per_rank")
    lines.append(f"- rank-0 writer H/rank: TP1={h1} TP2={h2}")
    if h1 and h2:
        if h2 == h1 // 2:
            lines.append("- sidecar sharding: rank-0 sees HALF the heads at TP=2 => **sharded as expected** (MEASURED).")
        elif h2 == h1:
            lines.append("- sidecar sharding: rank-0 sees ALL heads at TP=2 => **NOT sharded** (sidecars replicated/incorrect).")
        else:
            lines.append(f"- sidecar sharding: ambiguous (H1={h1}, H2={h2}) — inspect tp2.json.")
    if not same:
        lines.append("- Output differs => TP correctness FAIL; do not claim TP-validated.")
open(sumf, "a").write("\n".join(lines) + "\n")
print("\n".join(lines))
PY

section "TP smoke complete"
ok "Summary: $SUM  (artifacts: tp1.json, tp2.json, tp1.log, tp2.log)"
note "A TP=2 failure here is a MEASURED negative (TP not yet supported), not a harness bug."
