# Phase 6G — Sidecar diet (memory optimization design)

> **Status:** DESIGN ONLY. No code, no calibration changes until the
> tensor-by-tensor sidecar audit (Step 1) lands measured data.
>
> **Trigger:** The Phase 6 long-context HBM bench
> (`bench_phase6_long_context_gpu.py`, commit `1fb05f6`) showed
> int4_protected captured uses +5 GB more measured HBM than stock
> bf16 at every tested `max_model_len` (8K, 16K, 32K), even though
> vLLM's `max_concurrency` reports int4 = 2× bf16. The 2× advantage
> is logical (vLLM bookkeeping); the +5 GB delta is physical
> (sidecar tensors the writer allocates outside vLLM's budget).
>
> **Goal:** Recover the per-token int4 savings by shrinking the
> sidecars enough that the measured HBM crossover is real, not just
> vLLM's accounting.
>
> **Acceptance:** int4_protected captured HBM ≤ bf16 captured HBM at
> `max_model_len ∈ {16K, 32K}`, with quality intact (Phase 6E byte-eq
> verifier still GREEN; long-context quality sanity check passing
> equally for both cells in the long-context bench). Alternative
> partial-success: clear quantified reduction (≥40% sidecar shrink)
> with a documented quality vs memory trade-off.

## Background

vLLM's KV cache budget tracks only `kv_cache[0]` and `kv_cache[1]`
(the `(NB, BS, H, D)` uint8 tensors that the kernel reads). The
int4_protected writer allocates additional per-layer tensors at
`_lazy_alloc` time, on top of that budget:

| Tensor | Shape | Bytes per layer (NB=26K, H=4, D=128, BS=32, n_groups=4, n_protect=5) |
|---|---|---|
| `v_scale_ext` | `(NB, BS, H, n_groups)` bf16 | ~26.6 MB |
| `v_xmin_ext`  | `(NB, BS, H, n_groups)` bf16 | ~26.6 MB |
| `k_scale_ext` | `(NB, H, D)` bf16            | ~26.6 MB |
| `k_xmin_ext`  | `(NB, H, D)` bf16            | ~26.6 MB |
| `k_protect_ext` | `(NB, BS, H, n_protect)` bf16 | ~33.3 MB |
| `_k_stage_pool` | `(n_slots, BS, H, D)` bf16  | ~0.5 MB |
| `_bf16_*_backing_pool` (skip mode) | `(1, 1, H, D)` bf16 | negligible |

Subtotal per layer: ~140 MB. Across 28 layers (Qwen-7B): **~3.9 GB**.
Measured delta is ~5 GB; the extra ~1 GB is likely vLLM working
buffers + activation memory differences. The dominant five sidecars
above are the targets.

## Step 1 — Sidecar audit (mandatory first action)

Write `audit_phase6g_sidecar_overhead.py` (~80 lines):

* Loads int4_protected at `max_model_len=16K`, `gpu_memory_utilization=0.5`.
* After `_lazy_alloc` fires, iterates over every layer's writer and
  reports the byte size of each allocated tensor.
* Aggregates to a `(tensor_name, total_bytes, % of overhead)` table.
* Also computes the per-token marginal cost (allocated bytes per
  cached token) for each sidecar — the key metric for the diet
  options below.

**Output:** `bench_out/phase6g_sidecar_audit/overhead.json` + a
short text table. The diet options below are evaluated against
THIS measured baseline, not the rough estimates above.

**Gate:** no diet changes proposed until the audit lands.

## Step 2 — Diet options (ranked by ROI)

Each option is a separate workstream; pursue in this order. Stop
when measured HBM ≤ bf16 at 16K/32K.

### Option A — `v_n_groups = 2` (group_size = 64)

Halves `v_scale_ext` + `v_xmin_ext`. Estimated savings: **~1.5 GB**
across both tensors at 28 layers, NB=26K.

* **Cost**: V quantization granularity drops from 32-element groups
  to 64-element groups → larger quantization error per group → lower
  reconstruction fidelity for V.
* **Implementation**: changes `_DEFAULT_V_GROUP_SIZE` in
  `phase5b_4c_paged_writer.py`; updates the Phase 6E V kernel's
  `TORCH_CHECK(group_size == 32, ...)` to also accept 64 and
  switch the warp-reduce pattern accordingly (a 64-element group
  spans 2 warps so the shuffle reductions need a smem step).
* **Quality validation**: extend `verify_phase6e_fused_byte_eq.py`
  to A/B at `group_size=64`; verify the Phase 6E byte-eq contract
  still holds. Additionally run a short prompt benchmark on a
  factual-recall task (greedy decode, B=1) and compare top-1 token
  agreement at each step vs `group_size=32`. Acceptance: ≥99% token
  agreement.
* **Effort**: ~2 days.

### Option B — Reduce `n_protect` from 5 → 3

Shrinks `k_protect_ext` by 40%. Estimated savings: **~0.5 GB**.

* **Cost**: fewer protected channels per head means int4 quant
  applies to more dims, losing some of the protect-mask benefit.
  The whole point of the protect-mask design is that ~5 channels
  per head carry disproportionate activation mass; cutting to 3
  may sacrifice the quality story.
* **Implementation**: re-run Phase 5B.0 calibration with
  `n_protect=3`; rebuild the protect mask artifact. No code changes.
* **Quality validation**: long-context bench's quality sanity check
  at both `n_protect=3` and `n_protect=5`. Acceptance: equal
  long-context quality. Higher bar: re-run the original Phase 5B
  calibration's quality benchmark and stay within 1% perplexity.
* **Effort**: ~1 day (mostly re-calibration; no new code).

### Option C — Quantize the sidecars to fp8 (e4m3)

bf16 → fp8 halves each sidecar's bytes. Estimated savings:
**~2 GB** if applied to all five sidecars.

* **Cost**: fp8 has ~3-bit mantissa; quantizing the scale/xmin
  introduces a second layer of quantization noise on top of the
  int4 packing. The dequant formula becomes:
  `bf16_recon = (q4 * fp8_scale + fp8_xmin)` instead of
  `bf16_recon = (q4 * bf16_scale + bf16_xmin)`. Total
  reconstruction error compounds.
* **Implementation**: change sidecar dtype in writer's `_lazy_alloc`;
  update the Phase 6E kernels' `__float2bfloat16_rn` writes to
  emit fp8 via `__nv_fp8_e4m3` intrinsics; update flash_attn's
  int4_packed kernel to dequant fp8 → bf16 on read.
* **Quality validation**: byte-eq verifier no longer applies
  (different dtype). Need direct quality A/B against the bf16
  sidecar baseline.
* **Effort**: ~3 days (kernel changes on both write and read).

### Option D — Eliminate `k_protect_ext` (per-token protected dims)

The Phase 5B design stores protect-channel bf16 values
per-token-per-head in `k_protect_ext`. If we recompute these from
the int4-packed cache + per-channel calibration at read time, the
sidecar disappears. Estimated savings: **~1.2 GB**.

* **Cost**: structural change to the read path. The whole point
  of `k_protect_ext` was to skip int4 quantization on the
  protected channels; eliminating it means either (a) accepting
  int4 quantization on those channels (defeats the protect-mask
  premise) or (b) keeping them as bf16 INSIDE the packed cache
  layout (requires re-designing the kernel's input).
* **Implementation**: option (b) requires kernel surgery in
  `vllm_flash_attn-dev`'s int4_packed template. Major work.
* **Quality validation**: full re-verification of the protect-mask
  story.
* **Effort**: ~5 days. **High risk; recommend skipping unless
  A + B + C fall short.**

### Option E — Sparse / lazy sidecar allocation

vLLM pre-allocates the full `(NB, BS, H, ...)` sidecars even though
most blocks are unused at any given moment. A sparse layout (only
materialize sidecars for blocks the writer has touched) would
recover the unused portion. Estimated savings: highly utilization-
dependent — at 10% utilization, ~3.5 GB (90% of 3.9 GB).

* **Cost**: vLLM's allocator needs to know the full NB up front
  for `max_concurrency` calculation. Lazy allocation breaks this.
* **Implementation**: requires either (a) intercepting vLLM's
  allocator hooks to override the NB calculation, or (b) routing
  sidecar reads through a dict lookup ⟶ adds per-step host work.
* **Effort**: ~4 days, with risk of breaking vLLM's scheduling
  assumptions. **Recommend skipping** — high cost, doesn't shrink
  the budget visible to vLLM.

### Option F — Pack `v_scale_ext` + `v_xmin_ext` into one tensor

Cosmetic; no byte savings (same total). **Skip.**

## Step 3 — Combination strategy

To hit `int4 HBM ≤ bf16 HBM` (a ~5 GB reduction goal), no single
option is sufficient. Recommended stack:

1. **A (group_size=64)**: −1.5 GB.
2. **B (n_protect=3)**: −0.5 GB.
3. **C (fp8 sidecars)**: −2 GB.

Total: **−4 GB** projected. Tight but possibly enough to flip the
verdict at 16K and 32K (where the int4 delta is smaller). Each
option also independently moves the needle, so the bench can be
re-run after each one to measure incremental progress; halt as
soon as the acceptance criterion is met.

## Step 4 — Bench gate

After each diet option is implemented:

1. Re-run `verify_phase6e_fused_byte_eq.py` (or its updated
   variant if the option breaks byte-eq) — must stay GREEN or
   document the controlled quality drift.
2. Re-run `bench_phase6_long_context_gpu.py` — measure the new
   HBM delta vs bf16.
3. If `int4_HBM ≤ bf16_HBM` at 16K or 32K: ACCEPTANCE MET. Stop.
4. Else: continue to next diet option.

## Out of scope (defer to 6H or later)

* **Kernel surgery to move int4 logic into flash_attn**: that's
  Phase 6F. The user has explicitly halted 6F pending evidence
  from 6G + 6H.
* **High-load capacity bench**: that's Phase 6H (separate design
  doc). 6G focuses on shrinking the per-token cost; 6H validates
  the resulting capacity advantage.
* **VC brief updates**: blocked until 6G measured outcomes land.

## Estimated total effort

| Step | Work | Time |
|---|---|---|
| Step 1: audit script + run | ~80 LOC + 1 GPU run | 0.5 day |
| Option A: group_size=64 + kernel update + quality A/B | CUDA + Python | 2 days |
| Option B: n_protect=3 + recalibrate | Calibration only | 1 day |
| Option C: fp8 sidecars + kernel update + quality A/B | CUDA + Python | 3 days |
| Findings doc (`PHASE_6G_SIDECAR_DIET_FINDINGS.md`) | Doc | 0.5 day |
| **Total** | | **~7 days** if all three stacked, **~3 days** if A+B alone hit the gate |
