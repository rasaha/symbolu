# Phase 9 Step 2 — A/B harness runbook (`phase9_step2_ab.sh`)

> **What it is:** a properly-configured GPU A/B that measures (1) the int4
> decode-tax curve and (2) **the decisive piece — the attention bridge's per-step
> dispatch overhead** (Cython-vs-Python evictor = the Phase-8 −20% question = the
> PCAM gate). CPU-authored; runs on the pod. ~$0.50–1.00.

## ⚠ Scope — what this does and does NOT measure

Per `PHASE9_READSKIP_NOT_IMPLEMENTED.md` (RECONCILED conclusion): the CTM+ evictor
is **cross-request prefix-pool management**, not intra-sequence sparsity. So:

- ✅ **Measures:** the int4 vs bf16 throughput curve under a *correct* config (the
  smoke's cells were void — `GPU_UTIL=0.26` starved the cache to 0 completions);
  and the **dispatch overhead** of the route-A + attention-bridge stack via a
  Cython-vs-Python evictor control.
- ❌ **Does NOT measure** the Step-0 intra-sequence read-skip prize (~1.9× from a
  single long sequence skipping its own cold middle). That mechanism is **not
  implemented** and is a kernel build — gated below.

## Cells (same workload, same budget, prefix-caching matched ON)

| cell | stack | what it isolates |
|---|---|---|
| `c0_bf16` | bf16, LRU | ceiling |
| `a_int4` | route-A int4, LRU | all-int4 dense (reads everything) |
| `b_bridge_cy` | int4 + `--ctm-plus --phase3-attention --phase4-cython-evictor --phase4-fast-hooks` | the escape-the-tax stack |
| `bpy_bridge_py` | int4 + `--ctm-plus --phase3-attention` (Python evictor) | dispatch-attribution control |

**Decisive number = `b_bridge_cy` tps − `bpy_bridge_py` tps.** Cython ≫ Python ⇒
the bridge is CPU-dispatch-bound in Python ⇒ **the empirical PCAM case**. Cython
≈ Python ⇒ dispatch is not the bottleneck on this path.

## Config fixes vs the Step-1 smoke (why its cells were void)

| issue | smoke | here |
|---|---|---|
| KV starvation | `GPU_UTIL=0.26` → 1.91 GiB → 0 completions | `GPU_UTIL=0.60` + `--max-model-len 32768` |
| eviction never exercised | `--preemption-mode swap` (swap-thrash to CPU) | `--preemption-mode recompute` (frees blocks) |
| unmatched prefix-cache | 5b ON, 5a/5c OFF (invalid A/B) | `--enable-prefix-caching` on **all** cells |
| flusher race | `dict changed size during iteration` | fixed (atomic buffer-swap, this branch) |

## Run

```bash
cd /workspace/symbolu/CTM_plus
source /workspace/venv-vllm/bin/activate
# throughput + dispatch attribution only:
bash Bench/scripts/phase9_step2_ab.sh
# also run the int4 quality regression (needle + MMLU 200q, ~$0.10):
RUN_QUALITY=1 bash Bench/scripts/phase9_step2_ab.sh
```

Tunables (env): `GPU_UTIL`, `MAX_MODEL_LEN`, `MAX_REQUESTS`, `MAX_WALL_SECONDS`,
`PROMPT_LENGTH_CHOICES`, `RUN_QUALITY`. **If any cell reports `completed=0`, raise
`GPU_UTIL` (or cut `MAX_REQUESTS`/prompt lengths) until all four complete** —
there is no valid comparison without completions.

## How to read it (and the kernel-build gate)

1. **All four complete?** If not → config, not science. Re-tune and re-run.
2. **Dispatch attribution (B vs Bpy)** — the PCAM gate. Record the delta.
3. **Quality** (if `RUN_QUALITY=1`): needle `strict=` pass + `COLLAPSE=0`, MMLU
   within `--tol-pct` of bf16. NOTE: this is an int4 **+ bridge correctness**
   regression (the single-seq needle is not eviction-stressed because the evictor
   is cross-request) — it confirms the route-A round-trip + bridge didn't break
   basic long-context retrieval, *not* an eviction keep-set quality test.

### The corrected kernel-build gate

The user's rule was "build the kernel only if Cell B fails quality." Given the
(B) finding, restate it precisely:

- **If int4 + bridge keeps quality (needle/MMLU pass)** AND the dispatch
  attribution shows the bridge is **not** dispatch-bound → the route-A int4 path
  is sound; the intra-sequence read-skip kernel is the *only* remaining way to
  capture the Step-0 prize, so build it **only if the Step-0 prize is still
  wanted** (it is a real kernel build, separately scoped).
- **If the bridge IS dispatch-bound (Cython ≫ Python)** → that is the PCAM
  justification; building intra-sequence read-skip *in pure-Python software* would
  inherit the same tax, so the kernel build must target the fast path (Cython/CUDA),
  not a Python hook.
- **If int4 + bridge FAILS quality** → fix the keep-set / round-trip first; do not
  build read-skip on top of a broken base.

In all cases the intra-sequence read-skip kernel (block_table sparsifier / sparse
decode) is a **separate build** — this harness tells you whether it's worth it and
which integration shape (Python vs fast-path) it must use.
