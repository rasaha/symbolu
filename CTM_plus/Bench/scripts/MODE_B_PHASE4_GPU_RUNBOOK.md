# Phase 4 GPU Runbook

**Status:** all GPU-side code lands as of commit `<this commit>`.
This runbook documents the concrete procedure to (a) run
calibration once per model, (b) execute the four-cell
experiment that decides between Phase 3 (real attention
forwarding) and Phase 4 (TriAttention-style trig scoring) as
CTM+'s production scoring policy.

**Audience:** the engineer running this on a fresh RunPod pod.
**Prerequisites:** RunPod prep sequence from the Phase 3 runbook
(see commit message for `b5e7f14` or grep for "RunPod console —
do this BEFORE SSH" in the conversation history). Same vLLM 0.7+
+ Qwen2.5-7B-Instruct + 75 GB volume.

## §1 Estimated cost

| Step | Wall time | GPU spot |
|---|---:|---:|
| Calibration (one-time, per model) | ~10–15 min | ~$0.30 |
| LRU baseline cell | ~2 min | $0.05 |
| Phase 2 cell (LRU+freq, no attn, no trig) | ~2 min | $0.05 |
| Phase 4 cell (trig scoring) | ~3 min | $0.06 |
| Phase 3 cell (real attention; optional) | ~3 min | $0.06 |
| Aggregation + post-run analysis | ~5 min | $0.10 |
| **Total** | **~25–30 min** | **~$0.60–1.00** |

## §2 Calibration — one-time per model

Phase 4 needs per-(layer, head, frequency-band) Q-centre
statistics. The paper showed calibration is data-quality
robust (Google HTML works as well as ShareGPT chat) so a
single fixed corpus is fine. We use a slice of LMSYS-Chat-1M
or whatever's most convenient.

```bash
cd /workspace/symbolu/CTM_plus/Bench
source /workspace/symbolu/.venv-phase3/bin/activate

mkdir -p /workspace/.calibration

# Quick calibration script. Adapt to your favourite corpus.
python3 - <<'PY'
import torch
from vllm import LLM
from kv_policy.triattention import calibrate_q_centers

model_path = "/workspace/.hf_cache_phase3/qwen2.5-7b"
model_name = "Qwen2.5-7B-Instruct"

# Construct vLLM with prefix caching ON so the model is
# instantiated the same way as a Phase 4 run. This isn't
# strictly required for calibration (we just need a model),
# but using the same engine config avoids any "calibration
# happened on a different model" worry.
llm = LLM(
    model=model_path,
    gpu_memory_utilization=0.30,
    swap_space=4,
    enforce_eager=True,
    max_model_len=8192,
    enable_prefix_caching=True,
    seed=42,
)

# Walk down to the actual torch model.
inner = llm.llm_engine
for path in (
    ("model_executor", "driver_worker", "worker", "model_runner", "model"),
    ("model_executor", "model_runner", "model"),
    ("model_runner", "model"),
):
    cur = inner
    for attr in path:
        cur = getattr(cur, attr, None)
        if cur is None:
            break
    if cur is not None:
        torch_model = cur
        break

# Drive the model on calibration tokens. We use random token
# IDs from the model's vocab — robust per the paper's Table F.
import random
def driver(model):
    for _ in range(20):
        # 256 tokens × 20 batches = 5120 tokens per "session"
        token_ids = torch.tensor(
            [[random.randint(0, 32000) for _ in range(256)]],
            device="cuda", dtype=torch.long,
        )
        with torch.no_grad():
            try:
                model(input_ids=token_ids)
            except Exception:
                # vLLM models may not have a simple forward; try
                # via the engine instead. For robustness across
                # vLLM internal layouts, we drive the engine
                # with a generate call below.
                pass

# Fallback driver: use vLLM's generate to drive forward passes
# while the calibration hooks fire.
from vllm import SamplingParams
def driver_via_generate(model_unused):
    sp = SamplingParams(temperature=0.0, max_tokens=64, seed=42)
    llm.generate(
        ["The quick brown fox " * 32 for _ in range(8)], sp,
    )

# Determine model architecture parameters from the config.
config = torch_model.config
num_heads = config.num_attention_heads
num_kv_heads = getattr(
    config, "num_key_value_heads", num_heads,
)
head_dim = config.hidden_size // num_heads

stats = calibrate_q_centers(
    model=torch_model,
    forward_callable=driver_via_generate,
    model_name=model_name,
    num_heads=num_heads,
    head_dim=head_dim,
    num_kv_heads=num_kv_heads,
    rope_theta=getattr(config, "rope_theta", 10000.0),
    corpus_label="random_tokens_smoke",
    max_tokens=50_000,
)
out = "/workspace/.calibration/qwen2.5-7b.qcenters.json"
stats.save(out)
print(f"Calibration saved: {out}")
print(f"  layers: {stats.num_layers}")
print(f"  heads:  {stats.num_heads}")
print(f"  kv:     {stats.num_kv_heads}")
print(f"  bands:  {stats.num_bands}")
print(f"  tokens: {stats.calibration_token_count}")
PY
```

**Watch for in the calibration log:**

* `calibrate_q_centers: found N rotary_emb modules` — N should
  equal the model's transformer-layer count (28 for Qwen 7B).
  If 0: model class names don't match the
  `Rotary` / `RoPE` heuristic. Diagnose with the
  `_walk_rotary_emb_modules` debug print pattern in the design
  doc §4.
* No repeated `layer N Q reshape failed` warnings. If any: the
  rotary_emb forward signature differs from
  `(positions, q, k)` — adjust the pre-hook arg unpacking.
* Final stats dump shows `R > 0.5` for the majority of
  (layer, head, band) triples — implies Q/K concentration
  generalises to your model + calibration corpus. Per the
  paper, Qwen3-8B has 84.7% of heads with R > 0.95.

## §3 Four-cell experiment

Run all four cells with the same `seed=42`, same workload
(`chat_32k`), same hyperparameter regime that Phase 1 v4 proved
engages swap. Only the policy flag changes per cell. Total
~$0.30 of GPU spot.

```bash
COMMON_FLAGS=(
    --model /workspace/.hf_cache_phase3/qwen2.5-7b
    --workload chat_32k --seed 42
    --gpu-memory-utilization 0.26 --swap-space-gb 16
    --arrival-rate 6.0 --arrival-alpha 1.5
    --max-requests 30 --max-wall-seconds 120
    --max-decode-tokens 2048
    --prompt-length-choices "8000,16000,24000,30000"
)

# Cell 1: LRU baseline + prefix caching (apples-to-apples
# vLLM-native eviction; the comparator for Phase 4).
python3 -m ctm_bench.scripts.run_streaming \
    "${COMMON_FLAGS[@]}" \
    --enable-prefix-caching \
    --output-dir bench_out/4cell_lru_baseline \
    2>&1 | tee 4cell_lru.log

# Cell 2: CTM+ Phase 2 (recency + frequency only; no trig,
# no real attention). The audit-fix-acknowledged baseline.
python3 -m ctm_bench.scripts.run_streaming \
    "${COMMON_FLAGS[@]}" \
    --ctm-plus \
    --output-dir bench_out/4cell_phase2 \
    2>&1 | tee 4cell_phase2.log

# Cell 3: CTM+ Phase 4 (trig scoring + window pruning).
# THE NEW HEADLINE.
python3 -m ctm_bench.scripts.run_streaming \
    "${COMMON_FLAGS[@]}" \
    --ctm-plus \
    --phase4-trig-calibration /workspace/.calibration/qwen2.5-7b.qcenters.json \
    --phase4-window-interval 128 \
    --phase4-future-offsets "1,2,4,8,16" \
    --output-dir bench_out/4cell_phase4 \
    2>&1 | tee 4cell_phase4.log

# Cell 4 (optional): CTM+ Phase 3 (real attention forwarding).
# Decides whether the trig signal substitutes for real attention
# OR whether real attention is irreplaceable.
python3 -m ctm_bench.scripts.run_streaming \
    "${COMMON_FLAGS[@]}" \
    --ctm-plus \
    --phase3-attention \
    --output-dir bench_out/4cell_phase3_optional \
    2>&1 | tee 4cell_phase3_optional.log
```

## §4 Reading the results

After all four cells finish:

```bash
python3 - <<'PY'
import json
from pathlib import Path

def load(p):
    return json.loads(Path(p).read_text())

cells = {
    "LRU+prefix":  "bench_out/4cell_lru_baseline/streaming_summary.json",
    "Phase 2":     "bench_out/4cell_phase2/streaming_summary.json",
    "Phase 4":     "bench_out/4cell_phase4/streaming_summary.json",
    "Phase 3 opt": "bench_out/4cell_phase3_optional/streaming_summary.json",
}

print(f"{'Cell':<14s} {'tok/sec':>10s} {'swap_out':>10s} "
      f"{'evict_p99(μs)':>14s} {'attn_capt(s)':>13s}")
print("-" * 72)
for label, path in cells.items():
    if not Path(path).exists():
        print(f"{label:<14s}  (cell not run)")
        continue
    r = load(path)
    print(
        f"{label:<14s} "
        f"{r['tokens_per_second']:>10.2f} "
        f"{r['swap_out_blocks']:>10d} "
        f"{r['evict_p99_microseconds']:>14.1f} "
        f"{r['attention_capture_total_seconds']:>13.3f}"
    )
PY
```

**Decision tree** (matches `MODE_B_PHASE4_DESIGN.md` §9):

* **Phase 4 ≈ Phase 3 in `swap_out_blocks` and `tokens/sec`**:
  drop Phase 3 (cheaper). Phase 4 becomes the production policy.
  Diligence story: "TriAttention-style static signal matches
  real-attention scoring at much lower runtime cost; CTM+
  composes the signal with S3-FIFO admission + online recency."
* **Phase 4 < Phase 3** (Phase 3 produces fewer swap_out OR
  higher tokens/sec): real attention is irreplaceable for our
  workloads. Resume Phase 3 GPU validation as the production
  path; the trig signal is a useful augmentation but not a
  substitute.
* **Phase 4 ≈ Phase 2** (no win over recency+frequency alone):
  TriAttention's signal doesn't generalise from reasoning to
  chat / RAG / agentic workloads. Defer the trig score; revisit
  if a partner workload looks reasoning-heavy.
* **Phase 4 < Phase 2** (worse than the ablation): calibration
  is broken or the per-block aggregation is wrong. Inspect
  `phase4_blocks_captured_with_pre_rope_keys` — if low, the
  capture hook isn't firing reliably. Diagnose with the
  `attention capture failed` warnings (with
  `--log-level DEBUG`).

## §5 Diagnostic script for capture failures

If Phase 4 produces 0 `swap_out_blocks` AND
`phase4_blocks_captured_with_pre_rope_keys` is also 0, the
capture hook didn't fire. Diagnose:

```bash
python3 - <<'PY'
from vllm import LLM
from kv_policy.triattention import (
    install_pre_rope_capture, install_attn_metadata_side_channel,
    QCenterStats, TrigScorer, _walk_rotary_emb_modules,
    _walk_attention_modules,
)
from kv_policy.vllm_evictor import (
    CTMEvictorModern, patch_vllm_engine_modern,
)

llm = LLM(
    model="/workspace/.hf_cache_phase3/qwen2.5-7b",
    gpu_memory_utilization=0.30, swap_space=4,
    enforce_eager=True, max_model_len=4096,
    enable_prefix_caching=True, seed=42,
)
inner = llm.llm_engine

# Walk to the model.
def find_model(e):
    for path in (
        ("model_executor", "driver_worker", "worker", "model_runner", "model"),
    ):
        cur = e
        for attr in path:
            cur = getattr(cur, attr, None)
            if cur is None: break
        if cur is not None: return cur
    return e

model = find_model(inner)

# Inspect what the walkers find.
print("Rotary modules:")
for layer, name, m in _walk_rotary_emb_modules(model):
    print(f"  layer={layer} class={type(m).__name__:<24s} name={name}")

print("Attention modules:")
for name, m in _walk_attention_modules(model):
    print(f"  class={type(m).__name__:<24s} name={name}")
PY
```

If rotary modules are 0: the model uses a class name not
matching `Rotary` / `RoPE`. Common alternatives: `RotEmb`,
`PositionalEmbedding`, `FreqEncoding`. Add to the heuristic
in `_walk_rotary_emb_modules`.

If attention modules are 0: same diagnosis for
`_walk_attention_modules`.

## §6 What the first GPU run still validates

The CPU sandbox proves API + math correctness. The first GPU
run validates:

1. **Calibration math.** Q tensor reshape + complex-pair
   extraction matches the paper's expectation (R > 0.5
   on the majority of bands).
2. **Side-channel timing.** The Attention pre-hook fires
   BEFORE the rotary_emb pre-hook — if the order is reversed,
   the side-channel is empty when K capture runs. Test by
   inspecting log lines from both hooks; they should
   interleave per-layer.
3. **Slot mapping arithmetic.** `slot_mapping[token] // block_size`
   gives the correct block_id. Verify by spot-checking that
   `phase4_blocks_captured_with_pre_rope_keys` matches the
   number of blocks vLLM reports as cached.
4. **GQA layout.** Qwen2.5-7B has GQA (28 query heads, 4 KV
   heads). The hook captures K per KV head; the simplified
   `head_for_scoring=0` config uses head 0. Validate that
   per-block scores aren't trivially zero.

If all four pass, Phase 4's mechanism is validated end-to-end
and the four-cell results table is the diligence-grade
artifact.
