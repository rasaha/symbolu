# Phase 6K.7 — int4 dispatch fix: route int4kv_packed decode to the split-KV kernel

> **Status: FIXED & VERIFIED (eager).** One-line dispatch fix in
> `flash_api.cpp::run_mha_fwd`. Decode attention now matches bf16 ground
> truth; all prompt lengths generate coherently. The Phase 6K/6K.1/6K.2
> OOB patches were never the bug — they are valid correctness patches that
> were simply never reached, because the kernel containing them was never
> launched for decode.
>
> **Update — EAGER only (see 6K.7b below).** CUDA-graph mode
> (`enforce_eager=False`) still collapses protected decode on short/medium
> prompts, **non-deterministically**. The graph-mode Phase 6J sweep verdict
> is therefore INVALID; use `PHASE6B3_FORCE_EAGER=1` for the quality verdict.

---

## TL;DR

`run_mha_fwd()`'s dispatch ladder placed the int4 routing (packed >
int4kv > stock) **only in the split-KV (`else`) branch**. A short
int4_protected decode took the **non-split branch** — which runs the stock
`compute_attn_1rowblock` kernel that has **no int4 loaders** — so it read
the all-zero bf16 backing stub and produced an **exact zero attention
output on every layer**, every step. The fix excludes int4 modes from the
non-split branch so they always reach the wired split-KV kernel.

```diff
  // flash_api.cpp, run_mha_fwd(), ~line 331
- if (params.num_splits <= 1 && !force_split_kernel) {
+ if (params.num_splits <= 1 && !force_split_kernel
+         && !params.is_int4kv_packed && !params.is_int4kv) {
      run_mha_fwd_<elem_type, kHeadDim, Is_causal>(params, stream);   // stock non-split — no int4 path
  } else {
      if (params.is_int4kv_packed) run_mha_fwd_splitkv_dispatch_int4kv_packed<...>(...);
      else if (params.is_int4kv)   run_mha_fwd_splitkv_dispatch_int4kv<...>(...);
      else                         run_mha_fwd_splitkv_dispatch<...>(...);
  }
```

Apply script (idempotent, self-verifying, backs up first):
`CTM_plus/Bench/scripts/apply_phase6k7_int4_dispatch_fix.sh`.

---

## Why decode hit the non-split branch

The int4_protected backend **pre-gathers** a sequence's paged blocks in
Python (`get_packed_view`) and hands the kernel one contiguous
`(1, S_max, H_kv, …)` view. As a consequence, at the flash-attn entry
(`mha_fwd_kvcache`, line 1593) for an int4 decode:

* `paged_KV = false`  — no `block_table` passed (Python already gathered).
* `k_.has_value() = false` — the backend writes KV itself; no new tokens to append.
* `cache_batch_idx_.has_value() = false`.

⇒ `force_split_kernel = false`. And a short prompt is a single 32-token KV
block ⇒ `num_splits = 1`. So:

```
if (params.num_splits <= 1 && !force_split_kernel)   →   (1 <= 1 && !false)  →  TRUE
→ run_mha_fwd_<...>            (stock NON-split compute_attn_1rowblock)
→ no int4_packed_load wiring   →  reads the zero bf16 backing stub
→ Q·K = 0  (softmax_lse = ln(s_curr)),  P·V = 0   →  output ≡ 0
```

The split-KV kernel `compute_attn_1rowblock_splitkv` (flash_fwd_kernel.h
L501–1244) **does** contain the int4 loaders (L854–1110) with the correct
`s_curr = binfo.actual_seqlen_k`. It was simply never launched for this
decode shape.

---

## Why Phases 6K / 6K.1 / 6K.2 didn't fix it

Those phases fixed **OOB masking inside `int4_packed_load_{K,V}_block`**
(the `s_curr` call-site argument; zeroing K/V for positions `>= s_curr`).
All correct — but irrelevant to this failure, because **the loaders were
never invoked for decode**. The kernel containing them wasn't the one that
ran. The OOB patches remain valid correctness patches for when the loaders
*do* run (multi-block / partial-tail reads); keep them.

The OOB theory was also independently **disproven** by 6K.4: out-of-bounds
columns carried **0.0** softmax mass (the protected outlier channels make
valid scores dominate), and masked == unmasked attention.

---

## Proof chain (6K.3 → 6K.7)

| Phase | Probe | Result | Eliminated / Localized |
|---|---|---|---|
| 6K.3 | tensor-layout dump | layouts correct, dequant self-consistent | sidecars/layout OK |
| 6K.4 | masked-vs-unmasked attn + OOB softmax mass | OOB mass `0.0`; masked==unmasked; kernel ⟂ reference | **OOB theory dead**; kernel-side |
| 6K.5 | bf16 ground-truth 3-way | `INT4 dequant cos 0.987 vs TRUE`, K-fidelity 1%; **kernel output ⟂ both** | **writer correct**; kernel misreads/ignores |
| 6K.6 | zero-output probe (+ `softmax_lse`) | `out norm = 0`, **no NaN**, `lse = ln(9)` uniform; zero for all `cache_seqlens` & `causal` | not masking, not epilogue: **K/V tiles zero in-kernel** |
| source read | flash_fwd_kernel.h + flash_api.cpp | split-KV kernel is wired; `run_mha_fwd` non-split branch isn't | **dispatch ladder, one branch** |
| 6K.7 | the fix + rebuild | see verification below | **closed** |

Scripts: `phase6k4_attention_localizer.py`, `phase6k5_ground_truth.py`,
`phase6k6_zero_output_probe.py`.

---

## Verification (post-fix, eager)

`phase6k6_zero_output_probe.py`:

```
baseline (cache_seqlens=9): norm = 6.4665   (was 0.0)
softmax_lse: min=17.345  max=2905.345  neg_inf=0   (was uniform 2.197 = ln 9)
cache_seqlens sweep 1..32: all non-zero
Output text: ' The three primary colors'   (was ' The strugg性价性价')
```

`norm 6.4665` matches 6K.5's from-scratch reconstruction (`INT4=6.4639`,
`TRUE=6.3464`) — **the kernel now agrees with bf16 ground truth.** The
varied, finite `softmax_lse` confirms `Q·K` is real (K loaded, not zero).

N-bisection (`max_tokens=24`, eager) — **all coherent**, non-monotonic
garbage gone:

```
N=8   ' The three primary colors are Red, Blue, and Yellow. These are the fundamental colors...'
N=17  ' Sure! Here are three primary colors:\n\n1. Red\n2. Blue\n3. Yellow\n\nThese are the traditional'
N=30  ' Certainly! In additive color models, which are commonly used in electronic displays...'
N=44  ' Sure! Here are the three primary colors typically used in additive color models:\n\n1. **Red**...'
```

(Pre-fix expectation from `PHASE_6K_FLASH_ATTN_OOB_FIX_FINDINGS.md`:
N=8 `pérdida` garbage, N=30 degraded.)

**CUDA-graph mode: still broken — see 6K.7b (OPEN).** Confirmed post-fix:
protected decode collapses (pérdida-style) **non-deterministically** under
`enforce_eager=False` on short/medium prompts. Eager is fully fixed.

---

## Deploy gotcha (update the runbook)

vLLM loads the **vendored** extension at
`site-packages/vllm/vllm_flash_attn/_vllm_fa2_C.abi3.so`, NOT the dev tree.
The correct deploy is:

```bash
# build the wheel WITHOUT touching deps (the fork pins torch==2.4.0;
# plain `pip install -e .` DOWNGRADES torch 2.5.1 -> 2.4.0 and breaks
# torchvision/vllm), then copy the .so into vLLM's vendored slot.
cd /workspace/dev/vllm-flash-attn-dev
rm -rf build/ dist/ vllm_flash_attn.egg-info/ ; rm -f vllm_flash_attn/*.so
TMPDIR=/workspace/tmp MAX_JOBS=4 pip wheel --no-build-isolation --no-deps -w dist .
cd /workspace/symbolu
bash CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh    # copies .so into vendored slot
```

* **Do NOT** use `pip install -e .` for this fork: it leaves vLLM's
  vendored copy stale (so the fix never takes effect) AND downgrades torch.
* If torch was already clobbered: `pip install --no-deps --force-reinstall "torch==2.5.1"`.
* Restore the stock vendored copy: `restore_vendored_vllm_flash_attn.sh`.

---

## Implications for prior phase numbers

Pre-fix, **every int4_protected decode ran the stock non-split bf16 kernel
over a zero stub** — not the int4 split kernel — and produced zero
attention. Therefore:

* **Phase 6J quality:** the `pérdida`/`性价` garbage was this bug. Re-run
  the 6J quality A/B now that decode actually works; protected-vs-naive
  agreement should finally be meaningful.
* **Phase 6E/6H throughput:** the decode kernel that was timed was the
  *stock non-split* kernel over a tiny zero stub, **not** the int4 dequant
  kernel. Those decode-throughput numbers do **not** reflect the int4 path
  and should be re-measured post-fix.
* **Memory/capacity (6G/6H):** unaffected (measured allocations, not output).

---

## Phase 6K.7b — residual CUDA-graph protect collapse (OPEN)

The dispatch fix closed the **eager** path completely. **CUDA-graph mode
(`enforce_eager=False`) is still broken** for the protected cell, and it is
**non-deterministic**.

Evidence (same `.so`, protected, default 4pct mask, `PHASE6E_FUSED_WRITER=1`):

```
                                            eager           graph
"List three primary colors…" (N≈9)   ' …Red, Blue…' ✓   ' The pérdida pérdida…' ✗
"What is the capital of France?" (N≈13) ' …Paris.'   ✓   run A: ' …Paris.' ✓ / run B: ' pérdida…' ✗
```

The **same prompt** produced `'Paris'` on one graph run and a `pérdida`
collapse on the next → output depends on run-to-run state, i.e.
**uninitialized / stale memory or a capture-replay race**, not a quality
limitation.

**The graph-mode Phase 6J full sweep verdict is INVALID.** Run in graph mode it
returned `PROTECT_MASK_NOT_VALIDATED`, but the token-agreement column was
`~0.05` for **both** naive and protected, **identical across all three mml**
(naive `33/570`, protected `21/570` at 8K/16K/32K) — that is the collapse, not
a quality measurement. Needle stayed high (0.86–0.94) only because the secret
code is emitted before the collapse, so needle is not a coherence signal here
and the small `prot−naive` needle gap (+0.02…+0.08) from a collapsed run is
meaningless. **Do not act on that verdict / do not close the line on it.** The
dispositive quality A/B must run with `PHASE6B3_FORCE_EAGER=1` (int4 cells
eager, where protected is verified correct).

Localization (in progress): graph capture forces the int4 read down the
capture-only **batched** path — `_read_decode_packed_batched` +
`_splice_k_partial_tail_batched_unconditional` + the captured
`write_decode_batched` + the precapture-hook one-time pool sync
(`_sync_pool_counters_from_states`, sentinel-gated on
`_k_stage_block_id_pool == -1`) — all of which the verified **eager B=1** path
(`_read_decode_packed_one` + `_splice_k_partial_tail`) bypasses. naive (mask all
zeros → no protected channels) survives graph mode; protected (5 channels/head
via the bf16 sidecar) does not → the fault is in the protect-sidecar handling
of that capture-only path. Non-determinism ⇒ a read-before-init / stale-pool
issue is the leading hypothesis.

Probe: `phase6k8_graph_state_probe.py` (behavioral — first-vs-warm,
within/cross-process determinism, prompt-length map; the kernel can't be
intercepted under graph replay).

**Status: OPEN. Production blocker for captured-graph decode; independent of
the (eager) quality verdict.**

## Cross-references

* `apply_phase6k7_int4_dispatch_fix.sh` — the fix (idempotent apply script).
* `phase6k4_attention_localizer.py`, `phase6k5_ground_truth.py`,
  `phase6k6_zero_output_probe.py` — the dispatch-bug localization probes.
* `phase6k8_graph_state_probe.py` — 6K.7b CUDA-graph collapse characterizer.
* `PHASE_6K_FLASH_ATTN_OOB_FIX_FINDINGS.md` — 6K/6K.1/6K.2 OOB patches
  (valid correctness patches; not the bug).
* `install_dev_vllm_flash_attn.sh` / `vc_brief_tier_a_install_int4_kernel.sh`
  — vendored-slot deploy.
