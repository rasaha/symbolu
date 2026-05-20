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
| 0.1 | `git clone https://github.com/vllm-project/flash-attention` to a workspace (separate from /workspace/symbolu) at the SHA matching what vLLM 0.7.3 ships — **`720c94869cf2e0ff5a706e9c7f1dce0939686ade`** (2025-02-06, "fix illegal memory access #42"), pinned at vllm/CMakeLists.txt:602 at the v0.7.3 tag | `git log -1 --oneline` shows `720c948` |
| 0.2 | Confirm dev deps: CUDA toolkit (matching the venv-vllm install), `ninja`, `pybind11`, `cmake` | `python setup.py build_ext --inplace --dry-run` succeeds |
| 0.3 | Build the stock wheel (warm-cache; full build takes ~25–40 min on first cold build due to ~40 kernel instantiations) | `python setup.py bdist_wheel` produces a `.whl` |
| 0.4 | `pip install --force-reinstall <wheel>` into venv-vllm — REPLACES the bundled `vllm_flash_attn` | `python -c "import vllm.vllm_flash_attn as m; print(m.__file__)"` shows the dev install path |
| 0.5 | Smoke: rerun `kernel_int4_vs_fa_microbench.py` and confirm FA p50 at S=16k matches the 2026-05-20 baseline (67 μs) within ±10% | matches |
| 0.6 | Smoke: rerun `kernel_6c3a_throughput.py --cell A --prompt-tokens 32000` and confirm cell A tok/s matches the 2026-05-20 baseline (28.4 tok/s) within ±5% | matches |

### Phase 0 result (2026-05-20, GPU pod, A100-80GB, CUDA 12.8, torch 2.5.1+cu124)

**GREEN.** Built SHA `720c948` with `TORCH_CUDA_ARCH_LIST=8.0,
MAX_JOBS=16, NVCC_THREADS=2`. Wall-clock: ~48 minutes (198 build
steps). Wheel: `vllm_flash_attn-2.7.2.post1+cu128-cp312-cp312-linux_x86_64.whl`,
200 MB. Installed via `install_dev_vllm_flash_attn.sh` (overwriting
the vendored copy in venv-vllm; backup preserved at
`/workspace/dev/build-logs/vllm_flash_attn_vendored_backup`).

Smoke test result vs §20.6.3 baselines:

| Check | Baseline | Post-build | Drift | Threshold | Result |
|---|---|---|---|---|---|
| FA p50 @ S=16k | 67.3 μs | 69.6 μs | +3.4% | ±10% | PASS |
| Cell A @ S=32k | 28.40 tok/s | 28.59 tok/s | +0.7% | ±5% | PASS |

Observation worth recording: the dev build's `.so` sizes differ
materially from the vendored:

| File | Vendored | Dev build | Δ |
|---|---:|---:|---:|
| `_vllm_fa2_C.abi3.so` | 221 MB | 137 MB | −38% |
| `_vllm_fa3_C.abi3.so` | 276 MB | 648 MB | +135% |

FA2 smaller is expected (sm_80-only restriction vs vendored
multi-arch). FA3 larger at identical sm_80 restriction is unexpected
— likely `RelWithDebInfo` default vs vendored stripped `Release`,
and/or CUDA 12.8 vs older toolkit code-gen differences. Doesn't
affect correctness or perf (smoke confirms); record only.

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
| 1.1 | Python: add `flash_attn_with_int4_kvcache(...)` in `flash_attn/flash_attn_interface.py`. Signature accepts `q, k_cache_int4, v_cache_int4, k_scale, k_offset, v_scale, v_offset, k_fp16_protect, protect_mask, protect_indices, cache_seqlens, block_table, group_size_k=32, group_size_v=32, n_protect=0, ...`. **Phase 1: a no-op delegate** that ignores all INT4 args and calls into `flash_attn_with_kvcache` with the unmodified K/V tensors. The Phase 1 smoke test asserts bit-equality with the stock call | `flash_attn_with_int4_kvcache` returns the same tensor (bit-for-bit) as `flash_attn_with_kvcache` on identical inputs |
| 1.2 | C++: add `mha_fwd_kvcache_int4` in `csrc/flash_attn/flash_api.cpp` as a thin forwarding wrapper to `mha_fwd_kvcache`. NO new dispatch arm yet (deferred to Phase 2.1) | `import flash_attn_gpu; flash_attn_gpu.fwd_kvcache_int4` resolves and behaves identically to `fwd_kvcache` |
| 1.3 | (formerly: new dispatch arm) **Moved to Phase 2.1** per `KERNEL_6C3C_PHASE12_CODEREAD.md`: the dispatch arm only earns its existence once we have a different kernel body to route to. Phase 1 just routes the new entry back to the stock splitkv dispatch | — |
| 1.4 | (formerly: clone the .cu file) **Moved to Phase 2.1** for the same reason — a cloned identical .cu would only add build time without any behavior delta to validate | — |
| 1.5 | `Flash_fwd_params` extension: in `csrc/flash_attn/src/flash.h`, add fields `k_scale_ptr, k_offset_ptr, v_scale_ptr, v_offset_ptr, k_cache_protect_mask_ptr, k_cache_protect_indices_ptr, k_cache_fp16_protect_ptr, group_size_k, group_size_v, n_protect, is_int4kv` + strides. All NULL / 0 by default | builds; `mha_fwd_kvcache_int4` plumbs the new params through (initially all NULL) |
| 1.6 | Pybind registration in `csrc/flash_attn/flash_api_torch_lib.cpp` for the new entry | `fwd_kvcache_int4` callable from Python |
| 1.7 | Rebuild + reinstall wheel (incremental build of the touched TUs only — no kernel .cu changes) | smoke test from runbook Phase 0 still passes; the new Phase-1 parity test `flash_attn_with_int4_kvcache(...) == flash_attn_with_kvcache(...)` passes bit-for-bit |

### Phase 1 result (2026-05-20, GPU pod)

**GREEN** after one iteration. First apply had two bugs (patched the
~63KB standalone `flash_attn/flash_attn_interface.py` instead of the
~24KB vllm-specific `vllm_flash_attn/flash_attn_interface.py` which
is the one that ships in the wheel; and used absolute
`from flash_attn.flash_attn_interface import ...` in `__init__.py`
which crashed because the standalone `flash_attn` package's own
`__init__.py` imports `flash_attn_2_cuda`, not installed in
venv-vllm). Fix in `2dd93f2`: patch target → slim file; `__init__.py`
patch → relative `from .flash_attn_interface import ...`; idempotent
script now repairs the broken import line on re-run.

Second apply result:

```
PASS: flash_attn_with_int4_kvcache == flash_attn_with_kvcache (bit-equal)
  shapes: B=1 S_q=1 H_q=28 H_kv=4 D=128 S_kv=16384, dtype=bf16
Phase 1: GREEN. Safe to proceed to Phase 2.
```

Wheel size diff:
- `flash_attn_interface.py`: 24016 → 26177 bytes (+2161 — new wrapper)
- `__init__.py`: 309 → 390 bytes (+81 — re-export line)
- `_vllm_fa2_C.abi3.so`: unchanged (no kernel code modified yet)
- `_vllm_fa3_C.abi3.so`: unchanged

Phase 1 verified: additive scaffolding works without breaking
behavior. Safe to start Phase 2 — clone the kernel, add the
dispatch arm, route the Python wrapper through it, then start
modifying the kernel body.

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
| 2.1 | (moved from Phase 1) **Add the new dispatch arm + cloned kernel.** In `flash_fwd_launch_template.h` add `run_mha_fwd_splitkv_dispatch_int4kv` that mirrors the stock splitkv dispatch. Update `flash_api.cpp::mha_fwd_kvcache_int4` to route to it when `is_int4kv=true`. `cp csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_sm80.cu csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_sm80.cu` and edit the template instantiation tag to `_int4kv`. Initially the cloned kernel is IDENTICAL to the original — the smoke parity test from Phase 1.7 must still pass | dispatch + cloned kernel land; rebuild + Phase 1.7 parity test still bit-equal |

### Phase 2.1 result (2026-05-20)

**GREEN** on first try. Applied via `apply_phase2_1.sh` (commit
`db6457b`). The new `run_mha_fwd_splitkv_dispatch_int4kv` template
was inserted into `flash_fwd_launch_template.h` right after the
stock dispatch; new file `flash_fwd_split_hdim128_bf16_int4kv_sm80.cu`
landed and was auto-picked by the `flash_fwd_*.cu` glob.

Incremental rebuild: 62 .cu compilations, ~10 minutes, no errors.
`[38/62] Building CUDA object .../flash_fwd_split_hdim128_bf16_int4kv_sm80.cu.o`
confirms the new instantiation built.

Wheel diff vs Phase 1:
- `_vllm_fa2_C.abi3.so`: 137 MB → 142 MB (+4.5 MB = new dispatch
  + new instantiated kernel template). FA3 .so unchanged.

`verify_phase1.py` STILL passes (the new dispatch is dead code at
this point; Python wrapper still delegates to the stock path).

**Architectural insight from doing Phase 2.1 vs the original
runbook step ordering:** the runbook implied Phase 2.1 also
routes the Python wrapper through the new C++ entry. In practice
this requires cloning the ~150-200 line `mha_fwd_kvcache` setup
body so we can set `params.is_int4kv = true` before the dispatch.
That clone is significant. We chose to defer it to Phase 2.2 and
keep Phase 2.1 as pure dead-code scaffolding (compiles clean,
parity test still passes). Phase 2.2 is the first phase that
exercises the new path at runtime — and combines the body clone
with the routing change in one commit.

### Phase 2.2 result (2026-05-20)

**GREEN** after one iteration (forward declaration in flash.h
was missing — see commit `549b942`). New active code path:

```
Python flash_attn_with_int4_kvcache
  → torch.ops._vllm_fa2_C.fwd_kvcache_int4
  → mha_fwd_kvcache_int4 + Int4KvDispatchGuard (sets thread-local)
  → mha_fwd_kvcache (full stock param setup, ~280 lines untouched)
  → run_mha_fwd reads the thread-local → params.is_int4kv = true
  → if constexpr (bf16 && hdim==128 && !causal): route to _int4kv
  → run_mha_fwd_splitkv_dispatch_int4kv<bf16_t, 128, false>
  → run_flash_splitkv_fwd<Flash_fwd_kernel_traits<128, 64, 128,
      4, false, false, bf16_t>, false>  // SAME instantiation as stock
  → identical kernel binary
```

The new dispatch + cloned .cu instantiation point at the SAME
underlying `run_flash_splitkv_fwd<...>` template, so output is
bit-identical to the stock path. `verify_phase1.py` PASS.

Wheel diff vs Phase 2.1:
- `_vllm_fa2_C.abi3.so`: 142 MB → 142 MB (+3 KB — routing code only)
- `flash_attn_interface.py`: 26177 → 26946 bytes (+770 — new Python
  wrapper body that calls torch.ops._vllm_fa2_C.fwd_kvcache_int4
  with the right preprocessing)

**Architectural choice — thread-local routing flag.** The body of
`mha_fwd_kvcache` is ~280 lines of param setup; cloning it into
`mha_fwd_kvcache_int4` for a one-line flag flip would be a huge
diff. Instead `Int4KvDispatchGuard` is an RAII helper that sets a
file-scope `thread_local bool _int4kv_dispatch` flag, read by
`run_mha_fwd` on entry to set `params.is_int4kv`. ~15 lines of C++
added total (the helper + the read + the conditional dispatch in
`run_mha_fwd`). Future refactor: factor `mha_fwd_kvcache_impl`
out of `mha_fwd_kvcache` with a templated dispatch flag once we
have the time to cleanly restructure.

**Build-fail iteration that informed the runbook:** Phase 2.2's
first attempt died at flash_api.cpp:277 with "not declared in
this scope" for `run_mha_fwd_splitkv_dispatch_int4kv`. The
parser saw `name<...>` as `operator<` because the template name
wasn't visible. Root cause: `flash.h` provides forward
declarations for `run_mha_fwd_` and `run_mha_fwd_splitkv_dispatch`
at lines 211-212 (flash_api.cpp doesn't include the heavy
launch-template header, only flash.h). I forgot to add the
parallel forward decl for `_int4kv`. One-line fix in `549b942`.
| 2.2 | In the cloned kernel, locate the K read site: `tKgK.data() = gK.data() + flash::resolve_thread_kv_page_slice_offset<Kernel_traits>(...)` followed by `FLASH_NAMESPACE::copy(gmem_tiled_copy_KV, tKgK, tKsK, ...)` at `flash_fwd_kernel.h:~499` (and 3 other copy sites: masked K, masked V, subsequent V). Phase 2 code-read (`KERNEL_6C3C_PHASE12_CODEREAD.md`) confirms CUTLASS copy-atom **cannot** be reused for INT4 — bypass with manual `__ldg(reinterpret_cast<uint4*>)` loads + in-register unpack + dequant + scalar stores to `tKsK` | the 4 copy sites have parallel INT4 read paths gated on `params.is_int4kv` |
| 2.3 | INT4 K layout (LOCK from §5.3 + §4.3 crumbs): `(num_blocks, page_block_size, H_kv, D/2)` uint8 packed, asymmetric, with per-block `(num_blocks, H_kv, n_groups_per_block, D)` BF16 scale + BF16 offset. `group_size_k = 32` along seq, `page_block_size = 32`. Resolves §7.Q4 (`block_size = group_size = 32`) and §7.Q3 (physical block_id keying — defer prefix-cache support to v2; v1 ignores prefix-cache) | layout documented in code header of the cloned .cu |
| 2.4 | NO-OP transform proof: load FP16 K from HBM (same as stock), then in registers quantize→pack→unpack→dequantize using the same group_size_k math, before scalar stores to `tKsK`. Output must match stock FA to BF16 precision. **Use route-B's exact int4-rounding convention from `kv_policy/int4_per_channel_kv.py` — a ±1 LSB drift silently tanks the Phase 2.6 cosine** | cosine ≥ 0.9999 vs stock FA on Qwen shapes (B=1, H_q=28, H_kv=4, D=128, S=16384) |
| 2.5 | REAL INT4 read: change K HBM layout to packed uint8 (storage allocated by the test harness, not vLLM yet). Manual `__ldg(reinterpret_cast<uint4*>)` load with scaled page strides (D/2 packed), unpack to int4 in registers, dequant via scale/offset (smem miniset), scalar store to `tKsK`. NO CUTLASS copy atom — see Phase 2 risk brief | smoke test on B=1, H_q=28, H_kv=4, D=128, S=16384 returns reasonable values (finite, magnitudes within ±5σ of stock) |
| 2.6 | Correctness vs oracle: write a host-side test that quantizes a known FP16 K to INT4 with the §20.4 algorithm (asymmetric, group=32), runs both stock FA on the FP16 K and our new kernel on the INT4 K, compares to `fused_int4_attention_reference` from `int4_fused_attention_sketch.py` | both ours and oracle agree, cosine ≥ 0.999, max-abs ≤ 1e-2 across the Qwen shape grid in `kernel_6c_gpu_test.py::CASES` |

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
| 4.1 | §7.Q2 (compact vs dense) is LOCKED to **compact** in `KERNEL_6C3C_PROTECT_MASK_DESIGN.md` §3.6 — dense costs ~917 MB per 32k sequence (28 layers × full FP16 K size), compact ~44 MB. Layout: `protect_mask: (B, H_kv, D) int8`, `protect_indices: (B, H_kv, n_protect) int32`, `k_fp16_protect: (B, S_padded, H_kv, n_protect) bf16`. Per-head padding to `n_protect_per_head` keeps loads coalesced | layout headered in cloned .cu; `Flash_fwd_params` extension lands these pointers (Phase 1.5) |
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
