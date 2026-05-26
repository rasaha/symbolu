#!/usr/bin/env bash
# VC brief replication audit — Tier A GPU runs.
#
# Tier C wording fixes are already applied (commit pre-this).
# This script implements Tier A from VC_BRIEF_REPLICATION_AUDIT.md:
#
#   R1: fp8 needle on Qwen-7B — replaces the brief's inferred fp8
#       quality narrative with a direct measurement.
#
#   R3: 4-model needle 2-of-2 replication (Qwen-7B, Mistral-7B,
#       Llama-3.1-8B, Qwen-14B). Turns each model's single-run
#       claim into 2 independent measurements with different seeds.
#
#   R5: Cuda-blocks re-bench via the three-way comparison bench
#       (bf16 / fp8 / int4_protected on Qwen-7B at
#       gpu_memory_utilization=0.5). Pins the brief's
#       13,967 / 28,060 / 28,060 numbers to a reproducible run.
#
#   R7: 180s-style aggregate throughput @ B=8 (`bench_phase6_*`,
#       n_runs=5 -> median over 5 measurements is a 180s-class
#       confidence level) + per-seq latency from the same
#       PHASE5C three-way bench used for R5.
#
# Tier B is DEFERRED -- the KIVI 11-29% claim is now softened in
# the brief to "long-context collapse, measurement pending", so
# Tier B's R2 (KIVI 16K needle) is no longer load-bearing for
# partner-safety.
#
# Cost: ~$0.60 total, ~30 minutes wall.
#
# DO NOT RUN UNTIL YOU HAVE EXPLICIT APPROVAL. The Tier C edits
# to the brief are in tree; running this script then revising the
# brief with the measured numbers is the partner-safety follow-
# through.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"
cd "$REPO_ROOT"

OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/VC_BRIEF_TIER_A}"
mkdir -p "$OUT_ROOT"

QWEN_7B="${QWEN_7B:-Qwen/Qwen2.5-7B-Instruct}"
MISTRAL_7B="${MISTRAL_7B:-mistralai/Mistral-7B-Instruct-v0.3}"
LLAMA_8B="${LLAMA_8B:-NousResearch/Meta-Llama-3.1-8B-Instruct}"
QWEN_14B="${QWEN_14B:-Qwen/Qwen2.5-14B-Instruct}"

GPU_UTIL="${GPU_UTIL:-0.5}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"

# Protect-mask paths follow the auto-derive convention in
# verify_phase5b_5_needle.py: $PROTECT_MASK_PATH or
# /workspace/dev/build-logs/<model-slug>_protect_mask_4pct.pt
# The pod operator must have the masks at one of those locations.

# ----- R1: fp8 needle on Qwen-7B -----
echo
echo "[TIER A][R1] fp8 needle on Qwen-7B (5 codes x 3 length buckets)"
echo
R1_OUT="$OUT_ROOT/r1_fp8_needle_qwen7b"
mkdir -p "$R1_OUT"
python Bench/scripts/verify_phase5b_5_needle_fp8.py \
  --model "$QWEN_7B" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-model-len "$MAX_MODEL_LEN" \
  --num-needles 5 \
  --lengths 200,600,1200 \
  --seed 42 \
  --output-dir "$R1_OUT" \
  2>&1 | tee "$R1_OUT/run.log"

# ----- R3: 4-model needle 2-of-2 replication -----
# Same script per the int4_protected portfolio; two seeds per model
# so the runs aren't byte-identical replays. The needle script
# auto-derives the protect-mask path from the model slug; the pod
# must have masks at /workspace/dev/build-logs/.
echo
echo "[TIER A][R3] 4-model needle 2-of-2 replication"
echo

for model_pair in \
    "qwen2_5_7b_instruct:$QWEN_7B" \
    "mistral_7b_instruct_v0_3:$MISTRAL_7B" \
    "meta_llama_3_1_8b_instruct:$LLAMA_8B" \
    "qwen2_5_14b_instruct:$QWEN_14B"; do
  short="${model_pair%%:*}"
  full="${model_pair##*:}"
  for run_idx in 1 2; do
    seed_for_run=$((42 + run_idx))   # 43, 44 — different seeds for
                                     # independent draws of needle
                                     # codes + filler arrangement
    out="$OUT_ROOT/r3_needle_replication/${short}_run${run_idx}"
    mkdir -p "$out"
    echo "  [R3] ${short} run ${run_idx}/2 (seed=${seed_for_run})"
    python Bench/scripts/verify_phase5b_5_needle.py \
      --model "$full" \
      --gpu-memory-utilization "$GPU_UTIL" \
      --max-model-len "$MAX_MODEL_LEN" \
      --num-needles 5 \
      --lengths 200,600,1200 \
      --seed "$seed_for_run" \
      2>&1 | tee "$out/run.log"
  done
done

# ----- R5 + R7-latency: PHASE5C three-way bench on Qwen-7B -----
# bench_phase5c_v1.py runs bf16 + fp8 + int4_protected on the same
# prompt corpus. It reports cuda blocks (R5), max concurrency (R5),
# per-prompt decode tok/s (R7 latency component), and char-match
# vs bf16. Single invocation gives us both R5 and the per-seq
# latency component of R7.
echo
echo "[TIER A][R5 + R7-latency] PHASE5C three-way bench on Qwen-7B"
echo
R5_OUT="$OUT_ROOT/r5_r7lat_phase5c_three_way"
mkdir -p "$R5_OUT"
python Bench/scripts/bench_phase5c_v1.py \
  --model "$QWEN_7B" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-tokens 64 \
  2>&1 | tee "$R5_OUT/run.log"

# ----- R7-aggregate: bench_phase6 at B=8, n_runs=5 -----
# The brief's "42.5 tok/s @ B=8" is from bench_phase6_batched_*
# post B-pre-1 buffer fix. Replicate at n_runs=5 (vs the original
# single-run measurement) so the median is partner-credible.
echo
echo "[TIER A][R7-aggregate] bench_phase6 throughput @ B=8, n_runs=5"
echo
R7_AGG_OUT="$OUT_ROOT/r7_throughput_b8_int4_protected"
mkdir -p "$R7_AGG_OUT"
python Bench/scripts/bench_phase6_batched_throughput.py \
  --model "$QWEN_7B" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-model-len "$MAX_MODEL_LEN" \
  --batch-sizes 8 \
  --n-runs 5 \
  --max-tokens 32 \
  2>&1 | tee "$R7_AGG_OUT/run.log"

# ----- Report (auto-generated) -----
python <<'PY'
import json, os, pathlib, re

out_root = pathlib.Path(os.environ.get("OUT_ROOT", "./Bench/bench_out/VC_BRIEF_TIER_A"))

def read_json(p):
    return json.load(open(p)) if p.exists() else None

def grep_log(p, patterns):
    """Return {pattern_name: first match dict} from a run.log."""
    if not p.exists():
        return {}
    hits = {}
    text = p.read_text()
    for name, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            hits[name] = m.group(0).strip()
    return hits

lines = ["# VC brief Tier A replication report", ""]

# --- R1 ---
lines += ["## R1 — fp8 needle on Qwen-7B (direct measurement)", ""]
r1 = read_json(out_root / "r1_fp8_needle_qwen7b" / "summary.json")
if r1:
    lines.append(f"- Hit rate: **{r1['hits']}/{r1['total_trials']}** ({100*r1['hit_rate']:.1f}%)")
    for b, info in sorted(r1["per_bucket"].items(), key=lambda kv: int(kv[0])):
        lines.append(f"- {b}-filler-tokens bucket: {info['hits']}/{info['total']}")
else:
    lines.append("- (summary.json missing -- check run.log)")
lines.append("")
lines.append("This number replaces the brief's previous inferred-from-prefix-match")
lines.append("framing for fp8 needle. Whatever the number is, it goes into the brief.")
lines.append("")

# --- R3 ---
lines += ["## R3 — 4-model needle 2-of-2 replication", ""]
lines += [
    "| Model | Run 1 | Run 2 | Replicated? |",
    "|---|:-:|:-:|:-:|",
]
needle_re = re.compile(r"int4_rate\s*=\s*([0-9.]+)|retrieval rate.*?:\s*([0-9.]+)|(\d+)/(\d+)\s+retrievals?\s")
for short in ["qwen2_5_7b_instruct", "mistral_7b_instruct_v0_3",
              "meta_llama_3_1_8b_instruct", "qwen2_5_14b_instruct"]:
    runs = []
    for r in (1, 2):
        log = out_root / "r3_needle_replication" / f"{short}_run{r}" / "run.log"
        if not log.exists():
            runs.append("?"); continue
        # The needle verify script prints "int4_rate=X.XX (n/15)" or similar.
        text = log.read_text()
        m = re.search(r"int4_rate.*?(\d+)/(\d+)", text) or re.search(r"int4.*?(\d+)/(\d+)\s+hits", text) or re.search(r"int4.*?passed (\d+)/(\d+)", text)
        runs.append(f"{m.group(1)}/{m.group(2)}" if m else "?")
    repl = "yes" if all(r == "15/15" for r in runs) else \
           ("partial" if any(r == "15/15" for r in runs) else "no")
    lines.append(f"| {short} | {runs[0]} | {runs[1]} | {repl} |")
lines.append("")

# --- R5 + R7-latency ---
lines += [
    "## R5 + R7-latency — PHASE5C three-way bench (Qwen-7B)",
    "",
    "Numbers below come from `bench_phase5c_v1.py` stdout.",
    "Compare against the brief's Page 3 table:",
    "",
    "  bf16: 13,967 cuda blocks, 109x concurrency, 1.0x latency (baseline)",
    "  fp8 : 28,060 cuda blocks, 219x concurrency, ~1.0x latency",
    "  int4: 28,060 cuda blocks, 218x concurrency, ~3.7x latency",
    "",
]
r5_log = out_root / "r5_r7lat_phase5c_three_way" / "run.log"
if r5_log.exists():
    text = r5_log.read_text()
    # Three-way table appears near the end; pull the relevant lines.
    lines.append("```")
    for ln in text.splitlines():
        if any(tok in ln for tok in ("cuda blocks", "Maximum concurrency",
                                     "tok/s", "char-match", "bf16", "fp8",
                                     "int4_proto", "char_match")):
            lines.append(ln.rstrip())
    lines.append("```")
else:
    lines.append("(run.log missing)")
lines.append("")

# --- R7-aggregate ---
lines += ["## R7 — Aggregate throughput @ B=8, n_runs=5", ""]
lines.append("Compare against the brief's '42.5 tok/s @ B=8'.")
lines.append("")
r7_log = out_root / "r7_throughput_b8_int4_protected" / "run.log"
if r7_log.exists():
    text = r7_log.read_text()
    lines.append("```")
    for ln in text.splitlines():
        if any(tok in ln.lower() for tok in ("tok/s", "median", "b=8", "run ", "agg")):
            lines.append(ln.rstrip())
    lines.append("```")
else:
    lines.append("(run.log missing)")
lines.append("")

# --- Disposition ---
lines += [
    "## Disposition for brief revision (after this report is reviewed)",
    "",
    "After Tier A lands, the following brief claims become",
    "replicated-at-audit-standard:",
    "",
    "- fp8 quality narrative (R1) — measured directly",
    "- Each 4-model needle 15/15 claim (R3) — 2 independent runs",
    "- Cuda blocks 13,967 / 28,060 / 28,060 (R5) — re-bench",
    "- 42.5 tok/s @ B=8 and 3.7x latency (R7) — n_runs=5 median",
    "",
    "If any cell does NOT replicate (e.g., one model drops to 14/15",
    "on the second run, or fp8 needle is materially != 0/15), the",
    "brief should be revised to the measured value, not the prior",
    "claim. Either direction is partner-safe; what's not partner-",
    "safe is mismatched claim vs measurement.",
]

(out_root / "TIER_A_REPORT.md").write_text("\n".join(lines) + "\n")
print(open(out_root / "TIER_A_REPORT.md").read())
PY

echo
echo "[TIER A] Done. Report at $OUT_ROOT/TIER_A_REPORT.md"
echo "         Brief revision pending review of the report."
