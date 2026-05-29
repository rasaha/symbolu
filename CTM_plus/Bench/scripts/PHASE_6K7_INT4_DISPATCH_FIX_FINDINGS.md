# Phase 6K.7 — int4 dispatch fix: route int4kv_packed decode to the split-KV kernel

> **Status: dispatch fix landed (NECESSARY, not sufficient). Residual
> decode-collapse bug OPEN.** The one-line dispatch fix in
> `flash_api.cpp::run_mha_fwd` eliminated the **all-zero attention output**
> (kernel norm `0.0 → 6.47`, matching bf16 ground truth) — without it every
> int4 decode produced nothing. But a **deeper, non-deterministic
> pérdida-collapse bug remains** (see 6K.7b): it hits *some* prompts in
> **both eager and graph**, on **both naive and protected**, and accumulates
> across requests within a process. The Phase 6K/6K.1/6K.2 OOB patches were
> never the all-zero bug — they are valid correctness patches that were never
> reached because the kernel containing them was never launched for decode.
>
> **Phase 6J verdict (`PROTECT_MASK_NOT_VALIDATED`) is defensible on the
> NEEDLE metric only** (prot−naive `+0.04…+0.08` « `+0.20` threshold,
> consistent across 3 mml × 2 modes). The token-agreement column (`~0.04–0.11`
> for *both* cells, both modes) is **confounded by the collapse bug** and must
> not be cited as a quality measurement.

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
| 6K.7 | the fix + rebuild | all-zero output gone (norm 0→6.47) | **all-zero closed** |
| 6K.8 | graph/eager collapse probe | pérdida collapse on *some* prompts, both modes, naive+protected, non-deterministic, accumulates across requests | **residual collapse OPEN** |

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

N-bisection (`max_tokens=24`, eager) — these four are coherent, and the
all-zero output is gone:

```
N=8   ' The three primary colors are Red, Blue, and Yellow. These are the fundamental colors...'
N=17  ' Sure! Here are three primary colors:\n\n1. Red\n2. Blue\n3. Yellow\n\nThese are the traditional'
N=30  ' Certainly! In additive color models, which are commonly used in electronic displays...'
N=44  ' Sure! Here are the three primary colors typically used in additive color models:\n\n1. **Red**...'
```

> ⚠️ **This was a non-collapsing sample, NOT proof of "eager fixed."** 6K.8
> later showed eager *also* collapses on other prompts (e.g. "photosynthesis",
> "machine learning" → `pérdida`). The dispatch fix removed the all-zero
> output; it did not remove the residual collapse. See 6K.7b.

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

* **Phase 6J quality:** the all-zero output was this bug, but the
  `pérdida`/`性价` collapse is a *separate* residual bug (6K.7b) that the
  dispatch fix did NOT close. The full 6J sweep (both graph and forced-eager)
  returned `PROTECT_MASK_NOT_VALIDATED`; its token-agreement column is
  confounded by the collapse, so the verdict rests on the **needle** metric
  (prot−naive `+0.04…+0.08` « `+0.20`) → protect does not materially help.
* **Phase 6E/6H throughput:** the decode kernel that was timed was the
  *stock non-split* kernel over a tiny zero stub, **not** the int4 dequant
  kernel. Those decode-throughput numbers do **not** reflect the int4 path
  and should be re-measured post-fix.
* **Memory/capacity (6G/6H):** unaffected (measured allocations, not output).

---

## Phase 6K.7b / 6K.8 — residual non-deterministic decode collapse (OPEN, BOTH modes)

The dispatch fix removed the **all-zero** output. It did **not** remove a
deeper `pérdida`-style collapse that is **non-deterministic** and present in
**both eager and graph**, on **both naive and protected**. My earlier
"eager fixed" claim was wrong — it came from a non-collapsing prompt sample.

6K.8 evidence (`phase6k8_graph_state_probe.py`, protected, default 4pct mask,
`PHASE6E_FUSED_WRITER=1`):

```
EAGER (enforce_eager=True, confirmed in engine config):
  TEST 1  "capital of France" ×6   → all 'Paris'  (clean, identical)
  TEST 2  "photosynthesis…"        → ' Photos pérdida pérdida …'   ✗ COLLAPSE
          "machine learning…"      → ' Machine pérdida pérdida …'  ✗ COLLAPSE
          (other 4 prompts coherent)

GRAPH (enforce_eager=False):
  TEST 1  "capital of France" ×6   → req#1 pérdida ✗, req#2 degraded, req#3–6 'Paris' ✓
          (first-only-collapse = True)
  TEST 2  mixed: "programming"→'1111111…' , "machine learning"→'the the,,,' (degraded)
```

Key observations:
* **Eager collapses too** → not a graph-only / capture-only bug.
* **Accumulates across requests in ONE eager process** (TEST 1 clean → TEST 2
  collapses) → points at **writer slot-reuse / staging-buffer reset state not
  cleared on sequence eviction**, which is mode-independent (eager has no graph
  capture).
* **Graph adds a first-request init layer on top** (`first-only-collapse=True`)
  — likely the precapture-hook one-time pool sync
  (`_sync_pool_counters_from_states`, sentinel-gated on
  `_k_stage_block_id_pool == -1`).
* **Non-deterministic**: same prompt/config gives different output across runs
  (graph "capital" → Paris one run, pérdida the next; naive token-agree 0.568
  in the smoke vs 0.058 in the sweep) ⇒ read-before-init / stale state.
* **naive collapses too** (the smoke-vs-sweep naive swing) → it's an int4-path
  bug, **not** protect-specific.

### Phase 6J verdict — what it does and does NOT support

Both the graph sweep and the forced-eager sweep returned
`PROTECT_MASK_NOT_VALIDATED`. Read it carefully:

* **Token-agreement (`~0.04–0.11`, both cells, both modes) is CONFOUNDED** by
  the collapse — it measures broken decode, not quality. **Do not cite it** as
  evidence for or against the design.
* **Needle is the clean signal** (retrieval survives an occasional collapse
  because the code is copied early): `prot − naive = +0.04…+0.08`, consistent
  across 3 mml × 2 modes (6 measurements) — that's 1–2 items / 25, within noise
  and far below the `+0.20` acceptance bar.

So `PROTECT_MASK_NOT_VALIDATED` **is defensible on the needle metric**: the
protect mask does not materially improve long-context retrieval quality on this
model + workload. It is **not** a clean dual-metric refutation.

### Two separable conclusions

1. **Protect-mask research question:** answered — no material needle benefit.
   Closing / shelving the protect-mask line is justified on this evidence.
2. **int4 backend usability:** the residual non-deterministic collapse affects
   *all* int4 decode (naive + protected, both modes) → the int4 KV backend is
   **not production-usable** until it is fixed, independent of the mask. Leading
   hypothesis: stale writer/slot/staging state across sequence reuse.

Probes: `phase6k8_graph_state_probe.py` (behavioral first-vs-warm /
determinism / length map), `phase6k9_slot_reuse_probe.py` (does collapse
accumulate across sequential requests; does a writer-state reset clear it).

**Status: OPEN. Production blocker for the int4 backend; the protect-mask
research verdict (needle-based) stands independently.**

## Cross-references

* `apply_phase6k7_int4_dispatch_fix.sh` — the fix (idempotent apply script).
* `phase6k4_attention_localizer.py`, `phase6k5_ground_truth.py`,
  `phase6k6_zero_output_probe.py` — the dispatch-bug localization probes.
* `phase6k8_graph_state_probe.py` — 6K.7b CUDA-graph collapse characterizer.
* `PHASE_6K_FLASH_ATTN_OOB_FIX_FINDINGS.md` — 6K/6K.1/6K.2 OOB patches
  (valid correctness patches; not the bug).
* `install_dev_vllm_flash_attn.sh` / `vc_brief_tier_a_install_int4_kernel.sh`
  — vendored-slot deploy.
