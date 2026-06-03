# Phase 9 Step 1 — Route-A GPU smoke result (the integration gate)

> **Status: STEP 1 GREEN on what it tests (install + bridge), but throughput
> cells VOID (KV-cache starvation). No throughput/quality A/B yet — that is
> Step 2, still to build.** Pod: A100 80GB, vLLM 0.7.3, torch 2.5.1+cu121,
> Qwen2.5-7B-Instruct, `chat_32k` (prompts 8k–30k), 30 concurrent, 60s wall.
> Ran `phase8b_route_a_gpu_smoke.sh` (Days 4 + 5a/5b/5c).

## What PASSED (the Step 1 gates — the integration shape works)

| Gate | Result | Meaning |
|---|---|---|
| **Day 4 install** | `forward_calls=336` (0.5B); 52619 (7B 5a); 12385 (7B 5b) | Route-A's `_looks_like_attention` heuristic matches the real vLLM 0.7.3 Attention class; the hook **fires on real decode**. The "does it install on the pinned stack" question = **YES**. |
| **Day 5b bridge** | `fc=12385 flushed=917517 samples=6297436 fba=918034 nonzero=918032` | All five bridge assertions pass — including **non-zero attention sums reaching the evictor** (`forward_block_attention_nonzero_sum_calls=918032`). |

**The Day 5b non-zero number closes the Phase 8 audit's gap.** The audit's status
quo was "attention never reaches the evictor with a non-zero sum (Evictor-ABC
zeroes it)." The Phase-3 capture wrapper (installed on 7/28 layers,
`capture_every_n=4`) now demonstrably composes with Route-A end-to-end on GPU and
feeds non-zero per-block attention to `CTMEvictorModern.forward_block_attention`.
The bridge infrastructure described in `PHASE8B_ROUTE_A_BRIDGE_PLAN.md` is real
and works on a current vLLM. (The `forward_block_attention_*` counters were
present in the build — no logging-patch gap.)

## What is VOID (and why) — no throughput/quality answer from this run

**Every cell completed 0 requests** → all TPS = `None` in `PHASE8B_GPU_REPORT.md`.

| cell | policy / stack | admitted | completed | decode_tokens | swap_out | wall |
|---|---|---:|---:|---:|---:|---:|
| Day 5a | route-A int4 only | 30 | **0** | 0 | 579 | 60s |
| Day 5b | CTM+ + Phase3 + route-A | 30 | **0** | 0 | 0 | 60s |
| Day 5c | LRU (bf16 baseline) | 30 | **0** | 0 | 579 | 30s |

**Root cause: KV-cache starvation, not Route-A.** `GPU_UTIL=0.26` →
`0.26 × 79.25 = 20.6 GiB` usable; weights 14.25 + activation 4.35 + 0.09 leaves
**1.91 GiB for KV cache (2238 blocks, "Maximum concurrency 1.09×" for 32k)**. The
workload admits 30 concurrent requests with 8k–30k prompts — room for ~1 — so it
thrashes (Day 5a/5c `swap_out=579`) and nothing finishes in the wall window. The
`GPU_UTIL=0.26` default is fine for the cheap Day-4 install check on the 0.5B
model but **far too low to actually run the 7B @ 32k workload to completion.**

## Soft signal (record, do NOT conclude) — instantaneous decode tps

While none completed, vLLM's live `Avg generation throughput` differed sharply by
cell (under thrash, configs not matched — directional only):

- **Day 5c LRU bf16:** ~144–208 tok/s
- **Day 5a route-A int4 (compression):** ~50–110 tok/s  → roughly the known int4
  decode tax (0.22–0.54×), consistent with the locked curve.
- **Day 5b CTM+ bridge + route-A:** ~18–27 tok/s  → a *further* ~3–5× drop below
  5a.

**This is exactly the shape the PCAM gate (Step 3) is looking for** — the
attention-capture/flush bridge appears to add large CPU-side overhead on top of
the int4 tax. **But it is NOT a measurement:** (a) nobody completed, these are
instantaneous numbers under preemption; (b) **Day 5b had `enable_prefix_caching=True`
while 5a/5c had `False`** — an unmatched config; (c) the flusher threw a
concurrency error (below). Treat as a hypothesis to confirm with a matched,
profiled run, not as the dispatch-bound verdict.

## Bugs / issues to fix before the decisive run

1. **`GPU_UTIL=0.26` is too low for 7B@32k throughput.** Raise to ~0.85–0.9 (or
   cut prompt lengths / concurrency) so cells actually complete. Without
   completions there is no aggregate throughput and no quality to score.
2. **Flusher concurrency bug (non-fatal):** Day 5b logged
   `attention flush to evictor failed: dictionary changed size during iteration`.
   The flush iterates the aggregator buffer while the capture path mutates it.
   Most flushes still landed (flushed=917517) but this drops samples and could
   skew scores — needs a snapshot/lock in `_run_attention_flusher` /
   `flush_to_evictor`.
3. **Unmatched `enable_prefix_caching` across cells** (5b True, 5a/5c False). The
   A/B must hold this constant or the throughput comparison is invalid.

## Where this leaves the experiment

- **Step 1 = GREEN.** The integration installs and fires on vLLM 0.7.3, and the
  attention bridge carries non-zero signal to the evictor end-to-end on GPU. The
  "does the integration even work" risk is retired.
- **Step 2 (the decisive read-skip A/B) is NOT done.** Two things stand between
  here and a verdict:
  1. **Config:** fix the three issues above so the workload completes and yields
     real throughput + a quality (needle/MMLU) score.
  2. **Mechanism:** the cells run TODAY are int4 **compression** (dequant
     round-trip, every token read every step) + (5b) attention-fed **eviction**
     (deletion). **They are not read-skip** (keep stored in int4, skip the READ
     of cold blocks). The decisive A/B needs the actual skip path wired — the
     thing Step 0 modeled (~1.9× at long context) and the thing PCAM is scoped to
     accelerate.

**Discipline note:** Step 0 said the prize is real only at long context (≥8k) —
this workload (8k–30k) is correctly long. But a throughput number requires the
KV budget to fit more than one request, and the read-skip mechanism requires the
skip to actually happen, not just compression+eviction. Step 1 cleared the
integration gate; it did not (and was not designed to) measure the prize.
