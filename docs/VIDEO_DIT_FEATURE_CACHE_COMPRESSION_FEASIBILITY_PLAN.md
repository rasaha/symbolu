# Protected Compression of Reused Feature Caches in Video Diffusion Transformers — Pre-Registered Feasibility Study

**Internal engineering plan. Bounded research decision, not a product declaration.** This document
pre-registers a study to answer one narrow question and nothing more. It does **not** name a product, and
it does **not** assert novelty, patentability, or commercial value — those are explicitly out of scope
until measurement (§14). Where this study builds on the existing KVPro feasibility discipline
(`KVPRO_VIDEO_UNDERSTANDING_FEASIBILITY_PLAN.md`), it reuses the *method* (pre-registered gates, frozen
thresholds, CPU-testable verdict logic, evidence tiers) — it does **not** reuse or modify the KVPro core.

> **Final framing (required).** This study evaluates whether protected compression improves a persistent
> video-DiT cache **under the same compute-skipping policy**. It does not assume novelty, and it does not
> treat compression as an alternative to caching or skipping.

---

## 1. Research question

> Protected low-bit encoding plus explicit reconstruction-error admission **may** reduce the capacity and
> data-movement cost of **persistent cross-step feature caches** in video diffusion transformers **while
> preserving most of the compute-skipping and output-quality benefit** of the original full-precision
> cache.

The study is specifically about **tensors that are stored and reused across denoising steps.** It is
**not** about: model-weight quantization · ordinary one-pass activation quantization · standard
latent-space compression · FlashAttention · VAE tiling · generic CPU model offload · compressing
temporary tensors that are never reused.

## 2. Correct comparison framing

**Do not** frame this as *compression vs. skipping computation.* Caching already skips computation by
reusing a stored/predicted tensor; compression may reduce the cost of **storing and moving** that reused
tensor. The comparison is therefore always:

> **Full-precision cached features vs. compressed cached features under the *same* cache/reuse schedule.**

Compression and compute-skipping are **potentially complementary.** Every variant in the baseline ladder
(§6) holds the cache schedule fixed and changes only the *representation* of the cached bytes.

## 3. Novelty discipline

We do **not** state that the intersection is "unclaimed," "novel," or "greenfield." The permitted
statement is:

> A potentially differentiated technical intersection **may** exist in applying protected low-bit
> encoding and explicit reconstruction-error admission to **persistent cross-step video-DiT cache
> objects**, but **novelty has not been established.**

The prior-art matrix (summary below; full per-system detail in
[`VIDEO_DIT_CACHE_PRIOR_ART_MATRIX.md`](VIDEO_DIT_CACHE_PRIOR_ART_MATRIX.md)) separates **paper-literature
analysis from patentability analysis.** Literature coverage does not establish freedom-to-operate or
patentability; **a professional patent search would still be required** and is out of scope here (§14).

**Summary matrix** (columns: cached object · reuse decision · compression/quant method · error control ·
video · systems target · what remains potentially different):

| System | Cached object | Reuse decision | Compression method | Error control | Video | What remains potentially different |
|---|---|---|---|---|---|---|
| **DeepCache** | U-Net high-level features | Fixed cadence | **None** (FP reuse) | None | Image (U-Net) | Adds low-bit + error-gated reuse of the cached tensor |
| **FORA** | DiT attn/MLP outputs | Fixed interval | **None** (FP reuse) | None | Image/Video DiT | Compresses the cached object, not just reuses it |
| **TGATE** | Cross-attention output | Converged-step gating | **None** | Heuristic step split | Image | Low-bit + protected encoding of the cached CA output |
| **TeaCache** | Transformer output | Timestep-embedding-aware skip | **None** | Embedding-distance heuristic | Video DiT | Compression of the reused tensor + reconstruction-error admission |
| **ToCa / DuCa** | Token-wise features | Token-importance reuse | **None** | Token scoring | Image/Video | Bit-level compression + protected channels/tokens |
| **Δ-DiT** | Feature **deltas** | Front/back-block schedule | **None** (FP deltas) | None | Image DiT | Low-bit + protected encoding of the delta object itself |
| **PAB** | Attention outputs | Pyramid broadcast across steps | Broadcast heuristic | None | **Video DiT** (Open-Sora) | Compresses the broadcasted/cached attention state |
| **SVDQuant** | **Weights + activations** | n/a (one-pass PTQ) | 4-bit + **low-rank outlier branch** | Static | Image DiT | Applies outlier-absorbing idea to the **cross-step cache object**, not weights/activations |
| **Q-DiT** | Weights/activations | n/a (PTQ) | Mixed-grain quant | Static calibration | Image DiT | Target is the reused cache, not PTQ of the model |
| **PTQ4DiT** | Weights/activations | n/a (PTQ) | Channel-salience quant | Static calibration | Image DiT | Same distinction — cache object, cross-step, gated |
| **ViDiT-Q** | Weights/activations | n/a (timestep-aware PTQ) | Timestep/channel quant | Static | **Video DiT** | Same distinction — persistent cache, admission gate |
| Recent cache/hidden-state compression | Varies (LLM KV, hidden states) | Varies | Low-bit / low-rank | Varies | Mostly text/LLM | Video-DiT cross-step cache + protected+gated combination |

**Reading of the matrix (pre-measurement, honest):** the *caching* systems (DeepCache/FORA/TeaCache/
Δ-DiT/PAB/ToCa) overwhelmingly reuse features at **full precision** — they decide *when* to reuse, not
*how densely to store*. The *quantization* systems (SVDQuant/Q-DiT/PTQ4DiT/ViDiT-Q) compress **weights
and one-pass activations**, not a persistent cross-step cache. The combination this study tests — low-bit
**protected** encoding **plus a reconstruction-error admission gate** applied to the **persistent
cross-step cache object** — is not obviously covered by any single row, **but that is a literature
observation, not a novelty or FTO finding.**

## 4. Two-stage feasibility structure

> **A CPU harness cannot establish whether the workload is capacity-, bandwidth-, communication-, or
> compute-bound.** (Stated verbatim per plan requirement.)

### Stage A — representation feasibility (CPU-testable)

From captured cross-step cache tensors, determine whether the representations have compressible
structure. Measured on CPU (`analyze_cache_compressibility.py`): tensor dims by layer/step; bytes per
cached object; total persistent cache residency; delta magnitude between reusable steps; channel-wise and
token-wise outlier concentration; spatial and temporal redundancy; entropy and dynamic range; per-channel
vs per-block quant error; uniform INT8/INT4 reconstruction error; protected-channel reconstruction error;
low-rank residual reconstruction error; error accumulation over repeated reuse; reconstruction-gate
admission/rejection rates. **Evidence tier: Measured — CPU tensor analysis.**

### Stage B — systems feasibility (GPU-only)

On a real GPU with an actual cache-enabled video-DiT pipeline, measure: peak HBM; persistent cache HBM;
cache read/write bytes; HBM-bandwidth utilization; compression/decompression latency; kernel time;
end-to-end generation time; PCIe/NVLink transfer volume where applicable; max frames / resolution / batch;
cache hit/reuse rate; VBench, FVD, and task-specific quality; human-visible temporal artifacts where
practical. **Evidence tier: Measured — GPU profiling / Measured — end-to-end generation.**

## 5. Candidate models

Selection after repository + environment inspection (this repo already targets Qwen-family LLMs; it has
no video-DiT integration, so we pick a **diffusers-native** pipeline for reproducibility).

- **PRIMARY: CogVideoX (CogVideoX-2b / -5b).** Diffusers-native (reproducible inference, standard eval
  hooks); a true DiT whose transformer-block **hidden states and attention outputs are cleanly hookable**
  (read-only forward taps, no math change); diffusers ships cross-step cache methods
  (pyramid-attention-broadcast / faster-cache) to instrument as baseline B and strong baseline F;
  single-GPU feasible (2b on ~24–40 GB, 5b on 40–80 GB); VBench-supported.
- **SECONDARY: Wan2.1 T2V-1.3B.** Small, diffusers-native, feasible tensor instrumentation — a
  cross-model sanity check so a single-model result is not over-generalized.
- Alternates considered: **Open-Sora** (own repo, STDiT + PAB — heavier setup), **HunyuanVideo** (large,
  higher hardware bar). Named only as alternates; **we do not claim support for all families** (§14).

**Why CogVideoX was chosen:** lowest-friction reproducible instrumentation of a real video-DiT cross-step
cache on single-GPU hardware, with an existing strong cache baseline in the same framework.

## 6. Baseline ladder

Identical prompts, seeds, scheduler, denoising steps, cache schedule, resolution, frame count, and eval
pipeline across all variants. Only the cached-byte **representation** changes.

- **A. No-cache baseline** — full computation every step. Reference quality/latency/memory.
- **B. Existing FP16/BF16 cache** — the selected published reuse policy, **no compression**. Establishes
  the value and cost of ordinary caching.
- **C. Uniform low-bit cache** — quantize the cached representation uniformly (INT8; INT4 where
  numerically feasible). Determines whether simple quantization already suffices.
- **D. Protected low-bit cache** — bounded subset of high-error/high-importance channels/tokens kept
  higher-precision, remainder compressed. Measures the incremental value of protection.
- **E. Protected cache + reconstruction-error gate** — admit reuse only when reconstructed-cache error is
  within the **frozen** acceptance rule. Measures the incremental value and cost of explicit admission.
- **F. Strong existing acceleration baseline** — the chosen existing cache/broadcast/prediction/
  selective-recompute method at its recommended config. Prevents comparison only against weak baselines.

**Decisive deltas reported:** **C − B** (ordinary compression benefit and quality loss) · **D − C**
(incremental value of protected representation) · **E − D** (incremental value of reconstruction gating) ·
**E vs F** (value against a strong existing method).

## 7. Cache-object scope

Instrument and evaluate **separately** (never averaged into one number): residual-block features ·
transformer hidden states · attention outputs · cross-attention outputs · temporal-attention outputs ·
feature deltas · predicted residuals. Identify which object dominates **HBM residency**, **bandwidth**,
**transfer volume**, **reconstruction sensitivity**, and **end-to-end quality** — these need not be the
same object. The analyzer keys every metric by `cache_object` and reports the residency-dominant object.

## 8. Protected-representation experiments

Test protection policies **independently**: top-error channels · top-energy channels · top-outlier
channels · token-wise saliency · temporal saliency · layer-specific fixed masks · timestep-specific masks
· hybrid channel-plus-token. Also compare scaling granularity (per-tensor / per-block / per-channel),
symmetric vs asymmetric quantization, and direct-feature vs delta vs quant-plus-low-rank-residual. **Do
not presume the KVPro protection policy transfers unchanged** — the goal is to determine whether *any*
protected representation adds measurable value over uniform quantization on these objects (gate G5).

## 9. Error-gate design

The reconstruction-error gate is **deterministic and pre-registered** (`dit_cache_lib.gate_admit`).
Candidate inputs: relative L2 error · cosine similarity · maximum channel error · protected-channel
residual · temporal-delta error · layer sensitivity · timestep sensitivity. On evaluation the gate may:
admit cached reuse · fall back to full-precision cache · recompute the feature · reduce the reuse
interval. **The gate must never silently admit an object that violates the frozen acceptance rule** —
violation returns a fallback action, tested in `test_gate_admits_good_rejects_bad`. Measured: admission
rate · false-admission rate · recompute rate · quality preserved · latency overhead · memory overhead.

## 10. Pre-registered go/no-go gates

Thresholds are **frozen before** evaluating protected compression. First run a **calibration phase**
(`--calibrate`, see README) to estimate baseline run-to-run quality variation, metric noise, model/prompt
sensitivity, and profiling variance; **then** freeze thresholds (`verdict.freeze` → paste into
`FROZEN_SHA256`). `verdict.assert_gates_frozen` refuses to run against an unfrozen or post-hoc-edited gate
set (tested). **Do not tune final thresholds after seeing candidate results.**

- **G1 — cache materiality.** The reusable cache must be a meaningful constraint in ≥1 dimension: HBM
  capacity, HBM bandwidth, CPU–GPU transfer, multi-GPU communication, or max frames/resolution/batch. If
  operationally negligible, **STOP**. *(Bound-ness is GPU-only; CPU can only model the capacity side.)*
- **G2 — net compression.** Meaningful net density **after** scales, metadata, protected values, gate
  metadata, and temporary buffers. If trivial, **STOP**.
- **G3 — quality.** Compressed-cache config within the **frozen** quality margin vs the full-precision
  cache. Thresholds from calibration, not invented post hoc. *(CPU gives a tensor-fidelity proxy; output
  quality is Stage B.)*
- **G4 — systems value.** Improves ≥1 real system outcome (peak HBM, max frames, resolution, batch,
  transfer volume, latency, throughput) without unacceptable regression. **GPU-only.**
- **G5 — protected-method value.** Protected compression **materially outperforms** uniform low-bit. If
  uniform INT8/INT4 already meets quality+systems requirements, **STOP the protected branch.**
- **G6 — strong-baseline value.** Improves the memory–quality–latency **Pareto frontier** vs the strong
  existing method (F). If not, **do not** continue toward productization or patent claims. **GPU-only.**

## 11. Required verdicts

Exactly one, no ambiguous "promising":

- **STOP — cache not material**
- **STOP — cache material but not compressible**
- **STOP — uniform compression already sufficient**
- **STOP — protected compression fails quality**
- **STOP — compression overhead erases systems benefit**
- **CONTINUE — representation feasibility only**
- **CONTINUE — systems feasibility demonstrated**
- **CONTINUE — differentiated result requiring prior-art and patent review**

`verdict.decide` implements this mapping deterministically. **CPU evidence alone can reach at most
`CONTINUE — representation feasibility only`;** the two stronger CONTINUE verdicts require Stage-B GPU/e2e
evidence, by construction.

## 12. Implementation deliverables

1. This plan — `docs/VIDEO_DIT_FEATURE_CACHE_COMPRESSION_FEASIBILITY_PLAN.md`
2. Prior-art comparison table — §3 above + `docs/VIDEO_DIT_CACHE_PRIOR_ART_MATRIX.md`
3. Tensor-capture specification — §"Tensor-capture spec" below
4. GPU capture script — `scripts/kvpro_video_dit_cache/capture_dit_cache.py`
5. CPU analysis harness — `scripts/kvpro_video_dit_cache/analyze_cache_compressibility.py` (+
   `dit_cache_lib.py`)
6. Deterministic verdict logic — `scripts/kvpro_video_dit_cache/verdict.py`
7. Unit tests — `scripts/kvpro_video_dit_cache/test_cache_compression_cpu.py` (metadata validation,
   quant/dequant, protected-channel encoding, net-byte accounting, reconstruction metrics, error-gate
   behavior, gate freezing, verdict generation)
8. Results template — `artifacts/video_dit_cache/RESULTS_TEMPLATE.md` (all evidence fields `NOT RUN` /
   `NOT MEASURED` / `REQUIRES GPU`)
9. README — `scripts/kvpro_video_dit_cache/README.md`

### Tensor-capture spec

One `.pt` per `(cache_object, layer)`, a dict:

| Key | Type | Meaning |
|---|---|---|
| `cache_object` | str | one of `dit_cache_lib.CACHE_OBJECTS` (§7) |
| `layer` | int | transformer block index |
| `step_indices` | list[int] | denoising steps snapshotted (the reuse schedule's cache points) |
| `tensor` | float `(T,N,C)` | T cached snapshots · N spatial/token positions · C channels |
| `dtype` | str | source dtype `bf16`/`fp16`/`fp32` (for honest byte accounting) |
| `meta` | dict | model, num_frames, steps, prompt, seed |

Positions may be subsampled to a cap (`--max-positions`) to bound tensor size; residency metrics use the
captured `dtype` for baseline bytes. `feature_delta` is derived as consecutive-step differences.

## 13. Evidence discipline

Every result is labeled exactly one of: **Measured — CPU tensor analysis** · **Measured — GPU profiling**
· **Measured — end-to-end generation** · **Modeled — capacity projection** · **Inferred — not workload
validated** · **Not measured** · **Requires external patent review**. We do **not** present modeled
capacity as measured deployment capacity, tensor reconstruction as output-video quality, CPU analysis as
GPU systems evidence, emulated compression cost as fused-kernel performance, or one model's result as a
universal video-diffusion conclusion.

## 14. Scope control

This phase exists **only** to decide whether the hypothesis deserves further work. We do **not**: build a
polished product; add investor-facing claims; modify KVPro; file or draft patent claims; claim a
commercial wedge; benchmark many model families; optimize kernels before G1–G3 pass; or expand into image
diffusion unless the video-DiT study establishes value.

## 15. Current status

**Harness built; CPU verdict/analysis logic unit-tested (21/21 pass); model capture is pod-only and not
yet run.** No workload result exists yet — the results template is entirely `NOT RUN` / `REQUIRES GPU`.
The gates in `verdict.py` are **DEFAULT pre-registration values with a placeholder freeze hash**: the
study's first pod step is the calibration phase, after which thresholds are frozen (§10) before any
protected-compression variant is evaluated.
