# Kernel 6c — fused protected-K INT4 decode-attention kernel: design & test brief

Engineer's brief for Experiment 6c. Synthesises the in-house plan and an
external review (ChatGPT action plan, 2026-05) — they agree closely;
divergences are flagged inline.

## 1. Goal & scope

Convert the **measured** protected-K quality/compression result (§20.4.2–4:
100% needle at 16k/32k/64k, ~3.1× compression, validated static + on
Mistral) into **actual decode throughput**, by eliminating the per-call
dequant overhead of route-A's PyTorch fallback.

Scope — keep it narrow:
- **Decode only** (S_q = 1, large S_kv). Decode attention is
  bandwidth-bound; that is where a 4-bit KV read beats a 16-bit read. Do
  **not** touch prefill (compute-bound; no win there).
- **Protected-K specifically**, not a generic INT4 kernel: V is uniform
  INT4; most K channels are INT4; a **static** ~4% set of K channels is
  FP16. The static mask is the §20.4.3 result — **never** recompute it at
  runtime.
- Single config. No dynamic channel selection, no decode-side sampling
  hacks, no broad benchmark expansion.

## 2. The numerical contract — what "correct" means

The kernel must reproduce, within FP16 rounding, the route-B protected-K
result that §20.4.2–4 measured. That result is captured by
`fused_int4_attention_reference(...)` in
`KVPolicy/kv_policy/int4_fused_attention_sketch.py` — call it with the
`k_fp16` / `k_protect_mask` arguments. Numerically:

```
k_effective = where(protect_mask, k_fp16, dequant_int4(k_packed, k_scale, k_offset))
attn_out    = softmax(Q · k_effectiveᵀ · scale) · dequant_int4(v_packed, v_scale, v_offset)
```

This mirrors `_restore_outlier_channels` in `int4_per_channel_hf_cache.py`.
The reference is pure PyTorch, runs on CPU, and is the layer-1 test oracle.

**Terminology fix** (the external review conflated these): *route-B* is the
HF `DynamicCache` **quality-measurement vehicle** — it stores FP16 and has
no throughput meaning. The kernel's *numerical* oracle is route-B's
protected-K **result** (the reference function). The *throughput* baseline
the kernel must beat is **route-A's naive dequant fallback** and **FP8** —
route-B is never a throughput cell.

## 3. Memory layout (static protected-K)

Per (layer, head, KV block):

```
K_int4_rest    : remaining K channels, INT4-packed (uint8 nibble pairs)
K_scales       : per-(group, head, dim) scales  (+ offsets if asymmetric)
K_protected    : the protected K channels, FP16 — compact side-tensor
protect_mask   : (layer, head) → static bool/index set, fixed at calibration
V_int4         : V, INT4-packed
V_scales       : per-(token, head, group) scales (+ offsets)
```

Because the mask is **static** (§20.4.3), the channel partition is decided
once offline — the kernel never gathers/selects at runtime. v1 layout:
keep all D channels in `K_int4_rest` (protected slots unused) plus the
compact `K_protected` side-tensor; the kernel overlays the protected lanes.
A channel-partitioned layout (protected channels contiguous, Q permuted to
match) is a 6c.2 optimisation — not v1.

Watch the known snag: vLLM `block_size=16` vs KIVI `group_size=32`
misalignment — either move to `block_size=32` or get the group-index math
exactly right (`group_idx = global_token_idx // group_size`).

## 4. Computation path (per batch, per query head, decode token t)

```
A. Load Q (FP16/BF16) — small, stays FP16.
B. For each KV block (online / FlashAttention-style, no full logit buffer):
     logit_tile = dot(Q, K_effective_tile)
       where K_effective_tile is dequantized INT4 + FP16 protected
       channels, computed IN REGISTERS — never materialise a full
       dequantized K tensor.
   C. Causal bound — decode query attends over all cached positions.
   D. Online softmax across blocks:
        m_new = max(m_old, max(logit_tile))
        l_new = exp(m_old - m_new)·l_old + sum(exp(logit_tile - m_new))
        acc   = exp(m_old - m_new)·acc + sum(p_tile · dequant(V_int4_tile))
   E. V is dequantized inside the value-accumulation tile — not materialised.
F. Write FP16/BF16 attention output.
```

The fusion is the point: dequant happens in registers, inline in the dot
products — no INT4→FP16 round trip through HBM.

## 5. Implementation stages

**6c.1 — correctness-first fused kernel.** Triton (faster to write, ~70% of
CUDA perf, validates the algorithm + HBM access pattern). One batch/head
path, fixed `d_head`, static mask, online softmax, no fancy scheduling.
Pass when it matches the reference (§6 below, layer 1+2).
Recommended sub-order: get **uniform INT4** correct first (the existing
reference, no `k_fp16`/mask), then add the protected-K overlay — smaller
debugging surface.

**6c.2 — optimised decode kernel.** Vectorised INT4 unpack, coalesced
loads, channel-partitioned protected layout, shared-memory staging, block
size tuned for 16k–64k context. CUDA-promote only if Triton overhead vs the
FP16 FlashAttention baseline is > 5%.

**6c.3 — vLLM integration.** Only after the standalone kernel passes
correctness + perf. Behind a runtime flag, e.g.:
`--kv-cache-dtype protected_int4 --protected-k-fraction 0.04
--protected-k-mask static --attention-backend protected_k_fused`.

## 6. Testing — five layers

**Layer 1 — numerical, vs the reference.** Kernel output vs
`fused_int4_attention_reference` (with `k_fp16`/`k_protect_mask`). Random
inputs across a shape matrix: B ∈ {1,4}, S_kv ∈ {16,64,256,2048,4096},
GQA ratios, sym/asym, group sizes, protect fractions. **Pass: cosine ≥
0.999, max-abs-diff < 1e-3 (FP16), no NaN/Inf.** Fast, GPU, run constantly.

**Layer 2 — edge cases.** S_kv not divisible by group_size; block-vs-group
boundary misalignment; odd D; protect-mask empty (degenerates to uniform
INT4) and full (degenerates to FP16-K); S_kv = 1 first decode step.

**Layer 3 — end-to-end quality.** Kernel in route-A → run the existing §20
needle harness (`track_e_long_context.py`). Must reproduce §20.4.2–4: 16k
needle Qwen 100%, 16k needle Mistral = baseline, 32k/64k hold; short-context
MMLU sanity; perplexity sanity. **Do not invent a new benchmark.** If
layer 1 passed this is near-automatic — layer 3 catches *integration* bugs
(block-table indexing, scale-layout mismatch). Pass: matches route-B
protected-K; no regression to the K-INT4 failure mode (29%/stutter).

**Layer 4 — throughput (the real 6c gate).** Decode tokens/sec, four cells:
FP16 · FP8 (stock vLLM) · route-A naive dequant fallback · fused kernel.
Matrix: context 4k/8k/16k/32k/64k, batch 1/4/8/16 (memory permitting),
decode length 128/512, models Qwen2.5-7B + Mistral-7B-v0.3. The decisive
region is **long-context decode**.

**Layer 5 — profiling + memory.** Nsight Compute: confirm the kernel is
memory-bandwidth-bound, measure achieved HBM throughput vs the ~3.07×
analytic ceiling (`speedup_ceiling(k_protect_fraction=0.04)`), check
occupancy and load coalescing. Memory: actual peak GPU memory, KV
bytes/token/layer, max batch at fixed context, max context at fixed
batch — report **runtime** numbers, not just theoretical compression.

## 7. Success gates

| Gate | Pass condition |
|---|---|
| Correctness | matches the reference within cosine ≥ 0.999 / max-abs < 1e-3 |
| Quality | matches §20.4.2–4 protected-K (needle, no K-INT4 regression) |
| Compression | ~3.0×+ effective KV reduction, measured at runtime |
| Throughput vs route-A fallback | large improvement, near the ~3× analytic ceiling |
| Throughput vs FP8 | competitive or better in long-context / memory-bound decode |
| Integration | works behind a clean vLLM runtime flag |

Strongest honest claim if all gates pass:
> Fused protected-K preserves baseline long-context quality at ~3.1× KV
> compression and is throughput-competitive with FP8 in long-context decode.

Narrower claim if it beats route-A but not FP8:
> Fused protected-K is a memory-capacity feature, not yet the default
> throughput path.

## 8. What not to do

- Do **not** build a generic INT4 kernel as the deliverable (uniform INT4
  is only a 6c.1 stepping stone for debugging).
- Do **not** support dynamic protected-channel selection in v1 — §20.4.3
  showed a static set works; dynamic would kill kernel simplicity.
- Do **not** optimise prefill before decode.
- Do **not** hide protected-K gather/overlay overhead outside the benchmark.
- Do **not** claim "beats FP8" until layer-4 throughput is measured
  end-to-end.

## 9. Honest framing

Everything upstream of this kernel is now measured-green: quality (§20.4.2–4),
the analytic bandwidth ceiling (~3.07×, §20.4.2 6b). The kernel is the sole
remaining gate. It is ~1–2 weeks of GPU-kernel specialist work — a staffing
decision, not a script. Until layer-4 lands, "protected-K beats FP8" is a
compression-and-quality claim, not an end-to-end one.
