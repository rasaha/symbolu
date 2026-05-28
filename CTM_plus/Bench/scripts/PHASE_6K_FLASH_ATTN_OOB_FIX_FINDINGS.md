# Phase 6K — int4_packed_load OOB mask fix in vllm-flash-attn-dev

> **Status (Phase 6K.1):** APPLIED. 4 call-site fixes in `flash_fwd_kernel.h`
> confirmed present on pod. Necessary but not sufficient — bisection showed
> N=8 and N=30 still garbage in CUDA graph mode; ALL N garbage in eager mode.
>
> **Status (Phase 6K.2):** SCRIPT WRITTEN. Apply script at
> `apply_phase6k2_int4_load_oob_fix.sh`. Awaiting rebuild + re-bisection.
> The apply script is idempotent and self-verifying.
>
> **Discovery:** This bug was uncovered during Phase 6J's quality A/B
> bench. The int4_protected captured cell produced incoherent output
> (`pérdida pérdida pérdida...`) on short prompts (< ~32 tokens of
> prefill) while bf16 and naive-int4 cells worked. The bisection in
> N (prompt token count) revealed a NON-MONOTONIC failure pattern:
> N=8 garbage, N=17 coherent, N=30 degraded, N=44 coherent.
>
> Tracing the kernel call sites located the root cause; the fix is
> 4 one-line changes in `flash_fwd_kernel.h`.

## The bug

The kernel `int4_packed_load_K_block` (and its V counterpart) takes a
parameter `s_curr` that controls per-position OOB zeroing of the smem
K/V staging buffers:

```c
__device__ __forceinline__ void int4_packed_load_K_block(
    ...
    int S_max,            // buffer dimension (used for n_groups_total bound)
    int H_kv,
    int n_protect,
    int n_block_token_start,
    int s_curr) {         // <-- per-batch actual cache length

    for (int t = tidx; t < kBlockN; t += nthreads) {
        int global_t = n_block_token_start + t;
        if (global_t < 0 || global_t >= s_curr) {
            // OOB: zero the smem slot
            ...
            continue;
        }
        // Real token: load from gmem
        ...
    }
```

The caller at all FOUR int4_packed call sites in `flash_fwd_kernel.h`
(lines 969, 1020, 1080, 1115) passed `params.seqlen_k` as both
`S_max` AND `s_curr`:

```c
FLASH_NAMESPACE::int4_packed_load_K_block<...>(
    ...,
    bidh, params.seqlen_k, params.h_k, packed_n_protect,
    n_block * Kernel_traits::kBlockN, params.seqlen_k);    // <-- s_curr (BUG)
```

`params.seqlen_k` is the **buffer's S dimension** (= `n_blocks_max *
BS` = 8192 for `max_model_len=8192`), not the per-batch cache length.
So `s_curr = 8192` always, and the OOB check `global_t >= s_curr` never
fires for `global_t ∈ [0, kBlockN=128)`. **No smem-zeroing for OOB
positions.**

The kernel then reads gmem at all 128 positions. For positions ≥
actual cache_seqlens, gmem contains:

* **Positions N..31 of the partial-tail cache block**: quantized
  zero-padding written by the Python-side splice. Small but non-zero
  contribution to attention if downstream masking doesn't catch them.
* **Positions 32..127 (padded block_ids=0)**: zeros from the gathered
  kv_cache[0, padded_block_id=0] (block 0 unused at fresh init).

The kernel's downstream attention masking (`binfo.actual_seqlen_k -
n_block * kBlockN`) is designed for the BF16 cp.async path. It fires
`Clear_OOB_MN=true` on the V-side cp.async copy, but the int4_packed K
was already loaded into smem by `int4_packed_load_K_block` — the
OOB mask doesn't apply to data already in smem. Result: the OOB K
positions leak small but non-trivial bias into the attention scores,
which corrupts decode for prompts shorter than `kGroupSize=32` tokens.

## Why the failure was non-monotonic in N

Whether the leaked K values produce coherent or incoherent output
depends on **which specific channels** the protected sidecar covers
(5 calibrated channels per head). For some prompts, the 5 protected
channels carry enough signal to override the OOB bias (N=17, N=44
worked). For others, the OOB bias dominates (N=8, N=30 collapsed).

This non-monotonic behavior is what made the bug invisible across
Phases 6E-6H — those benches measured throughput/HBM/completion
counts, not output coherence. The bug-corrupted outputs were
"completed" successfully and counted toward the throughput
numerator; we were measuring the speed of broken decode.

The Phase 6B.3 captured smoke that **looked** coherent in earlier
sessions started with a Greendell prompt (~50 prefill tokens) where
the answer was already in the prompt — the model emitted `"1742"`
as its first output (a verbatim copy from prompt) and then drifted
into AI-assistant template text. That output looked OK at a glance
but wasn't real generation. The bug was always there.

## The fix

For all four int4_packed call sites, change `s_curr` from
`params.seqlen_k` to `binfo.actual_seqlen_k`:

```diff
-    n_block * Kernel_traits::kBlockN, params.seqlen_k);
+    n_block * Kernel_traits::kBlockN, binfo.actual_seqlen_k);
```

`binfo.actual_seqlen_k` is the per-batch cache length already in scope
at every call site (it's used by neighboring `FLASH_NAMESPACE::copy<
Is_even_MN, Is_even_K, /*Clear_OOB_MN=*/true>(...)` calls to mask the
BF16 path). Using it as `s_curr` makes the int4_packed OOB zeroing
fire correctly: positions ≥ actual cache length get smem-zeroed
during the load, so their post-dequant contribution to the qK GEMM is
zero.

`S_max` (the SECOND-TO-LAST argument, also `params.seqlen_k`) stays
correct — it IS the buffer dimension, used by the scale-load loop's
bounds check `global_g < n_groups_total = S_max / kGroupSize`.

## Files

* `PHASE_6K_FLASH_ATTN_OOB_FIX.patch` — applies cleanly via `patch
  -p0`. Four hunks, all the same one-line change.
* `apply_phase6k_flash_attn_oob_fix.sh` — idempotent helper script
  that applies the patch with safety checks (4-call-site count,
  pre-state verification, backup creation).

## Verification plan (next GPU session)

```bash
# 1. Apply + rebuild.
bash CTM_plus/Bench/scripts/apply_phase6k_flash_attn_oob_fix.sh
cd /workspace/dev/vllm-flash-attn-dev
pip install --no-build-isolation -e .

# 2. Bisection — should now produce coherent output for ALL four N values.
cd /workspace/symbolu
export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:$PYTHONPATH
PHASE6E_FUSED_WRITER=1 python -c "
from kv_policy.int4_protected import Int4ProtectedLLM
from vllm import SamplingParams
llm = Int4ProtectedLLM(model='Qwen/Qwen2.5-7B-Instruct', max_model_len=8192,
                       gpu_memory_utilization=0.5, max_num_seqs=8)
sampling = SamplingParams(temperature=0.0, max_tokens=24)
tests = [
    ('N≈12',  'List three primary colors and their names.'),
    ('N≈20',  'Please write me a short list of three primary colors, with each color clearly named.'),
    ('N≈32',  'Could you please write me a short detailed list of three primary colors that are typically used in additive color models, with each color clearly named for me?'),
    ('N≈50',  'Could you please write me a short detailed list of three primary colors that are typically used in additive color models with each color clearly named for me, and also briefly explain in one sentence what additive color mixing means in practice?'),
]
for label, prompt in tests:
    out = llm.generate([prompt], sampling)
    n_in = len(out[0].prompt_token_ids)
    print(f'{label} (actual={n_in} tokens): {out[0].outputs[0].text!r}')
"
```

**Expected pre-fix (current):**
```
N≈12 (actual=8):  ' The pérdida pérdida pérdida ...'                     GARBAGE
N≈20 (actual=17): ' Sure! Here are three primary colors: ...'             COHERENT (by luck)
N≈32 (actual=30): ' Certainly a a not, a. I. short ... 3D printing'      DEGRADED
N≈50 (actual=44): ' Sure! Here are three primary colors ...'              COHERENT
```

**Expected post-fix:**
```
N≈12 (actual=8):  Coherent list-of-colors output
N≈20 (actual=17): Coherent list-of-colors output
N≈32 (actual=30): Coherent list-of-colors output
N≈50 (actual=44): Coherent list-of-colors output (unchanged)
```

If all four are coherent post-fix, the bug is closed.

## Then resume Phase 6J

Once the bug is verified fixed:

1. Re-run the Phase 6J smoke (`bench_phase6j_quality_gpu.py --smoke`).
   The token-agreement metric should now show protected ≫ naive in
   agreement with bf16 (since the protect channels actually carry
   their information through attention).

2. If smoke is green, run the full Phase 6J sweep. This is the
   correctness comparison that justifies (or doesn't) the protect-mask
   design.

3. If protected ≫ naive on needle + token-agreement, the project
   ships as a long-context quality backend. If protected ≈ naive even
   AFTER the kernel fix, the protect-mask design's contribution is
   measured to be small — close as research artifact.

## Implications for Phase 6E-6H findings

The Phases 6E, 6G, 6H benches measured int4_protected captured
performance/memory/capacity on **bug-corrupted outputs**. Specifically:

* **Phase 6E throughput:** completed_tps counted broken decode
  tokens. Numbers are valid as "tokens per second through the
  decode pipeline" but the tokens themselves were partially
  incoherent. Throughput as such is unaffected by the fix (kernel
  cycle count doesn't change); ratio vs bf16 should hold.
* **Phase 6G sidecar audit:** measures memory only; unaffected.
* **Phase 6H high-load capacity:** completion counts and HBM
  measurements unaffected; throughput numbers carry the same
  caveat as 6E.
* **Phase 6J quality:** completely affected. Pre-fix Phase 6J
  smoke showed 4% token agreement for protected vs bf16 — that
  was the bug manifest. Post-fix, agreement should be much higher.

The "captured int4 is slower than bf16" finding from 6E/6H/6 long-
context holds independent of the bug — the kernel doesn't run any
fewer cycles when given short cache_seqlens. So the per-request
throughput conclusion is unchanged.

## Cross-references

* `PHASE_6J_QUALITY_COMPARISON_DESIGN.md` — design that hit the bug.
* `PHASE_6E_WRITER_FUSION_FINDINGS.md` — wrote the fused kernels that
  the int4_packed read path consumes.
* `KERNEL_6C3C_PHASE12_CODEREAD.md` — original code-read of the
  vllm-flash-attn-dev fork at `/workspace/dev/vllm-flash-attn-dev/`.

---

## Phase 6K.2 — Additional bugs in int4_packed_load.h

Bisection after applying Phase 6K.1 (correct `s_curr` argument):

```
N=8  (actual=8):  GARBAGE in CUDA graph mode; GARBAGE in eager mode
N=17 (actual=17): COHERENT in CUDA graph mode; GARBAGE in eager mode
N=30 (actual=30): GARBAGE in CUDA graph mode;  GARBAGE in eager mode
N=44 (actual=44): COHERENT in CUDA graph mode; GARBAGE in eager mode
```

### Root cause A — K Phase B/C: unguarded group scale/xmin loads

`int4_packed_load_K_block` Phase B loops over `kNGroupsPerBlock = kBlockN/kGroupSize`
groups and loads scale (Phase B) and xmin (Phase C) from HBM for each group:

```c
// BUGGY (Phase B):
if (global_g >= 0 && global_g < n_groups_total) {
    val = gmem_k_scale_base[global_g * H_kv * kHeadDim + bidh * kHeadDim + d];
}
```

This checks that the group index is within the buffer dimension but does NOT
check whether the group's tokens are within `s_curr`. For N=8 with
`kGroupSize=32`, groups 1..3 (covering tokens 32..127) were never written by
the fused writer. In eager mode their HBM locations contain stale data from a
previous request — potentially including NaN bit patterns. NaN K values corrupt
the QK GEMM and cannot be corrected by -inf masking (`nan + (-inf) = nan`).

**Fix**: Add `global_g * kGroupSize < s_curr` to each guard:
```c
if (global_g >= 0 && global_g < n_groups_total &&
        global_g * kGroupSize < s_curr) {
    val = gmem_k_scale_base[...];
}
```

### Root cause B — K Phase F: xmin written for OOB tail positions

After Phase A zeroes the packed nibbles for positions `t >= s_curr`, Phase F
computes:
```c
float x = static_cast<float>(nibble) * scale + xmin;
//      = 0              * scale + xmin
//      = xmin                         ← non-zero!
```
for positions `n` in the range `[s_curr, group_boundary)` (the OOB tail of the
last valid group). These positions get K = xmin (the minimum quantized value)
instead of 0.

When flash attention's masking loop does not fire for the block — which occurs
when `ceil_div(kBlockM + s_curr - n_block_max * kBlockN, kBlockN) == 0` for
short sequences — those non-zero K values enter the QK GEMM without -inf
correction, producing garbage attention scores.

**Fix**: Explicitly zero and skip any position where
`n_block_token_start + n >= s_curr`:
```c
if (n < 0 || n >= kBlockN || d < 0 || d >= kHeadDim) continue;
{
    const int global_n = n_block_token_start + n;
    if (global_n < 0 || global_n >= s_curr) {
        tKsK(i0, i1, i2) = Element(0);
        continue;
    }
}
```

### Root cause C — V Phase D: no OOB guard (belt-and-suspenders)

V Phase B/C already zero per-token scales for positions `global_t >= s_curr`,
so V[OOB] = `0 * 0 + 0 = 0`. However, adding the same explicit guard in
Phase D provides a second line of defence and makes the intent clear:
```c
{
    const int global_t = n_block_token_start + n;
    if (global_t < 0 || global_t >= s_curr) {
        tVsV(i0, i1, i2) = Element(0);
        continue;
    }
}
```

### Files

* `apply_phase6k2_int4_load_oob_fix.sh` — idempotent apply script (4 fixes,
  self-verifying, creates `.phase6k2_backup` before modifying).

### Verification plan

```bash
# 1. Apply fixes.
bash CTM_plus/Bench/scripts/apply_phase6k2_int4_load_oob_fix.sh

# 2. Rebuild (~1 h).
cd /workspace/dev/vllm-flash-attn-dev
TMPDIR=/workspace/tmp MAX_JOBS=4 pip install --no-build-isolation -e .

# 3. Eager bisection (must pass first).
cd /workspace/symbolu
export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:$PYTHONPATH
PHASE6E_FUSED_WRITER=0 python -c "
from kv_policy.int4_protected import Int4ProtectedLLM
from vllm import SamplingParams
llm = Int4ProtectedLLM(model='Qwen/Qwen2.5-7B-Instruct', max_model_len=8192,
    gpu_memory_utilization=0.5, max_num_seqs=8, enforce_eager=True)
sp = SamplingParams(temperature=0.0, max_tokens=24)
tests = [
    ('N=8',  'List three primary colors and their names.'),
    ('N=17', 'Please write me a short list of three primary colors, with each color clearly named.'),
    ('N=30', 'Could you please write me a short detailed list of three primary colors that are typically used in additive color models, with each color clearly named for me?'),
    ('N=44', 'Could you please write me a short detailed list of three primary colors that are typically used in additive color models with each color clearly named for me, and also briefly explain in one sentence what additive color mixing means in practice?'),
]
for label, prompt in tests:
    out = llm.generate([prompt], sp)
    print(f'{label}: {out[0].outputs[0].text!r}')
"

# 4. CUDA graph bisection (after eager passes).
bash CTM_plus/Bench/scripts/verify_phase6k_bisection.sh
```

**Pass condition for both modes:**
- No `pérdida` / `性价` repetition loops
- No topic hallucination at N=30
- All four N values produce a coherent list-of-colors response

**If all 4 N values pass in both modes:** proceed to Phase 6J smoke bench.
