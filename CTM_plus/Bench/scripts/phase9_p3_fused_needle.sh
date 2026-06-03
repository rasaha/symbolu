#!/usr/bin/env bash
# =============================================================================
# phase9_p3_fused_needle.sh — P3 payoff: real needle through fused_v2 + read-skip.
# Three cells (off / retain_all / retention) at long context, then combine into
# byte-eq + quality + throughput. ~$0.50-1.00 (4 model loads incl. check).
# =============================================================================
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$PWD}"; cd "$REPO_ROOT"
OUT="${OUT:-./Bench/bench_out/PHASE9_P3}"; mkdir -p "$OUT"
PY="Bench/scripts/phase9_p3_fused_needle.py"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
CONTEXT="${CONTEXT:-8000}"
DEPTHS="${DEPTHS:-0.1,0.5,0.9}"
ITEMS="${ITEMS:-2}"
MML="${MML:-16384}"
GU="${GU:-0.6}"
COMMON=(--model "$MODEL" --backend fused_v2 --context-tokens "$CONTEXT"
        --depths "$DEPTHS" --items "$ITEMS" --max-model-len "$MML" --gpu-util "$GU")
log() { printf '\n[P3] %s\n' "$*"; }

log "preflight — does fused_v2 fire under batch=1 offline generate?"
INT4_READSKIP_MODE=off python "$PY" "${COMMON[@]}" --check-install \
  --out "$OUT/_check.json"

log "cell OFF (full int4 baseline)"
INT4_READSKIP_MODE=off python "$PY" "${COMMON[@]}" --out "$OUT/off.json"

log "cell RETAIN_ALL (read-skip plumbing on, keeps all -> byte-eq vs off)"
INT4_READSKIP_MODE=retain_all python "$PY" "${COMMON[@]}" --out "$OUT/retain_all.json"

log "cell RETENTION (sink+recent+attention skip -> quality must hold)"
INT4_READSKIP_MODE=retention python "$PY" "${COMMON[@]}" --out "$OUT/retention.json"

log "PHASE9_P3_REPORT.md"
python - "$OUT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
off = json.load(open(root/"off.json"))
ra  = json.load(open(root/"retain_all.json"))
ret = json.load(open(root/"retention.json"))
L = ["# Phase 9 P3 — fused_v2 + read-skip (real needle) report", "",
     f"model={off['model']} context={off['context_tokens']} backend={off['backend']}", ""]

# (1) BYTE-EQ: off vs retain_all per-item generated text identical.
L.append("## (1) BYTE-EQ — off vs retain_all (read-skip plumbing transparent?)")
n = min(len(off["items"]), len(ra["items"]))
ident = sum(1 for i in range(n) if off["items"][i]["generated"] == ra["items"][i]["generated"])
L.append(f"- identical generations: {ident}/{n}")
L.append("- PASS if all identical -> active_positions plumbing changes nothing when "
         "everything is retained." if ident == n else
         "- FAIL: retain_all diverged from off -> the gather/wiring is NOT transparent.")

# (2) QUALITY: retention vs off (baseline) by depth.
L += ["", "## (2) QUALITY — needle hit rate by depth",
      "| depth | off | retain_all | retention |", "|---|---:|---:|---:|"]
for d in off["hit_rate_by_depth"]:
    L.append(f"| {d} | {off['hit_rate_by_depth'][d]} | "
             f"{ra['hit_rate_by_depth'].get(d)} | {ret['hit_rate_by_depth'].get(d)} |")

# (3) THROUGHPUT.
L += ["", "## (3) THROUGHPUT (decode tps, batch=1 long-context)",
      f"- off        : {off['decode_tps']}",
      f"- retention  : {ret['decode_tps']}  "
      f"(readskip_calls={ret['readskip_calls']} fused_v2_decodes={ret['fused_v2_decodes']})"]
if off["decode_tps"]:
    g = (ret["decode_tps"] - off["decode_tps"]) / off["decode_tps"] * 100
    L.append(f"- delta     : {g:+.1f}%  (>0 => read-skip faster at this context)")

L += ["", "## Read it",
      "- byte-eq identical + retention quality ~= off + retention faster => the read-skip",
      "  kernel WORKS on the production path: faster at preserved quality. The per-watt",
      "  bullet in the VC brief becomes a measured number.",
      "- retention quality << off => the real-kernel skip drops needed tokens (tune",
      "  budget/observe/refresh, or the kernel skip != the proxy).",
      "- byte-eq NOT identical => wiring bug (investigate before trusting anything else).",
      "- retention NOT faster => skipping isn't reducing work (check it actually skipped:",
      "  readskip_calls>0 and retained<seq_len at this context)."]
pathlib.Path("PHASE9_P3_REPORT.md").write_text("\n".join(L)+"\n")
print("\n".join(L))
PY
log "done — PHASE9_P3_REPORT.md"
