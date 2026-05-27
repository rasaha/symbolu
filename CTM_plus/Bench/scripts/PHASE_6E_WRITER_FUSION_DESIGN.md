# Phase 6E — writer op fusion (custom CUDA kernel)

> **Status:** Plan-of-record only. No code lands on this plan until
> the implementation gate is approved.
>
> **One-sentence goal:** Collapse the writer's per-decode-step
> sequence of ~30 small CUDA ops into 2 fused custom CUDA kernels
> (`fused_decode_write_v`, `fused_decode_write_k`), eliminating the
> ~280 ms of per-launch + per-elementwise-kernel overhead that
> Phase 6D measured as the dominant source of the remaining
> int4-vs-bf16 gap.
>
> **Why this is the right fix:** Phase 6D torch.profiler captured
> 5944 `aten::index` + 4732 `index_put_` + 11k `aten::to`/`copy_`
> launches per generation in the int4 path; bf16 stock has ~5
> equivalent launches. Each launch is ~30-50 µs of CPU dispatch +
> ~5-15 µs of GPU work. At 28 layers × 8 decode steps × ~25 extra
> ops per layer, this is 5600-6720 surplus launches per generation
> = **~200-400 ms of pure overhead** — the exact size of the
> measured int4-eager vs bf16-eager gap (1133 - 467 = 666 ms total,
> of which the writer accounts for ~280-450 ms after subtracting
> the int4 attention kernel itself and shared GEMMs).
>
> **Projected outcome:** captured-cell B=8 throughput goes from
> 174 tok/s today → ~250-300 tok/s after fusion → **cap/bf16
> ratio improves from 0.30× to ~0.45-0.50×**. Total int4 captured
> wall time drops by 20-30%. HBM unchanged (we already won that
> in 6C).

## Background — what the data showed

Phase 6D torch.profiler on int4_eager vs bf16_eager (same Qwen-7B + A100, B=8, max_tokens=8):

```
int4_eager total CUDA time: 1133 ms
bf16_eager total CUDA time:  467 ms   (int4/bf16 = 2.43×)

Same in both cells (sanity-checked):
  Model linear layer GEMMs (aten::mm, aten::linear):   ~111 ms each
  Model RMSNorm / rotary / silu / etc.:                ~117 ms each

Int4-only excess that's costing the gap:
  vllm::unified_attention_with_output wrapper:         185 ms (vs 3 ms in bf16)
  Writer Python-side ops outside the kernel:           ~285 ms
    of which:
      aten::index (5944 calls):                         43 ms
      aten::copy_ + aten::to/_to_copy (~11k calls):     56 ms
      aten::index_put_ (4732 calls):                    26 ms
      aten::nonzero (1568 calls):                       11 ms
      aten::_unique2 (224 calls):                        9 ms
      aten::__and__ + bitwise_and (2268 calls):         16 ms
      aten::amax + amin (1036+1036 calls):              14 ms
      aten::where (2156 calls):                          7 ms
      aten::div + sub (2072+2275 calls):                12 ms
      Misc small kernels:                              ~91 ms
  CPU-sync ops (eager-only, captured-mode eliminates):  ~19 ms
```

The writer is launching ~25-30 small CUDA ops per layer per decode step. Each launch has ~30-50 µs of CPU-side dispatch overhead PLUS ~5-15 µs of small-payload GPU work. At 224 (28 layers × 8 decode steps) launches × ~30 surplus ops = ~6700 surplus launches. **That's the gap.**

bf16 stock does the equivalent of all this inside ONE C++ kernel call (`flash_fwd_splitkv_kernel`) — fused write+read. We carry the cost of having the writer in Python.

## Proposed kernels — two fused ops

### Kernel 1: `fused_decode_write_v_int4_protected`

Collapses the V-side path of `write_decode_batched`'s captured region:

```
Inputs:
  value             (B, H, D) bf16     -- new V tokens this step
  slot_idx_t        (B,) long           -- pool slot per batch position
  slot_mapping      (B,) long           -- vLLM cache slot per batch position
  active_mask       (B,) bool           -- (slot_mapping >= 0)
  kv_cache_v        (NB, BS, H, D//2)   uint8  -- packed int4 V cache (in-place writeback)
  v_scale_ext       (NB, BS, H, n_groups) bf16  -- (in-place writeback)
  v_xmin_ext        (NB, BS, H, n_groups) bf16  -- (in-place writeback)
  group_size                                    -- compile-time constexpr (=32)

Compute (current op chain):
  block_id  = slot_mapping // BS              -- 1 op
  position  = slot_mapping % BS               -- 1 op
  v_grouped = value.view(B, H, n_groups, gs)  -- (no-op view)
  v_max     = v_grouped.amax(-1)              -- amax
  v_min     = v_grouped.amin(-1)              -- amin
  v_scale   = ((v_max - v_min) / 15.0).clamp_(min=1e-8)   -- 3 ops
  q_v       = ((v_grouped - v_min.unsqueeze(-1)) / v_scale.unsqueeze(-1)).round_().clamp_(0,15).to(uint8)
                                              -- 5 ops
  v_packed  = (q_v[...,0::2] & 0x0F) | ((q_v[...,1::2] & 0x0F) << 4)   -- 3 ops (with bitwise_and ops)

Scatter (current op chain):
  kv_cache_v[block_id, position, :, :half_D] = v_packed       -- index_put_
  v_scale_ext[block_id, position]             = v_scale.to(bf16)  -- index_put_ + to
  v_xmin_ext [block_id, position]             = v_min.to(bf16)    -- index_put_ + to

Today: ~14 separate CUDA kernel launches per layer per decode step.
Fused: 1 kernel.

Inactive mask handling:
  Inside the kernel, threads with active_mask[batch]==False
  write to position 0 of block 0 (harmless; matches the current
  unconditional-scatter design's "safe_slot_mapping" pattern).
```

### Kernel 2: `fused_decode_write_k_int4_protected`

Collapses the K-side path:

```
Inputs:
  key                          (B, H, D) bf16     -- new K tokens this step
  slot_idx_t                   (B,) long
  slot_mapping                 (B,) long
  active_mask                  (B,) bool
  k_stage_pool                 (n_slots, BS, H, D) bf16     -- (in-place rmw)
  k_stage_count_pool           (n_slots,) int32             -- (in-place rmw)
  k_stage_block_id_pool        (n_slots,) int64             -- (in-place rmw; -1 sentinel)
  seq_pos_pool                 (n_slots,) int32             -- (in-place increment)
  protect_mask                 (H, D) int8                  -- (read-only; from writer at alloc)
  protected_d_per_head         (H, n_protect) long          -- (read-only; from writer)
  kv_cache_k                   (NB, BS, H, D//2) uint8      -- (in-place writeback, block_full only)
  k_scale_ext                  (NB, H, D) bf16              -- (in-place writeback, block_full only)
  k_xmin_ext                   (NB, H, D) bf16              -- (in-place writeback, block_full only)
  k_protect_ext                (NB, BS, H, n_protect) bf16  -- (in-place writeback every step)

Compute (current op chain — see write_decode_batched lines 1213-1291):
  prior_block_id = k_stage_block_id_pool[slot_idx_t]              -- gather
  is_new_block   = (block_id != prior_block_id)                   -- eq
  keep_mask      = ~is_new_block                                  -- not
  current_k_stage = k_stage_pool[slot_idx_t]                      -- gather
  cleared_k_stage = where(keep_mask, current_k_stage, zeros)      -- where
  batch_arange    = arange(B)                                     -- arange
  cleared_k_stage[batch_arange, position] = key                   -- index_put_
  k_stage_pool[slot_idx_t] = cleared_k_stage                      -- index_put_

  # Quantize the staging block (whole BS=32 tokens, in-register if possible)
  buf_f  = cleared_k_stage.float()                                -- to
  x_max  = buf_f.amax(dim=1)                                      -- amax
  x_min  = buf_f.amin(dim=1)                                      -- amin
  scale  = ((x_max - x_min) / 15.0).clamp_(min=1e-8)              -- 3 ops
  q      = ((buf_f - x_min.unsqueeze(1)) / scale.unsqueeze(1)).round_().clamp_(0,15).to(uint8)  -- 5 ops
  packed = (q[...,0::2] & 0x0F) | ((q[...,1::2] & 0x0F) << 4)     -- 3 ops

  block_full_mask = ((position + 1) == BS) & active_mask          -- 2 ops

  # K protect gather + scatter (per step, regardless of block_full)
  protect_idx = protected_d_per_head.unsqueeze(0).expand(B, -1, -1)  -- view
  k_protect   = gather(key, dim=-1, index=protect_idx)             -- gather
  k_protect_ext[block_id, position] = k_protect                    -- index_put_

  # Conditional writeback under block_full_mask
  kv_cache_k[block_id, :, :, :half_D] = where(full_mask_kv, packed, kv_cache_k[block_id, :, :, :half_D])
                                                                   -- 2 gathers + where + index_put_
  k_scale_ext[block_id] = where(full_mask_ext, scale.to(bf16), k_scale_ext[block_id])
                                                                   -- gather + where + to + index_put_
  k_xmin_ext [block_id] = where(full_mask_ext, x_min.to(bf16), k_xmin_ext [block_id])
                                                                   -- gather + where + to + index_put_

  # Bookkeeping updates
  k_stage_block_id_pool[slot_idx_t] = where(active_mask, block_id, k_stage_block_id_pool[slot_idx_t])
                                                                   -- gather + where + index_put_
  k_stage_count_pool[slot_idx_t]    = where(block_full_mask, 0, position + 1)
                                                                   -- 2 ops + where + index_put_
  seq_pos_pool.index_add_(0, slot_idx_t, active_mask.to(int32))    -- index_add_

Today: ~25-30 separate CUDA kernel launches per layer per decode step.
Fused: 1 kernel.
```

## What gets deleted from `phase5b_4c_paged_writer.py`

The captured region of `write_decode_batched` (lines 1147-1293) — the ~80-line op chain that today launches 25-30 small kernels — becomes a single call:

```python
# Before (~80 lines of small ops):
seq_pos_t = self._seq_pos_pool[slot_idx_t].long()
self._bf16_k_backing_pool[slot_idx_t, seq_pos_t] = key   # (already 6C-skipped)
...
# (current code)

# After (2 fused kernel calls):
torch.ops._int4_protected_C.fused_decode_write_v(
    value, slot_idx_t, slot_mapping, active_mask_t,
    kv_cache[1], self.v_scale_ext, self.v_xmin_ext,
    v_group_size=self.v_group_size,
)
torch.ops._int4_protected_C.fused_decode_write_k(
    key, slot_idx_t, slot_mapping, active_mask_t,
    self._k_stage_pool, self._k_stage_count_pool,
    self._k_stage_block_id_pool, self._seq_pos_pool,
    self.protect_mask, self.protected_d_per_head,
    kv_cache[0], self.k_scale_ext, self.k_xmin_ext,
    self.k_protect_ext,
)
```

Plus skip the bf16 backing pool entirely (already done in Phase 6C).

## Where the code lives

* **CUDA source:** new package `CTM_plus/CUDA_int4_protected/` (or extend existing `CTM_plus/CUDA/` if there's a fork). Two `.cu` files + a `setup.py` to build a small extension `_int4_protected_C`.
* **Python registration:** `phase5b_4c_paged_writer.py` adds `import` of the extension; the captured region of `write_decode_batched` switches over via an env flag `PHASE6E_FUSED_WRITER={1,0}`.

## CPU test plan (gate before any GPU compile)

| Test | Purpose | Pass criterion |
|---|---|---|
| `verify_phase6e_fused_vs_unfused_byte_eq.py` | Build a small CPU reference implementation of both fused kernels in pure PyTorch; assert byte-equal output vs the existing op chain for 100 random inputs at B ∈ {1,2,4,8,16,32} | All 100 trials byte-equal on every output tensor |
| `verify_phase6e_inactive_mask_semantics.py` | Verify that `active_mask[i]==False` rows are correct no-ops (don't corrupt other slots' state) | Same as today — the "safe_slot_mapping" pattern |
| `verify_phase6e_block_boundary_semantics.py` | Drive a sequence across a block boundary (position 30, 31, 32); verify k_stage_block_id transition fires exactly once + kv_cache writeback occurs only on the BS=32-th token | State matches today's writer at every step |

All three must PASS GREEN on CPU before any GPU work.

## GPU verification gate (after CUDA implementation)

Re-run the existing 6B.4 bench + the 6B.3 smoke:

| Gate | Criterion |
|---|---|
| **6B.3 semantic-eq gate re-passes** | All 20 G_CAPTURE.2 checks GREEN with `PHASE6E_FUSED_WRITER=1` |
| **No HBM regression** | Captured cell HBM at B=32 ≤ 46 GB (within 1 GB of Phase 6C's 45.83 GB) |
| **Throughput uplift** | captured B=8 agg_tps ≥ 220 tok/s (current 174 tok/s; gate ≥ 1.25× of current) |
| **cap/bf16 ratio improvement at B=32** | ≥ 0.25× (current 0.19×) — measurable improvement on the highest-leverage row |
| **No regression at low B** | captured B=1 agg_tps ≥ 35 tok/s (within 5% of current 39.2 tok/s) |

If GPU gate passes → Phase 6E ships, `PHASE6E_FUSED_WRITER=1` becomes default. Env override `=0` retained for A/B comparison + emergency rollback.

If GPU gate fails on throughput → keep the new code behind `PHASE6E_FUSED_WRITER=1` opt-in, document the actual measured factor, scope Phase 6F.

If GPU gate fails on correctness → revert to pre-6E state via env override; debug the CUDA kernel; the CPU verifier should have caught most issues but device-side bugs (memory ordering, atomics) are still possible.

## Estimated effort

| Stage | Work | Time |
|---|---|---|
| Detailed kernel design + CUDA kernel skeletons (signatures, shared memory layout, block/grid sizing) | C++ design doc | 1 day |
| Implement `fused_decode_write_v` | CUDA dev | 1.5 days |
| Implement `fused_decode_write_k` (more complex due to K stage + block-boundary logic) | CUDA dev | 2 days |
| Python registration + dispatch fork integration | Python | 0.5 day |
| CPU verifiers (3 tests, ~200 LOC each) | Python | 1 day |
| GPU verification re-bench + analysis | GPU bench | 0.5 day |
| Finding doc (`PHASE_6E_WRITER_FUSION_FINDINGS.md`) | Doc | 0.5 day |
| **Total** | | **~7 days + ~$0.20 GPU** |

CUDA dev expertise required for the two fused kernels (kernel-level memory ordering, smem layout for K stage + scatter intricacies). The K kernel is the harder one because of the conditional block-boundary state machine.

## Risks

1. **CUDA kernel correctness — atomic / memory ordering bugs.** The `seq_pos_pool.index_add_` in the K kernel is a per-slot atomic increment; need to ensure correct ordering with the preceding `k_stage_pool` read. Mitigation: explicit `__threadfence()` after the stage updates; CPU verifier catches most semantic bugs before they go to GPU.

2. **Build complexity.** A new CUDA extension adds setup.py overhead + a wheel to ship. Mitigation: model it on the existing `vllm-flash-attn-dev` fork's build structure. The codebase already builds CUDA extensions, so the infrastructure is there.

3. **Throughput projection might be optimistic.** The 280 ms savings estimate assumes the writer overhead is purely launch-latency-bound. Some fraction is actual compute. If only half the savings materialize, captured B=8 goes from 174 → 200 tok/s, not 250. Still a win, but smaller. Mitigation: the CPU verifier validates correctness; the GPU re-bench is the dispositive throughput measurement, not the projection.

4. **The remaining gap to bf16.** Even after Phase 6E, int4 captured may still be 0.45-0.50× of bf16. The structural overhead of having a Python writer alongside a C++ kernel doesn't go to zero; it shrinks. Mitigation: this is acknowledged in the finding doc; the brief narrative emphasizes the *algorithmic* value of the protect-mask design, not parity with stock bf16.

5. **Kernel maintainability.** A custom CUDA extension is a long-term liability — every PyTorch/CUDA upgrade risks breakage. Mitigation: pin the build to a specific CUDA toolkit + PyTorch version; the existing forked `vllm-flash-attn` already represents this commitment.

## Files that will change (G5c SHA delta projection)

* **NEW**: `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_v.cu`
* **NEW**: `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_k.cu`
* **NEW**: `CTM_plus/CUDA_int4_protected/csrc/binding.cpp`
* **NEW**: `CTM_plus/CUDA_int4_protected/setup.py`
* **MODIFIED**: `KVPolicy/kv_policy/phase5b_4c_paged_writer.py` — `_lazy_alloc` imports the extension; `write_decode_batched` captured region becomes 2 kernel calls when `PHASE6E_FUSED_WRITER=1`.
* **NEW**: `KVPolicy/tests/verify_phase6e_*.py` — 3 CPU verifiers.

Existing 10 int4_protected files: only `phase5b_4c_paged_writer.py` changes for SHA delta.

## Deferred (post-6E)

1. **Fuse the read path too** (`_read_decode_packed_batched`'s splice + view ops). Phase 6D shows another ~50 ms of pre-kernel preparation that could be folded into the kernel call. Smaller potential win than 6E.
2. **Move int4 logic into the flash_attn kernel itself.** Truly C++/CUDA all the way down. Eliminates the writer concept entirely. Highest potential payoff, highest risk + effort (multi-week kernel surgery).
3. **Cross-family verification post-6E** (Mistral-7B-Instruct, Llama-3.1-8B).
4. **Long-context bench** (max_model_len=16K, 32K) — where int4's per-position memory savings should compound into a memory-side win regardless of throughput.
