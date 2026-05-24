# Phase 5A — native-kernel-routed vLLM decode (BF16-backed KV cache)

> **Scope discipline.** Phase 5A is the routing+quality proof phase.
> It demonstrates that vLLM can call our `flash_attn_with_int4_kvcache`
> kernel end-to-end on a real model and produce sensible decode outputs
> with a static top-fraction protect-K mask. It does NOT claim
> any HBM memory savings — that's Phase 2.4 / later block-manager work.

## What Phase 5A delivers

1. A Python installer `install_phase5a_native(model, ...)` that
   monkey-patches each Attention layer's `forward` in a running vLLM
   model.
2. End-of-prefill computation of a per-(layer, kv_head, dim) protect
   mask from K magnitudes (top-`protect_fraction` channels, default
   0.04 per Phase 6.4 GREEN).
3. Decode-path bypass: every decode step routes through
   `flash_attn_with_int4_kvcache(q, k_cache, v_cache, cache_seqlens,
   protect_mask=mask, n_protect=...)` instead of vLLM's stock
   PagedAttention.
4. Process-level state lifecycle (`manager.reset()` between sequences,
   `teardown()` to fully uninstall).

## What Phase 5A does NOT deliver

- **No HBM memory savings.** The wrapper maintains a PARALLEL FP16
  sidecar `(1, max_seqlen, H_kv, D)` per layer for K and V. At
  Qwen2.5-7B + max_seqlen=32768 + 28 layers + H_kv=4 + D=128, this is
  ~3.7 GB of additional KV (FP16, 2 bytes/elem). vLLM's own paged
  cache also holds the same K/V (because we still call the original
  forward for prefill, which populates the paged cache as a side
  effect). Net effect: Phase 5A roughly **doubles** KV memory at v1.
- **No vLLM-side `kv_cache_dtype="int4_protected"` registration.**
  The install is a user-explicit Python call, not a first-class
  config option. Phase 5C (or wherever) makes it a top-level vLLM knob.
- **No batch > 1.** Single-sequence only. Multi-sequence dispatch is
  Phase 5B.
- **No prefix caching.** Sidecar is per-process, not shared between
  sequences.

## Architecture

### Per-layer sidecar (`Phase5ANativeCache`)

Stored layout: `(1, max_seqlen, H_kv, D)` FP16 for both K and V. This
is the exact shape `flash_attn_with_int4_kvcache` expects for
`k_cache` / `v_cache`, so no contiguous() / transpose on the decode
hot path.

State fields:

| Field | Meaning |
|---|---|
| `k_fp16` / `v_fp16` | The parallel sidecar buffers, lazily allocated on first prefill. |
| `s_curr` | Current cached sequence length (number of tokens written). |
| `protect_mask` | `(1, H_kv, D) int8` — 1 means "protected, skip quant in kernel". Computed once per prefill. |
| `mask_frozen` | Bool. True after first `compute_protect_mask` call. |
| `n_protect` | Per-(B, H_kv) count of protected channels (= `round(D * protect_fraction)`). |

### Manager (`Phase5ANativeManager`)

Owns `Dict[int, Phase5ANativeCache]` keyed by `id(module)` so each
attention layer in the model gets a distinct cache. Tracks call
stats (prefill_calls, decode_calls, fallback_calls) for sanity
verification.

`manager.reset()` clears all per-sequence state (`s_curr`,
`protect_mask`, `mask_frozen`) on every cache. Buffers stay
allocated so the next sequence reuses them. Caller must invoke
`reset()` between sequences (vLLM doesn't expose a per-sequence
cleanup hook we can register to).

### Wrapper logic

For each attention module, `forward` is replaced with a thin shim:

```
T = key.shape[0]
cache = manager.get_or_create(id(module))

if T > 1:                       # PREFILL
    cache.append(key, value)    # populate sidecar
    cache.compute_protect_mask(manager.protect_fraction)
    return original_forward(...)  # vLLM's stock attention runs

else:                           # DECODE (T == 1, batch=1 assumption)
    cache.append(key, value)
    out = flash_attn_with_int4_kvcache(
        q, cache.k_fp16, cache.v_fp16,
        cache_seqlens=tensor([cache.s_curr]),
        protect_mask=cache.protect_mask,
        n_protect=cache.n_protect,
    )
    return out  # bypass vLLM's PagedAttention
```

Fails open: any unexpected condition (shape mismatch, missing
kernel, mask not yet frozen, exception in kernel) falls back to
`original_forward`. Stats record fallback count for visibility.

### Sequence identity

V1 batch=1: there's no explicit sequence ID anywhere. The single
cache per layer is implicitly "the current sequence". `reset()` must
be called between user-level requests; the wrapper does NOT detect
sequence boundaries on its own.

If two sequences arrive concurrently (batch=2 decode call), `T` will
equal 2 (one new token per sequence), which the wrapper currently
mis-interprets as prefill. **This is the v1 limitation** — the test
harness must serialize requests.

## V1 protect_fraction policy

Per Phase 6.4 GREEN (commit 1e4dfb5, run on real Qwen2.5-7B at
~30k tokens):

- **Default: `protect_fraction = 0.04`.** Achieves 100% needle
  retrieval, matching FP16 baseline exactly (needle_delta = 0.0%).
  Supporting metrics (repeated_token_rate, first_stutter) also match
  baseline. Some additional post-answer entropy collapse vs baseline,
  but that's confident-decode behavior, not a failure.

- **Safe mode: `protect_fraction = 0.08`.** Also 100% needle. Use
  if downstream decode-quality issues appear that the synthetic
  needle test doesn't catch. Cost: ~4% extra effective KV memory
  (i.e., 4 more channels out of 128 stay BF16-equivalent in the
  kernel's in-register transform — net ~0% HBM impact since HBM
  is BF16 either way at Phase 5A).

- **0% (no protection):** decode collapses (33% needle on the same
  test). Documented as the "this is why protect-K exists" data
  point; not a runtime option in Phase 5A.

## API

```python
from vllm import LLM, SamplingParams
from kv_policy.phase5a_native_install import install_phase5a_native

llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=32768)

# Locate the underlying nn.Module (path varies by vLLM version).
model = llm.llm_engine.model_executor.driver_worker.model_runner.model

manager, teardown = install_phase5a_native(
    model,
    protect_fraction=0.04,        # 0.08 for safe mode
    max_seqlen=32768,
    # num_kv_heads auto-detected from model.config
)

# Generate.
outputs = llm.generate(["Hello"], SamplingParams(temperature=0, max_tokens=32))

# Between sequences:
manager.reset()

# Inspect stats:
print(manager.stats())
# {'prefill_calls': ..., 'decode_calls': ..., 'fallback_calls': ...,
#  'num_layers_wrapped': 28, 'protect_fraction': 0.04, 'max_seqlen': 32768}

# Restore stock vLLM (e.g. for A/B comparison):
teardown()
```

## Acceptance

`verify_phase5a_smoke.py` runs a short Qwen2.5-7B generation
through the install and asserts:

1. Install attached to ≥ 1 attention module (else raise).
2. `prefill_calls > 0` after generate().
3. `decode_calls > 0` after generate().
4. `fallback_calls / total_calls <= 10%` (any higher means the
   wrapper isn't doing its job).
5. Generated text is non-empty.

Optionally compares to a stock vLLM run (informational; outputs
won't match exactly because of INT4 drift — that's expected and
not a fail condition).

## What unlocks after Phase 5A GREEN

| Next phase | What it adds | Effort |
|---|---|---|
| **Phase 6.4-native** | Re-run the protect-fraction sweep through the native kernel path (vs the cache-wrapper that Phase 6.4 used). Confirms the transitive argument we relied on. | ~1 day |
| **Phase 2.4** | REAL HBM INT4 K storage (custom CUTLASS load atoms). Drops the sidecar entirely; net 4× memory savings on K. | ~3-5 days, highest remaining risk |
| **Phase 6.1-6.3** | Throughput / KV-memory / quality measurement on Qwen2.5-7B at 32k. The headline v1 numbers. | ~2 days, gated on Phase 2.4 |
| **Phase 5B / 5C** | Multi-sequence (batch > 1), `LLM(kv_cache_dtype="int4_protected")` first-class registration, prefix caching, scheduler integration. | ~5+ days |
| **Phase 6.4-real-data** | Production-grade quality sweeps (multi-model, multi-task). Phase 6.4-narrow today covers Qwen-only needle. | ~5+ days, separate workstream |

## Risk callouts

1. **vLLM internal path drift.** `_find_inner_model()` tries several
   paths to reach the `nn.Module`. If vLLM 0.7.3 → 0.8 changes the
   internals, the path resolver needs updating. Failure mode is a
   clear `RuntimeError` at install time, not silent corruption.

2. **Sidecar OOM at large `max_seqlen`.** 28 layers × 32768 seqlen ×
   4 H_kv × 128 D × 2 bytes × 2 (K+V) = ~3.7 GB. Plus vLLM's own
   paged cache. If the test machine is tight on HBM, drop
   `max_seqlen` or reduce `gpu_memory_utilization`.

3. **Mask staleness across sequences.** If the user forgets to call
   `manager.reset()`, sequence N+1 reuses sequence N's mask. Mask
   computation is a NO-OP on already-frozen caches (the
   `mask_frozen` guard). Behavior: sequence N+1 decode uses
   sequence N's protect mask → quality may degrade. The smoke test
   only runs one sequence so this isn't tested; document loudly.

4. **Batch > 1 silent corruption.** Per v1 constraint. The wrapper
   treats `T == 2` as prefill (T > 1), which fails for
   batch=2-decode. The smoke test pins batch=1.

5. **Falls open to stock vLLM on errors.** A buggy kernel call or
   shape mismatch returns the stock path's output, which produces
   correct text but unmasked INT4 isn't tested. `manager.stats()`
   shows fallback count to catch this.
