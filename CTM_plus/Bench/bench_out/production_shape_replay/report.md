# Production-Shape Workload Replay
**Scope: workload-shape evidence, not real-attention evidence.** The length and arrival distributions below are parametric models. The attention itself still comes from KVSimulator's synthetic attention generators. True real-attention replay requires GPU-extracted attention from a real model on real prompts (not implemented in this tool).

Lead metric: **recompute_cost** (the §11 audit-passed metric — observes the operational consequence of eviction rather than predicting importance from policy-coupled signals).
## §1 agentic_sustained_long

_Long-context agentic workload with sustained KV pressure (high arrival, slow completion, large concurrent set). This is the regime KVSimulator §11 surfaced as a CTM+ regression — included here so the replay does not silently skip the bad case._

**Shape caveat:** Sustained-pressure regime. Mode A and §11 KVSimulator both surface CTM+ regressions on this shape. Reported here explicitly to keep the replay honest.

| Parameter | Value |
|---|---|
| max_blocks | 96 |
| block_size | 16 |
| total_steps | 400 |
| arrival_rate (base) | 0.2 |
| completion_rate | 0.04 |
| max_concurrent | 12 |
| arrival_burstiness_alpha | None |
| seeds | [42, 137, 271] |

**Arrival shape (first seed):** 72 arrivals, mean gap 5.54 steps, max gap 21 steps. (Reported for the burstiness-aware schedule even when the KVSimulator runner used uniform Bernoulli.)

| Policy | recompute_cost | blocks_evicted | accuracy | important_evictions* |
|---|---:|---:|---:|---:|
| **ctm_plus** | 393,349 | 24,589 | 60.2% | 0 |
| fifo | 380,624 | 23,789 | 61.2% | 0 |
| kv_policy | 435,621 | 27,252 | 57.7% | 0 |
| **lru** | 386,533 | 24,158 | 60.6% | 0 |
| random | 381,387 | 23,837 | 61.2% | 0 |

*important_evictions is policy-coupled (see RESULTS.md §11.2): SINK is structurally pinned for all policies, ENTITY classification overlaps with CTM+'s scoring inputs. Reported for completeness only; do not cite as a CTM+ headline.

**Lead finding:** CTM+ vs LRU on recompute_cost: +1.8% (CTM+ worse). Accuracy delta: -0.48pp.

## §2 chat_short_long_mix

_Bimodal length: short chat turns dominate, occasional long context. Steady arrival rate. Stresses scan-resistance + small-block-eviction quality._

**Shape caveat:** Parametric bimodal length distribution. NOT validated against LMSYS-Chat-1M / ShareGPT specifically — replace the length_distribution tuples with empirical measurements if you have them.

| Parameter | Value |
|---|---|
| max_blocks | 128 |
| block_size | 16 |
| total_steps | 400 |
| arrival_rate (base) | 0.15 |
| completion_rate | 0.05 |
| max_concurrent | 10 |
| arrival_burstiness_alpha | None |
| seeds | [42, 137, 271] |

**Arrival shape (first seed):** 56 arrivals, mean gap 7.15 steps, max gap 21 steps. (Reported for the burstiness-aware schedule even when the KVSimulator runner used uniform Bernoulli.)

| Policy | recompute_cost | blocks_evicted | accuracy | important_evictions* |
|---|---:|---:|---:|---:|
| **ctm_plus** | 38,320 | 2,396 | 95.2% | 0 |
| fifo | 38,096 | 2,381 | 95.0% | 17 |
| kv_policy | 68,709 | 4,311 | 91.8% | 0 |
| **lru** | 41,509 | 2,594 | 94.5% | 24 |
| random | 38,581 | 2,411 | 95.1% | 18 |

*important_evictions is policy-coupled (see RESULTS.md §11.2): SINK is structurally pinned for all policies, ENTITY classification overlaps with CTM+'s scoring inputs. Reported for completeness only; do not cite as a CTM+ headline.

**Lead finding:** CTM+ vs LRU on recompute_cost: -7.7% (CTM+ better). Accuracy delta: +0.78pp.

## §3 rag_bursty

_Long-context retrieval-augmented workload with bursty arrivals (Pareto inter-arrival shape). Stresses scan-resistance under heavy admission pressure._

**Shape caveat:** Pareto burstiness models heavy-tailed inter-arrival. Production traces (e.g. BurstGPT) are known to be heavy-tailed but the alpha here is a stylized parametric value, not an empirical fit to a specific dataset.

| Parameter | Value |
|---|---|
| max_blocks | 256 |
| block_size | 16 |
| total_steps | 300 |
| arrival_rate (base) | 0.2 |
| completion_rate | 0.05 |
| max_concurrent | 10 |
| arrival_burstiness_alpha | 1.5 |
| seeds | [42, 137, 271] |

**Arrival shape (first seed):** 87 arrivals, mean gap 3.47 steps, max gap 47 steps. (Reported for the burstiness-aware schedule even when the KVSimulator runner used uniform Bernoulli.)

| Policy | recompute_cost | blocks_evicted | accuracy | important_evictions* |
|---|---:|---:|---:|---:|
| **ctm_plus** | 324,389 | 20,275 | 78.7% | 0 |
| fifo | 326,235 | 20,390 | 78.2% | 42 |
| kv_policy | 359,696 | 22,500 | 77.0% | 0 |
| **lru** | 328,816 | 20,551 | 78.1% | 42 |
| random | 325,979 | 20,374 | 78.2% | 30 |

*important_evictions is policy-coupled (see RESULTS.md §11.2): SINK is structurally pinned for all policies, ENTITY classification overlaps with CTM+'s scoring inputs. Reported for completeness only; do not cite as a CTM+ headline.

**Lead finding:** CTM+ vs LRU on recompute_cost: -1.3% (CTM+ better). Accuracy delta: +0.66pp.

## Honest scope statement

* This tool produces **workload-shape replay**, not real-attention replay. The length distributions and arrival patterns are parametric; the attention is synthetic.
* Presets are **parametric models, not validated against specific public datasets** (LMSYS, ShareGPT, BurstGPT, etc.). To map a preset to your data, replace its parameters with empirical measurements from your trace.
* Lead metric is `recompute_cost` (the §11 audit-passed metric); `important_evictions` is reported for completeness with the policy-coupling caveat.
* Real-model CTM+ vs LRU validation remains gated on either Path A (vLLM 0.5+ rewrite) or Path B (partner serving stack). See `PARTNER_VALIDATION_NOTE.md`.
