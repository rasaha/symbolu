# Kernel 6c.3C — FA-integrated paged protected-K INT4 decode (design shell)

> **Status: design shell, base implementation TBD pending PR triage.**
> Replaces `KERNEL_6C3A_DESIGN.md`'s "model-level bypass" architecture
> after §20.6.3 closed 6c.3A as not competitive (cell D D/A = 0.55× at
> S=32k vs FP16 FA; head-to-head microbench showed our Triton kernel
> 1.75×–8.41× slower than `vllm.vllm_flash_attn.flash_attn_with_kvcache`).
> Architectural lesson: competitive INT4 KV doesn't *replace* the
> attention kernel — it *modifies* the attention kernel to dequant
> INT4 inline at register level (KIVI, KVQuant, Atom all follow this
> pattern; vLLM's `kv_cache_dtype="fp8"` is the same shape for FP8).
> 6c.3C lands the FA-integrated path.

## 1. Context — what 6c.3A taught us

The 6c.3A v1 bypass intercepted `Attention.forward` and ran a custom
Triton kernel on a shadow contiguous INT4 cache. The §20.6.3 verdict:

* The bypass pays an *additional* per-call wrapper overhead
  (quantize-append + 3 contiguous copies + dtype casts ≈ 0.37 ms/call
  at S=32k) on top of a kernel that is itself slower than FA.
* Even at zero wrapper overhead, the bypass loses to FP16 FA because
  the kernel itself is 4–8× slower than `flash_attn_with_kvcache`.
* The §20.6.2 microbench's "1.30× faster than FP16" claim was vs
  `F.scaled_dot_product_attention`'s GQA fallback backends (math /
  mem-efficient), **not** vs the FA kernel vLLM actually calls.

The §20.4.2 / §20.4.3 *algorithm* result (static protected-K + INT4
KV recovers FP16 quality at 32k) is unchanged and remains the
deliverable. 6c.3C is the delivery vehicle.

## 2. Required architecture

Six architectural properties the base implementation must satisfy.
The PR triage in §4 scores each candidate against these.

| Property | What it means |
|---|---|
| **a. Native vLLM / FA integration** | Kernel called via vLLM's attention backend dispatch, not via a wrapper that intercepts `Attention.forward`. The INT4 dequant happens inside the attention kernel at register level (not in a pre-kernel CPU/Python step). Entry point looks like `flash_attn_with_kvcache(...)`-shaped, with optional INT4 args. |
| **b. Actual INT4 paged KV storage** | K and V live in vLLM's block-managed paged cache as INT4 packs (4 bits/element × token × head × dim). Block table threading inherited from FA. No shadow contiguous cache. Memory savings are real (4× vs FP16 for unprotected channels) and reported. |
| **c. Static protected-K mask** | A `(H_kv, D)` int8 mask determines which channels are stored in higher precision. Mask is per-sequence-static (frozen after prefill). Matches the §20.4.3 algorithm verbatim. |
| **d. INT4 unprotected K/V** | Asymmetric INT4 with group_size_k = group_size_v = 32 (matches §20.4 measured config). Unprotected channels (mask = 0) are stored INT4; the rest are stored in FP16/BF16 (K only — V is INT4 throughout). |
| **e. Protected-K higher-precision side channel** | The ~4% of K channels with mask = 1 are loaded as FP16/BF16 alongside the INT4 read inside the kernel, merged before the qK dot. Layout: dense `(B, H_kv, S, D)` with mask, or compact `(B, H_kv, S, n_protect)` + index list — TBD in §5. |
| **f. GQA support** | H_q > H_kv (Qwen2.5: 28/4) handled either via the FA seqlenq-ngroups swap (so the kernel sees H_q == H_kv) or via in-kernel head broadcast. Either is acceptable; both work for decode. |

## 3. v1 scope — locked, narrow

| Axis | v1 |
|---|---|
| **Phase** | Decode only. Prefill stays FP16/BF16 through stock `vllm_flash_attn`; cache write-back at end of prefill quantizes to INT4. No prefill kernel changes. |
| **Quant** | Asymmetric uniform INT4, group_size_k = group_size_v = 32 |
| **Protected K** | Static mask (per §20.4.3), top-~4% magnitude channels in model dtype (FP16/BF16) |
| **Protected V** | None — V is INT4 throughout |
| **Model** | Qwen2.5-7B first (H_q=28, H_kv=4, D=128, BF16). One new bf16-hdim128 kernel instantiation. |
| **GQA** | Inherited from FA (seqlenq-ngroups swap or equivalent) |
| **Paged KV** | Inherited from FA (`block_table`, `resolve_thread_kv_page_slice_offset` or equivalent) |
| **Validation** | (a) cell-D-style throughput: vLLM INT4-FA vs vLLM FP16-FA vs vLLM FP8-FA at S ∈ {2k, 16k, 32k}, B=1. (b) §20.4.3 32k-needle quality re-run on the new kernel. (c) Real KV memory measurement (`nvidia-smi` + `torch.cuda.max_memory_allocated`). |

**Out of scope for v1:**

- Dynamic protected-K masks (per-step mask updates)
- Pre-RoPE quantization
- FP4 / NVFP4 storage
- Speculative decoding
- Multi-model sweep beyond Qwen2.5-7B
- Prefill kernel modifications
- FA3 / Hopper instantiations (sm80 only)
- Symmetric quantization variants
- Group sizes ≠ 32

Each item above is a deliberate non-goal; do not creep.

## 4. Base implementation — TBD pending PR triage

Two candidate bases:

* **A. Fork `vllm.vllm_flash_attn`.** Clone one existing decode-kernel
  instantiation (`flash_fwd_split_hdim128_bf16_sm80.cu`) into an
  `_int4kv` variant. Replace the two `FLASH_NAMESPACE::copy(...,
  tKgK/tVgV, ...)` sites in `compute_attn_1rowblock_splitkv` with an
  INT4 + dequant + protected-K-sidecar read. Plumb scale/offset/mask
  pointers through `Flash_fwd_params`. Add an `_int4kv` dispatch arm
  in `flash_api.cpp::mha_fwd_kvcache`. Auto-picked up by the
  `flash_fwd_*.cu` glob in `CMakeLists.txt`.
* **D. Extend an open vLLM INT4 KV PR.** Four candidates exist in
  vLLM's PR queue (per §20.6.3 research): #39074, #39668, #40633,
  #40835 — all draft / needs-rebase as of May 2026. If any is ≥60%
  aligned with the required architecture in §2 and the v1 scope in
  §3, extending it is shorter than starting from A.

**Triage rubric.** Each PR scored 0–5 against:

| Axis | What it tests |
|---|---|
| License | Compatible with vLLM's redistribution (Apache 2.0 / BSD) |
| Paged KV support | Block-table-aware read; integrates with vLLM's block manager |
| FA integration | Built on `vllm_flash_attn` / FA-fork or FlashInfer / custom |
| GQA / MQA | Handles H_q > H_kv natively or via swap |
| INT4 K/V layout | Asymmetric vs symmetric; group_size; alignment with §20.4 |
| Scale/offset layout | Per-block vs per-token; key into paged blocks vs sequence |
| Protected-K extensibility | How invasive is adding the FP16 sidecar? |
| Invasiveness | How big is the diff against vLLM main? Affects rebase pain |
| Local runnability | Does the PR actually build + pass smoke tests today? |

**Decision rule.** Each PR scored ≥60% (≥27 / 45) of the maximum on
the rubric is a candidate base. If any candidate scores higher than
A on integration cost and license combined, pick that PR. Otherwise,
commit to A.

The triage outcome (with per-PR scores and one-paragraph rationale)
lands in §4 of this document and replaces this paragraph.

## 5. Architectural decisions deferred until base is chosen

These are the choices the base implementation forces. Listed
unresolved so the PR triage can score each candidate's stance.

### 5.1 Cache write-time vs lazy quantization

- **Write-time:** Prefill output quantized to INT4 at block boundary.
  Decode is then pure read. Matches `ROUTE_A_VLLM_CACHE_KV_PLAN.md`.
- **Lazy:** K/V written FP16/BF16, quantized just before decode
  attention reads. Costs per-decode quantize work but simplifies
  cache layout.

Tradeoff: write-time is what KIVI / KVQuant / Atom do; lazy is
simpler but quantize-on-decode cost is exactly what 6c.3A v1 paid.
Default: **write-time**, but the PR may dictate.

### 5.2 Scale / offset side-channel keying

- **By physical block_id:** Side-channel tensor `(num_blocks,
  H_kv, n_groups_per_block, D)` indexed by `block_table[i, n_block]`.
  Compatible with vLLM's prefix-cache reuse.
- **By logical (seq_id, position):** Side-channel grows per-sequence,
  not paged-aware. Incompatible with prefix-cache.

Tradeoff: physical is correct for vLLM; logical is what 6c.3A v1 used
and won't transfer.

### 5.3 Block size vs group size

- **block_size = 32:** Each vLLM block IS one quant group along seq.
  Cleanest; one scale/offset pair per (block, H_kv, D-group).
- **block_size = 16 (vLLM default), group_size = 32:** Quant group
  spans two adjacent blocks. Either constrain block allocation to
  always-pair, or accept per-block sub-grouping (different boundaries
  → re-validate quality).
- **block_size = 16, group_size = 16:** Smaller groups, more
  scale/offset overhead; quality re-validation needed.

Default: **block_size = 32, group_size = 32** (matches §20.4 exactly,
quality bit-identical). The PR may use a different block size; if so,
note in triage.

### 5.4 GQA path

- **Seqlenq-ngroups swap (current FA pattern):** `mha_fwd_kvcache`
  reshapes (B, 1, H_q, D) → (B, ngroups, H_kv, D) before calling the
  kernel, so the kernel sees H_q == H_kv. INT4 path inherits the
  swap; no kernel changes needed.
- **In-kernel head broadcast:** Kernel iterates H_q heads and
  broadcasts one H_kv to multiple H_q. More complex, no advantage for
  decode.

Default: **inherit the swap**.

### 5.5 Protected-K layout

- **Dense `(B, H_kv, S, D)` FP16 + mask:** Simple, FA already reads
  full K tensor; the mask gates which channels merge with the
  dequant'd INT4. Wastes HBM on unprotected channels (stored zero or
  whatever).
- **Compact `(B, H_kv, S, n_protect)` + index list `(H_kv,
  n_protect)`:** Memory-efficient (only ~4% × D = ~5 channels per
  head stored). Indexed gather in the kernel — extra indirection.

Tradeoff: dense is simple but loses some of the memory savings INT4
buys back; compact is what's worth doing if HBM is the constraint.
Default: **compact**, but defer to PR.

### 5.6 Dispatch entry point

- **Extend `flash_attn_with_kvcache` with optional INT4 args:** One
  Python entry point; INT4 path triggered when scale/offset/mask are
  passed.
- **New function `flash_attn_with_int4_kvcache`:** Separate entry
  point. Cleaner diff; less risk of breaking existing FA callers.

Default: **new function**, to minimise diff against upstream.

## 6. Honest measurement claims

What 6c.3C must claim if v1 lands successfully:

* **Throughput.** "vLLM tokens/sec with protected-K INT4 KV is ≥X×
  of FP16 KV at S=32k decode, B=1, Qwen2.5-7B." X is measured, not
  predicted. Target: ≥1.0× (parity); stretch ≥1.2×.
* **Memory.** "vLLM KV pool at S=32k uses Y GB with INT4 protected-K
  vs Z GB with FP16, a ratio of Y/Z." Z is measured; target Y/Z ≤
  0.30 (3.3× compression after accounting for ~4% FP16 sidecar +
  scales/offsets).
* **Quality.** "32k needle-in-haystack pass-rate matches §20.4.3
  baseline (FP16 = INT4-protected, within ±2%)."

What 6c.3C must NOT claim:

* Prefill throughput improvements (out of scope).
* Multi-model generalization (Qwen-only in v1).
* FP4 / NVFP4 (out of scope).
* "1.x× faster than FP8" — only claim if measured, against the same
  vLLM serving stack.

## 7. Open questions for design — fill during PR triage

1. Which of the 4 vLLM INT4 KV PRs (#39074, #39668, #40633, #40835)
   is closest to the required architecture in §2?
2. If a PR is chosen, what design choices in §5 does it already
   force? Which remain to decide?
3. If A is chosen, do we name the new entry point
   `flash_attn_with_int4_kvcache` or fold it into
   `flash_attn_with_kvcache`?
4. Where does the static protect-mask come from at decode time —
   computed in vLLM at prefill end and threaded into the attention
   backend, or precomputed offline and loaded as a model attribute?
5. What's the cost-benefit threshold for compact vs dense protected-K
   layout? At ~4% protect, dense wastes ~25% of FP16 KV's
   per-channel allocation; compact saves it but adds gather cost.
6. Bench harness reuse: does `kernel_6c3a_throughput.py` extend to
   6c.3C, or do we need a new harness that lets vLLM own the cache
   end-to-end?

## 8. Files this design will produce (next step)

After PR triage and base lock:

* `KERNEL_6C3C_DESIGN.md` — §4 filled in with chosen base + scores
* `KERNEL_6C3C_RUNBOOK.md` — engineering checklist: build the
  forked wheel / extend the PR; smoke-test the modified kernel;
  wire into vLLM; throughput + quality validation
* In the chosen base (vllm_flash_attn fork OR PR fork):
  - `flash_fwd_split_hdim128_bf16_int4kv_sm80.cu` (new) or
    equivalent in the PR's structure
  - `flash.h` extension with quant fields
  - `flash_api.cpp` dispatch arm
  - `flash_attn_interface.py` Python wrapper
* On the vLLM side (separate work item):
  - INT4 paged KV storage in vLLM's block manager (extends
    `ROUTE_A_VLLM_CACHE_KV_PLAN.md` to land natively, not as a shadow
    cache)
  - Quantize-at-write hook at prefill end
  - Attention backend extension that calls the modified FA
* Bench harness:
  - Extend or replace `kernel_6c3a_throughput.py` for a true vLLM
    end-to-end measurement (vLLM owns the cache; no shadow caches)
  - §20.4.3 32k-needle quality re-run script (existing one with new
    backend flag)
