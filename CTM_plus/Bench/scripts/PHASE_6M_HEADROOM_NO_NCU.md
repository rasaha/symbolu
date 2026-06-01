# Phase 6M — Sizing the throughput prize WITHOUT a profiling GPU

> **Purpose:** answer "can we estimate/test the gather (#1) and attention (#2)
> tax without the ncu-locked pod?" Yes — for the part that matters. This records
> the Tier-0 estimate (computed) and the Tier-1 sweep tool (ready to run), and is
> explicit about what genuinely needs ncu and what does not.

## The key fact: ncu only gates HALF the problem

The locked counters (`ERR_NVGPUCTRPERM`) block ncu, which looks *inside the
attention kernel* (#2) to split compute- vs bandwidth-bound. But the measured
**#1 tax is `mem_other` (+44 s, ~25%)** — the eager paged gather + slot
bookkeeping (`index` / `sort` / `unique` / `nonzero` / `bitwise_and`). Those are
ordinary eager ops, **fully visible to `torch.profiler`** — no ncu needed.

So: **#1 (gather/orchestration) is attackable now; #2 (attention internals) is
what truly needs the profiling pod.**

## Tier 0 — the bounded prize (computed, $0, no GPU)

`estimate_phase6m_headroom.py` — Amdahl bound from the measured 6D profile
(A100, this session: gather 25.1%, attention 21.0% of int4 GPU time; base
aggregate 0.22× at saturation):

| Scenario | int4 GPU time removed | agg ratio | slower/user |
|---|---:|---:|---:|
| no change (baseline) | 0% | 0.220× | 4.5× |
| gather fully fused (attn untouched) | 25.1% | **0.294×** | 3.4× |
| gather 2/3 fused (realistic 6F) | 16.7% | **0.264×** | 3.8× |
| gather fully + attn 1/3 | 32.1% | 0.324× | 3.1× |
| THEORETICAL MAX (both gone) | 46.1% | 0.408× | 2.4× |

**Read this honestly:** the realistic recovery is **~0.22× → ~0.26–0.29×** — which
**matches the plan's stated ~0.27–0.30× ceiling**. Even the *theoretical max*
(remove 100% of both taxes — impossible) is **0.41×, nowhere near bf16 parity**.
int4 fundamentally reads packed KV + scale + xmin + protected and dequants every
token; that floor is irreducible. **The prize is real but bounded.**

## Tier 1 — find the best EXISTING config (cheap, no ncu, no code change)

`phase6m_operating_point_sweep.sh` — sweeps the capacity demo across batch sizes
and generation lengths and tabulates the protected/bf16 ratio at each point. This
is why we saw **0.22× at B=128/gen=512 but 0.32× at b-list 96,128/gen mixed**:
the ratio is operating-point-sensitive. The sweep locates the sweet spot you
**already have for free** — a "deploy at the least-taxed config" answer, no
engineering. Pure measurement; runs on the ncu-locked pod.

```bash
source /workspace/venv-vllm/bin/activate
export HF_HUB_ENABLE_HF_TRANSFER=0 HF_HOME=/workspace/.cache/huggingface
bash CTM_plus/Bench/scripts/phase6m_operating_point_sweep.sh
```

## Tier 2 — actually remove the gather (no ncu, but it IS engineering)

Reducing the eager gather/orchestration and A/B-timing it works **without ncu** —
the harness already exists (`analyze_phase6f_acceptance.py` diffs two
`torch.profiler` runs and checks the gather bucket shrank). **But this is a slice
of the gated Test 3 / 6F work** — careful code that must stay byte-equivalent, not
a config flip. Gate: needs go-ahead + the correctness oracle GREEN. ncu still adds
value later to guide the *attention (#2)* half (compute- vs bandwidth-bound).

## What stays off-limits (regardless of tier)

Closed tracks — **int8-V, fewer protected channels, predicted/symmetric xmin,
sidecar diet** — are RED for quality (6G.2) and are **not** modeled or proposed
here. All throughput work is data-movement/compute only. Density + quality remain
the product; throughput recovery is bounded upside.

## CPU verification (runs anywhere)

```bash
python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py --selftest   # 7/7
python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py              # the table above
bash -n CTM_plus/Bench/scripts/phase6m_operating_point_sweep.sh
```

## Tier-1 result (A100, 2026-06-01) — generation length is the big lever

Sweep across generation length (all mml=8192, prompt_frac=0.95):

| gen | b_list | bf16 tps | prot tps | **agg ratio** | per-user | net_density | prot_live |
|---|---|---:|---:|---:|---:|---:|---:|
| **128** | 48,72,96,128 | 211.3 | 113.4 | **0.54x** | **0.27x** | 1.81x | 114 |
| 512 | 96,128 | 575.4 | 182.8 | 0.32x | 0.16x | 1.83x | 117 |
| 512 | 128 (deep sat, 6L-locked) | 597.3 | 130.4 | 0.22x | 0.11x | 1.83x | 117 |

**KEY FINDING — the throughput tax is operating-point-dependent, range 0.22x-0.54x:**
- **Short generation (gen=128): 0.54x aggregate / 0.27x per-user (~3.7x slower)** —
  far better than the 0.22x headline.
- **Long generation (gen=512): 0.22-0.32x** — the gather tax dominates.
- **Density invariant ~1.81-1.83x** across all points (a memory measurement).

**Why:** the fixed per-step int4 orchestration (paged-gather setup) amortizes over
fewer decode steps at short gen, so the tax is a smaller *share* of total work. The
"0.22x / ~9x slower" headline is the **worst case** (deep saturation + long gen),
not the typical case.

**Product implication (honest — and it HELPS the story):**
- **Short-output, high-concurrency workloads** (classification, extraction, scoring,
  embeddings, agentic tool-routing, MMLU-style eval) get the full ~1.81x density at
  only **~2x aggregate slowdown** (0.54x).
- **Long-generation** (chat, long summarization) stays batch/offline (0.22-0.32x).
- Still NOT interactive-viable (>=0.70x/user bar) anywhere — but the gap is
  workload-dependent; short-gen serving is the strongest fit.

Best NO-CODE lever found: **deploy at short generation, where the tax is already
smallest.** It does not remove the gather (Tier 2); it picks the least-taxed point.
Tier 2's bounded ~0.26-0.30x ceiling is computed at the *worst-case* long-gen point;
the gain there is smaller precisely because short-gen is already better for free.
