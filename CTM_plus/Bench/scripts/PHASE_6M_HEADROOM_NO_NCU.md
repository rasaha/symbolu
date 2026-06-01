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

## Tier-1 result so far (A100, 2026-06-01)

One operating point measured (gen=512, b-list 96,128) — a **third independent
reproduction** of the same point:

| gen | b_list | bf16 tps | prot tps | agg_ratio | net_density | prot_live |
|---|---|---:|---:|---:|---:|---:|
| 512 | 96,128 | 575.4 | 182.8 | **0.318×** | **1.827** | 117 |

Combined with the locked **0.22×** point (B=128, gen=512, deeper saturation), the
existing-config throughput band is **~0.22–0.32×**. Density is invariant at
**1.83×** across all points (as it must be — it's a memory measurement).

**Conclusion (honest):** no *existing* config escapes "throughput-negative"; the
sweep refines *where in the 0.22–0.32× band* you land, not whether the tax exists.
A fuller sweep (more gen values / batch sizes) would pinpoint the least-taxed
deploy config but won't change the conclusion. The real lever remains **Tier 2
(code: remove the gather)**, bounded by the **Tier-0 ceiling ~0.26–0.29×** — not a
config choice. (Throughput valid; quality NOT quoted — this pod's regenerated
mask collapses output.)
