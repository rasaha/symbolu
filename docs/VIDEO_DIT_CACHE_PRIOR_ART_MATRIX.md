# Video-DiT Cache Compression — Prior-Art Matrix (literature analysis only)

**Companion to** `VIDEO_DIT_FEATURE_CACHE_COMPRESSION_FEASIBILITY_PLAN.md`. This is a **paper-literature**
comparison, deliberately kept separate from any patentability analysis. **Nothing here establishes
novelty, freedom-to-operate, or patentability.** A professional patent search is required before any such
claim and is out of scope for this feasibility phase.

The study's hypothesis (see plan §1): protected low-bit encoding **plus** an explicit reconstruction-error
admission gate, applied to the **persistent cross-step cache object** of a video diffusion transformer,
**under the same reuse schedule** — evaluated for capacity/data-movement benefit at preserved quality.

Per-system detail. Columns: **Cached object** · **Reuse decision** · **Compression/quant method** ·
**Error-control mechanism** · **Video support** · **Systems target** · **What remains potentially
different** (relative to the studied combination; a literature observation, **not** a novelty finding).

---

### Caching / step-reuse systems (decide *when* to reuse — mostly full-precision)

**DeepCache**
- Cached object: high-level U-Net feature maps.
- Reuse decision: fixed caching cadence across adjacent steps.
- Compression: **none** — features reused at full precision.
- Error control: none (heuristic cadence).
- Video: image U-Net (not a video DiT).
- Systems target: FLOP/latency reduction.
- Potentially different: adds **low-bit + protected encoding + error-gated** reuse of the cached tensor.

**FORA (fast-forward caching)**
- Cached object: DiT attention/MLP block outputs.
- Reuse decision: fixed reuse interval.
- Compression: **none** (FP reuse).
- Error control: none.
- Video: image/video DiT.
- Systems target: latency.
- Potentially different: compresses **how densely the cached object is stored/moved**, not just whether it is reused.

**TGATE**
- Cached object: cross-attention output.
- Reuse decision: gate at the "convergence" step; reuse thereafter.
- Compression: none.
- Error control: heuristic step split (semantics-planning vs fidelity).
- Video: image.
- Potentially different: low-bit **protected** encoding of the cached cross-attention state.

**TeaCache (timestep-embedding-aware cache)**
- Cached object: transformer output.
- Reuse decision: skip based on timestep-embedding distance.
- Compression: none.
- Error control: embedding-distance heuristic (no reconstruction check).
- Video: **video DiT**.
- Potentially different: **compression of the reused tensor** + a **reconstruction-error** admission gate (vs an input-side embedding heuristic).

**ToCa / DuCa (token-wise caching)**
- Cached object: token-level features.
- Reuse decision: per-token importance/error scoring.
- Compression: none.
- Error control: token scoring.
- Video: image/video.
- Potentially different: **bit-level** compression + protected channels/tokens on top of token reuse.

**Δ-DiT (delta caching)**
- Cached object: **feature deltas** between steps.
- Reuse decision: front/back transformer-block schedule.
- Compression: **none** — deltas kept full precision.
- Error control: none.
- Video: image DiT.
- Potentially different: **low-bit + protected** encoding of the **delta object** itself (a delta cache is exactly a `feature_delta` cache object in §7).

**PAB (Pyramid Attention Broadcast)**
- Cached object: attention outputs (spatial/temporal/cross).
- Reuse decision: broadcast attention across a pyramid of step ranges.
- Compression: broadcast heuristic (reuse, not compress).
- Error control: none.
- Video: **video DiT** (Open-Sora) — the strongest video-native reference.
- Systems target: latency/throughput.
- Potentially different: **compresses the broadcasted/cached attention state**; candidate strong baseline **F**.

---

### Quantization / PTQ systems (compress *weights & one-pass activations* — not a cross-step cache)

**SVDQuant**
- Cached object: **weights + activations** (not a cross-step cache).
- Reuse decision: n/a (one-pass PTQ).
- Compression: 4-bit + **low-rank branch absorbing outliers**.
- Error control: static low-rank residual.
- Video: image DiT.
- Potentially different: this study applies the **outlier-absorbing / low-rank-residual idea to the persistent cross-step cache object**, gated by reconstruction error — a different target than weight/activation PTQ. (Directly motivates our "quant + low-rank residual" branch, §8.)

**Q-DiT**
- Cached object: weights/activations.
- Reuse decision: n/a (PTQ).
- Compression: mixed-granularity quantization.
- Error control: static calibration.
- Video: image DiT.
- Potentially different: target is the **reused cache**, not model PTQ.

**PTQ4DiT**
- Cached object: weights/activations.
- Compression: channel-salience-aware quantization.
- Error control: static calibration.
- Video: image DiT.
- Potentially different: same distinction — a **cross-step cache object**, error-gated.

**ViDiT-Q**
- Cached object: weights/activations.
- Reuse decision: n/a (timestep-aware PTQ).
- Compression: timestep/channel-aware quantization.
- Error control: static.
- Video: **video DiT** — closest on the "video + timestep-aware quant" axes.
- Potentially different: quantizes the **model**, not a **persistent reused cache**, and has no reconstruction-admission gate.

**Recent cache-/hidden-state-compression systems (LLM KV caches, hidden-state compressors)**
- Cached object: LLM KV cache or transformer hidden states (mostly text).
- Reuse decision: varies.
- Compression: low-bit / low-rank / eviction.
- Error control: varies.
- Video: mostly text/LLM (this repo's KVPro is one such system for LLM KV).
- Potentially different: the **video-DiT cross-step diffusion cache** target, plus the **protected + error-gated** combination.

---

## Honest reading (pre-measurement)

- The **caching** systems decide *when* to reuse and overwhelmingly reuse at **full precision** — they do
  not compress the stored cache bytes.
- The **quantization** systems compress **weights and one-pass activations** — not a persistent
  cross-step cache, and without a reconstruction-admission gate.
- The specific combination under study — **protected low-bit encoding + reconstruction-error admission,
  on the persistent cross-step video-DiT cache object, under a fixed reuse schedule** — is not obviously
  covered by any single row above.

**This is a literature observation only.** It does **not** establish novelty, patentability, or
freedom-to-operate. Per the plan, a differentiated result (verdict *"CONTINUE — differentiated result
requiring prior-art and patent review"*) is precisely the trigger for a **professional prior-art and
patent search** — not a substitute for one.
