# Kernel 6c.3C — resume / status snapshot

> Read this first when resuming work on the 6c.3C kernel-fork
> pivot. Points at the design docs, captures the current state of
> the dev pod, and gives concrete first actions.

## TL;DR

- **Working on:** 6c.3C — a fork of `vllm-project/flash-attention` (the
  vendored vLLM FA fork) at SHA `720c948`, adding INT4 KV cache with
  static protected-K channels.
- **Why this fork:** §20.6.3 closed 6c.3A as not competitive (bypass-FA-
  with-our-own-Triton-kernel loses at end-to-end throughput because
  vLLM's FA is too fast). 6c.3C lands the FA-integrated INT4 path.
- **Latest verified state:** Phase 2.4.1b GREEN at commit `23a08cc`
  (+ orchestrator/verify scripts at `97bc861`, anchor fixes at `fe92a6c`
  + `23a08cc`). Kernel-side packed-K HBM read works end-to-end:
    - `verify_phase2_4_1b.py` cosine **0.9999792** vs Phase 5A
      reference (gate 0.9995). Max-abs diff 3.66e-04, mean-abs
      6.19e-05. BF16 scale precision held — no FP32 fallback needed.
    - `verify_phase4.py` still GREEN (non-packed in-register quant
      path unchanged; cosine 0.994 Gaussian, 0.996 outlier,
      protect-K recovery 4.5 milli-cosine).
    - Phase 5A smoke still GREEN (28 prefills, 868 decodes,
      0 fallbacks, needle "XYZ123" retrieved). Template gating
      isolates packed path; non-packed callers unaffected.
  The new kernel template instantiation
  `flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu` builds and the
  three-way dispatch (`packed > int4kv > stock`) routes correctly.
  Packed-K path uses synchronous `__ldg(uint4*)` loads + per-thread
  fragment unpack/dequant/protect-blend. `cp.async` is a Phase 2.4.1c+
  perf optimization.
- **What's NOT yet done:** Phase 2.4.1c (Python install integration —
  `Phase2_4PackedCache` drops the FP16 sidecar and feeds packed kwargs
  from `phase5a_native_install.py`), Phase 2.4.2 (memory measurement —
  K sidecar bytes drop from 1.84 GB → 0.65 GB at S=32k), Phase 2.4.b
  (free vLLM paged K cache — actual HBM savings vs stock), Phase 2.6
  (V pack), Phase 5B/5C (batch > 1, `kv_cache_dtype` first-class),
  Phase 6 measurement (throughput, KV memory, real-data needle on full
  ship config).
- **Next phase:** Phase 2.4.1c — wire the packed-K path through the
  vLLM install. Replace `Phase5ANativeCache`'s FP16 K sidecar with
  `Phase2_4PackedCache` that calls `pack_k_for_phase2_4` at prefill
  end and feeds packed kwargs into `flash_attn_with_int4_kvcache` at
  decode. No CUDA work; ~0.5-1 day of Python.

## Hard scope guard (do not creep)

v1 is decode-only, static protected-K mask, INT4 unprotected K/V,
BF16 protect sidecar, **Qwen2.5-7B only**, sm80 only.

**Out of scope:** dynamic masks, pre-RoPE quant, FP4/NVFP4, speculative
decode, multi-model sweep, prefill kernel mods, FA3/Hopper instantiations,
symmetric quant, group sizes ≠ 32.

## Files to read (in order)

| File | Owns |
|---|---|
| `KERNEL_6C3C_RESUME.md` (this) | Snapshot + first actions |
| `KERNEL_6C3C_DESIGN.md` | Required architecture + v1 scope locked + PR triage outcome (base = A) |
| `KERNEL_6C3C_RUNBOOK.md` | Phase-by-phase plan + per-phase results so far |
| `KERNEL_6C3C_PHASE12_CODEREAD.md` | Source map at SHA 720c948 + Phase 1/2 surface |
| `KERNEL_6C3C_PROTECT_MASK_DESIGN.md` | §7.Q1 resolution — protect mask provenance + storage layout |
| `KERNEL_6C3C_PHASE2_3_DESIGN.md` | Phase 2.3 surface (the K read sites, insertion point, gating, effort) |
| `KERNEL_6C3C_PHASE5A_DESIGN.md` | Phase 5A — native-kernel-routed vLLM decode (BF16-backed reference path) |
| `KERNEL_6C3C_PHASE2_4_DESIGN.md` | Phase 2.4 — REAL INT4 K HBM read; locked architecture + sub-phase breakdown |
| `KERNEL_6C3C_PHASE2_4_1B_DESIGN_QUESTIONS.md` | Phase 2.4.1b open design questions + locked answers (read before writing the patcher) |

## Audit trail — branch `claude/fp8-kv-competitive-gap-zpSjg`

| Commit | Closes |
|---|---|
| `e09aee5` | 6c.3A close — §20.6.3 verdict in PHASE4_GPU_FINDINGS.md |
| `e7ce0eb` | 6c.3C design shell |
| `8d44162` | PR triage closes — base = A (fork vllm_flash_attn) |
| `eab8c3d` | Runbook |
| `5a9ce4f` | File-path fix for v0.7.3 SHA |
| `ac45ec1` | Phase 0 scripts (install + restore + smoke) |
| `4d76779` | §7.Q1 + §5.5 compact-lock |
| `6261c09` | Phase 1/2 code-read + runbook re-partition |
| `bb5928e` | **Phase 0 GREEN** (stock build matches baseline) |
| `e53e14c` | Phase 1 patch scripts |
| `2dd93f2` | Phase 1 fix (slim file + relative import) |
| `8a4ffba` | **Phase 1 GREEN** (bit-equality of no-op delegate) |
| `db6457b` | Phase 2.1 patches (dispatch + cloned .cu, dead code) |
| `0fdd1b8` | **Phase 2.1 GREEN** (build mechanics) |
| `3d3efe8` | Phase 2.2 patches (route through new path) |
| `549b942` | Phase 2.2 fix (forward decl in flash.h) |
| `200196d` | **Phase 2.2 GREEN** (route live, bit-equal) |
| `6a2347a` | Phase 2.3 design brief |
| `61f83df` | Phase 2.3 patcher + helper + verify script (builds clean) |
| `df67260` | Phase 2.3 diagnostic — algorithm drift floor ~0.997 (vs brief's 0.9999) |
| `edf0bcd` | **Phase 2.3 GREEN** (relaxed gate to 0.995, route-B match bit-for-bit) |
| `492e590` | **Phase 2.5 GREEN** (template-gated dispatch, stock perf restored 80 → 67 μs) |
| `8a39a08` | **Phase 3 GREEN** (V cache INT4 transform — per-token, axis-flipped helper) |
| `48c2b4a` | Phase 4 patcher (protect-K mask plumbing + helper extension) |
| `7993e8d` | Phase 4 gate-calibration commit (Gaussian-only test was unfair to algorithm) |
| `3f8787b` | **Phase 4 GREEN** (outlier sub-test + recovery-delta gate; 4.5 milli-cosine recovery on outliers) |
| `9c54f6b` | Docs — Phase 2.5/3/4 GREEN results recorded |
| `028cffe` | Phase 2.3 insertion-point retrospective audit |
| `095961e` | Phase 6.4 sweep (algorithm path) + decision-rule aggregator |
| `e9e48a5` | Phase 6.4 — transformers >=5.0 prophylactic check bypass |
| `e8eecbf` | Phase 6.4 long-context sweep at ~30k Qwen tokens |
| `0b80770` | Phase 6.4 aggregator — fix to match track_e JSON schema |
| `1e4dfb5` | **Phase 6.4 GREEN** — delta-gates vs FP16 baseline; 4% protect = 100% needle on real Qwen |
| `4b07f97` | Phase 5A code lands — native-kernel-routed vLLM decode installer + smoke test + design doc |
| `b821ace` | **Phase 5A GREEN** — leaf-attention fix; 0 fallbacks, 28+868 wrapped calls, needle correctly retrieved |
| `b9daf9f` | Phase 5A GREEN milestone recorded in RESUME |

## Audit trail — branch `claude/fp8-kv-competitive-gap-MNj74`

| Commit | Closes |
|---|---|
| `07511fe` | Phase 2.4 design note — REAL INT4 K HBM read; sidecar layout + sub-phase breakdown locked |
| `1c4d80b` | Phase 2.4.0 — Python pack/unpack helpers + round-trip test (GREEN; 2.84× compression) |
| `3211008` | **Phase 2.4.1a GREEN** — packed-K data plumbing (no kernel changes); Phase 5A + Phase 4 verifies still pass |
| `62c8478` | Phase 2.4.1b design-questions checkpoint (Q1/Q2/Q3 locks for the patcher) |
| `97bc861` | Phase 2.4.1b patcher + helper (int4_packed_load.h) + verify script + orchestrator |
| `fe92a6c` | Phase 2.4.1b fix — flash.h fwd-decl anchor (single-line format vs my split-line guess) |
| `23a08cc` | **Phase 2.4.1b GREEN** — OptionalInt4Scratch gate fix (V transform needs it on packed path too); cosine 0.9999792 vs Phase 5A |

## GPU pod state (as of last session)

- **Dev tree:** `/workspace/dev/vllm-flash-attn-dev` at SHA `720c948`
  with patches applied through Phase 2.4.1a (idempotent via the apply
  scripts; re-running is a no-op).
- **Backup of original vendored .so:**
  `/workspace/dev/build-logs/vllm_flash_attn_vendored_backup` — restore
  via `bash CTM_plus/Bench/scripts/restore_vendored_vllm_flash_attn.sh`
  if anything breaks.
- **Installed in venv-vllm:** the Phase 2.4.1a wheel
  (`vllm_flash_attn-2.7.2.post1+cu128`) overwrites
  `/workspace/venv-vllm/lib/python3.12/site-packages/vllm/vllm_flash_attn/`
  with the dev build. `flash_attn_with_int4_kvcache` is importable
  and accepts the new packed-K kwargs.

## Active code path (Phase 5A + 2.4.1a plumbing)

```
Python flash_attn_with_int4_kvcache (vllm_flash_attn/flash_attn_interface.py)
  → torch.ops._vllm_fa2_C.fwd_kvcache_int4
  → mha_fwd_kvcache_int4 + Int4KvDispatchGuard (thread-local ON)
  → mha_fwd_kvcache (stock 280-line param setup, untouched)
  → run_mha_fwd reads thread-local, sets params.is_int4kv = true
  → if constexpr (bf16 && hdim==128 && !causal):
      → run_mha_fwd_splitkv_dispatch_int4kv<bf16_t, 128, false>
      → run_flash_splitkv_fwd<Flash_fwd_kernel_traits<128, 64, 128, 4, false, false, bf16_t>, false>
  → (Phase 2.3+ adds the conditional in-register transform here)
```

## Smoke test commands

To verify the dev install is still working:

```bash
# 1. Import sanity.
python3 -c "
from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache, flash_attn_with_kvcache
import torch
print('OK:', torch.ops._vllm_fa2_C.fwd_kvcache_int4)
"

# 2. Bit-equality of the new path.
python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase1.py

# 3. Stock vLLM unbroken (cell A throughput).
bash /workspace/symbolu/CTM_plus/Bench/scripts/smoke_test_fa_install.sh
```

All three should PASS. If any fails on a fresh session, restore the
vendored copy:

```bash
bash /workspace/symbolu/CTM_plus/Bench/scripts/restore_vendored_vllm_flash_attn.sh
```

…then re-run the patch+build cycle:

```bash
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase1.sh        # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_1.sh      # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_2.sh      # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_3.sh      # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_5.sh      # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase3.sh        # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase4.sh        # idempotent
bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_4_1a.sh   # idempotent
# Phase 2.4.1b apply script not yet written — see DESIGN_QUESTIONS doc.
```

(All apply scripts skip already-applied patches via sentinel-string
detection. The cold rebuild takes ~10-15 min if any C++ files were
touched. Re-running through 2.4.1a end-to-end is a no-op once the
dev tree is at that state.)

## Where Phase 2.4.1b picks up

Phase 2.4.1a put packed-K pointers + `is_int4kv_packed` flag into
`Flash_fwd_params`. The kernel does not read them yet. Phase 2.4.1b
adds the kernel-side consumer:

1. New helper `csrc/flash_attn/src/int4_packed_load.h`
   (`int4_packed_load_K_block`) — cooperatively `__ldg`-loads
   packed K + scale + xmin + protect-bf16 from HBM into per-block
   smem scratchpads, then per-thread iterates the CUTLASS K-tile
   fragment doing unpack + dequant + protect blend, writing BF16
   to `sK`.
2. New `bool Is_int4kv_packed = false` template parameter threaded
   through `compute_attn_1rowblock_splitkv` → `compute_attn_splitkv`
   → `flash_fwd_splitkv_kernel` → `run_flash_splitkv_fwd` (mirrors
   Phase 2.5's `Is_int4kv` propagation).
3. New `run_mha_fwd_splitkv_dispatch_int4kv_packed` + new `.cu`
   instantiation file `flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu`
   (mirrors Phase 2.1's pattern).
4. `flash_api.cpp` `run_mha_fwd` gains `if (params.is_int4kv_packed)`
   branch ahead of the existing `_int4kv` arm.

**Open design questions locked in
`KERNEL_6C3C_PHASE2_4_1B_DESIGN_QUESTIONS.md`:**

- Q1: `kPackedNProtectMax = 16` (smem alignment + safe-mode headroom)
- Q2: Pad `k_protect_bf16` in Python at `PHASE2_4_N_PROTECT_MAX = 16`
- Q3: BF16 scale/xmin storage default; FP32 fallback flagged as
  one-line patcher flip if cosine misses 0.9995

**Acceptance:** `verify_phase2_4_1b.py` cosine ≥ 0.9995 vs Phase 5A
reference on Qwen2.5-7B-shaped K at S=16k. Phase 4 + Phase 5A smoke
tests still pass (template gating isolates the packed path).

**Effort estimate:** 1.5-2.5 hours of focused session time including
rebuilds (~15-20 min each) and 1-2 iteration rounds for cosine
fixup or BF16→FP32 fallback.

**Files to modify:** see the file list in
`KERNEL_6C3C_PHASE2_4_1B_DESIGN_QUESTIONS.md`.

## What NOT to do in Phase 2.4.1b

- Don't pack V. That's Phase 2.6 (mirror of Phase 2.4 for V).
- Don't free vLLM's paged K cache. That's Phase 2.4.b.
- Don't add `cp.async` for the HBM load — `__ldg` first; `cp.async`
  is a perf optimization for 2.4.1c+.
- Don't extend to batch > 1. That's Phase 5B.
- Don't add prefill kernel modifications.
- Don't widen instantiation beyond bf16/hdim=128/non-causal —
  template explosion is real (3 splitkv specializations already:
  stock, `_int4kv`, `_int4kv_packed`).
