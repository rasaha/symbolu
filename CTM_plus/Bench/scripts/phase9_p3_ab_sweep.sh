#!/usr/bin/env bash
# =============================================================================
# phase9_p3_ab_sweep.sh — STEP 0 length sweep on the HARDENED yardstick.
#
# Runs the within-process paired A/B (off vs retention on ONE warm engine,
# decode-only timing, warmup discarded, repeated measurements) at a series of
# context lengths, then combines the per-context JSONs into one markdown table.
# This is the Phase-10 Step-0 measurement: does the read-skip throughput delta
# grow with context once cross-run noise and prefill dilution are removed?
#
# Each context = ONE process / ONE warm engine, so the off-vs-retention delta
# at that context is within-process (the part that must be noise-free). Only the
# rows differ by process — fine, because the headline per row is the paired delta.
#
# Knobs (env-overridable). Aggressive skip (RECENT/BUDGET/SINK) = the P4b/c regime
# that reached breakeven at ~86% skip; at longer context the same fixed keep-set
# is a smaller fraction -> more skip -> (hypothesis) a bigger decode prize.
# =============================================================================
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$PWD}"; cd "$REPO_ROOT"
OUT="${OUT:-./Bench/bench_out/PHASE10_AB}"; mkdir -p "$OUT"
PY="Bench/scripts/phase9_p3_fused_needle.py"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"

# Read-skip regime (consumed at manager __init__ -> must be in env). Aggressive.
export INT4_READSKIP_SINK="${INT4_READSKIP_SINK:-64}"
export INT4_READSKIP_RECENT="${INT4_READSKIP_RECENT:-512}"
export INT4_READSKIP_BUDGET="${INT4_READSKIP_BUDGET:-512}"
export INT4_READSKIP_BLOCK="${INT4_READSKIP_BLOCK:-32}"
export INT4_READSKIP_NEIGHBOR="${INT4_READSKIP_NEIGHBOR:-1}"
export INT4_READSKIP_OBSERVE="${INT4_READSKIP_OBSERVE:-8}"
export INT4_READSKIP_REFRESH="${INT4_READSKIP_REFRESH:-16}"

# A/B measurement shape.
MODES="${MODES:-off,retention}"
SEEDS="${SEEDS:-1,2,3}"
DEPTHS="${DEPTHS:-0.1,0.5,0.9}"
REPEATS="${REPEATS:-3}"
WARMUP="${WARMUP:-2}"
GEN="${GEN:-128}"
GU="${GU:-0.6}"

# Sweep = space-separated  context:max_model_len  pairs.
#   8000  control (the P4c breakeven point, re-measured noise-free)
#   16384 longer context
#   30720 ~"32k": kept under Qwen2.5-7B's 32768 ceiling to leave room for
#         needle+template+GEN (prompt+gen must be <= max_position_embeddings).
SWEEP="${SWEEP:-8000:9216 16384:18432 30720:32768}"

log() { printf '\n[AB-SWEEP] %s\n' "$*"; }
log "model=$MODEL  skip(SINK=$INT4_READSKIP_SINK RECENT=$INT4_READSKIP_RECENT BUDGET=$INT4_READSKIP_BUDGET)"
log "seeds=$SEEDS depths=$DEPTHS repeats=$REPEATS warmup=$WARMUP gen=$GEN modes=$MODES"
log "sweep(context:max_model_len)=$SWEEP"

# gap #4: bf16 reference line (separate vanilla engine). On by default; BF16=0 to
# skip (it doubles model loads, and bf16 KV is larger -> may need a lower GU/ctx).
BF16="${BF16:-1}"

for pair in $SWEEP; do
  CTX="${pair%%:*}"; MML="${pair##*:}"
  log "ctx=$CTX max_model_len=$MML"
  python "$PY" --ab --model "$MODEL" --backend fused_v2 \
    --context-tokens "$CTX" --max-model-len "$MML" --gpu-util "$GU" \
    --ab-modes "$MODES" --seeds "$SEEDS" --depths "$DEPTHS" \
    --repeats "$REPEATS" --warmup "$WARMUP" --ab-gen "$GEN" \
    --out "$OUT/ab_ctx${CTX}.json"
  if [ "$BF16" = "1" ]; then
    log "ctx=$CTX bf16 reference (vanilla, no int4/read-skip)"
    python "$PY" --bf16-ref --model "$MODEL" \
      --context-tokens "$CTX" --max-model-len "$MML" --gpu-util "$GU" \
      --seeds "$SEEDS" --depths "$DEPTHS" \
      --repeats "$REPEATS" --warmup "$WARMUP" --ab-gen "$GEN" \
      --out "$OUT/bf16_ctx${CTX}.json"
  fi
done

log "combine -> PHASE10_STEP0_AB_REPORT.md"
python - "$OUT" "$SWEEP" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1]); sweep = sys.argv[2].split()
TARGET_X = 1.9   # Step-0 cost-model modeled net read-skip speedup vs off (long ctx)
rows = []
for pair in sweep:
    ctx = pair.split(":")[0]
    p = out / f"ab_ctx{ctx}.json"
    bf = out / f"bf16_ctx{ctx}.json"
    bf16 = json.load(open(bf)) if bf.exists() else None
    if not p.exists():
        rows.append((ctx, None, bf16)); continue
    rows.append((ctx, json.load(open(p)), bf16))
L = ["# Phase 10 Step 0 — read-skip length sweep (within-process paired A/B)", "",
     "Hardened yardstick: off vs retention on ONE warm engine, decode-only timing",
     "(prefill excluded), warmup discarded, repeated measurements. The paired delta",
     "per context is within-process, so it is NOT contaminated by the cross-run drift",
     "(10.75->8.9->7.29) that made the original breakeven untrustworthy.", ""]
any_ok = False
for ctx, r, bf16 in rows:
    if r is None:
        L.append(f"- ctx={ctx}: MISSING ({out}/ab_ctx{ctx}.json not found)"); continue
    any_ok = True
    L.append(f"## context = {r['context_tokens']} tokens  "
             f"(gen={r['gen']}, method={r['decode_time_method']}, "
             f"samples/mode={r['per_mode'][r['baseline']]['n_samples']})")
    L += ["", "| mode | decode tps (mean +/- std) | quality (hit by depth) |",
          "|---|---:|---|"]
    for m in r["modes"]:
        pm = r["per_mode"][m]
        L.append(f"| {m} | {pm['tps_mean']:.2f} +/- {pm['tps_std']:.2f} | "
                 f"{pm['hit_rate_by_depth']} |")
    if bf16:
        L.append(f"| bf16 (ref) | {bf16['tps_mean']:.2f} +/- {bf16['tps_std']:.2f} | "
                 f"{bf16['hit_rate_by_depth']} |")
    for m, pv in r.get("paired_vs_baseline", {}).items():
        lo, hi = pv["delta_pct_mean"]-pv["delta_pct_std"], pv["delta_pct_mean"]+pv["delta_pct_std"]
        verdict = ("WIN (beyond spread)" if lo > 0 else
                   "LOSS (beyond spread)" if hi < 0 else "BREAKEVEN (within spread)")
        L += ["", f"**{m} vs {r['baseline']}: {pv['delta_pct_mean']:+.1f}% "
                  f"+/- {pv['delta_pct_std']:.1f}%** over {pv['n_cells']} (seed,depth) "
                  f"cells -> **{verdict}**  (per-cell: {pv['deltas_pct']})"]
    # gap #4: where do off/retention sit vs the bf16 bar, and vs the modeled target?
    tgt = (TARGET_X - 1.0) * 100.0
    base_tps = r["per_mode"][r["baseline"]]["tps_mean"]
    ret = r["per_mode"].get("retention", {}).get("tps_mean")
    if bf16 and bf16.get("tps_mean"):
        b = bf16["tps_mean"]
        line = f"- vs bf16 ({b:.2f} tps): off={base_tps / b:.2f}x bf16 (the int4 density tax)"
        if ret:
            line += f", retention={ret / b:.2f}x bf16 ({ret / b:.0%} of bf16)"
        L += ["", line]
    L += ["", f"- cost-model target: read-skip ~{TARGET_X:.1f}x off (paired Δ ≈ "
              f"+{tgt:.0f}%) at long context; this row's Δ vs that target = "
              f"{(r['paired_vs_baseline'].get('retention', {}).get('delta_pct_mean', 0)) - tgt:+.0f} pts"]
    sd = r.get("skip_diag") or {}
    if sd.get("steady_steps"):
        L += ["", f"- retention skipped **{sd['steady_skip_frac']:.0%}** in steady state "
                  f"(retained ~{sd['steady_retained_mean']:.0f} of "
                  f"~{sd['steady_seq_mean']:.0f}); steps observe={sd['observe_steps']} "
                  f"steady={sd['steady_steps']} (observe steps re-read all + re-score "
                  f"— time them with `--profile-ab`)"]
    L.append("")
L += ["## How to read it",
      "- Quality is the GATE: retention hit-rate must match off (needle survives the",
      "  skip). A throughput number on broken quality is a FAIL, not a win.",
      "- WIN/LOSS is declared only when the paired delta clears its own +/- spread.",
      "  Within spread = BREAKEVEN; do NOT report it as a win (the meta-lesson).",
      "- Step-0 hypothesis: the delta TREND should rise with context (fixed keep-set",
      "  is a smaller fraction at 16k/32k -> more skip). If it crosses to a clear WIN",
      "  at length with quality intact -> much of the Phase-10 goal is met before any",
      "  kernel change. If it stays BREAKEVEN even at 32k -> the kernel-emitted-scores",
      "  lever (Step 1) is the next move; persistent breakeven after that = the PCAM case."]
pathlib.Path("PHASE10_STEP0_AB_REPORT.md").write_text("\n".join(L)+"\n")
print("\n".join(L))
if not any_ok:
    sys.exit("no A/B JSONs found — did the runs fail?")
PY
log "done — PHASE10_STEP0_AB_REPORT.md"
