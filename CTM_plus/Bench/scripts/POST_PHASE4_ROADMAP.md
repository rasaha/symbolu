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

## Step 1 — Phase 4 GPU validation (this week)

**Goal:** prove that TriAttention-inspired trig scoring on real pre-RoPE Q/K
geometry, plugged into vLLM 0.7+ via the CTM+ evictor, beats LRU on streaming
hit-rate at fixed cache budget.

**Effort:** ~1 GPU-day on a single A100 / H100, **~$1** at spot pricing.

**Procedure:** follow `MODE_B_PHASE4_GPU_RUNBOOK.md` end-to-end:

1. §2 — calibrate Q-centers on Llama-3-8B (~5 min, ~$0.05).
2. §3 — four-cell experiment: LRU baseline / Phase 2 ablation / Phase 4 trig /
   Phase 3 ablation.
3. §4 — run results-reading script, file artifacts under
   `bench_out/phase4_gpu/`.
4. §6 — first-GPU-run validation list (sanity: capture rate ≥ 95%, calibration
   MRL > 0.3, evict latency < 50µs/call).

**Validates:**
- Pre-RoPE K capture works in production vLLM.
- Trig predictor reproduces TriAttention's near-attention quality on a real
  decoder.
- CTM+'s structural advantage (S3-FIFO + window pruning) survives swapping the
  scorer.

**Does NOT validate:**
- Quality on downstream tasks (MMLU, perplexity).
- Performance under multi-tenant or long-tail traffic.
- Anything about TurboQuant or CTXL.

**Gate to step 2:** Phase 4 hit-rate uplift over LRU ≥ **+3 percentage points**
at the 50% cache-budget setting on at least one workload, with capture rate
≥ 95% and no perf regressions > 10%.

If the gate misses: investigate per `MODE_B_PHASE4_GPU_RUNBOOK.md` §5
(diagnostics) before re-running. Do **not** widen scope until the algorithm
clears its single-cell bar.

---

## Step 2 — Quality measurement integrated as a 5th metric (~1 day, no GPU)

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
