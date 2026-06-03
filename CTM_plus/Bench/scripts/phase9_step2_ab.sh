#!/usr/bin/env bash
# =============================================================================
# phase9_step2_ab.sh — Phase 9 Step 2 A/B: route-A int4 + the attention bridge,
# PROPERLY configured (the Step-1 smoke's cells were void: GPU_UTIL=0.26 starved
# the KV cache -> 0 completions). Measures what the EXISTING path can measure.
# =============================================================================
#
# DO NOT RUN ON A CPU CONTAINER. This is the GPU-pod deliverable. ~$0.50-1.00.
#
# ⚠ SCOPE (read PHASE9_STEP2_AB_RUNBOOK.md + PHASE9_READSKIP_NOT_IMPLEMENTED.md):
#   This harness measures (i) the int4 decode-tax curve under a CORRECT config,
#   and (ii) THE DECISIVE PART — the per-step dispatch overhead of the attention
#   bridge, via a Cython-vs-Python evictor A/B (the Phase-8 -20% question = the
#   PCAM gate). It does NOT measure the Step-0 intra-sequence read-skip prize:
#   that mechanism is NOT implemented (the evictor is cross-request prefix-pool
#   management, not per-sequence sparsity), so it would be a kernel BUILD. Build
#   that kernel only if this harness says it's worth it (see runbook gate logic).
#
# Cells (same workload, same budget, prefix-caching MATCHED across all):
#   C0  bf16            — ceiling (no int4, no CTM+)
#   A   int4-routeA     — all-int4 dense baseline (LRU; reads everything)
#   B   int4+bridge-CY  — + CTM+ attention bridge, CYTHON evictor + fast-hooks
#   Bpy int4+bridge-PY  — same as B but PYTHON evictor  ➜  B vs Bpy = dispatch tax
#
# The decisive number: (B tps - Bpy tps). If Cython materially beats Python,
# the bridge IS CPU-dispatch-bound in pure Python -> the empirical PCAM case
# (Step 3). If B ~= Bpy, dispatch is NOT the bottleneck on this path.
#
# Config fixes vs the smoke (the reasons its cells were void):
#   * GPU_UTIL 0.60 (was 0.26) so KV cache fits several 32k seqs -> completions.
#   * --max-model-len pinned so the engine sizes the cache deterministically.
#   * --preemption-mode recompute (was swap) so eviction is actually EXERCISED
#     (swap only thrashed blocks to CPU; it never evicted).
#   * --enable-prefix-caching on ALL cells (CTM+ forces it on; the smoke's 5a/5c
#     had it OFF while 5b had it ON -> an invalid comparison).
#
# Output: $OUT_ROOT/{c0_bf16,a_int4,b_bridge_cy,bpy_bridge_py}/streaming_summary.json
#         + optional quality/{needle,mmlu}.json  + PHASE9_STEP2_REPORT.md
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$PWD}"           # run from CTM_plus so ./Bench resolves
cd "$REPO_ROOT"
OUT_ROOT="${OUT_ROOT:-./Bench/bench_out/PHASE9_STEP2}"
mkdir -p "$OUT_ROOT"

VLLM_VERSION_PIN="${VLLM_VERSION_PIN:-0.7.3}"
BENCH_MODEL="${BENCH_MODEL:-Qwen/Qwen2.5-7B-Instruct}"

# --- config (tunable; defaults chosen so cells COMPLETE and eviction fires) ---
GPU_UTIL="${GPU_UTIL:-0.60}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
SWAP_GB="${SWAP_GB:-16}"
PREEMPTION="${PREEMPTION:-recompute}"
WORKLOAD="${WORKLOAD:-chat_32k}"
PROMPT_LENGTH_CHOICES="${PROMPT_LENGTH_CHOICES:-8000,16000,24000,30000}"
MAX_DECODE_TOKENS="${MAX_DECODE_TOKENS:-512}"
MAX_WALL_SECONDS="${MAX_WALL_SECONDS:-90}"
MAX_REQUESTS="${MAX_REQUESTS:-40}"
ARRIVAL_RATE="${ARRIVAL_RATE:-6.0}"
ARRIVAL_ALPHA="${ARRIVAL_ALPHA:-1.5}"
KV_K_GROUP="${KV_K_GROUP:-32}"; KV_V_GROUP="${KV_V_GROUP:-32}"
KV_BITS="${KV_BITS:-4}"; KV_SINK="${KV_SINK:-4}"
RUN_QUALITY="${RUN_QUALITY:-0}"          # 1 = also run needle + MMLU (extra ~$0.10)
PROTECT_MASK="${PROTECT_MASK:-/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt}"

log() { printf '\n[STEP2] %s\n' "$*"; }

python -c "
import vllm, sys
if vllm.__version__ != '$VLLM_VERSION_PIN':
    print(f'vllm {vllm.__version__} != pinned $VLLM_VERSION_PIN', file=sys.stderr); sys.exit(2)
"

# Common run_streaming args shared by every cell (prefix-caching MATCHED ON,
# preemption recompute, fixed budget) — the apples-to-apples spine.
common_args=(
  --model "$BENCH_MODEL"
  --workload "$WORKLOAD"
  --gpu-memory-utilization "$GPU_UTIL"
  --max-model-len "$MAX_MODEL_LEN"
  --swap-space-gb "$SWAP_GB"
  --preemption-mode "$PREEMPTION"
  --enable-prefix-caching
  --arrival-rate "$ARRIVAL_RATE" --arrival-alpha "$ARRIVAL_ALPHA"
  --max-requests "$MAX_REQUESTS" --max-wall-seconds "$MAX_WALL_SECONDS"
  --max-decode-tokens "$MAX_DECODE_TOKENS"
  --prompt-length-choices "$PROMPT_LENGTH_CHOICES"
)
int4_args=(
  --int4-kv-route-a
  --int4-kv-k-group-size "$KV_K_GROUP" --int4-kv-v-group-size "$KV_V_GROUP"
  --int4-kv-bits "$KV_BITS" --int4-kv-sink-size "$KV_SINK"
)

run_cell() {  # $1=name  $2..=extra args
  local name="$1"; shift
  local out="$OUT_ROOT/$name"; mkdir -p "$out"
  log "cell $name"
  python -m ctm_bench.scripts.run_streaming "${common_args[@]}" "$@" --output-dir "$out"
}

# C0 — bf16 ceiling (no int4, no CTM+; LRU under prefix caching)
run_cell c0_bf16

# A — all-int4 dense (route-A int4, LRU)
run_cell a_int4 "${int4_args[@]}"

# B — int4 + attention bridge, CYTHON evictor + fast hooks (the escape-the-tax stack)
run_cell b_bridge_cy "${int4_args[@]}" \
  --ctm-plus --phase3-attention --phase4-cython-evictor --phase4-fast-hooks

# Bpy — same as B but PYTHON evictor (the dispatch-attribution control)
run_cell bpy_bridge_py "${int4_args[@]}" \
  --ctm-plus --phase3-attention

# --- optional quality block (int4 round-trip + bridge correctness regression) -
# NOTE: the evictor is cross-request (does not touch a single sequence's KV), so
# the single-sequence needle is NOT an eviction-keep-set stress test — it is an
# int4+bridge CORRECTNESS regression vs the locked numbers. See runbook.
if [[ "$RUN_QUALITY" == "1" ]]; then
  log "quality — needle (mml=8192) + MMLU 200q (bf16 vs protected)"
  mkdir -p "$OUT_ROOT/quality"
  CELL=protected ENFORCE_EAGER=1 PHASE6E_FUSED_WRITER=1 \
    OUTPUT="$OUT_ROOT/quality/needle.json" \
    python Bench/scripts/phase6k12_hard_needle.py --worker --mml 8192 --items 4 \
    2>&1 | grep -E "strict=|COLLAPSE" || echo "WARN: needle produced no summary"
  python Bench/scripts/bench_phase6n_mmlu_quality.py \
    --cells bf16,protected --num-questions 200 \
    --gpu-util "$GPU_UTIL" --max-model-len "$MAX_MODEL_LEN" \
    --out "$OUT_ROOT/quality/mmlu.json" || echo "WARN: MMLU cell failed"
fi

# --- report ------------------------------------------------------------------
log "PHASE9_STEP2_REPORT.md"
python - "$OUT_ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
def load(n):
    p = root / n / "streaming_summary.json"
    return json.load(open(p)) if p.exists() else None
def tps(r):
    if not r: return None
    return r.get("throughput_tokens_per_second") or r.get("decode_tokens_per_second")
def done(r):
    return None if not r else r.get("completed")
cells = {k: load(k) for k in ("c0_bf16","a_int4","b_bridge_cy","bpy_bridge_py")}
L = ["# Phase 9 Step 2 — A/B report", ""]
L.append("| cell | tps | completed | note |")
L.append("|---|---:|---:|---|")
labels = {"c0_bf16":"bf16 ceiling","a_int4":"int4 dense (LRU)",
          "b_bridge_cy":"int4+bridge CYTHON","bpy_bridge_py":"int4+bridge PYTHON"}
for k,r in cells.items():
    L.append(f"| {labels[k]} | {tps(r)} | {done(r)} | {'OK' if done(r) else 'CHECK config (completed=0?)'} |")
b, bpy = tps(cells["b_bridge_cy"]), tps(cells["bpy_bridge_py"])
L += ["", "## Dispatch-tax attribution (the PCAM gate)"]
if b and bpy:
    d = (b - bpy)/bpy*100
    L.append(f"- Cython {b:.1f} vs Python {bpy:.1f} tps  ->  **{d:+.1f}%**")
    L.append("- If Cython >> Python (e.g. >=+10%), the bridge is CPU-DISPATCH-BOUND "
             "in pure Python -> the empirical PCAM case (Step 3).")
    L.append("- If ~equal, dispatch is NOT the bottleneck on this path.")
else:
    L.append("- one of B/Bpy did not complete -> fix config (raise GPU_UTIL / cut "
             "concurrency) and re-run; no attribution possible until both complete.")
L += ["", "⚠ This measures the int4 curve + the bridge DISPATCH overhead, NOT the",
      "Step-0 intra-sequence read-skip prize (unimplemented). See the runbook."]
out = root.parent.parent / "PHASE9_STEP2_REPORT.md" if (root.parent.parent).exists() else pathlib.Path("PHASE9_STEP2_REPORT.md")
pathlib.Path("PHASE9_STEP2_REPORT.md").write_text("\n".join(L)+"\n")
print("\n".join(L))
PY
log "done — inspect PHASE9_STEP2_REPORT.md + $OUT_ROOT/*/streaming_summary.json"
