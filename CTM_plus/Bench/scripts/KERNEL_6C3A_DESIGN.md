# Kernel 6c.3A — model-level fused protected-K decode bypass (design note)

Status: **design, pre-code.** Supersedes ``KERNEL_6C3_RUNBOOK.md``'s
"backend flag inside route-A" sketch — that approach was wrong because
the route-A interception point sees only the **current-step K/V**, not
the accumulated cache the fused kernel needs to read.

This note pins the v1 contract before code lands; the runbook gets a
follow-up edit once the code is in.

---

## 1. The gap with the original runbook

``int4_cache_kv_route_a.py`` intercepts ``Attention.forward(q, k, v, ...)``
at the per-call boundary and **rewrites the K/V positional args in
place** (quantize → dequant → reinject). vLLM's PagedAttention then
runs on the lossy FP16 K/V exactly as before. The KV **cache** itself
is still vLLM's FP16 paged pool, untouched.

That gives us the §20.3-style *quality* signal (lossy K/V flowing
through real attention) but NOT throughput, because:

- The K/V at the hook are **this step's projected K/V only** (shape
  ``(num_tokens, H_kv * D)`` — `num_tokens=1` for decode). The
  *accumulated* past-K/V lives in vLLM's paged KV pool which route-A
  doesn't see.
- The fused kernel (``int4_fused_attention_kernel.py``) needs the
  **full INT4-packed accumulated KV** for the sequence
  (``k_packed (B,H_kv,S_kv,D//2)`` etc.). At this hook there is
  nothing to gather.

The runbook's "gather paged KV into contiguous tensors per call" step
was wrong: there is no INT4 paged tensor to gather. Acknowledged.

6c.3A is the smallest measurable replacement: a **parallel** INT4 KV
cache that route-A owns, populated alongside vLLM's normal prefill,
read by the fused kernel during decode (replacing the original
attention call). vLLM's paged cache stays allocated; we don't free it.

---

## 2. v1 scope (locked)

| Decision | v1 choice | Rationale / what defers |
|---|---|---|
| Batch | **B = 1** | vLLM's continuous batching can pack multiple sequences' decode steps into one ``forward`` call; sequence-identity threading is non-trivial in 0.7.3. Batch > 1 = 6c.3.2. |
| Sequence | single | One ``ProtectedKINT4Cache`` per (layer, sequence). Multi-sequence = 6c.3.2. |
| K group size | **1** (per-token) | Group-32 K-along-seq makes the cross-append partial-group accounting non-trivial at decode time. Per-token K is the clean incremental case. Departs from §20.4 group=32; needle sanity confirms or flags. |
| V group size | **32** (per the §20.4 ship config) | V grouping is **within-token** (along ``head_dim``) — no incremental issue. |
| Cache layout | **preallocated contiguous** per (layer, sequence), max_seq_len up front | vLLM-style paging = 6c.3C. |
| Prefill path | unchanged ``round_trip_kv`` + **sidecar** into our cache | The route-A lossy-FP16 path keeps vLLM's attention math intact during prefill; we observe the same K/V into our cache so decode reads them. |
| Decode path | **bypass** original ``forward`` | quantize-append-kernel-return — vLLM's PagedAttention does not run on decode. |
| Multi-token decode (S_q > 1) | out of scope | Speculative decoding, lookahead. Decode path asserts S_q == 1; falls back to ``dequant_fallback`` if violated. |
| Memory compression claim | **none** | vLLM's FP16 KV pool stays allocated; our cache is *additional* memory. 6c.3C closes this. |
| Mask source | **per-sequence-static** top-4% by max-abs over prefill K | The §20.4.3-validated path. Frozen before first decode call. Offline-corpus calibration = Roadmap Exp 5, deferred. |
| Mask layout | **(H_kv, D) int8**, full per-(head, dim) | Matches the kernel's existing ``protect_mask`` input. |
| ``k_fp16`` side-tensor | **full** ``(max_S, H_kv, D)`` | Matches blueprint §3 v1 simplification — kernel reads only protected lanes but full tensor is the simplest layout. Compact (H_kv, n_protect) variant = follow-on. |

---

## 3. Answers to the six design points

### 3.1 Sequence identity / cache slot

**Where it would come from in vLLM 0.7.3:** the attention
``forward_context`` carries per-call ``AttentionMetadata`` with
``slot_mapping`` (per-token block-table slots), ``block_tables``
(per-sequence block lists), ``seq_lens``, and ``query_start_loc`` /
``query_lens`` (the prefill/decode split). At runtime one can read it
via ``vllm.attention.get_forward_context()`` (or the
v0.7.3-equivalent thread-local) inside the wrapped ``forward``.

**v1 decision:** **skip the slot-mapping entirely.** Scope to **batch
= 1 single-sequence decode**. The manager holds one cache *per layer*,
no per-sequence indexing. Between requests, the harness calls
``manager.reset()`` to clear ``s_curr`` and ``protect_mask`` on every
layer cache.

What this assumes:
- The throughput harness submits one sequence at a time, sequentially,
  with ``manager.reset()`` between sequences.
- vLLM's scheduler does **not** silently interleave two sequences'
  decode steps. At batch=1 with a single request this is true.

What this gives up: the multi-sequence batching that real vLLM
serving relies on. That gap closes with proper slot-mapping (6c.3.2)
or with native paged INT4 KV (6c.3C).

### 3.2 Cache lifecycle

| Stage | Where | What happens |
|---|---|---|
| **Alloc** | first ``append()`` call | Detect ``H_kv``, ``D``, ``device``, ``dtype`` from the input K. Allocate all per-layer buffers (``k_packed``, ``k_scale``, ``k_offset``, ``k_fp16``, ``v_packed``, ``v_scale``, ``v_offset``, ``protect_mask``) on the right device. ``protect_mask`` left as ``None`` until freeze. |
| **Prefill populate** | wrapped ``forward`` with ``num_tokens > 1`` | ``cache.append(k_step, v_step)`` writes ``T = num_tokens`` rows starting at ``s_curr``; advances ``s_curr += T``. Then the wrapper still runs the **original** ``round_trip_kv`` + ``original_forward`` so vLLM's prefill attention runs on the lossy FP16 K/V (the §20.3 quality path). |
| **Mask freeze** | first ``cache.kernel_inputs()`` call (lazy) | Compute ``mag = k_fp16_buf[:s_curr].abs().amax(dim=0)`` → ``(H_kv, D)``; ``n_protect = max(1, round(protect_fraction * H_kv * D))``; ``top-n_protect`` over the flattened ``(H_kv*D,)``; build ``mask (H_kv, D) int8``. Mark ``_protect_frozen = True``. |
| **Decode append** | wrapped ``forward`` with ``num_tokens == 1`` | ``cache.append(k_step, v_step)`` (T=1) → ``cache.kernel_inputs()`` → ``fused_protected_k_decode_attention(...)`` → return ``(1, H_q * D)`` to caller. ``original_forward`` is **not called**. |
| **Reset** | ``manager.reset()`` between requests | For every per-layer cache: ``s_curr = 0``, ``protect_mask = None``, ``_protect_frozen = False``. **Buffers stay allocated** (avoid the re-alloc cost; the manager outlives requests). |
| **Free** | manager garbage-collected | Python releases the tensors. No explicit ``free()`` — the lifetime is tied to the manager. Teardown (returned from ``install_int4_cache_kv_route_a``) drops all cache buffers explicitly for the test path. |

Refusal conditions (per cache, raise / log on violation):
- ``append()`` overrunning ``max_seq_len`` → ``ValueError`` ("max_seq_len exceeded; pre-allocate larger or use 6c.3.2 paged variant").
- ``append()`` with mismatched ``H_kv`` / ``D`` after alloc → ``ValueError``.
- ``kernel_inputs()`` before any ``append()`` → ``ValueError`` ("cache empty").
- Decode wrapper sees ``num_tokens > 1`` (multi-token decode) → log + fall back to ``dequant_fallback`` for that call.

### 3.3 Buffer layout

Per-layer buffers (all preallocated to ``max_seq_len`` rows on the
device of the first appended K):

| Buffer | Shape | dtype | Append op |
|---|---|---|---|
| ``k_packed_buf`` | ``(max_S, H_kv, D//2)`` | ``uint8`` | ``buf[s_curr:s_curr+T] = pack_int4(kq)`` |
| ``k_scale_buf`` | ``(max_S, H_kv, D)`` | ``fp16`` | ``buf[s_curr:s_curr+T] = ks.to(fp16)`` |
| ``k_offset_buf`` (asym only) | ``(max_S, H_kv, D)`` | ``fp16`` | ``buf[s_curr:s_curr+T] = ko.to(fp16)`` |
| ``k_fp16_buf`` | ``(max_S, H_kv, D)`` | ``fp16`` | ``buf[s_curr:s_curr+T] = k_step.to(fp16)`` (raw input) |
| ``v_packed_buf`` | ``(max_S, H_kv, D//2)`` | ``uint8`` | ``buf[s_curr:s_curr+T] = pack_int4(vq)`` |
| ``v_scale_buf`` | ``(max_S, H_kv, n_grp_v)`` | ``fp16`` | ``buf[s_curr:s_curr+T] = vs.to(fp16)`` |
| ``v_offset_buf`` (asym only) | ``(max_S, H_kv, n_grp_v)`` | ``fp16`` | ``buf[s_curr:s_curr+T] = vo.to(fp16)`` |
| ``protect_mask`` | ``(H_kv, D)`` | ``int8`` | computed once at freeze |

``n_grp_v = D // v_group_size`` (D=128, gv=32 → n_grp_v=4 for Qwen2.5).

**Append along axis 0** (the seq axis) — contiguous-in-place write,
matches the quantize op's natural output layout, no copy.

**Read for the kernel** in ``kernel_inputs()``:

| Kernel arg | Source | Transform |
|---|---|---|
| ``k_packed`` | ``k_packed_buf[:s]`` | ``.permute(1, 0, 2).contiguous().unsqueeze(0)`` → ``(1, H_kv, s, D//2)`` *(copy)* |
| ``k_scale`` | ``k_scale_buf[:s]`` | ``.unsqueeze(0)`` → ``(1, s=n_grp_k, H_kv, D)`` *(no copy)* |
| ``k_offset`` | ``k_offset_buf[:s]`` | ``.unsqueeze(0)`` → ``(1, s, H_kv, D)`` *(no copy)* or ``None`` |
| ``k_fp16`` | ``k_fp16_buf[:s]`` | ``.permute(1, 0, 2).contiguous().unsqueeze(0)`` → ``(1, H_kv, s, D)`` *(copy)* |
| ``protect_mask`` | ``protect_mask`` | as-is, ``(H_kv, D)`` |
| ``v_packed`` | ``v_packed_buf[:s]`` | ``.permute(1, 0, 2).contiguous().unsqueeze(0)`` → ``(1, H_kv, s, D//2)`` *(copy)* |
| ``v_scale`` | ``v_scale_buf[:s]`` | ``.unsqueeze(0)`` → ``(1, s, H_kv, n_grp_v)`` *(no copy)* |
| ``v_offset`` | ``v_offset_buf[:s]`` | ``.unsqueeze(0)`` → ``(1, s, H_kv, n_grp_v)`` *(no copy)* or ``None`` |

Three ``.contiguous()`` copies per decode call (``k_packed``,
``k_fp16``, ``v_packed``). **Accepted v1 overhead** — naming it so it
shows up honestly in the throughput numbers. Compact storage that
matches the kernel layout natively is a 6c.3.2 refinement.

**Memory footprint at S=32k, Qwen2.5-7B (H_kv=4, D=128, group_size_k=1, asym, 28 layers):**

| Buffer | Bytes/layer | × 28 layers |
|---|---|---|
| ``k_packed_buf`` | 32k·4·64·1 = 8 MB | 0.22 GB |
| ``k_scale_buf`` | 32k·4·128·2 = 32 MB | 0.88 GB |
| ``k_offset_buf`` | 32 MB | 0.88 GB |
| ``k_fp16_buf`` | 32 MB | 0.88 GB |
| ``v_packed_buf`` | 8 MB | 0.22 GB |
| ``v_scale_buf`` | 32k·4·4·2 = 1 MB | 28 MB |
| ``v_offset_buf`` | 1 MB | 28 MB |
| **Total** | **~114 MB / layer** | **~3.2 GB** |

For reference, the corresponding FP16 vLLM KV cache at S=32k is
~1.8 GB (K + V at fp16). So our v1 cache is **~1.8× larger than FP16
KV** — driven by ``group_size_k = 1`` (per-token K scales + offsets
dominate) and the duplicate ``k_fp16`` side-tensor. **The §20.4 6b
3.07× compression ceiling does NOT apply to this v1 cache.**

This is exactly why the design note states **no memory-compression
claim** for 6c.3A.

### 3.4 Prefill hook

In the wrapped ``forward`` (per layer):

```
key_2d, value_2d = args[1], args[2]                # (T, H_kv*D) typical vLLM
key_3d = key_2d.reshape(T, H_kv, D)
value_3d = value_2d.reshape(T, H_kv, D)
T = key_3d.shape[0]

if T > 1:   # prefill
    cache.append(key_3d, value_3d)              # populate our INT4 cache
    k_lossy, v_lossy = manager.round_trip_kv(...) # existing path
    new_args = (q, k_lossy, v_lossy, ...)
    return original_forward(*new_args, **kwargs)  # vLLM's normal prefill attention
```

Properties:
- Cache holds quantized prefill K/V; vLLM's path runs on the *dequant
  reconstruction* of the same quantized values. Same K/V content
  flows through both.
- Two quantize passes during prefill (one in ``append``, one in
  ``round_trip_kv``). Constant-factor overhead, acceptable v1.
- No mask freezing here — freeze happens lazily on first
  ``kernel_inputs()`` call from the decode side.

### 3.5 Decode hook

In the wrapped ``forward``:

```
T = key_3d.shape[0]

if T == 1 and manager.backend == "fused_v2":     # decode
    cache.append(key_3d, value_3d)                # T=1 row appended
    inputs = cache.kernel_inputs()                # freezes mask if first time
    q3d = q_2d.reshape(1, H_q, D)                 # query: (B=1, H_q, D)
    out = fused_protected_k_decode_attention(
        q=q3d,
        **inputs,
        group_size_k=cache.k_group_size,          # 1 in v1
        group_size_v=cache.v_group_size,          # 32
        asymmetric=cache.asymmetric,
    )                                              # (1, H_q, D) fp16
    return out.reshape(1, H_q * D)                # 2-D back to vLLM's caller
    # original_forward NOT called
```

Properties:
- Query stays FP16 — no quantization on Q.
- ``kernel_inputs`` returns contiguous tensors on the kernel's device.
- Output dtype FP16, shape matches the 2-D vLLM Attention output
  contract.
- If decode hook fires with ``T > 1`` (speculative decode etc.): log,
  fall back to the prefill/dequant_fallback branch. Out-of-v1-scope.

### 3.6 Honest measurement claims

What 6c.3A measures:
- **Decode tokens/sec** with our fused INT4 kernel running on each
  layer's attention, on a real Qwen2.5-7B forward pass driven by
  vLLM-loaded weights and tokenizer.
- **Per-token decode latency** (a derived view).
- **Peak GPU memory** for the whole process — FP16 vLLM KV pool +
  our INT4 cache + all weights + activations.
- **Needle quality sanity** end-to-end through the 6c.3A pipeline
  (re-run the §20.4.2 / §20.4.4 harness on cell D).

What 6c.3A does **NOT** measure:
- Real vLLM serving throughput. PagedAttention's scheduling,
  continuous batching, prefix caching, chunked prefill — all
  bypassed in the decode path.
- INT4 KV memory compression. vLLM's FP16 cache is still allocated;
  ours is *additional*.
- Multi-sequence batched decode. Batch=1 only.
- Multi-token decode (speculative / lookahead). S_q=1 only.

Labels for the cells in the throughput table:
- Cell A: ``vLLM FP16`` — production baseline.
- Cell B: ``vLLM FP8`` (``--kv-cache-dtype fp8``) — current competitor.
- Cell C: ``route-A naive dequant`` — existing ``dequant_fallback``
  (no kernel; INT4 round-trip; vLLM PagedAttention on the FP16
  reconstruction). Measures the "what does route-A cost without a
  kernel" floor.
- Cell D: ``6c.3A model-level fused kernel`` — this work. Labelled
  "model-level fused kernel decode (PagedAttention bypassed during
  decode)" wherever it appears.

Decision rules (from the runbook, refined):

| Outcome | Read |
|---|---|
| Cell D decode tok/s > A and > B at long context | "Protected-K + fused kernel decode beats FP16 *and* FP8 at the attention-layer level, end-to-end through a real model — bypassing vLLM serving optimisations." Still NOT a vLLM-serving claim. Strong evidence the integration is worth pushing through 6c.3C. |
| Cell D ≈ A, > B | Parity with FP16 SDPA at the model level; beats FP8. Same scope caveat. |
| Cell D > C but < A | Kernel beats no-kernel route-A, but the model-level integration loses to FP16. Profile the per-call quantize/append/copy overhead — these were the accepted v1 costs and may be too high. |
| Cell D ≤ C | Integration regression — the per-call overheads ate the kernel win. Profile. |
| Cell D needle quality drops vs §20.4.2 / §20.4.4 | Integration bug *or* the ``group_size_k=1`` config genuinely shifts quality. Compare needle of cell D vs ``group_size_k=32`` route-B run; if route-B at gk=1 also drops, it's the config, not a bug. |

---

## 4. v1 simplifications restated (per the user's bullet list)

- ✅ **batch = 1** (single-sequence decode only; no slot mapping).
- ✅ **preallocated contiguous cache** (no paging).
- ✅ **per-sequence-static top-4% mask** from prefill K (no global calibration).
- ✅ **decode-only fused path** (prefill = current route-A + sidecar).
- ✅ **no paged-direct cache** (6c.3C is later, specialist work).
- ✅ **no dynamic masks** (frozen at end of prefill).
- ✅ **no memory-compression claim** — FP16 vLLM KV stays allocated.
- ➕ **group_size_k = 1** (per-token K). The cleanest incremental
  append; departs from §20.4 group=32 config; ``v1 cache is ~1.8×
  larger than FP16 KV`` honestly reflected; needle sanity confirms or
  flags the quality impact.
- ➕ **S_q = 1 only** in the decode bypass. Multi-token decode falls
  back to the dequant path.
- ➕ **Three per-call .contiguous() copies** (``k_packed``,
  ``k_fp16``, ``v_packed``) — accepted overhead.

---

## 5. Files this design produces (next step)

1. ``CTM_plus/KVPolicy/kv_policy/int4_protected_k_cache.py``:
   ``ProtectedKINT4Cache`` class. Lazy-allocated buffers, ``append()``
   (T ≥ 1), ``freeze_protect_mask()``, ``kernel_inputs()`` (auto-freeze
   on first call), ``reset()``, ``__repr__`` / stats.

2. ``CTM_plus/KVPolicy/kv_policy/int4_cache_kv_route_a.py`` (extend):
   - ``INT4CacheKVRouteA``: new ``kernel_backend`` param
     (``"dequant_fallback"`` | ``"fused_v2"``), new ``max_seq_len``,
     ``protect_fraction``, ``v_group_size``, ``k_group_size``
     params. Per-layer cache dict keyed by ``id(module)``.
     ``reset()`` method.
   - ``install_int4_cache_kv_route_a``: ``kernel_backend`` plumbing.
   - New ``_wrap_attention_forward_with_fused_v2``: prefill-sidecar +
     decode-bypass wrapper. The existing ``_wrap_attention_forward_with_kv_rewrite``
     remains for the ``dequant_fallback`` backend.

3. (Following turn) A CPU-importable unit test that exercises the
   cache class without GPU/Triton: build a faked attention forward,
   run a fake prefill of T tokens, then a series of T=1 decodes,
   verify ``kernel_inputs`` shapes match the kernel's contract and
   the sliced contents match the reference quantize-then-attend.
   Numerical equivalence vs ``fused_int4_attention_reference``
   (with ``k_fp16`` / ``k_protect_mask``) is the test bar — same
   oracle the kernel was validated against.

4. (Following turn) Four-cell throughput script per §3.6.

---

## 6. Open questions that need a GPU run to answer

These are NOT v1 blockers, just things we'll only learn from the
measurement:

1. **Quantize/append cost on GPU.** ``quantize_per_channel_int4`` is
   pure PyTorch — at decode (T=1) on GPU it should be a handful of
   small ops, but it's not fused with the kernel. If this dominates,
   a fused quantize+append op is the next optimisation.
2. **``.contiguous()`` copy cost.** Three permute-then-copy passes per
   decode step. Each is ``(H_kv, S, D)`` or similar; small at short
   context, grows with S_kv.
3. **Whether the kernel's ``k_fp16`` full-tensor read becomes the
   memory bottleneck** at S=32k. The compact-side-tensor variant
   (blueprint §13 v2) is the mitigation if so.
4. **Whether ``group_size_k = 1`` materially changes needle quality
   vs §20.4.2 / §20.4.4 measured at ``group_size_k = 32``.** Expected
   answer: per-token K is at least as accurate as group-32; needle
   should be ≥ §20.4 numbers. If it's worse, the simplification was
   wrong and a group-32 cache with proper partial-group handling
   needs to land before 6c.3A is releasable.
