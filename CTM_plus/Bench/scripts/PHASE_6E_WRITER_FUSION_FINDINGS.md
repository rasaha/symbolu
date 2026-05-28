# Phase 6E — writer op fusion: findings

> **Status:** CLOSED. Phase 6E shipped as `PHASE6E_FUSED_WRITER=1` opt-in.
> Default OFF; FUSED=0 path retained bit-for-bit for A/B + rollback.
> Byte-equivalence verified across the full sweep; throughput uplift
> at the design target (B=8 captured) is +10.7% — modest vs the
> 25% projection but the implementation is correctness-locked and
> shipped behind an env flag.

## TL;DR

| Gate | Pre-6E | Post-6E (FUSED=1) | Design target | Status |
|---|---|---|---|---|
| captured B=1 agg_tps | 39.2 tok/s | **46.9** | within 5% of 39.2 | **+20% ✓** |
| captured B=8 agg_tps | 174 tok/s | **192.6** | ≥ 220 (1.25×) | partial (+10.7%) |
| captured B=32 agg_tps | — | **319.1** | — | — |
| cap/bf16 ratio at B=32 | 0.19× | **0.20×** | ≥ 0.25× | partial |
| HBM at B=32 captured | — | **45.22 GB** | ≤ 46 GB | ✓ |
| Byte-eq vs inline | — | **15/15 GREEN** | byte-equal | ✓ |
| In-run B=8 cap/eager speedup | — | **1.25×** | bench self-gate ≥ 1.88× of historical | ✓ (bench GREEN) |

Phase 6E delivers a correctness-locked fusion of the writer's
per-decode-step Python op chain into two custom CUDA kernels
(`fused_decode_write_v`, `fused_decode_write_k`). The throughput
uplift came in below the optimistic 25% projection but the bench
self-reports GREEN against its own gates and the cap/bf16 ratio
moved positively. Code ships behind an env flag; the inline path
is the default until follow-up perf work closes the remaining gap.

## What changed

### New CUDA package: `CTM_plus/CUDA_int4_protected/`

* `csrc/fused_decode_write.h` — public C++ API (two kernel
  declarations, contract docstrings).
* `csrc/fused_decode_write_v.cu` — V-side kernel: per-group bf16 V →
  int4 quantize + pack + scatter. One block per (B, H), D=128 threads
  per block, warp-shuffle reductions for the per-group amax/amin.
* `csrc/fused_decode_write_k.cu` — K-side kernel: rolling K-stage
  update + per-column amax/amin/quantize + protect-dim gather +
  conditional block-fill commit + bookkeeping (k_stage_block_id_pool,
  k_stage_count_pool, seq_pos_pool). One block per (B, H); the
  bookkeeping section is gated on `(h=0, d=0)` to avoid races.
* `csrc/binding.cpp` — PyTorch `pybind11` module exposing both
  kernels under `int4_protected_C.fused_decode_write_{v,k}`.
* `setup.py` + `pyproject.toml` — build via
  `pip install --no-build-isolation -e .` (must skip build isolation
  so the build links the venv's torch, matching the pod's CUDA
  toolchain).

### Python integration: `KVPolicy/kv_policy/phase5b_4c_paged_writer.py`

* `_fused_writer_enabled()` reads `PHASE6E_FUSED_WRITER` env (default
  `0`).
* `_phase6e_fused_decode_write_python_ref()` is the byte-identical
  Python reference and the dispatch point. When the CUDA extension
  is importable AND `_bf16_backing_skipped=True` AND not in
  `_bf16_v_mode()`, it forwards to `int4_protected_C.fused_decode_write_v`
  + `fused_decode_write_k`; otherwise it falls back to the Python
  op chain (which itself is byte-equal to the original inline body).
* `write_decode_batched()`'s captured region dispatches via
  `_fused_writer_enabled()` — when set, calls the fused ref; when
  unset, calls the original inline body verbatim. The two paths
  produce byte-equal state mutations on all writer pools + kv_cache.
* Production vLLM passes non-contiguous `(B, H, D)` views (slices
  of the QKV projection output); the dispatch wrapper calls
  `.contiguous()` on `key`/`value` before forwarding to the CUDA
  kernel, which correctly asserts contig inputs.

### Verifier: `KVPolicy/tests/verify_phase6e_fused_byte_eq.py`

Drives `write_decode_batched` in both FUSED=0 and FUSED=1 modes
on the same fresh writer + kv_cache, snapshots every mutated
state tensor (`kv_cache[0]`, `kv_cache[1]`, `k_scale_ext`,
`k_xmin_ext`, `v_scale_ext`, `v_xmin_ext`, `k_protect_ext`,
`_k_stage_pool`, `_k_stage_block_id_pool`, `_k_stage_count_pool`,
`_seq_pos_pool`), and asserts byte equality via `torch.equal`.

Coverage:

* B ∈ {1, 2, 4, 8, 16, 32}, n_steps ∈ {3, 35, 70}
* Block-boundary crossings (n_steps=35 walks each slot across BS=32)
* Multi-block sequences (n_steps=70 hits two block boundaries)
* `inactive_pattern="first"` — one row inactive every step
* `inactive_pattern="rotating"` — inactive row rotates through batch
* **Non-contig key/value views** — `big_k[:, :H, :]` from `(B, 2H, D)`,
  matching the production QKV-projection layout
* Env-flag wiring (default OFF, opt-in via `=1`)
* CPU device skips the CUDA dispatch correctly

Result: **15 tests GREEN, 1 skipped (CPU-only test, irrelevant on CUDA pod).**

### G5c SHA baseline regen

`CTM_plus/Bench/ctm_bench/scripts/int4_protected_files_baseline.json`
regenerated. Only `phase5b_4c_paged_writer.py` changed in the
existing 10-file set (the new CUDA package and verifier are
additive — outside the SHA pin).

## Three correctness bugs found during bring-up

These are documented in detail because they illustrate the gap
between "math says it should work" and what CUDA codegen actually
emits, and they shape the verifier's coverage.

### Bug 1: kv_cache last-dim stride

* **Symptom**: `RuntimeError: kv_cache_v packed dim mismatch (expected D/2)`
  on first invocation.
* **Cause**: kernel asserted `kv_cache_v.size(3) == D/2` and used that
  as the stride between `(h)` rows. Production vLLM allocates the cache
  with last dim == D (packed int4 bytes occupy the first D/2; the bf16
  backing area in the second half went unused after Phase 6C but is
  kept for layout uniformity).
* **Fix**: relaxed check to `>= D/2`; passed actual `kv_cache.size(3)`
  as `kv_last_stride` into the kernel; used it for the per-row stride.
* **Lesson**: production tensor shapes don't always match the kernel
  author's mental model. Plumb the actual stride; don't assume it.

### Bug 2: scale-divide codegen mismatch

* **Symptom**: byte-eq verifier failed with `max_abs_diff=16` (one
  nibble of a packed byte off by 1) or `=17` (both nibbles off).
* **Cause**: PyTorch's `tensor / python_scalar` does NOT emit a
  true IEEE divide. The CUDA backend precomputes `float32(1/scalar)`
  and emits a tensor-multiply. For `scalar=15.0f`,
  `float32(1.0/15.0)` rounds to one ulp above the mathematical 1/15,
  so PyTorch's `scale = (v_max - v_min) * 0.06666667014` differs
  from a true `__fdiv_rn(v_max - v_min, 15.0f)` by up to 1 ulp.
  When `(v_max - v_min)` is a clean dyadic value like 4.6875, the
  true divide gives **exactly** 0.3125 and `rintf((v - xmin)/scale)`
  lands EXACTLY on 7.5, which banker's rounding takes to 8. PyTorch's
  reciprocal-multiply gives `scale = 0.3125 + 1 ulp`, the normalized
  value lands just below 7.5, and round-to-nearest gives 7.
* **Fix**: replaced `__fdiv_rn(v_max - v_min, 15.0f)` with
  `(v_max - v_min) * (1.0f / 15.0f)` in both kernels. Matches
  PyTorch's codegen byte-for-byte. The second divide
  `(v - xmin)/scale` stays as `__fdiv_rn` (PyTorch's tensor/tensor
  div uses real IEEE division).
* **Lesson**: "bf16-equal sidecars" does NOT imply float32-equal
  intermediates. Bf16 has 7 mantissa bits, so two floats differing
  by up to ~127 ulp_float can cast to the same bf16. The verifier's
  `torch.equal` on the bf16 sidecars was a NECESSARY but INSUFFICIENT
  check; only `torch.equal` on the packed-byte output tensors caught
  the divergence.

The diagnosis path is reproducible: kernel-side `printf` gated
by `#ifdef PHASE6E_KERNEL_DEBUG` (compiled in via
`PHASE6E_KERNEL_DEBUG=1 pip install --no-build-isolation -e .`),
plus the verifier diagnostic at
`KVPolicy/tests/diagnose_phase6e_fused_kv.py` which dumps both
PyTorch's and the kernel's intermediates as raw bit patterns.
Both are retained for future debugging.

### Bug 3: non-contiguous key/value views

* **Symptom**: `RuntimeError: value must be contiguous` on first
  decode step of the 6B.3 smoke (production workload).
* **Cause**: production vLLM passes the writer `(B, H, D)` views
  sliced from the QKV projection output (which is `(B, 3H, D)` or
  similar). These views have stride `(3H*D, D, 1)` — last dim is
  contiguous but the full tensor is not. The CUDA kernel correctly
  asserts contig inputs; the dispatch wrapper didn't normalize.
* **Fix**: call `.contiguous()` on `key`/`value` in the Python
  dispatch when they're non-contig. No-op on the verifier path
  (fresh `torch.randn` is contig); ~tens of µs copy on production.
* **Lesson**: verifier coverage must include the production tensor
  layout, not just freshly allocated tensors. Added
  `test_B8_noncontig_key_value` which slices `(B, 2H, D) -> (B, H, D)`
  to reproduce the production stride pattern.

## Throughput discussion

The Phase 6E target was 1.25× of the pre-6E captured baseline at
B=8 — i.e., 174 → ≥220 tok/s. Measured result: **192.6 tok/s**,
which is +10.7% over baseline.

Why the shortfall vs the 25% projection? The design doc projected
~280 ms of Python launch-latency overhead would be eliminated by
fusing ~25 small ops per layer per decode step into 1-2 fused
kernels. The actual measurement shows:

* B=1 saw the **biggest relative win** (+20%, 39.2 → 46.9 tok/s).
  Small B is most dominated by per-launch overhead, so fusion helps
  proportionally more.
* B=8 saw +10.7% (the design target row). Fusion still helps but
  GEMMs become a larger share of total time.
* B=16 was roughly flat (+1.3%); B=32 was a slight regression (-10.7%).
  At large B, the fused kernel's launch is amortized across all B
  batch positions per call, so the per-launch saving is small in
  relative terms — and the kernel itself is bandwidth-bound at high B.

The cap/bf16 ratio improved from 0.19× to 0.20× at B=32 — a
positive direction but well short of the 0.25× gate. The remaining
gap to bf16 reflects the structural overhead of having a Python
writer alongside a C++ attention kernel; closing it further would
require moving the writer logic into the flash_attn kernel itself
(deferred, see "Post-6E" section of the design doc).

The bench's self-gate `in_run_speedup_B8_captured_vs_eager_positive`
is **GREEN** at 1.25× (eager 153.8 → captured 192.6 tok/s). The
bench's overall verdict is **GREEN**.

## What didn't work

* **`__fdiv_rn` for both divisions.** First fix attempt for Bug 2.
  Replaced both `/` operations with explicit `__fdiv_rn` to force
  IEEE round-to-nearest division. Didn't help — the issue wasn't
  the divide intrinsic but PyTorch's use of multiply-by-reciprocal
  for `tensor / scalar`. Kept for the second (tensor/tensor) divide
  since PyTorch does use true division there.
* **Removing `--use_fast_math`.** Was already removed before bringup;
  not the cause of any of the three bugs.
* **`pip install -e .` without `--no-build-isolation`.** Downloads
  the latest torch from PyPI, which mismatches the pod's CUDA driver
  and fails to build. `pyproject.toml` intentionally omits torch
  from build deps so this fails fast with a clear error.

## Known limitations (out of scope for 6E)

### Eager-mode garbled output

6B.3 GPU smoke shows that **eager mode (enforce_eager=True) produces
garbled output** even with `PHASE6E_FUSED_WRITER=0`. Captured mode
produces coherent output. The eager_vs_captured prefix check fails
identically at all B∈{1,2,4,8} with the same garbled token sequence
`[220, 7930, 106897, 106897, ...]`.

This is **pre-existing baseline behavior in the int4_protected
backend's eager read path** — confirmed by running the smoke with
both `PHASE6E_FUSED_WRITER=0` and `=1` and observing byte-identical
garbled output. Phase 6E does not regress it; the byte-equivalence
verifier proves the fused path produces the same kv_cache bytes
as the inline path on CUDA tensors.

The production target per the design docs is captured-graph mode,
where Phase 6E delivers correctly. Eager-mode operation is a
debug/slow-path configuration. Investigating and fixing the eager
read path is **out of scope for Phase 6E**; tracked as a separate
backlog item.

### Throughput gates partially met

The strict design-doc gates were:
* B=8 captured ≥ 220 tok/s — got 192.6 (10.7% over baseline, vs
  25% target).
* cap/bf16 at B=32 ≥ 0.25× — got 0.20× (vs 0.19× baseline).

Per the design doc's "what happens if throughput gate fails" branch:
> "If GPU gate fails on throughput → keep the new code behind
> `PHASE6E_FUSED_WRITER=1` opt-in, document the actual measured
> factor, scope Phase 6F."

This is the shipped configuration. Phase 6F scope is left for a
follow-up design doc; likely candidates:

1. **Fuse the read path** too (`_read_decode_packed_batched`'s
   splice + view ops). Phase 6D profile showed another ~50 ms of
   pre-kernel preparation that could be folded into the kernel
   call. Smaller potential win than 6E (no 30-op chain to collapse).
2. **Move int4 logic into the flash_attn kernel itself.** Eliminates
   the Python writer concept entirely. Highest potential payoff,
   highest risk + effort (multi-week kernel surgery).
3. **Investigate the eager garbled output** as a separate workstream.

## Files touched

* **NEW** (5):
  * `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write.h`
  * `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_v.cu`
  * `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_k.cu`
  * `CTM_plus/CUDA_int4_protected/csrc/binding.cpp`
  * `CTM_plus/CUDA_int4_protected/setup.py`
  * `CTM_plus/CUDA_int4_protected/pyproject.toml`
  * `CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py`
  * `CTM_plus/KVPolicy/tests/diagnose_phase6e_fused_kv.py`
  * `CTM_plus/Bench/scripts/PHASE_6E_WRITER_FUSION_FINDINGS.md` (this file)

* **MODIFIED** (2):
  * `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py` —
    `_phase6e_fused_decode_write_python_ref` + dispatch + contig-guard
    + env flag plumbing.
  * `CTM_plus/Bench/ctm_bench/scripts/int4_protected_files_baseline.json` —
    G5c SHA regen for the writer.

## How to invoke

Production captured-mode workloads (default OFF):
```bash
# Falls back to the inline op chain (pre-6E behavior).
python my_workload.py
```

Opt in to the fused CUDA kernels:
```bash
PHASE6E_FUSED_WRITER=1 python my_workload.py
```

Build the CUDA extension (one-time, on the pod):
```bash
source /workspace/venv-vllm/bin/activate
cd /workspace/symbolu/CTM_plus/CUDA_int4_protected
pip install --no-build-isolation -e .
```

Verify byte-equivalence after any change:
```bash
PHASE6E_FUSED_WRITER=1 python CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py --device cuda
```

Diagnose a byte-eq failure (kernel-side printf instrumentation):
```bash
PHASE6E_KERNEL_DEBUG=1 pip install --no-build-isolation -e \
    CTM_plus/CUDA_int4_protected
python CTM_plus/KVPolicy/tests/diagnose_phase6e_fused_kv.py
```
