# CTM+ Validation Status and Real-Stack Integration Path

**Audience:** prospective design partner evaluating CTM+ for an
LLM-inference deployment.
**Status:** safe to share; conservative framing throughout.
**Last updated:** 2026-05-08 (revised after Phase 2 audit pass +
Phase 3 attention-forwarding scaffolding + TriAttention paper
review + Phase 4 design).

This note states what CTM+ has and has not been validated to
do today, why a real-stack `vLLM` validation has not yet been
run end-to-end, and what a partner-specific integration would
look like.

## §1 What is proven today

* **Mode A — synthetic tier-aware simulation.** Five rounds of
  results plus an independent critical-audit pass plus
  multi-seed confirmation across {42, 137, 271}. Headline
  findings, all reproducible from `runner_sim.py`:
  * **Chat under heavy KV pressure:** HBF + CTM+ delivers a
    **52% latency reduction** vs DDR + LRU on `chat_32k` at
    oversubscription 0.025. CTM+ alone contributes ~38%; HBF
    tier alone contributes ~24%; together ~52%.
  * **Retrieval-augmented (RAG):** CTM+'s S3-FIFO admission
    keeps one-shot prefill chunks out of the working set
    entirely. Slow-tier reads collapse to **0** at every
    oversubscription tested (−100% vs LRU).
  * **Agentic (honest regression):** CTM+ is **worse** than
    LRU on agentic workloads, with the gap amplifying under
    heavier pressure (+12% to +192% depending on
    oversubscription). The α=0.20 production default helps
    in moderate regimes; a recency-floor extension (Round 6,
    not yet implemented) is the candidate fix at heavy
    spillover.
* **Mode B — real-vLLM harness execution.** A May 2026 GPU
  run on a RunPod A100 (~15 minutes wall, ~$0.30 spend)
  validated that the harness loads `Qwen2.5-7B-Instruct` on
  a real GPU through vLLM, runs the workload generators end
  to end, and produces honest wall-clock-per-decode-token
  timing data. The harness execution path is proven.
* **CTM+ patch installs cleanly on a real vLLM serving
  stack.** A second RunPod A100 session (May 2026, vLLM 0.4.0
  + TinyLlama-1.1B-Chat) verified the `patch_vllm_engine`
  call swaps vLLM's default `LRUEvictor` for `CTMEvictor` in
  the `CachedBlockAllocator`. Verified by a 30-second
  allocator probe (documented in `MODE_B_VLLM04_RUNBOOK.md`
  §1.2): pre-patch reads `LRUEvictor`, post-patch reads
  `CTMEvictor`. **This is the first time CTM+'s scoring math
  has been wired into a real serving stack with real
  attention flowing through it.** What this does **not** do:
  validate end-to-end CTM+ vs LRU policy-effect under load
  (that's gated on §4).
* **Independent simulator cross-confirmation.** Three
  separate simulators converge on the same workload-
  conditional shape: Mode A (tier-cost simulator),
  KVSimulator (continuous-batching simulator, different
  codebase), and the production-shape replay tool
  (parametric workload over KVSimulator, multi-seed
  averaged). All three show: small CTM+ wins on
  bimodal-chat / bursty-RAG; regression on sustained
  long-context agentic. The convergence rules out "the
  simulator is wrong" as an alternative explanation for
  the headline; what it does **not** rule out is that
  real-attention behaviour differs from synthetic-attention
  behaviour. That gap is closed by §4.
* **Modern-vLLM streaming runner produces real swap
  counters.** A May 2026 RunPod A100 + vLLM 0.7.3 +
  Qwen2.5-7B-Instruct run validated the streaming-runner
  Phase 1 mechanism end-to-end. Single-cell smoke produced
  **2205 swap_out blocks across 2 preemption events** at
  `GPU_MEM_UTIL=0.26 + arrival_rate=6.0/sec + max_decode=2048`.
  vLLM's own scheduler log corroborated:
  `Sequence group ... is preempted by PreemptionMode.SWAP
  mode ...`. This closes the architectural gap from the
  prior batch-mode Mode B run (where FCFS-no-preempt produced
  zero swap counters). Full artifact at
  `bench_out/streaming_smoke_v4_proof.json`. **Important
  caveat:** this is LRU only; Phase 2 (CTM+ on modern vLLM)
  is the path that produces head-to-head policy numbers,
  still gated on partner request.
* **Methodology.** Audit-pass discipline — every non-trivial
  change goes through an independent critical-audit pass
  before merge. Two of the five rounds caught and corrected
  the team's own errors mid-flight (a 2× decode-count metric
  bug in Round 4; a seed-propagation bug found at the same
  time). Reproducer commands ship next to every published
  number.

## §2 What is not yet proven

* **Real-model CTM+ vs LRU policy-effect numbers.** No
  measurement of how CTM+'s eviction decisions actually
  change wall-clock latency, throughput, or hit rates on a
  real model exists today. The patch is now verified to
  install (May 2026), but no end-to-end workload sweep has
  produced apples-to-apples CTM+-vs-LRU numbers. **A
  May 2026 audit pass on the Phase 2 implementation
  surfaced that vLLM's Evictor ABC does not forward
  attention to the evictor** — so even with the patch
  installed, CTM+'s scoring formula's 0.35·attn term is
  effectively zero. The policy that runs through the
  patched vLLM is roughly "recency + frequency" (close to
  LRU + a tiebreaker), NOT the attention-aware policy that
  produced the simulator headlines. **Real-model evidence
  of CTM+'s actual scoring math requires a Phase 3
  attention-forwarding hook** — ~3–4 days of vLLM-internals
  + model-runner work, not yet scoped. Phase 2 GPU smoke
  is still defensible as "integration fires end-to-end with
  no silent failures," but is NOT defensible as "CTM+ vs
  LRU on a real model."
* **Phase 3 (attention forwarding) code-complete; GPU
  validation deferred pending Phase 4 evaluation.**
  Code-complete as of May 2026 (commit `b5e7f14` for the
  Q@K extraction; `7b5df3f` for the timing instrumentation).
  However, after reviewing the TriAttention paper
  (arXiv:2604.04921, April 2026), the premise of Phase 3
  is contested: TriAttention shows that pre-RoPE Q/K
  geometry (not real attention scores) can drive eviction
  decisions that beat attention-based methods on both
  reasoning (AIME25) and general long-context (LongBench)
  workloads, at much lower runtime cost. Running Phase 3's
  GPU validation before evaluating the trig-based
  alternative would commit to the wrong direction.
* **Phase 4 (trigonometric position scoring) — design
  complete.** A May 2026 design at
  `scripts/MODE_B_PHASE4_DESIGN.md` adopts TriAttention's
  pre-RoPE Q-center-based scoring as a new component in
  CTM+'s scoring formula, while keeping CTM+'s structural
  advantages (S3-FIFO admission for scan resistance,
  online recency tracking, block-level vLLM integration).
  Implementation **code-complete as of May 2026** (49
  tests, 237 total in Bench). All GPU-side hooks are
  written: offline `calibrate_q_centers`, runtime
  `install_pre_rope_capture`, sibling
  `install_attn_metadata_side_channel`. The four-cell GPU
  experiment runbook is at
  `scripts/MODE_B_PHASE4_GPU_RUNBOOK.md`. Estimated
  validation cost: ~$0.60–1.00 GPU spot (RunPod A100,
  ~25–30 minutes wall).

* **Acknowledged related work — TriAttention.** The
  TriAttention paper (Mao et al., MIT/NVIDIA/ZJU, arXiv:
  2604.04921) presents a pre-RoPE Q/K-concentration
  observation that yields a static scoring signal
  outperforming attention-based methods (SnapKV, R-KV,
  H2O, LazyEviction) on AIME25, MATH 500, and LongBench.
  Headline: 10.7× KV memory reduction, 2.5× throughput at
  matched accuracy. CTM+'s differentiation in light of
  this:
  - **Admission policy.** S3-FIFO for scan resistance —
    TriAttention has no admission policy; RAG one-shot
    reads still pollute the cache without it. CTM+'s
    Mode A −100% slow-tier-reads on RAG is admission-
    driven, structurally orthogonal to TriAttention.
  - **Online recency + access-frequency tracking.**
    TriAttention's score is essentially static. CTM+
    captures temporal access patterns (Markov-dwell on
    agentic hot blocks).
  - **Workload-conditional behavior validated on three
    independent simulators** — Mode A, KVSimulator,
    production-shape replay. TriAttention's headline
    benchmarks are reasoning-task-heavy; CTM+'s
    canonical workloads (chat/RAG/agentic) are partner-
    relevant.
  Phase 4 incorporates TriAttention's core insight (the
  trigonometric distance-preference signal) into CTM+'s
  scoring formula. See `papers/triattention_notes.md` for
  paper notes + Phase 4 design rationale.
* **Real-silicon swap-byte calibration.** Mode A's
  `avg_access_latency_ns` predictions and slow-tier byte
  counts have not been cross-checked against real swap-byte
  traffic on any GPU. The vLLM runs that were attempted did
  not engage the swap path (see §3).
* **Production workload traces.** Mode A's workload
  generators (`chat`, `rag`, `agentic`, `agentic_clustered`)
  are synthetic; they capture the qualitative shape of each
  class but they are not your production traces. Numbers on
  your workloads will differ in magnitude, possibly in
  direction.
* **HBF tier on real hardware.** The HBF tier-cost model is
  derived from public SanDisk announcements. No real-silicon
  HBF measurements exist yet; the 52% headline depends on
  the published bandwidth/latency numbers being roughly
  correct.

## §3 Why vLLM Mode B did not exercise CTM+

Two independent reasons, either sufficient on its own:

1. **vLLM 0.5+ removed the public eviction-policy hook the
   CTM+ patch targeted.** The original integration replaced
   `BlockSpaceManagerV1.gpu_allocator.evictor` (a
   replaceable attribute on vLLM ≤ 0.4). vLLM 0.5+ replaced
   that with `SelfAttnBlockSpaceManager` plus a private
   `CpuGpuBlockAllocator._allocators` dict; there is no
   public abstraction to register a custom eviction policy
   against. The existing CTM+ patch fails fast with
   `NotImplementedError` on vLLM 0.5+ and was not invoked
   during the May 2026 sweep — only LRU cells ran.
2. **vLLM batch-mode FCFS execution did not trigger
   swap/preemption.** The `engine.generate(prompts=[...])`
   API with the default first-come-first-served scheduler
   either admits a prompt (it fits) or queues it (waits for
   active prompts to complete). It does not preempt running
   sequences. `swap_space` engages only on preemption.
   `block_allocator.get_and_reset_swaps()` honestly returned
   zero across every Mode B cell — the API path was correct;
   no swap events occurred. The harness reports
   `counter_source = vllm_0_7_no_swaps_observed` to
   distinguish "API works, no swaps happened" from "API path
   didn't match."

The latency cross-check tool
(`ctm_bench.scripts.latency_cross_check`) reports per-seed
tokens/sec and ms/token from the existing Mode B runs as
**harness/timing evidence only — not CTM+ performance
evidence**. That is the honest scope of the data the May 2026
GPU run produced.

## §4 What a 2–3 day partner-specific integration would test

Two paths, sized similarly; the choice depends on what your
serving stack already exposes.

### §4.1 Path A — vLLM 0.5+ integration rewrite

Rebuild the CTM+ patch against the post-0.5 allocator
architecture. Three sub-options, in order of decreasing
invasiveness:

1. **Subclass `CpuGpuBlockAllocator`** and inject a
   CTM+-aware variant via vLLM's engine-config layer. Hold a
   private fork or invasive monkey-patch.
2. **Patch `BlockTable` / `KVCacheManager`** to intercept
   block-level eviction decisions before they reach the
   allocator. Higher-leverage; harder to keep stable across
   vLLM minor versions.
3. **Submit a vLLM PR** to add a public `EvictorPolicy`
   abstraction. Cleanest long-term outcome; longest path to
   landing.

In parallel, switch the runner to `AsyncLLMEngine` with
`add_request()` calls timed to exceed steady-state capacity,
and configure the scheduler with `preemption_mode="swap"` so
the swap path actually engages. Capture
`get_and_reset_swaps()` periodically during the run, not
just at the end.

**What this would test:** real-model CTM+ vs LRU head-to-head
on each of the four canonical workloads, at the partner's
chosen model + context length, with real swap-byte counters.
Validates Mode A's directional predictions (sign and rough
magnitude) and produces a calibration constant between Mode A
`avg_access_latency_ns` and observed wall-clock-per-token.

### §4.2 Path B — partner-specific serving harness

If the partner's serving stack already exposes a public
eviction-policy hook (TGI, SGLang, an internal fork, or
custom serving infrastructure), CTM+ can be ported in 1–2
days against that hook directly. Tests the same questions as
Path A but on the partner's actual production runtime.

**What both paths test (success criteria from Mode A):**

| Workload | Mode A predicts | Partner-run threshold | If breached |
|---|---|---|---|
| `rag_128k` | −100% slow-tier B/tok vs LRU | CTM+ ≥ 50% reduction | Investigate scan-resistance plumbing in the partner integration |
| `chat_32k` @ heavy spillover | −52% latency vs LRU (with HBF) or containment to 61% of LRU's slow-tier B/tok (without HBF) | CTM+ ≤ 70% of LRU on slow-tier B/tok | Containment property doesn't hold under real attention; revisit α default + Round 6 |
| `agentic_clustered_64k` | +22% (oversub 0.10) up to +192% (oversub 0.025) | CTM+ within +30% of LRU at moderate pressure | Document calibration; do not ship CTM+ default for agentic-heavy partner without Round 6 |
| `chat_32k` @ moderate pressure | parity (within ~5%) | CTM+ ≤ LRU within 5% | Real-model chat behaves differently from synthetic; investigate |

Estimated cost of one validation cycle: **2–3 days of
focused work** (integration + sweep + calibration) plus
GPU-hours measured in single-digit dollars at partner-spot
rates.

## §5 What we need from a design partner

To scope a Path A or Path B validation accurately, the
partner conversation should pin down:

* **Model.** Architecture (Llama, Qwen, Mistral, …), size
  (7B, 13B, 70B, …), and license posture (gated, open,
  internal-only). Mode A is model-agnostic at the cost
  level; the integration path depends on whether the
  partner's model fits a single GPU.
* **Context length.** Both prefill (`max_model_len`) and
  steady-state working-set length per session. Mode A's RAG
  cell assumes 128K prefill; chat assumes 32K; agentic
  assumes 64K. Partner workloads at substantially different
  lengths need a Mode A re-run before partner integration.
* **Concurrency.** Number of in-flight requests at
  steady state, request-arrival distribution
  (Poisson, bursty, scheduled), and target queue depth.
  Determines whether preemption pressure exists at all
  (without it, swap stays zero — the same gap Mode B hit
  in batch mode).
* **Serving stack.** vLLM (and which minor version), TGI,
  SGLang, internal/custom. Determines Path A vs Path B and
  the integration-day estimate. If vLLM, the minor-version
  matters: 0.4.x is straightforward; 0.5+ requires the
  rewrite in §4.1.
* **Latency / SLO targets.** P50 and P99 time-to-first-token
  and inter-token latency targets, plus the workload mix
  weighting (chat-heavy, RAG-heavy, agentic-heavy). Drives
  which Mode A cell is the most relevant headline for the
  partner's deployment.
* **GPU type.** A100-40/80GB, H100, H200, MI300X, Gaudi,
  custom. KV-cache budget per GPU is what determines
  oversubscription; the headline cells assume A100-class
  budgets. Different VRAM ratios shift which oversubscription
  cell maps to "production-realistic" pressure for the
  partner.
* **Workload traces.** Anonymized or synthetic-but-shape-
  matched traces from the partner's actual production
  traffic. Mode A's generators are stand-ins; production
  traces close the gap between "synthetic prediction" and
  "real workload prediction." Even one-week trace samples
  let us re-run Mode A against the partner's distribution
  before Path A/B integration starts.

With these inputs we can convert the Mode A headline cells
into partner-specific predictions and a 2–3 day Path A or
Path B validation plan. Without them, any cost or latency
quote is a synthetic-workload extrapolation.

## §5a Roadmap beyond Phase 4

What is laid out in §4 (Path A / Path B real-stack integration)
is one slice of a longer roadmap. The full plan — covering
Phase 4 GPU validation, quality-preservation measurement,
multi-model sweeps, the TurboQuant CUDA v4 kernel, the combined
TurboQuant + CTM+ + CTXL stack measurement, head-to-head
comparison vs vLLM-FP8 / KIVI / H2O, and a partner production
deployment — is documented at
`CTM_plus/Bench/scripts/POST_PHASE4_ROADMAP.md`.

The roadmap is structured so that **each step earns a single
narrow honest claim**:

| After step | Honest claim |
|---|---|
| 1 (~$1 GPU) | "TriAttention-inspired trig scoring works on real Llama-3 KV cache." |
| 2 (~1 day) | "…without measurable quality loss on MMLU." |
| 3 (~$5–10) | "…across multiple modern open-weight models and production traffic shapes." |
| 4 (~1 wk eng + 1 GPU-day) | "TurboQuant 3-bit polar quant runs on GPU at v3-equivalent compression." |
| 5 (~3 days eng + 1 GPU-day) | "Combined CTM+ + TurboQuant + CTXL stack delivers ≥5× effective serving capacity over bf16+LRU at matched quality." |
| 6 (~1 GPU-day) | "…and beats every off-the-shelf vLLM KV-quant or eviction policy on the Pareto frontier." |
| 7 (months) | Partner-validated production case study. |

The roadmap explicitly distinguishes algorithm-layer evidence
(steps 1–3, what CTM+ Phase 4 produces) from system-layer
evidence (steps 4–6, the TurboQuant + CTM+ + CTXL stack the
architecture documents project an 8.8× capacity claim for) from
product-market evidence (step 7). Any "game-changer" framing
is reserved for after step 6 with step 7 in flight; everything
earlier stays inside the narrower per-step claims above.

## §6 Reproducer for everything in §1

```
Repository:  github.com/rasaha/symbolu
Branch:      claude/safety-state-machine-Rrvj2 (canonical)
Mode A:      cd CTM_plus/Bench && python -m ctm_bench \
                 --tier-config hbm_hbf_nvme \
                 --output-dir bench_out/round5_hbf_stress
             (see bench_out/RESULTS.md §5 for the 48-cell summary)
Mode B:      cd CTM_plus/Bench && ./scripts/run_mode_b.sh --quick
             (LRU only on vLLM 0.5+; CTM+ cells fail fast — see §3)
Cross-check: python -m ctm_bench.scripts.latency_cross_check \
                 --mode-b-dir <mode_b_run_dir> \
                 --mode-a-summary bench_out/round4_multi_seed/multi_seed_summary.json
Tests:       cd CTM_plus/Bench && python3 -m pytest tests -q
             (101 tests covering Mode A, the harness, and the
              cross-check tool)
```

Cite Mode A numbers with the round directory and seed; cite
Mode B numbers with the timestamped run directory and the
explicit `harness/timing-only` qualifier. Never cite a Mode B
number as a CTM+ result — it isn't one.
