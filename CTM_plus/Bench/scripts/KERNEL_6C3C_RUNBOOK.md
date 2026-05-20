# Kernel 6c.3C — engineering runbook (v1)

> **Companion to** `KERNEL_6C3C_DESIGN.md`. Design doc owns the
> *what*; this runbook owns the *how* — phase-by-phase execution,
> with one-line acceptance criteria, the §7 open questions resolved
> in order as they surface, and explicit risk callouts. Out-of-scope
> work explicitly skipped at each phase.

**Hard scope guard.** v1 is decode-only, static protected-K, INT4
K/V, BF16 sidecar for protect channels, Qwen2.5-7B (hdim=128, BF16,
H_q=28, H_kv=4), sm80. If a phase tempts you toward dynamic masks,
pre-RoPE quant, FP4, FA3, speculative decode, or multi-model — stop
and re-read `KERNEL_6C3C_DESIGN.md` §3.

## Phase 0 — environment

Goal: a local checkout of `vllm-project/flash-attention` that builds
the stock wheel cleanly and the existing microbench still measures
~the same numbers against it.

| Step | Action | Done when |
|---|---|---|
| 0.1 | `git clone https://github.com/vllm-project/flash-attention` to a workspace (separate from /workspace/symbolu) at the tag matching what vLLM 0.7.3 ships | `git log` shows the matching SHA |
| 0.2 | Confirm dev deps: CUDA toolkit (matching the venv-vllm install), `ninja`, `pybind11`, `cmake` | `python setup.py build_ext --inplace --dry-run` succeeds |
| 0.3 | Build the stock wheel (warm-cache; full build takes ~25–40 min on first cold build due to ~40 kernel instantiations) | `python setup.py bdist_wheel` produces a `.whl` |
| 0.4 | `pip install --force-reinstall <wheel>` into venv-vllm — REPLACES the bundled `vllm_flash_attn` | `python -c "import vllm.vllm_flash_attn as m; print(m.__file__)"` shows the dev install path |
| 0.5 | Smoke: rerun `kernel_int4_vs_fa_microbench.py` and confirm FA p50 at S=16k matches the 2026-05-20 baseline (67 μs) within ±10% | matches |
| 0.6 | Smoke: rerun `kernel_6c3a_throughput.py --cell A --prompt-tokens 32000` and confirm cell A tok/s matches the 2026-05-20 baseline (28.4 tok/s) within ±5% | matches |

**Risk:** different CUDA toolkit / cuBLAS versions between our dev
checkout and what shipped with vLLM 0.7.3 → ABI mismatch on the
modified wheel. Mitigation: pin the toolkit to whatever vLLM 0.7.3
was built against (check `vllm_flash_attn._C.__file__` symbol
versions in the existing wheel before replacing).

**Out of scope:** building FA3 / Hopper instantiations
(`hopper/` subdir). We target sm80 only.

## Phase 1 — additive scaffolding (no behavior change)

Goal: every new entry point / dispatch arm / kernel file in place,
all routing to the unmodified internals. No functional change. This
catches build mechanics + dispatch wiring bugs before they collide
with kernel-correctness bugs.

| Step | Action | Done when |
|---|---|---|
| 1.1 | Python: add `flash_attn_with_int4_kvcache(...)` in `flash_attn/flash_attn_interface.py`. Signature accepts `q, k_cache_int4, v_cache_int4, k_scale, k_offset, v_scale, v_offset, k_fp16_protect, protect_mask, cache_seqlens, block_table, ...`. INITIALLY: call `flash_attn_with_kvcache` with `k_cache=k_cache_int4.view(<original dtype>)` and ignore the new args | `flash_attn_with_int4_kvcache` returns the same output as `flash_attn_with_kvcache` on identical inputs |
| 1.2 | C++: add `mha_fwd_kvcache_int4` in `csrc/flash_attn/flash_api.cpp` as a thin wrapper around `mha_fwd_kvcache`. Register in `flash_api_torch_lib.cpp` | `import flash_attn_gpu; flash_attn_gpu.fwd_kvcache_int4` resolves |
| 1.3 | Dispatch: add `_int4kv` arm in `run_mha_fwd_splitkv_dispatch` (in `flash_fwd_splitkv_launch_template.h`). INITIALLY routes to the same template instantiation as fp16/bf16 | new dispatch arm picked at runtime when `mha_fwd_kvcache_int4` is called |
| 1.4 | Kernel file: `cp csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_sm80.cu csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_sm80.cu`. Edit the template instantiation name to `_int4kv`. NO OTHER CHANGES | rebuild picks up the new .cu via the `flash_fwd_*.cu` glob; dispatch arm 1.3 actually calls into it |
| 1.5 | `Flash_fwd_params` extension: in `csrc/flash_attn/src/flash.h`, add fields `k_scale_ptr, k_offset_ptr, v_scale_ptr, v_offset_ptr, k_fp16_protect_ptr, protect_mask_ptr, group_size_k, group_size_v, n_protect, is_int4kv`. All NULL / 0 by default | builds; `mha_fwd_kvcache_int4` plumbs the new params through (initially all NULL) |
| 1.6 | Rebuild + reinstall wheel | `flash_attn_with_int4_kvcache(q, k_cache_bf16, v_cache_bf16, None, None, None, None, None, None, cache_seqlens, ...)` matches stock FA bit-for-bit |

**Acceptance criterion for phase 1:** new entry point name, new
dispatch arm, new .cu file all in place; behaviour bit-identical to
stock FA when called with NULL quant args.

**Risk:** the glob in `CMakeLists.txt` may not pick up the new .cu
file without a `touch CMakeLists.txt` or full clean build. Mitigate
by `rm -rf build/` between rebuilds in this phase.

**Resolves §7.Q6** (dev loop): once phase 1 ships, every kernel
change rebuilds only the modified .cu instantiation + the flash_api
TU. ~5–10 min per cycle on sm80, hot cache. Don't optimize further
until measured.

## Phase 2 — INT4 K read path (correctness, no protect, V still FP)

Goal: reach a kernel that reads INT4 K from HBM, dequants inline,
runs attention against FP16/BF16 V, and matches the
`fused_int4_attention_reference` oracle to cosine ≥ 0.999.

| Step | Action | Done when |
|---|---|---|
| 2.1 | In the cloned kernel, locate the K read site: `tKgK.data() = gK.data() + flash::resolve_thread_kv_page_slice_offset<Kernel_traits>(...)` followed by `FLASH_NAMESPACE::copy(..., tKgK, tKsK, ...)`. Add a `#if Is_int4kv` guard that takes a different path | new path triggers when `params.is_int4kv == true` |
| 2.2 | INT4 K layout (LOCK from §5.3 + §4.3 crumbs): `(num_blocks, page_block_size, H_kv, D/2)` uint8 packed, asymmetric, with per-block `(num_blocks, H_kv, n_groups_per_block, D)` BF16 scale + BF16 offset. `group_size_k = 32` along seq, `page_block_size = 32`. Resolves §7.Q4 (`block_size = group_size = 32`) and §7.Q3 (physical block_id keying — defer prefix-cache support to v2; v1 ignores prefix-cache) | layout documented in code header of the cloned .cu |
| 2.3 | NO-OP transform proof: load FP16 K from HBM (same as stock), then in registers quantize→pack→unpack→dequantize using the same group_size_k math, before `FLASH_NAMESPACE::copy`. Output must match stock FA to FP16 precision | cosine ≥ 0.9999 vs stock FA on Qwen shapes (B=1, H_q=28, H_kv=4, D=128, S=16384) |
| 2.4 | REAL INT4 read: change K HBM layout to packed uint8 (storage allocated by the test harness, not vLLM yet). New copy atom for uint8 → unpack → dequant via `cast_load(scale, offset)`-style inline. Reuse `resolve_thread_kv_page_slice_offset` with adjusted byte strides (D/2 packed) | smoke test on B=1, H_q=28, H_kv=4, D=128, S=16384 returns reasonable values (finite, magnitudes within ±5σ of stock) |
| 2.5 | Correctness vs oracle: write a host-side test that quantizes a known FP16 K to INT4 with the §20.4 algorithm (asymmetric, group=32), runs both stock FA on the FP16 K and our new kernel on the INT4 K, compares to `fused_int4_attention_reference` from `int4_fused_attention_sketch.py` | both ours and oracle agree, cosine ≥ 0.999, max-abs ≤ 1e-2 across the Qwen shape grid in `kernel_6c_gpu_test.py::CASES` |

**Acceptance criterion for phase 2:** INT4 K + FP16 V + no protect
matches the existing route-B oracle on all 8 cases in
`kernel_6c_gpu_test.py::CASES`.

**Risk (high):** CUTLASS copy atoms are templated on element type;
the existing K read uses a copy atom typed for `Element` (FP16/BF16).
We can't reuse it for uint8 packed. Need either (a) a parallel
custom copy atom for uint8 with a register-level unpack/dequant
step, or (b) a load-then-process pattern that bypasses the CUTLASS
atom for the INT4 path. (a) is faster but harder; (b) is simpler.
**v1 picks (b).**

**Risk (medium):** dequant cost in registers may eat the HBM
bandwidth savings. Watch the per-call timing as soon as the kernel
runs — if it's not faster than stock FA by S=16k, the kernel design
needs rethink before phase 3.

## Phase 3 — INT4 V read path

Goal: V also INT4, kernel still no-protect, still matches oracle.

| Step | Action | Done when |
|---|---|---|
| 3.1 | Mirror phase 2 steps 2.1–2.5 for V. V layout: `(num_blocks, page_block_size, H_kv, D/2)` uint8 packed, per-token asymmetric (group_size_v = 32 along seq matches our config; per-token across head-dim) | smoke test runs |
| 3.2 | Correctness vs oracle: full INT4 K + V on all 8 `CASES` | cosine ≥ 0.999 |

**Acceptance criterion for phase 3:** full INT4 K + V + no protect
matches the oracle. Equivalent to the existing
`fused_protected_k_decode_attention` correctness gate but inside FA
instead of standalone Triton.

## Phase 4 — protected-K BF16 sidecar

Goal: the §20.4.3 algorithm faithfully reproduced inside the FA
kernel.

| Step | Action | Done when |
|---|---|---|
| 4.1 | Decide §7.Q2 (compact vs dense). Default LOCK: **dense `(num_blocks, page_block_size, H_kv, D)` BF16 sidecar** + `protect_mask: (H_kv, D) int8`. Dense wastes ~96% of the sidecar but reads are trivial; phase-4 doesn't need gather. v2 may revisit if HBM is tight | choice recorded in cloned .cu header |
| 4.2 | Plumb `k_fp16_protect_ptr` (BF16 dense sidecar) and `protect_mask_ptr` ((H_kv, D) int8) through `Flash_fwd_params` and the C++ entry | NULL still works (no-protect path); non-NULL routes to the sidecar read |
| 4.3 | In the K read: parallel load of `k_fp16_protect` for the same block. After dequant of INT4 K, blend with sidecar via `protect_mask`: `K[h, d] = mask[h, d] ? k_fp16_protect[h, d] : dequant(int4_K[h, d])`. Blend happens in registers before the qK dot | output identical to a host-side reference that does the same blend |
| 4.4 | Correctness vs §20.4.3 reference: run the full grid in `kernel_6c_gpu_test.py::CASES` with `protect_fraction=0.04` (the §20.4.3 ship config) | cosine ≥ 0.999 |

**Acceptance criterion for phase 4:** the FA-integrated kernel
produces the §20.4.3 algorithm's outputs bit-for-bit (within FP16
precision) at all measured S.

**Resolves §7.Q7** (BF16 not FP16): protected-K sidecar is BF16 for
Qwen2.5; if/when we add Llama-3-8B (v2), it's FP16. The kernel
templates on `Element`.

## Phase 5 — vLLM integration

Goal: a vLLM attention backend that owns the INT4 paged cache
end-to-end and dispatches to our modified FA.

| Step | Action | Done when |
|---|---|---|
| 5.1 | Add `Int4ProtectedKVAttentionBackend` in `vllm/attention/backends/` extending the FA backend. Override `forward` to call `flash_attn_with_int4_kvcache` for decode. Prefill uses unmodified FA on the FP16 staging buffer | backend importable; vLLM-level smoke test (one prefill + 1 decode token, no quant args yet) runs |
| 5.2 | Block manager extension: per-block INT4 K, INT4 V, BF16 K-protect sidecar storage. Per-block scale/offset side-channel `(num_blocks, H_kv, n_groups_per_block, D)`. Keyed by physical block_id. Resolves §7.Q3 in v1 (physical keying; prefix-cache reuse deferred to v2) | new block fields allocated; `num_kv_heads * head_size_bytes` accounting updated |
| 5.3 | Prefill→decode quant hook: at the boundary, bulk-quantize the prefill K/V tail into INT4 blocks + scales, populate the protect-mask from the §20.4.3 magnitude criterion (top-4% over the prefill), drop the FP16 staging buffer. Resolves §7.Q1 (mask computed in vLLM at prefill end, stored in the attention backend's per-sequence state) | one decode token after a 32k prefill produces correct output (matches CPU host-side reference) |
| 5.4 | Register `kv_cache_dtype="int4_protected"` in vLLM's enum + arg parser. Wire `LLM(..., kv_cache_dtype="int4_protected")` to install the new backend | `LLM(..., kv_cache_dtype="int4_protected").generate(...)` completes one prompt |

**Acceptance criterion for phase 5:** `LLM(model="Qwen2.5-7B",
kv_cache_dtype="int4_protected").generate(prompts, sampling_params)`
returns text on a Qwen2.5 prompt at S=2k, matches FP16 output at the
token level for the first ~16 tokens (greedy + same seed).

**Risk (high):** vLLM's block manager assumes uniform byte-size per
block. INT4 + sidecar + scales is a non-trivial extension. May
require allocating an additional KV pool typed differently rather
than extending blocks. Watch for this in 5.2.

**Risk (medium):** the §20.4.3 protect-mask is computed per-sequence
over the full prefill K magnitude. If vLLM streams prefill (chunked
prefill), the mask isn't known until the last chunk completes. v1
disables chunked prefill for this backend; v2 supports it.

## Phase 6 — measurement (the deliverable)

Goal: §20.6.4 in `PHASE4_GPU_FINDINGS.md` with measured numbers.

| Step | Action | Done when |
|---|---|---|
| 6.1 | New harness `kernel_6c3c_throughput.py` — stock vLLM `LLM(...)` with `kv_cache_dtype` toggled across {"auto", "fp8", "int4_protected"}. Same Qwen2.5-7B, same prompt-token / decode-token / num-prompts knobs as `kernel_6c3a_throughput.py`. Resolves §7.Q5 — new script, not extending the bypass harness | script runs end-to-end on Qwen2.5-7B at S=2k |
| 6.2 | Cell-grid run: cells A (FP16), B (FP8), E (INT4-protected, new) at S ∈ {2k, 16k, 32k}, B=1, decode=128 | JSON output per cell + a summary table |
| 6.3 | KV memory measurement: `torch.cuda.max_memory_allocated` snapshots before / after KV pool init, plus `nvidia-smi` for the steady-state during decode. Per cell | memory ratios E/A and E/B in the summary table |
| 6.4 | §20.4.3 quality re-run: 32k-needle pass-rate on Qwen2.5-7B with the new backend, n=24 (matches §20.4.3 sample size) | pass-rate within ±2% of §20.4.3 FP16 baseline |
| 6.5 | Update `PHASE4_GPU_FINDINGS.md` with §20.6.4 — measured tables, methodology recap, honest-scope (Qwen-only, decode-only, sm80-only) | section lands |

**Acceptance criterion for v1 (the whole runbook):**

- E/A (INT4-protected vs FP16) tok/s ratio ≥ 1.0 at S=32k. Stretch ≥
  1.2×.
- E/A KV memory ratio ≤ 0.30 (accounting for ~4% BF16 sidecar +
  scales/offsets vs full FP16).
- §20.4.3 quality re-run within ±2% of FP16 baseline.

If any of those misses, the v1 result still ships as the honest
measurement (just like the §20.6.3 cell-D close did), and the gap
defines v2's scope.

## Effort sizing (rough)

| Phase | Effort (focused engineer-days) | Risk |
|---|---:|---|
| 0 Environment | 1 | low (build mechanics) |
| 1 Scaffolding | 2 | low |
| 2 INT4 K | 5 | high (CUTLASS copy atom) |
| 3 INT4 V | 2 | medium (mirrors phase 2) |
| 4 Protected-K | 2 | medium |
| 5 vLLM integration | 5 | high (block manager extension) |
| 6 Measurement | 2 | low |
| **Total** | **~19 days** | |

3–4 weeks elapsed for a single engineer on this full-time. Add 50%
for the integration-and-debug tail (vLLM block manager surprises are
not bounded by code complexity).

## Out-of-scope items deferred to v2 / later

- **Prefix-cache reuse** — v1 keys scales by physical block_id but
  doesn't yet support shared block reuse across sequences. v2.
- **Chunked prefill** — v1 disables. v2 streams the mask.
- **Compact protect-K layout** — v1 is dense; v2 may switch if HBM
  becomes the binding constraint.
- **Multi-model** — v1 is Qwen2.5-7B-only. Llama-3-8B, Mistral-7B
  validation is v2 (uses FP16 sidecar, otherwise same kernel).
- **FA3 / Hopper** — sm80 only in v1.
- **Symmetric quant, group sizes ≠ 32, pre-RoPE quant, FP4/NVFP4,
  dynamic masks, speculative decode** — explicitly out of scope per
  the design doc §3.
