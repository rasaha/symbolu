#!/usr/bin/env bash
# =============================================================================
# phase9_readskip_proxy.sh — DE-RISK the read-skip kernel before building it.
# Toggle sliding-window attention (= fixed intra-sequence read-skip) on a model,
# on a long needle-in-haystack, and measure Step-0's two IFs:
#   throughput win (SWA on vs off) + quality cliff (needle depth vs window).
# See PHASE9_READSKIP_PROXY_RUNBOOK.md. GPU pod. ~$0.30-0.50.
# =============================================================================
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$PWD}"; cd "$REPO_ROOT"
OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/PHASE9_READSKIP_PROXY}"
mkdir -p "$OUT_ROOT"

# Defaults sit in Mistral-v0.1's VIABLE BAND: it was trained with a 4096 window,
# so full attention (the OFF baseline) only works in-distribution up to ~its
# training length. context=4000 keeps OFF valid; window=1024 < context leaves a
# skippable middle (depths 0.10/0.50 outside the window, 0.80/0.95 inside).
# A 16k context made OFF degenerate (emitted ~1 token) -> cliff unmeasurable.
MODEL="${MODEL:-mistralai/Mistral-7B-Instruct-v0.1}"   # native sliding_window=4096
WINDOW="${WINDOW:-1024}"
CONTEXT_TOKENS="${CONTEXT_TOKENS:-4000}"
DEPTHS="${DEPTHS:-0.1,0.5,0.8,0.95}"
ITEMS="${ITEMS:-4}"
MAX_GEN="${MAX_GEN:-32}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
GPU_UTIL="${GPU_UTIL:-0.85}"
PROXY="Bench/scripts/phase9_readskip_proxy.py"
log() { printf '\n[PROXY] %s\n' "$*"; }

# 0. Cheap toggle preflight — confirm the SWA override actually takes effect on
#    this vLLM build BEFORE spending on the full run. If the two effective
#    windows are identical, the override is being ignored -> STOP, the proxy is
#    invalid (fall back to comparing Mistral-v0.1 vs a full-attention model).
log "preflight — confirm sliding-window toggle takes effect"
python "$PROXY" --model "$MODEL" --sliding-window "$WINDOW" --max-model-len "$MAX_MODEL_LEN" --gpu-util "$GPU_UTIL" --check-window
python "$PROXY" --model "$MODEL" --sliding-window 0        --max-model-len "$MAX_MODEL_LEN" --gpu-util "$GPU_UTIL" --check-window

# 1. read-skip ON (SWA = WINDOW)
log "cell read-skip ON (sliding_window=$WINDOW)"
python "$PROXY" --model "$MODEL" --sliding-window "$WINDOW" \
  --context-tokens "$CONTEXT_TOKENS" --depths "$DEPTHS" --items "$ITEMS" \
  --max-gen "$MAX_GEN" --max-model-len "$MAX_MODEL_LEN" --gpu-util "$GPU_UTIL" \
  --out "$OUT_ROOT/swa_on.json"

# 2. read-skip OFF (full attention)
log "cell read-skip OFF (full attention)"
python "$PROXY" --model "$MODEL" --sliding-window 0 \
  --context-tokens "$CONTEXT_TOKENS" --depths "$DEPTHS" --items "$ITEMS" \
  --max-gen "$MAX_GEN" --max-model-len "$MAX_MODEL_LEN" --gpu-util "$GPU_UTIL" \
  --out "$OUT_ROOT/swa_off.json"

# 3. combine
log "PHASE9_READSKIP_PROXY_REPORT.md"
python - "$OUT_ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
on = json.load(open(root/"swa_on.json")); off = json.load(open(root/"swa_off.json"))
L = ["# Phase 9 — read-skip proxy (sliding-window) report", "",
     f"model={on['model']}  context_tokens={on['context_tokens']}  "
     f"window(on)={on['effective_sliding_window']}", "",
     "## (1) THROUGHPUT — does read-skip win?",
     f"- read-skip ON  decode_tps = {on['decode_tps']}",
     f"- read-skip OFF decode_tps = {off['decode_tps']}"]
if off['decode_tps']:
    g = (on['decode_tps']-off['decode_tps'])/off['decode_tps']*100
    L.append(f"- **delta = {g:+.1f}%**  (>0 => read-skip is faster at this context)")
L += ["", "## (2) QUALITY — the H2O cliff (hit rate by needle depth)"]
if off.get("degenerate_baseline") or on.get("degenerate_baseline"):
    L += [f"⚠ DEGENERATE CELL(s): mean_gen_tokens ON={on.get('mean_gen_tokens')} "
          f"OFF={off.get('mean_gen_tokens')} (<3 = model emitted ~nothing). The "
          "quality table below is INVALID — lower CONTEXT_TOKENS into the model's "
          "viable band (full attention must work for the OFF baseline). The "
          "THROUGHPUT number above is still valid.", ""]
L += ["| depth | ON inside-window? | ON hit | OFF hit |", "|---|---|---:|---:|"]
for d in on['per_depth_hit_rate']:
    o = on['per_depth_hit_rate'][d]; f = off['per_depth_hit_rate'].get(d, {})
    L.append(f"| {d} | {o.get('needle_inside_window')} | {o['hit_rate']} | {f.get('hit_rate')} |")
L += ["",
      "## Read it (the kernel go/no-go)",
      "- read-skip FASTER (delta>0) AND OFF keeps hits everywhere (so the model+task work):",
      "  the throughput lever is real. Then look at the quality cliff:",
      "  * ON keeps hits for deep (inside-window) needles but MISSES early/mid ones",
      "    => the EXPECTED H2O loss. Attention-guided read-skip (keep sinks+high-attn)",
      "    would rescue exactly those misses -> the kernel build is JUSTIFIED.",
      "  * ON misses even the LATE/inside-window needles => the proxy/model is broken",
      "    (or window didn't apply) -> investigate before concluding.",
      "- read-skip NOT faster (delta<=0) => no throughput prize even from a perfect",
      "  fixed skip at this context -> DO NOT build the kernel; lengthen context or stop.",
      "- ON quality == OFF quality with delta>0 would be the dream (free lunch) — treat",
      "  with suspicion; confirm the window actually applied (effective_sliding_window)."]
pathlib.Path("PHASE9_READSKIP_PROXY_REPORT.md").write_text("\n".join(L)+"\n")
print("\n".join(L))
PY
log "done — inspect PHASE9_READSKIP_PROXY_REPORT.md"
