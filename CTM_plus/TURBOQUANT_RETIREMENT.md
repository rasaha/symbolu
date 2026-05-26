# TurboQuant / QJL KV-cache path — RETIRED

> **Status: RETIRED from the active KV-cache product path** (May 2026).
>
> This document is the durable record of why TurboQuant / QJL was
> tried as a low-bit KV-cache compression scheme, what we measured,
> and why protected-K INT4 supersedes it.
>
> **Scope of retirement:** the local TurboQuant / QJL KV-cache work
> (Track B Tier 1). Google's published TurboQuant W4A4 remains in
> the brief as external competitor / prior-art context.
> **The PCAM-edge `tq_edge_compressor.py` is NOT retired** — it
> applies a related compression scheme to PCAM attention edge
> profiles, which is a different workstream with no documented
> measured failure.

## TL;DR

| Item | Status |
|---|---|
| Local TurboQuant / QJL as low-bit KV-cache compressor | ❌ **Retired** — failed Qwen2.5-7B validation (~3052× perplexity ratio) |
| Track B Tier 1 (`--turboquant-kv` CLI, `TurboQuantKVStore`) | ❌ **Retired** — fail-fast guard added; code preserved for archaeology |
| Protected-K INT4 (the replacement) | ✅ **Active** — needle 15/15 == bf16 on 4 models, this quarter |
| Google TurboQuant W4A4 (external paper) | 🔵 **External reference only** — kept as competitor/prior-art mention |
| PCAM-edge TurboQuant (`simulator/pcam/tq_edge_compressor.py`) | ✅ **Unchanged** — different use case, no measured failure for that workstream |

## What was attempted

Three local TurboQuant / QJL configurations were tested as low-bit
KV-cache compressors on Qwen2.5-7B in `PHASE4_GPU_FINDINGS.md` §17:

1. **TurboQuant baseline** — random rotation + 3-bit polar quant +
   KV-only application.
2. **Baseline + per-channel scale rescue** — borrowed from KIVI to
   try to recover the catastrophic quality drop.
3. **Baseline + sink-skip rescue** — first-N positions kept FP16,
   rest TurboQuanted.

Plus the engineering scaffolding:

* `kv_policy/turboquant_kvstore.py` — Tier 1 (numpy) + Tier 2 (torch)
  `TurboQuantKVStore` that owns N compressed blocks, each holding
  K + V tensors of one `(block_size, num_kv_heads, head_dim)` slot.
* `kv_policy/turboquant_torch.py` — torch-ops port of the numpy
  reference compressor.
* `kv_policy/turboquant_hf_cache.py` — HuggingFace `DynamicCache`
  subclass that routes K/V through `TurboQuantKVStore`.
* `--turboquant-kv` CLI flag on `run_streaming.py` (Track B Tier 1
  surface; the actual `cache_kv` monkey-patch never landed).
* `Bench/scripts/track_d_capture_kv.py` — offline TurboQuant
  variation harness for captured KV activations.

## What failed (measured)

From `PHASE4_GPU_FINDINGS.md` §17:

| Config | Result on Qwen2.5-7B |
|---|---|
| TurboQuant baseline (random rotation, 3-bit, KV-only) | **Perplexity ratio 3052×** vs bf16 baseline — catastrophic quality blow-up |
| Baseline + per-channel scale rescue | **24× worse** than the random-rotation baseline (KIVI's per-channel trick does not transfer to rotation-based designs) |
| Baseline + sink-skip rescue | Modest 27% improvement, still catastrophic at **220× perplexity ratio** |

The 3052× perplexity ratio is the load-bearing negative. No
single-axis change (per-channel scale, sink-skip) recovered
useful quality. The retirement decision is: **this implementation
is not a viable low-bit KV-cache path at the configurations we
tested**.

### Caveats — what this negative does NOT prove

* It does **not** refute Google's published TurboQuant W4A4 result
  on Llama-2 / Gemma. Our config diverged on four axes:
  - random rotation vs Google's learned-polar rotation
  - 3-bit vs the paper's 4-bit headline config
  - KV-only vs W4A4 (weights + activations)
  - Qwen2.5 vs Llama-2 / Gemma
* It does **not** mean the PCAM-edge compression scheme is broken.
  That scheme applies a related transform to attention edge
  profiles (`simulator/pcam/tq_edge_compressor.py`) and has its own
  validation track — uncoupled from the KV-cache path.
* It is **measured at one config on one model**; reproducing
  Google's full method on Llama-2 was filed at the time as
  deferred follow-on and is now **out of scope** for the active
  product path.

## Why protected-K INT4 replaces it

The replacement is described in detail in
`INT4_PROTECTED_VC_BRIEF.md` and `INT4_PROTECTED_README.md`.
Key replacement properties:

| Property | TurboQuant / QJL (our config) | protected-K INT4 (the replacement) |
|---|---|---|
| Long-context needle retrieval | catastrophic | **15/15 = 100% == bf16** (4 models, single-run per model in v1) |
| Bit-identical greedy decode | not measured beyond perplexity | **3/6 prompts bit-identical vs bf16** |
| Memory savings | 5-7× (CPU-simulated, never realized in vLLM) | **0.50× of bf16** (measured in vLLM via paged cache) |
| Integration surface | Track B Tier 1 wrapper, never wired into vLLM's cache_kv | `Int4ProtectedAttentionImpl` swap + forked FA kernel — shipped |
| Methodology | random rotation + polar bit-packing | calibrated per-(layer, head, channel) magnitude-based protect mask + int4 nibble pack |

Protected-K INT4 takes the same memory tier (~0.5× of bf16) and
delivers measured quality parity instead of the rotation-based
catastrophic failure. It is the supersedant.

## What stays in the codebase (and why)

Per the retirement directive: **keep code in-tree for archaeology
and reproducibility; strip partner-facing forward-looking language;
add fail-fast guards on accidental selection.**

Kept (unchanged source, fail-fast at construction or selection):

* `kv_policy/turboquant_kvstore.py` — `TurboQuantKVStore` now raises
  `RuntimeError` on construction with the retirement message, unless
  the bypass env var `TURBOQUANT_KV_RETIRED_BYPASS=1` is set (for
  archaeology / reproducing the negative result).
* `kv_policy/turboquant_torch.py` — lower-level torch helper; no
  guard added (it's a utility, not a product path entry point;
  guarded indirectly via the kvstore).
* `kv_policy/turboquant_hf_cache.py` — `TurboQuantCache`
  (HF `DynamicCache` subclass); imports `TurboQuantKVStore`
  internally, so the kvstore guard catches this too.
* `CUDA/turboquant.cu` / `turboquant_benchmark.cu` /
  `turboquant_ctxl_integration.cu*` — CUDA kernels; not currently
  loaded by any active product code; left in place as kernel-source
  archaeology.
* `Bench/scripts/track_d_capture_kv.py` — Track D offline-capture
  script; constructs `TurboQuantKVStore` and will therefore
  fail-fast through the kvstore guard. Re-runnable for archaeology
  with the bypass env var.
* `Bench/tests/test_turboquant_kvstore.py`,
  `test_turboquant_kvstore_torch.py`,
  `test_turboquant_hf_cache.py` — tests now set
  `TURBOQUANT_KV_RETIRED_BYPASS=1` at module import so the negative
  result remains reproducible.
* `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md` and CPU benchmark
  scripts — historical record; unchanged.

Removed / softened in docs:

* `INVESTOR_PITCH.md` — the forward-looking "TurboQuant W4A4
  reproduction on Llama-2-7B | Not yet attempted. Estimated 2-4
  engineer-weeks..." row removed. The "8.8× combined-stack" row's
  forward-looking clause about "If a future session reproduces
  Google's W4A4..." softened to point at this retirement doc. The
  historical-negative findings rows (3052× perplexity, etc.) and
  the peer-positioning external-competitor paragraph remain.
* `TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` — banner prepended
  marking the document historical / retired, with a pointer here.
  Body kept for architecture archaeology.

Guards added:

* `run_streaming.py --turboquant-kv` flag — args parser still
  accepts it (so old reproduction commands don't choke on
  "unrecognized argument") but `main()` raises `SystemExit` with
  the retirement message before any engine init.
* `TurboQuantKVStore.__init__` — raises `RuntimeError` unless the
  bypass env var is set.

Guard message (canonical):

> TurboQuant/QJL KV path retired after failed local validation;
> see TURBOQUANT_RETIREMENT.md

## Code disposition decision matrix (for future maintainers)

If you're tempted to delete the retired code, run through this
matrix first:

| Reason to delete | Counterargument | Decision |
|---|---|---|
| "No one uses it" | Archaeology / reproducing the negative is sometimes asked-for in diligence | Keep |
| "It's confusing" | The fail-fast guard + this doc resolves the confusion | Keep |
| "Maintenance cost" | The code is frozen — no maintenance required as long as it doesn't break Python imports | Keep |
| "Tests fail" | Tests set the bypass env var; they reproduce the negative result, which IS the contract | Keep |
| Active import in production code | None found as of retirement date | (Would warrant deletion if true) |

If a future maintainer discovers an active production import
that's bypassing the guard, the right move is to **fix the
import** (remove or guard it), not delete the underlying code.

## Revisit conditions

This work could be revisited if any of the following holds:

1. **Reproducing Google's actual published method** — learned-polar
   rotation (not random), 4-bit (not 3-bit), with the full
   calibration pipeline. Estimated 2-4 engineer-weeks for a clean
   attempt. Would belong in a NEW workstream, not in revival of
   the retired path.
2. **A different bit-depth target** that protected-K INT4 doesn't
   serve (e.g., 2-bit storage with a tolerable quality drop).
   TurboQuant's rotation transform might be more competitive at
   2-bit, where per-channel calibration alone might not be enough.
3. **A hardware path that favors rotation-based formats** — e.g.,
   NVFP4 / FP4 on Hopper / Blackwell, if the rotation transform
   composes well with the hardware-native format.

None of these are committed work. They are notes for the next
maintainer who asks "is there any reason to look at this again?"

## Artifact pointers

| Topic | Reference |
|---|---|
| Original negative-result documentation | `Bench/bench_out/PHASE4_GPU_FINDINGS.md` §17, §17.8, §19.2 |
| Architecture/design doc (now historical) | `TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` (retirement banner prepended) |
| CPU benchmark | `CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md` |
| Investor pitch historical-negative section | `CTM_plus/INVESTOR_PITCH.md` §"Tested-and-failed" |
| Replacement (active path) | `INT4_PROTECTED_VC_BRIEF.md`, `KVPolicy/INT4_PROTECTED_README.md` |
| Guard env var | `TURBOQUANT_KV_RETIRED_BYPASS=1` (set this only for archaeology / reproducibility) |
