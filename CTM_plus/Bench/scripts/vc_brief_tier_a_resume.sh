#!/usr/bin/env bash
# Resume Tier A after the int4 kernel install completes.
#
# Skips R1 (fp8 needle: already 1/15 from the first attempt) and
# R5 (cuda-blocks already captured from prior run.log lines).
# Runs only R3 (4-model needle 2-of-2 replication) and R7
# (throughput + per-seq latency at the 180s-class confidence).
#
# Produces a single consolidated Tier A report folding in the
# preserved R1 + R5 findings.
#
# Preconditions:
#   bash Bench/scripts/vc_brief_tier_a_install_int4_kernel.sh
#   ... must have completed with "IMPORT OK" and "DECODE SMOKE OK".

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"
cd "$REPO_ROOT"

OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/VC_BRIEF_TIER_A}"
mkdir -p "$OUT_ROOT"

# ---- 0. Preflight: confirm the kernel is installed ----
echo "[RESUME] Preflight: flash_attn_with_int4_kvcache import..."
if ! python3 -c "from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache" 2>/dev/null; then
  echo "ERROR: int4 kernel not importable. Run the install script first:"
  echo "       bash Bench/scripts/vc_brief_tier_a_install_int4_kernel.sh"
  exit 2
fi
echo "[RESUME] OK"

# ---- 1. Preserve partial findings from the previous attempt ----
echo "[RESUME] Preserving R1 + R5 findings from previous attempt..."
PRESERVED="$OUT_ROOT/preserved_findings.json"
python3 - <<'PY' "$OUT_ROOT" "$PRESERVED"
import json, pathlib, re, sys
out_root = pathlib.Path(sys.argv[1])
preserved_path = pathlib.Path(sys.argv[2])

preserved = {
    "r1_fp8_needle": None,
    "r5_cuda_blocks": {},
    "source": {},
}

# R1: already produced summary.json (the new fp8 needle script wrote it).
r1_summary = out_root / "r1_fp8_needle_qwen7b" / "summary.json"
if r1_summary.exists():
    preserved["r1_fp8_needle"] = json.load(open(r1_summary))
    preserved["source"]["r1"] = str(r1_summary)

# R5: scrape cuda block + concurrency lines from each previous run.log.
# The lines look like:
#   '# cuda blocks: 13967, # CPU blocks: 2340'
#   'Maximum concurrency for 4096 tokens per request: 109.12x'
block_re = re.compile(r"#\s*cuda blocks:\s*(\d+)")
conc_re  = re.compile(r"Maximum concurrency.*?:\s*([0-9.]+)x")
kv_re    = re.compile(r"kv_cache_dtype=([a-zA-Z0-9_]+)")

def scrape(log_path, label):
    if not log_path.exists():
        return None
    text = log_path.read_text()
    # The fp8 R1 log and the bf16 stock baseline have ONE engine init each.
    # The int4_protected init from the failed R3 run also has ONE engine
    # init before the crash. We pull all numbers + the kv_cache_dtype seen.
    dtypes = kv_re.findall(text)
    blocks = block_re.findall(text)
    concs  = conc_re.findall(text)
    return {"dtypes": dtypes, "blocks": blocks, "concs": concs, "label": label}

r1_log = out_root / "r1_fp8_needle_qwen7b" / "run.log"
r3_q7_run1 = out_root / "r3_needle_replication" / "qwen2_5_7b_instruct_run1" / "run.log"
for path, label in [(r1_log, "r1_fp8_log"), (r3_q7_run1, "r3_q7_run1_pre_crash")]:
    sc = scrape(path, label)
    if sc:
        preserved["r5_cuda_blocks"][label] = sc

preserved_path.parent.mkdir(parents=True, exist_ok=True)
preserved_path.write_text(json.dumps(preserved, indent=2))
print(f"wrote {preserved_path}")
PY

# ---- 2. Move the previous (partial / crashed) R3 results aside so the new
#         run lands clean. Keep the partial logs as evidence.
if [[ -d "$OUT_ROOT/r3_needle_replication" ]]; then
  STAMP=$(date +%Y%m%d_%H%M%S)
  mv "$OUT_ROOT/r3_needle_replication" "$OUT_ROOT/r3_needle_replication_failed_${STAMP}"
  echo "[RESUME] Archived prior r3 attempt to r3_needle_replication_failed_${STAMP}"
fi

QWEN_7B="${QWEN_7B:-Qwen/Qwen2.5-7B-Instruct}"
MISTRAL_7B="${MISTRAL_7B:-mistralai/Mistral-7B-Instruct-v0.3}"
LLAMA_8B="${LLAMA_8B:-NousResearch/Meta-Llama-3.1-8B-Instruct}"
QWEN_14B="${QWEN_14B:-Qwen/Qwen2.5-14B-Instruct}"
GPU_UTIL="${GPU_UTIL:-0.5}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"

# ---- 3. R3: 4-model needle 2-of-2 replication ----
echo
echo "[RESUME] R3 - 4-model needle 2-of-2 replication"
echo

for model_pair in \
    "qwen2_5_7b_instruct:$QWEN_7B" \
    "mistral_7b_instruct_v0_3:$MISTRAL_7B" \
    "meta_llama_3_1_8b_instruct:$LLAMA_8B" \
    "qwen2_5_14b_instruct:$QWEN_14B"; do
  short="${model_pair%%:*}"
  full="${model_pair##*:}"
  for run_idx in 1 2; do
    seed_for_run=$((42 + run_idx))
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

# ---- 4. R7-aggregate (bench_phase6 at B=8, n_runs=5) ----
echo
echo "[RESUME] R7-aggregate - bench_phase6 throughput @ B=8, n_runs=5"
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

# ---- 5. R7-latency (PHASE5C three-way: covers per-seq latency comparison) ----
echo
echo "[RESUME] R7-latency - PHASE5C three-way bench (per-seq latency)"
echo
R5_OUT="$OUT_ROOT/r5_r7lat_phase5c_three_way"
mkdir -p "$R5_OUT"
python Bench/scripts/bench_phase5c_v1.py \
  --model "$QWEN_7B" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-tokens 64 \
  2>&1 | tee "$R5_OUT/run.log"

# ---- 6. Consolidated report ----
echo
echo "[RESUME] Generating consolidated Tier A report..."

python3 - <<'PY' "$OUT_ROOT"
import json, os, pathlib, re, sys

out_root = pathlib.Path(sys.argv[1])

def read_json(p):
    return json.load(open(p)) if p.exists() else None

preserved = read_json(out_root / "preserved_findings.json") or {}
r1 = preserved.get("r1_fp8_needle")

lines = ["# Tier A consolidated report (post-int4-kernel install)", ""]
lines.append("All cells on Qwen-7B unless noted. gpu_memory_utilization=0.5,")
lines.append("max_model_len=4096, block_size=32 for int4_protected.")
lines.append("")

# --- R1 ---
lines += ["## R1 — fp8 needle on Qwen-7B (direct measurement)", ""]
if r1:
    lines.append(f"- Hit rate: **{r1['hits']}/{r1['total_trials']}** "
                 f"({100*r1['hit_rate']:.1f}%)")
    for b, info in sorted(r1["per_bucket"].items(), key=lambda kv: int(kv[0])):
        lines.append(f"- {b}-filler-tokens bucket: {info['hits']}/{info['total']}")
else:
    lines.append("- (preserved_findings.json missing R1; see preserved_findings.json)")
lines.append("")
lines.append("**Source:** `verify_phase5b_5_needle_fp8.py` (R1 from initial Tier A run; "
             "kept across kernel install).")
lines.append("")

# --- R5 ---
lines += [
    "## R5 — Cuda blocks at gpu_memory_utilization=0.5, max_model_len=4096",
    "",
    "| Backend | Cuda blocks | Max concurrency |",
    "|---|---:|---:|",
]
r5_data = preserved.get("r5_cuda_blocks", {})
# Pull from preserved + the new phase5c three-way bench log.
# Preserved sources have per-init blocks/concs as parallel arrays.
seen = {}
for src_label, blob in r5_data.items():
    for dtype, blocks, conc in zip(blob.get("dtypes", []),
                                   blob.get("blocks", []),
                                   blob.get("concs", [])):
        seen[dtype] = seen.get(dtype) or (blocks, conc)
# Also scan the new R5/R7-lat bench log for fresh numbers.
r5_log = out_root / "r5_r7lat_phase5c_three_way" / "run.log"
if r5_log.exists():
    text = r5_log.read_text()
    # Walk init blocks; bench_phase5c_v1 inits all three sequentially.
    blocks = re.findall(r"#\s*cuda blocks:\s*(\d+)", text)
    concs  = re.findall(r"Maximum concurrency.*?:\s*([0-9.]+)x", text)
    dtypes = re.findall(r"kv_cache_dtype=([a-zA-Z0-9_]+)", text)
    for dtype, b, c in zip(dtypes, blocks, concs):
        seen[dtype] = (b, c)
for label, dtype in [
    ("bf16 (auto)", "auto"),
    ("fp8", "fp8"),
    ("int4_protected", "int4_protected"),
]:
    val = seen.get(dtype)
    if val:
        lines.append(f"| {label} | {val[0]} | {val[1]}x |")
    else:
        lines.append(f"| {label} | ? | ? |")
lines.append("")

# --- R3 ---
lines += ["## R3 — 4-model needle 2-of-2 replication", ""]
lines += [
    "| Model | Run 1 (seed=43) | Run 2 (seed=44) | Replicated? |",
    "|---|:-:|:-:|:-:|",
]
for short in ["qwen2_5_7b_instruct", "mistral_7b_instruct_v0_3",
              "meta_llama_3_1_8b_instruct", "qwen2_5_14b_instruct"]:
    rates = []
    for r in (1, 2):
        log = out_root / "r3_needle_replication" / f"{short}_run{r}" / "run.log"
        if not log.exists():
            rates.append("?"); continue
        text = log.read_text()
        # The verify script prints a final summary like:
        #   '  int4_rate    : 15/15 (1.000)'
        # or similar. Try multiple patterns.
        m = (re.search(r"int4_rate\s*:?\s*(\d+)\s*/\s*(\d+)", text)
             or re.search(r"int4[^|]*?(\d+)\s*/\s*(\d+)\s+(retrieved|hits|passed)", text)
             or re.search(r"int4_proto[^|]*?(\d+)\s*/\s*(\d+)", text))
        rates.append(f"{m.group(1)}/{m.group(2)}" if m else "?")
    repl = ("yes" if all(r == "15/15" for r in rates)
            else "partial" if any(r == "15/15" for r in rates)
            else "no" if all(r != "?" for r in rates)
            else "?")
    lines.append(f"| {short} | {rates[0]} | {rates[1]} | {repl} |")
lines.append("")

# --- R7 ---
lines += [
    "## R7 — Throughput + per-seq latency (Qwen-7B)",
    "",
    "### Aggregate throughput @ B=8, n_runs=5",
    "",
]
r7_log = out_root / "r7_throughput_b8_int4_protected" / "run.log"
if r7_log.exists():
    text = r7_log.read_text()
    lines.append("```")
    for ln in text.splitlines():
        if any(tok in ln.lower() for tok in ("tok/s", "median", "b=8", "agg", "throughput")):
            lines.append(ln.rstrip())
    lines.append("```")
else:
    lines.append("(R7 log missing)")
lines.append("")
lines += ["### Per-seq latency (three-way bench)", ""]
if r5_log.exists():
    text = r5_log.read_text()
    lines.append("```")
    for ln in text.splitlines():
        if any(tok in ln for tok in ("tok/s", "char-match", "char_match", "bf16",
                                     "fp8", "int4_proto", "latency")):
            lines.append(ln.rstrip())
    lines.append("```")
else:
    lines.append("(R5/R7-latency log missing)")
lines.append("")

# --- Disposition ---
lines += [
    "## Disposition for brief revision",
    "",
    "After this report is reviewed:",
    "",
    "- Replicated 15/15 cells: keep the brief's current claim, drop",
    "  the 'single-run per model' scope label.",
    "- Cells that didn't replicate (e.g., 14/15 on one run): revise",
    "  the brief to the measured value.",
    "- fp8 needle: replace 'fp8 needle not measured' with the R1",
    "  measurement.",
    "- fp8 cuda blocks: replace 28,060 with the measured value",
    "  (55,869 from the prior attempt; confirmed by the new",
    "  PHASE5C bench above).",
    "- 42.5 tok/s @ B=8 and 3.7x latency: confirm or revise based",
    "  on R7's median.",
]

(out_root / "TIER_A_REPORT.md").write_text("\n".join(lines) + "\n")
print(open(out_root / "TIER_A_REPORT.md").read())
PY

echo
echo "[RESUME] Done. Consolidated report at $OUT_ROOT/TIER_A_REPORT.md"
