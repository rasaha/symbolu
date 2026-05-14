# Post–Phase-4 Roadmap

**Branch:** `claude/safety-state-machine-EXAlZ`
**Date authored:** 2026-05-09
**Audience:** Engineers running CTM+ validation, partner-pitch authors, and reviewers
deciding what claims the project is currently entitled to make.

This document lays out the path from the current state (Phase 4 code-complete,
GPU validation pending) to a position where CTM+ — and the broader
TurboQuant + CTM+ + CTXL stack — can credibly be called a game-changer.

It is deliberately written in honest scope: each step says what it validates,
what it does **not** validate, and what would change a recommendation.

---

## 0. Where we are right now

| Layer | Status | Evidence |
|------|------|------|
| CTM+ Phase 1 (synthetic CPU sim, 3-tier hierarchy) | ✅ measured | `bench_out/round*` |
| CTM+ Phase 2 (vLLM 0.7+ evictor wired, attention disabled) | ✅ code-complete + audit-pass | `KVPolicy/kv_policy/vllm_evictor.py`, `tests/test_vllm_evictor*.py` |
| CTM+ Phase 3 (post-RoPE attention forwarding) | ✅ code-complete + audit-pass; **deferred** in favor of Phase 4 | `KVPolicy/kv_policy/vllm_evictor.py`, `runner_vllm_streaming.py` |
| CTM+ Phase 4 (TriAttention-inspired pre-RoPE trig scoring) | ✅ code-complete + audit-pass; **GPU validation pending** | `KVPolicy/kv_policy/triattention.py`, `MODE_B_PHASE4_DESIGN.md`, `MODE_B_PHASE4_GPU_RUNBOOK.md` |
| TurboQuant CUDA kernel (3-bit polar) | 🟡 v3 measured (CPU sim), **v4 pending GPU** | `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md`, `benchmark_results_v2.json` |
| TurboQuant ↔ vLLM KV-cache integration | ❌ not attempted | — |
| CTXL (HBM→CXL→NVMe) tiering | ✅ designed; ❌ no runtime/perf measurement | `TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` |
| Combined-stack 8.8× capacity claim | ❌ projected, not measured | architecture doc only |
| Quality preservation (MMLU/perplexity) | ❌ not measured at any layer | — |
| Comparison vs vLLM-FP8 / KIVI / H2O | ❌ not run | — |

**Honest one-liner:** the algorithmic foundations are in place and pass internal
audits; we have **zero** end-to-end real-model GPU evidence that the stack
delivers the claimed gains. Every step below moves a single bar from "compelling
on paper" to "demonstrated on hardware."

---

## Step 1 — Phase 4 GPU validation (executed May 2026, negative result)

> **STATUS UPDATE — May 2026:** Step 1 was executed end-to-end on
> RunPod A100 + Qwen2.5-7B-Instruct + vLLM 0.7.3. **Nine GPU runs
> total (~$2.10 spot)** across three engineering generations:
>
> 1. **Algorithm (v3–v6):** Phase 4 trig scoring. Mechanism dominantly
>    active (98.7% of evict decisions); −11.1% swap_out/decode_token
>    vs LRU. Throughput regression: −20%.
> 2. **Optimization sequence I1–I5 (v8):** five compute-side fixes
>    targeting trig math + capture sync. Audit estimate 12–23pp;
>    **measured 0pp**. py-spy revealed CTM+ code is 1.1% of wall.
> 3. **Cython port (v9):** drop-in C-extension for `CTMEvictorModern`.
>    Audit estimate 5–10pp; **measured 0pp**. Semantically bit-identical
>    to v8 (swap_out=1134, 0.2769/decode_token). Integration tax is
>    located outside CTM+ code entirely.
>
> 4. **Hook-shape fix (v10):** monkey-patched `module.forward`
>    instead of `register_forward_pre_hook`. Audit estimate 2–5pp;
>    **measured ~1pp** (v10 tokens/sec=68.26, equal to v8). Fast-hooks
>    demonstrably worked (+33% more rotary forward fires per wall-
>    second) but the freed compute couldn't translate into more
>    decode tokens within the 60s wall budget on this workload.
>
> **Combined: 19–38pp audit estimate, ~1pp measured.** Phase 4
> throughput optimisation is now **CLOSED as an engineering
> work-track**. The 20% gap vs LRU on chat_32k is structural at
> vLLM 0.7.3's Evictor-ABC patching layer.
>
> The original gate ("Phase 4 hit-rate uplift over LRU ≥ +3pp") was
> **missed** — and the corrected gate below was itself overtaken by
> the engineering arc. The current canonical decision tree is
> `bench_out/PHASE4_GPU_FINDINGS.md` §13.2 (v10 pre-committed
> interpretation). Read `PHASE4_GPU_FINDINGS.md` §1 (TL;DR), §12.6
> (v9), §13 (v10 path) before citing any Step 1 claim to a partner.
>
> Net of throughput negatives: the **algorithm-quality result**
> (−11.1% swap_out per decoded token vs LRU, mechanism active in
> 98.7% of evict decisions) is durable and reproduced across FIVE
> distinct evictor implementations (v5/v6/v8/v9/parametrized fixture).

**Goal (original):** prove that TriAttention-inspired trig scoring on real pre-RoPE Q/K
geometry, plugged into vLLM 0.7+ via the CTM+ evictor, beats LRU on streaming
hit-rate at fixed cache budget.

**Effort (actual):** 6 GPU runs over one session, ~$1.60 spot. Six audit-pass
findings landed during the session; a seventh closed the comparison-validity
issue surfaced by the data.

**Procedure (executed):** see `MODE_B_PHASE4_GPU_RUNBOOK.md` for what was
attempted and `PHASE4_GPU_FINDINGS.md` for what actually happened.

**What Step 1 validated:**
- Calibrator runs end-to-end on Qwen2.5-7B (with documented pooled-layer caveat).
- CTM+ Phase 2 evictor patch installs cleanly on vLLM 0.7.3.
- Phase 4 hooks fire end-to-end after seven repairs: side-channel,
  rotary capture, speculative storage, window pruning.
- The audit-pass discipline produces real fixable findings during
  GPU validation.

**What Step 1 did NOT validate (the negative result):**
- **Phase 4 with pooled-layer calibration does not beat Phase 2 or
  LRU on streaming chat at heavy KV pressure on Qwen2.5-7B.**
  Throughput drops ~20% relative to Phase 2; swap-out per decode
  token is roughly identical (Phase 4: 0.28, Phase 2: 0.31).

**Why the original gate was wrong:** the +3pp hit-rate target assumed
LRU and CTM+ would see the same workload regime. They don't.
Patching `PrefixCachingBlockAllocator.evictor` with CTM+'s wrapper
disrupts vLLM's prefix-cache promotion path: LRU runs at 12.5%
prefix-cache hit rate / 57% peak KV / 0 swaps, while CTM+ runs at 0%
hit / 99% peak KV / 3188 swaps on the same prompts. Comparing raw
swap_out counts across the two regimes is comparing apples to oranges.

### Corrected Step 1 gate (supersedes the original)

Phase 4 wins iff **all three** of the following hold:

1. **Calibration quality:** mean `mean_resultant_length` ≥ 0.3 across
   (layer, head, band) triples on the model's calibration corpus
   (per the TriAttention paper's healthy-stat threshold). This
   requires per-layer indexing on shared-rotary models like Qwen2.5;
   pooled-layer calibration on shared-rotary models reliably
   under-shoots.
2. **Latency at matched p99:** CTM+ Phase 4 reduces decode latency
   at matched p99 by ≥ 5% on chat_32k workload, comparing CTM+ vs
   LRU at **matched `enable_prefix_caching` setting** (both off,
   since CTM+'s patch is only meaningful when the eviction decision
   actually controls cache state).
3. **Quality:** MMLU subset score within ±0.5 points of LRU baseline
   at the same cache budget.

If any of the three misses: write the result up; do not iterate on
GPU before fixing the failed criterion in code or rejecting the
experimental design.

### Original gate (preserved for reference; do not use)

> Phase 4 hit-rate uplift over LRU ≥ +3 percentage points at the 50%
> cache-budget setting on at least one workload, with capture rate
> ≥ 95% and no perf regressions > 10%.

---

## Step 2 — Quality measurement integrated as a 5th metric (~2–3 days CPU eng + $0.50–$3.00 GPU run)

> **Sizing correction (post-Tier-2 audit, see PHASE4_GPU_FINDINGS §16):**
> the previous "~1 day, no GPU" estimate counted only the
> harness-scaffolding work and assumed the underlying eval would
> piggyback on the existing streaming runner. In practice the eval has
> to drive a real model forward pass with a chosen evictor (and, for
> the TurboQuant variant, with a real `cache_kv` hook installed). That
> requires either finishing Tier 2's hook install (route A in §16.2),
> building an HF-transformers attention-hook bypass (route B), and a
> GPU run to actually measure. CPU-only scaffolding still fits in
> ~1 day; the *measurement* is the larger ask.

**Goal:** stop reporting hit-rate alone; every cell now reports a quality
number alongside the cache stat.

**Procedure:**
1. Add a `--quality-eval {mmlu_subset,wiki_perplexity}` flag to
   `run_streaming.py` and a small `ctm_bench.quality` module that, after the
   streaming run completes, evaluates the same model+evictor configuration on a
   100-question MMLU subset and/or 50k-token Wikipedia perplexity stream.
2. Persist quality numbers into `StreamingRunCellResult` and surface them in the
   results-reading script.
3. Add a regression test that pins the harness contract (input shape, score
   range, output schema).
4. **(post-Tier-2)** For the TurboQuant cell variant, ensure the
   `cache_kv` monkey-patch is installed (`PHASE4_GPU_FINDINGS.md` §14.3
   coordinates) before the quality eval — otherwise the lossy KV path
   isn't actually exercised and the eval reports the baseline number
   under a "compressed" label.
5. **(recommended, cheap)** Land Track D first (real-value KV cosine
   on captured Qwen2.5-7B fixtures, see `PHASE4_GPU_FINDINGS.md`
   §16.5). A real-value cosine ≪ 0.95 would explain a Step-2 quality
   regression cheaply, before spending the GPU dollar on a full eval.

**Validates:** that CTM+ does not silently degrade generation quality at the
cache budgets where it claims hit-rate wins.

**Does NOT validate:** anything about absolute quality of the underlying model
or about long-context retrieval quality at the >32k regime.

**Gate to step 3:** quality delta vs LRU within ±0.5 MMLU points (or
±0.05 perplexity) at the cache budget that produced step-1's hit-rate uplift.

If quality regresses > 0.5 points: tune the scoring weights
(`MODE_B_PHASE4_DESIGN.md` §3) and re-run step 1's narrowest cell before
proceeding.

---

## Step 3 — Multi-workload + multi-model Phase 4 sweep (~2 GPU-days, ~$5–10)

**Goal:** show the gains hold beyond a single model and a single traffic shape.

**Procedure:**
1. Models: Llama-3-8B, Qwen2.5-7B, Mistral-7B-v0.3 (re-calibrate Q-centers per
   model; calibration is cheap).
2. Workloads: streaming chat (existing), production-shape replay
   (`production_shape_replay/` shapes), long-context retrieval (≥ 32k context
   needles-in-haystack subset).
3. Cache budgets: {25%, 50%, 75%} of full KV.
4. Cells per (model, workload, budget): {LRU, Phase 4} — Phase 2/3 ablations
   only on the Llama cell to keep cost down.
5. File artifacts under `bench_out/phase4_sweep/<model>/<workload>/`.

**Validates:** generality of the algorithmic win across model families and
traffic shapes.

**Does NOT validate:** the system-level capacity story; that requires the
TurboQuant + CTM+ + CTXL stack.

**Gate to step 4:** Phase 4 wins (hit-rate uplift ≥ +3pp **and** quality within
gate from step 2) on **≥ 4 of 9** (model × workload) cells at the 50% budget.

Failure mode: if Phase 4 wins on chat but loses on long-context retrieval,
that's still publishable — but the partner-pitch positioning must be narrowed
to "streaming chat / production traffic" until long-context is addressed.

---

## Step 4 — TurboQuant CUDA v4 kernel end-to-end measurement (~1 week eng + 1 GPU-day)

**Goal:** replace the CPU-simulated v3 benchmark with real GPU-measured numbers
for the v4 polar-quant kernel.

**Procedure:**
1. Engineering: complete v4 kernel per the open work in
   `CTM_plus/CUDA/` and `CTM_plus/DeepSpeed/`.
2. Re-run `CTM_plus/DeepSpeed/benchmark_*` with **real GPU** kernels and real
   model gradients (not synthetic vectors). File artifacts under
   `CTM_plus/DeepSpeed/benchmark_results_v4_gpu.json`.
3. Add comparison cells against bf16 baseline and vLLM-FP8 quant.
4. Gate this step's claims behind audit-pass: HIGH = silent corruption, MEDIUM
   = > 1% throughput regression vs v3 sim, LOW = doc/test gaps.

**Validates:** that TurboQuant's compression ratio (claimed 7.15× at 0.965
cosine, 3-bit standard) survives the move from CPU sim to real GPU and from
synthetic vectors to real gradients.

**Does NOT validate:** anything about TurboQuant on KV cache (it currently
targets gradients in DeepSpeed). KV-cache TurboQuant is its own integration.

**Gate to step 5:** GPU-measured compression ratio ≥ 5× at cosine ≥ 0.95 on
real model gradients, with kernel throughput such that wall-clock training
time is within 5% of bf16 baseline.

---

## Step 5 — Combined-stack measurement (TurboQuant × CTM+ × CTXL, ~3 days eng + 1 GPU-day)

**Goal:** test the architecture-doc 8.8× effective-capacity claim end-to-end,
or replace it with the actually-measured number.

**Procedure:**
1. Engineering: integrate TurboQuant kernels into vLLM's KV-cache write path
   (this is the integration the architecture doc assumes but that does not
   exist in code today). Land it behind a feature flag.
2. Wire CTXL tiering so evicted-but-not-yet-discarded blocks land on the CXL or
   NVMe tier with the TurboQuant compression on disk.
3. Run a streaming workload at each of: HBM-only, HBM+CXL, HBM+CXL+NVMe with
   and without CTM+ and with and without TurboQuant. (8 cells total.)
4. Report **effective serving capacity** (concurrent requests × context length
   sustained at p99 latency budget) for each cell.

**Validates:** the system-level capacity claim. The 8.8× number either
reproduces, comes in lower, or comes in higher; either way the doc gets updated
to match measurement.

**Does NOT validate:** generation quality at the new operating point. Quality
must be re-checked per step 2 at every cell where the new capacity actually
gets used.

**Gate to step 6:** combined-stack effective capacity ≥ **5×** baseline (a
softer bar than the doc's 8.8× claim, but enough to lead a partner pitch),
with quality within step-2 gate at the new operating point.

---

## Step 6 — Comparison vs vLLM-FP8 + KIVI + H2O (~1 GPU-day)

**Goal:** rule out the obvious "is this just FP8 with extra steps?" objection
that any partner technical reviewer will raise.

**Procedure:**
1. Run the step-3 winning cells with: bf16 baseline, vLLM-FP8 KV cache, KIVI
   2-bit KV cache, H2O eviction policy, and CTM+ Phase 4.
2. Plot the Pareto frontier: quality (MMLU / perplexity) vs effective capacity.
3. CTM+ wins if it sits on or above the Pareto frontier; loses otherwise.

**Validates:** that CTM+ is meaningfully better than what a careful engineer
would build with off-the-shelf vLLM features.

**Does NOT validate:** future-proofing — newer KV-quant work (KVQuant, ScaleKV,
etc.) lands monthly and any leadership claim has a shelf life.

**Gate to step 7:** CTM+ on Pareto frontier on ≥ 50% of (model × workload)
cells from step 3.

---

## Step 7 — One design partner running it in production (months)

**Goal:** the only evidence that actually moves the "game-changer" needle.

**Procedure:**
1. Pick a partner whose workload matches the cells where CTM+ wins step 3 and
   step 6 (likely streaming chat or production-shape RAG, not long-context
   retrieval, based on current expectations).
2. Land a partner-deployable artifact: the CTM+ evictor wired into their vLLM
   fork, calibrated Q-centers for their specific model checkpoint, runbook
   for re-calibration after fine-tunes.
3. Measure: their quality KPI (whatever they already track), their cost-per-
   token, their p99 latency, their effective concurrency. All four numbers must
   move in the right direction or the partner walks.
4. Publish: case study, signed off by the partner, with the actual numbers.

**Validates:** product-market fit, not just algorithm-market fit. This is the
only step that lets the team write "X uses CTM+ in production."

---

## Decision matrix: what each milestone earns

| After step | Honest claim |
|------|------|
| 1 | "TriAttention-inspired trig scoring works on real Llama-3 KV cache." |
| 2 | "…without measurable quality loss on MMLU." |
| 3 | "…across multiple modern open-weight models and production traffic shapes." |
| 4 | "TurboQuant 3-bit polar quant runs on GPU at v3-equivalent compression." |
| 5 | "The combined CTM+ + TurboQuant + CTXL stack delivers ≥5× effective serving capacity over bf16+LRU at matched quality." |
| 6 | "…and beats every off-the-shelf vLLM KV-quant or eviction policy on the Pareto frontier on the workloads we tested." |
| 7 | "Partner X serves production traffic on the stack and reports {quality+, cost-, latency-, concurrency+}." |

**Game-changer claim is reserved for after step 6 with step 7 in flight.**
Anything earlier is "promising research artifact with audit-pass discipline."

---

## What governs all steps

1. **Audit-pass discipline.** Each step ships with a test file pinning its
   contracts, a HIGH/MEDIUM/LOW severity audit, and `bench_out/<step>/RESULTS.md`
   describing what's measured vs not.
2. **No retroactive scope changes.** If a step's gate misses, write down what
   missed and what would unblock it before widening or re-defining the gate.
3. **Single source of truth.** `bench_out/RESULTS.md` and
   `bench_out/PARTNER_VALIDATION_NOTE.md` reflect actual measured state. They
   do not promise step-N evidence until step-N artifacts exist.
4. **Cost discipline.** Steps 1–3 are sub-$20 GPU. Steps 4–6 are
   engineering-bound, not GPU-bound. Step 7 is a partner conversation. There is
   no point at which the project requires a multi-thousand-dollar compute spend
   to prove its core algorithmic claim.
5. **Fail forward.** A step that misses its gate is informative — file the
   negative result in `bench_out/<step>/RESULTS.md` with the same rigor as a
   positive one.

---

## File map

| Path | Role |
|------|------|
| `CTM_plus/Bench/scripts/POST_PHASE4_ROADMAP.md` | This document. |
| `CTM_plus/Bench/scripts/MODE_B_PHASE4_DESIGN.md` | Step 1 design rationale. |
| `CTM_plus/Bench/scripts/MODE_B_PHASE4_GPU_RUNBOOK.md` | Step 1 execution. |
| `CTM_plus/Bench/bench_out/RESULTS.md` | Live state of measured evidence. |
| `CTM_plus/Bench/bench_out/PARTNER_VALIDATION_NOTE.md` | What the partner pitch is currently entitled to claim. |
| `CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` | Architecture-doc source of the 8.8× capacity claim that step 5 is meant to validate. |
| `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md` | Step 4 starting point. |
