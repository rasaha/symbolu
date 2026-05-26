# Phase 8 — Bridge proven; Phase 4 trig retired from VC narrative

> **Status:** Phase 8 closed. The Route-A → Phase 4 evictor bridge is
> mechanically proven on GPU. The Phase 4 trig algorithm story did
> not replicate at partner-credible measurement depth and has been
> retired from the VC narrative.
>
> **VC brief: unchanged.** INT4 protected remains the headline.

## The work, end-to-end

Phase 8 was kicked off in response to a strategic question: can we
take Phase 4's earlier KV-eviction algorithm work and compose it
with the shipped INT4-protected stack inside vLLM, producing a
combined operating point worth a VC brief update?

The work ran in three stages over four GPU iterations:

| Stage | Driver | Outcome |
|---|---|---|
| **8b** | `phase8b_route_a_gpu_smoke.sh` | Route-A install + Phase 3 bridge proven (Day 4 + 5a + 5b). 1,105,566 nonzero attention forwards reached the evictor. |
| **8a** | `phase8a_remeasure.sh` | Four-cell measurement under per-layer calibration. Cell 4 (combined) reported -47% swap_out at 60s — but 60s was undersampled. |
| **8a-tighten** | `phase8a_tightening.sh` | 180s-wall reruns. The 60s swap reduction evaporated (T2 at 180s: swap_out unchanged vs LRU). Per-layer vs pooled cal produced identical results. |
| **8a-diag** | `phase8a_trig_sweep.sh` | Bounded trig-parameter sweep. NO configuration beat LRU on either TPS or swap/completed. Decision rule triggered. |

## The bridge proof — what's keep-able

**Route-A → Phase 4 evictor bridge is mechanically proven** on real
vLLM 0.7.3 + Qwen2.5-7B + chat_32k. This is durable engineering work:

* `install_int4_cache_kv_route_a` finds and wraps the right vLLM
  Attention modules on a 7B model (Day 4 + 5a; `forward_calls=600`
  on small model, `forward_calls=74,646` on 7B chat_32k).
* `install_attention_capture` with `capture_every_n=4` patches 7 of
  28 inner Attention modules (Day 5b iteration 3 fix).
* `CTMEvictorModern.forward_block_attention` admits un-tracked
  block_ids speculatively (the Day 5b iteration 2 fix).
* The streaming runner composes CTM+ + Phase 3 + INT4 route-A in a
  single command without crashing.
* 1,105,566 of 1,105,573 `forward_block_attention` calls in Day 5b
  carried non-zero attention. The audit's "attention never reaches
  the evictor" gap is closed.

**These pieces are partner-shareable as "infrastructure / proof of
compatibility", not as "operating-point algorithm win".**

## What didn't replicate

Two older claims didn't survive 180s-wall measurement:

### 1. v5's -11% swap_out algorithm win

| Run | Wall | Cal | swap_out vs LRU |
|---|---:|---|---:|
| v5 (May 2026) | 60s | pooled (MRL=0.221) | **-11%** (claim) |
| 8a Cell 3 | 60s | per-layer | -1.3% |
| 8a-tighten T1 | 60s | pooled (broadcast) | -1.3% |
| 8a-tighten T3 | 180s | per-layer | -1.7% (raw); **+7.2% per completed** |

Per-layer vs pooled calibration produces **identical** results
(T1 vs Cell 3: TPS 102.4=102.4, swap 2178≈2177). The audit's
hypothesis — "pooled-layer methodology inflated v5's -11%" —
**does not hold**. Both calibration modes give the same answer.

What that means: either v5's workload differed materially, the
codebase has drifted since v5, or v5's measurement had unidentified
confounds. **We can't reproduce -11% on this codebase under any
calibration mode tested.**

### 2. The v9/v10 audit -20% throughput tax

At 60s, no tax was visible (all CTM+ cells = LRU = 102.4 TPS).
At 180s, a smaller tax appeared (T3 -9.1%; sweep cells -27%).
The 60s number was a wall-time artifact masking it.

But the diagnostic sweep showed **the tax can NOT be tuned away
via window_interval or candidate_count**:

* `s2` disabled trig in evict() entirely (`candidate_count=1`):
  no improvement. -27.7% TPS, +31.2% swap.
* `s3` minimized trig everywhere (`window=512, candidate=1`):
  no improvement. -27.3% TPS, +32.4% swap.
* `trig_score_computes` stays high (19,790 in s3) because
  `set_block_pre_rope_keys` during prefill drives most computes —
  not tunable via the two flags tested.

## Three diagnostic findings that survive

These would matter if Phase 4 trig is ever revisited:

1. **The cost source is `set_block_pre_rope_keys` during prefill**,
   not evict()-blend and not window_pruning. The sweep proved this
   by elimination. Optimizing this would require a different
   intervention than parameter tuning (e.g., layer subsampling of
   pre-RoPE captures, or caching the trig score across captures).

2. **The trig signal changes 99% of evict() picks** (T3:
   1,529/1,541 changed) but the changed picks **do not improve
   swap quality**. The trig score is influential but not accurate
   for this workload. The calibration data corpus
   (`_DEFAULT_PROMPTS` in `calibrate_qcenters_vllm.py` — 10
   generic sentences) is probably a poor match for chat_32k. A
   workload-matched calibration corpus might change this.

3. **Phase 3 attention forwarding (the bridge) IS proven** and
   carries real attention to the evictor. A future research branch
   could test "real attention-driven eviction" using the bridge,
   but Path B (GPU aggregation rewrite) would be needed to make
   the Phase 3 capture overhead acceptable. Out of scope here.

## What stays in the VC narrative

| Element | Status |
|---|---|
| INT4 protected (quality + memory at int4) | ✅ **Headline** — shipped, partner-credible, unchanged |
| Route-A install in vLLM (mechanical compatibility) | ✅ **Infrastructure** — proven Day 4 + 5a |
| Bridge (attention reaches evictor) | ✅ **Infrastructure** — proven Day 5b |
| Phase 4 KV eviction algorithm | ❌ **Retired** — doesn't replicate at partner-credible depth |
| Combined-stack operating point | ❌ **Retired** — Cell 4 swap win evaporated at 180s wall |

## What stays out

* No VC brief update (per user directive throughout Phase 8).
* No Phase 3 GPU aggregation work (Path B not pursued).
* No further Phase 4 tuning until/unless a workload-matched
  calibration corpus or a different algorithm direction is
  explicitly authorized.

## Open questions for any future revisit

If Phase 4 KV eviction is revisited later (post other priorities):

1. **Workload-matched calibration.** Re-do `calibrate_qcenters_vllm`
   with a chat_32k-style calibration corpus instead of the 10
   generic English sentences in `_DEFAULT_PROMPTS`. The trig
   signal's accuracy depends on calibration data; mismatched data
   means mismatched scores.

2. **Investigate the 99% pick-change-no-quality-gain.** The trig
   signal has high influence but low accuracy on this workload.
   What does it think is "high-value" that LRU disagrees with —
   and is it wrong, or is LRU wrong? Comparing trig-picked vs
   LRU-picked blocks at eviction time would diagnose this.

3. **Pre-RoPE compute reduction.** Most trig score computes happen
   in `set_block_pre_rope_keys` during prefill. Subsampling
   captures (similar to `capture_every_n` for Phase 3) might
   recover throughput without algorithm quality cost.

4. **Real-attention eviction (Path B branch).** The bridge proves
   real attention can drive eviction. Whether it would be better
   than trig is an open research question. Path B is the
   prerequisite engineering.

None of these are committed work. They're notes for the next
visit, whenever that is.

## Artifact pointers

| Doc / data | What it captures |
|---|---|
| `PHASE8_EVICTION_AUDIT.md` | Pre-work audit + revised plan |
| `PHASE8B_ROUTE_A_BRIDGE_PLAN.md` | Bridge architecture + Day 4-5 plan |
| `PHASE8A_REMEASUREMENT_SCAFFOLD.md` | 8a methodology |
| `Bench/bench_out/PHASE8B_GPU/` | Day 4 + 5a + 5b + 5c JSONs |
| `Bench/bench_out/PHASE8A/` | 8a four-cell JSONs (60s wall) |
| `Bench/bench_out/PHASE8A_TIGHTENING/` | 180s reruns + pooled cal |
| `Bench/bench_out/PHASE8A_TRIG_SWEEP/` | Trig parameter sweep |
| `Bench/calibration/qwen25_7b_per_layer.json` | Per-layer cal artifact |
| `Bench/calibration/qwen25_7b_pooled.json` | Broadcast-pooled cal artifact |

## Closing

Phase 8 produced honest, durable engineering: the bridge is real
and works mechanically. It also produced an honest negative
finding: the Phase 4 trig algorithm story doesn't hold at
partner-credible measurement depth. INT4 protected continues as
the shipped headline. The team has clean ground to either return
to Phase 4 with a workload-matched calibration or pivot to other
priorities.
