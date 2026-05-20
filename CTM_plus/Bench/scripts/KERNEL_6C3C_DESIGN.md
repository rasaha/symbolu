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

## 4. Base implementation — LOCKED: A (fork `vllm.vllm_flash_attn`)

### 4.1 PR triage outcome

Triaged 4 candidate vLLM PRs (research run 2026-05-20) against the
9-axis rubric in §4.2 below. **No PR clears the gate** (≥27/45 AND
scores ≥4 on Paged KV + FA integration + GQA). All four are
**Triton-only**; FA integration is 0–1 across the board. #39668
even has an explicit `test_flash_attn_rejects_int4_kv_cache` guard
that *registers* INT4 as a rejected dtype in FA. None provides what
6c.3C needs: dequant *inside* the FA kernel against a paged
block_table.

| PR | Author | State | License | Paged | **FA** | GQA | INT4 layout | Scale layout | Protect-K | Invasive | Runnable | **Total** |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| #39074 | JartX | open, stale | 5 | 4 | **0** | 4 | 4 (per-tok-head) | 3 | 2 | 3 | 3 | **28/45** |
| #39668 | lesj0610 | draft, needs-rebase | 5 | 4 | **1** | 3 | 5 (g=32 seq) | 4 | 3 | 3 | 1 | **29/45** |
| #40633 | JartX | open, needs-rebase | 5 | 4 | **0** | 4 | 4 (per-tok-head) | 3 | 3 | 3 | 2 | **28/45** |
| #40835 | JartX | open, stale | 5 | 4 | **1** | 5 | 4 (per-tok-head) | 3 | 3 | 2 | 2 | **29/45** |

(Full per-axis notes in the triage transcript; this table is the
audit summary.)

### 4.2 Verdict and base lock

**Pick: A — fork `vllm.vllm_flash_attn`, clone one decode-kernel
instantiation into an `_int4kv` variant, add INT4 dequant in the K/V
read sites, add protected-K FP16 sidecar.**

Concrete plan (per the source map in track-E research, 2026-05-20):

1. New file: `csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_sm80.cu`
   — cloned from the existing `flash_fwd_split_hdim128_bf16_sm80.cu`,
   with the two `FLASH_NAMESPACE::copy(..., tKgK/tVgV, ...)` sites
   replaced by an INT4 + dequant + protected-K read path. Auto-picked
   up by the `flash_fwd_*.cu` glob in `CMakeLists.txt` — no CMake
   edit needed for the instantiation.
2. `csrc/flash_attn/src/flash.h` — extend `Flash_fwd_params` with
   `k_scale`, `k_offset`, `k_fp16_protect`, `protect_mask`, `v_scale`,
   `v_offset`, `group_size_k`, `group_size_v`. Add `kIsInt4KV` trait.
3. `csrc/flash_attn/src/flash_fwd_launch_template.h` — at SHA
   720c948 the splitkv dispatch lives in the main launch template,
   not in a separate `_splitkv_launch_template.h` (which appears
   later on upstream main). Add the new `_int4kv` dispatch arm in
   `run_mha_fwd_splitkv_dispatch` here, plus a `static_switch.h`
   flag.
4. `csrc/flash_attn/flash_api.cpp` — INT4 dtype detection on
   `k_cache` / `v_cache`; plumb the new params into `Flash_fwd_params`;
   route to the `_int4kv` dispatch arm in `mha_fwd_kvcache`.
5. New Python entry point: `flash_attn/flash_attn_interface.py` —
   `flash_attn_with_int4_kvcache(...)` accepts INT4 K/V tensors plus
   scales/offsets/protect_mask. Cleaner diff than overloading
   `flash_attn_with_kvcache`.

### 4.3 Crumbs to mine from the rejected PRs

Each PR is rejected as a base, but specific patterns are worth
borrowing:

* **#39668 (lesj0610) — INT4 storage layout.** Closest to our §20.4
  config. Asymmetric INT4, 2 vals/byte packed `uint8`, FP16 grouped
  scales with **group_size = 32 along seq axis**. Use this layout
  verbatim. Look at the storage struct + alignment / padding logic.
* **#40835 (JartX) — GQA Triton reference.** Dedicated
  `_pth_attn_stage1_packed_gqa` kernel restores WMMA/MFMA for
  H_q > H_kv. We're going CUTLASS, not Triton, so the kernel itself
  doesn't port — but the dispatch pattern (grouped vs ungrouped
  decode) is a useful design reference.
* **#39668 — paged scale alignment.** "scale bytes included in the
  page/block sizing path"; padding logic for odd packed sizes. Mirror
  this for our per-block scale side-channel.
* **None — protected-K.** None of the 4 PRs has a protected-K /
  outlier-channel concept. This is our novel contribution on top of
  the existing INT4 literature.

### 4.4 Decision rule recap (for future readers)

The original rubric (axes + scoring) lives in §4.2 above. Decision
rule: PR scored ≥27/45 AND ≥4 on (Paged KV, FA integration, GQA) is
viable. **None passed FA integration**, so the rule selected A
unanimously.

## 5. Architectural decisions deferred until base is chosen

These are the choices the base implementation forces. Listed
unresolved so the PR triage can score each candidate's stance.

### 5.1 Cache write-time vs lazy quantization — LOCKED: write-time

- **Write-time (LOCKED):** Prefill writes FP16/BF16 into a staging
  buffer; at prefill→decode boundary, a single bulk quantize op
  converts the entire prefill tail into INT4 blocks + per-block
  scales/offsets, drops the FP16 staging buffer, and freezes the
  protect mask. Decode then writes one INT4 token per step (T=1
  group of size 32 fills every 32 steps).
- ~~Lazy:~~ ruled out — quantize-on-decode is exactly what 6c.3A v1
  paid and lost on.

Matches `ROUTE_A_VLLM_CACHE_KV_PLAN.md`. The v1 scope (decode-only
kernel) requires this: prefill is unmodified FA on FP16/BF16.

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

### 5.5 Protected-K layout — LOCKED: compact

- ~~Dense `(num_blocks, page_block_size, H_kv, D)` FP16:~~ RULED
  OUT — at S=32k, 28 layers, Qwen2.5 shapes the dense allocation
  is ~917 MB **per sequence**, wasting 96% of it on unprotected
  channels. Not viable for any usable concurrency.
- **Compact `(batch, S_padded, H_kv, n_protect)` BF16 sidecar +
  index list `(batch, H_kv, n_protect) int32` + mask `(batch,
  H_kv, D) int8` (LOCKED).** At Qwen2.5 shapes the per-sequence
  cost is ~44 MB at S=32k. Per-head padding to the per-batch
  maximum `n_protect_per_head` keeps the layout rectangular for
  coalesced FA loads.

See `KERNEL_6C3C_PROTECT_MASK_DESIGN.md` §3.6 for the memory math
and §3.5 for the resulting `Flash_fwd_params` extension.

### 5.6 Dispatch entry point — LOCKED: new function

- ~~Extend `flash_attn_with_kvcache`:~~ ruled out — overloading
  risks breaking existing FA callers; INT4 detection on FP16/BF16
  tensors is fragile.
- **New function `flash_attn_with_int4_kvcache` (LOCKED).** Separate
  Python entry point in `flash_attn/flash_attn_interface.py`, separate
  C++ entry `mha_fwd_kvcache_int4` in `flash_api.cpp`, separate
  dispatch arm. Diff against upstream stays bounded to additions —
  no modifications to existing entry points.

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

## 7. Open questions for design — for runbook to resolve

Triage-resolved questions are removed; what remains is design work
the runbook (`KERNEL_6C3C_RUNBOOK.md`) must close:

1. ~~Protect-mask provenance at decode time~~ — **RESOLVED** in
   `KERNEL_6C3C_PROTECT_MASK_DESIGN.md`: per-sequence × per-layer,
   computed once at prefill-end (before the FP16→INT4 quantize hook
   so the staging buffer is still FP16), owned by the new
   `Int4ProtectedKVAttentionBackend` in a per-sequence state dict,
   freed on sequence completion via vLLM's
   `Scheduler.free_finished_seq_groups` hook.
2. ~~Compact vs dense protected-K layout (§5.5)~~ — **RESOLVED**
   compact in `KERNEL_6C3C_PROTECT_MASK_DESIGN.md` §3.6. Dense
   costs ~917 MB per 32k sequence at Qwen shapes (28 layers ×
   full FP16 K); compact ~44 MB. §5.5 above LOCKED.
3. **Scale/offset side-channel keying (§5.2) — physical block_id
   vs logical position** — physical is the correct answer for vLLM
   compatibility, but the implementation effort is non-trivial. v1
   may accept logical-keyed and add a `prefix_cache_supported=False`
   flag; v2 lifts the restriction.
4. **Block_size vs group_size (§5.3)** — `block_size=32,
   group_size=32` is the clean answer that matches §20.4 bit-for-bit.
   vLLM's default `block_size=16` would require either setting it to
   32 for this attention backend, or doing intra-block sub-grouping.
   Choose 32 for v1 unless there's a vLLM constraint we hit.
5. **Bench harness** — `kernel_6c3a_throughput.py` is the 6c.3A
   bypass harness (manager.install_into_model). 6c.3C needs vLLM to
   own the cache end-to-end, so the harness becomes a stock vLLM
   `LLM(...)` invocation with `kv_cache_dtype="int4"` (or whatever
   the new flag is called). A new `kernel_6c3c_throughput.py` script
   is cleaner than extending the bypass harness.
6. **Build / dev loop** — modified `vllm_flash_attn` wheel must be
   installed locally into the GPU pod's venv-vllm. Cycle time per
   kernel change ≈ build time (~5-10 min for one new instantiation
   on sm80). Optimise: build only the new `_int4kv` .cu file in
   development by setting the FA2_GEN_SRCS glob narrowly.
7. **Protect-K data type alignment with model dtype** — Qwen2.5 is
   BF16; the FP16 sidecar in §5.5 must actually be BF16 to match.
   "FP16 sidecar" in the design shell is shorthand for "model
   dtype sidecar".

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
