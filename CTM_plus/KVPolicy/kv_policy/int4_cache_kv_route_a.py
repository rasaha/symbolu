"""Route-A INT4 KV-cache integration for vLLM.

Route-B (``int4_per_channel_hf_cache.INT4PerChannelCache``) subclasses
HF transformers' ``DynamicCache`` — it is the **measurement vehicle**
for the §18/§19 quality numbers but cannot deploy on vLLM.

Route-A (this module) is the vLLM-side integration: a monkey-patch of
the ``Attention`` modules' ``forward``. Two backends:

* ``kernel_backend='dequant_fallback'`` (the original, §20.3 quality
  path): rewrites the K/V positional args via the KIVI INT4
  round-trip, then lets vLLM's original ``forward`` run on the lossy
  FP16 K/V. vLLM's paged KV pool and PagedAttention are unchanged;
  this measures the **quality** of INT4 under real attention without
  any throughput win.
* ``kernel_backend='fused_v2'`` (6c.3A model-level fused-decode
  bypass, see ``Bench/scripts/KERNEL_6C3A_DESIGN.md``): owns a
  parallel ``ProtectedKINT4Cache`` per layer. Prefill keeps the
  ``dequant_fallback`` path AND sidecars the same K/V into the
  parallel cache. Decode (``num_tokens == 1``) **bypasses** vLLM's
  original ``forward`` and instead calls
  ``fused_protected_k_decode_attention`` over the accumulated cache.
  This measures **decode throughput** with the fused kernel running
  on each layer, end-to-end through a real model. vLLM's
  PagedAttention is bypassed during decode — see §3.6 of the design
  note for the honest scope.

What this module IS
-------------------

* ``INT4CacheKVRouteA`` — the per-call manager. Holds KIVI config,
  per-layer caches (fused_v2 only), counters. Reuses the route-B
  quantizer ops directly. vLLM passes K/V at the Attention layer as
  ``(num_tokens, num_kv_heads * head_dim)`` (the common 2-D case;
  confirmed by ``triattention.py``'s GPU-validated Phase 4 hook) or
  ``(num_tokens, num_kv_heads, head_dim)`` (3-D); both are handled.

* ``install_int4_cache_kv_route_a(model, **config)`` — walks the
  model's ``Attention`` modules and wraps each one's ``forward``
  according to ``kernel_backend``. Returns ``(manager, teardown)``.
  CPU-importable (no ``vllm`` import; identifies Attention modules
  by class-name heuristic, the same approach ``triattention.py``
  uses).

What this module IS NOT
-----------------------

* It does **not realize INT4 memory compression**. Both backends
  leave vLLM's FP16 KV pool allocated; ``fused_v2``'s parallel cache
  is *additional* memory. Native paged INT4 KV is 6c.3C, deferred.
* The real-vLLM call-site verification + GPU correctness run is
  done via the throughput harness (see ``KERNEL_6C3A_DESIGN.md``).
  This file's tests are CPU-only against faked Attention modules.

This mirrors the repo's established staging: TurboQuant §15 landed
its PyTorch-ops port "as CPU-correct, GPU-ready code in a no-GPU
session" with the ``cache_kv`` monkey-patch deferred. Route-A INT4
goes one step further — the monkey-patch install itself lands here,
CPU-tested; GPU verification rides the throughput run.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover - guarded at the caller
    torch = None  # type: ignore


logger = logging.getLogger("int4_cache_kv_route_a")


# Backend identifiers (kept as module-level constants so callers and
# tests can refer to them without typos).
BACKEND_DEQUANT_FALLBACK = "dequant_fallback"
BACKEND_FUSED_V2 = "fused_v2"
_VALID_BACKENDS = (BACKEND_DEQUANT_FALLBACK, BACKEND_FUSED_V2)


class INT4CacheKVRouteA:
    """Per-call KIVI INT4 compress→decompress for the vLLM Attention
    layer.

    Holds the KIVI config and applies the round-trip to K/V tensors as
    they pass through ``Attention.forward``. Stateless across calls
    (each forward's K/V are quantized independently — matching vLLM's
    per-block write model); the only state is the running stats.

    Constructor args mirror ``INT4PerChannelCache`` so route-A and
    route-B are configured identically:

        k_group_size / v_group_size : KIVI group quantization sizes
                                      used by ``round_trip_kv`` (the
                                      ``dequant_fallback`` path). Note:
                                      the ``fused_v2`` parallel cache
                                      uses its own group sizes (v1
                                      requires ``k_group_size_cache=1``
                                      — see ``cache_*`` params below).
        asymmetric                  : affine (scale+offset) quant.
        bits                        : 4 = validated KIVI config.
        sink_size                   : StreamingLLM sink-FP16 passthrough
                                      (>0 keeps the first N positions
                                      of a multi-token forward in FP16).
        num_kv_heads                : KV-head count. REQUIRED to handle
                                      vLLM's 2-D K/V layout — vLLM
                                      passes K/V to ``Attention.forward``
                                      as ``(num_tokens, num_kv_heads *
                                      head_dim)`` (confirmed by the
                                      repo's GPU-validated
                                      ``triattention.py`` Phase 4 hook,
                                      which asserts the same 2-D
                                      shape). ``round_trip_kv`` reshapes
                                      2-D → 3-D ``(num_tokens,
                                      num_kv_heads, head_dim)`` using
                                      this. May be ``None`` if every
                                      call is guaranteed 3-D (rare).
        kernel_backend              : ``"dequant_fallback"`` (default;
                                      §20.3 quality path) or
                                      ``"fused_v2"`` (6c.3A — fused
                                      decode bypass, batch=1 only).
        max_seq_len                 : REQUIRED for ``fused_v2``;
                                      preallocated cache size per layer.
        protect_fraction            : top-fraction of K channels kept
                                      FP16 in the parallel cache
                                      (default 0.04 — the §20.4.2 win).
                                      ``fused_v2`` only.
        cache_k_group_size          : K group size for the parallel
                                      cache. v1 requires 1 (per-token
                                      K — the clean incremental case);
                                      this is a 6c.3A SIMPLIFICATION,
                                      not the §20.4 measured config
                                      (group=32). See
                                      ``KERNEL_6C3A_DESIGN.md`` §2.
        cache_v_group_size          : V group size for the parallel
                                      cache (default 32, matches §20.4).
    """

    def __init__(
        self,
        *,
        k_group_size: int = 32,
        v_group_size: int = 32,
        asymmetric: bool = True,
        bits: int = 4,
        sink_size: int = 0,
        num_kv_heads: Optional[int] = None,
        kernel_backend: str = BACKEND_DEQUANT_FALLBACK,
        max_seq_len: Optional[int] = None,
        protect_fraction: float = 0.04,
        cache_k_group_size: int = 1,
        cache_v_group_size: int = 32,
    ) -> None:
        if torch is None:
            raise ImportError("INT4CacheKVRouteA requires PyTorch.")
        if k_group_size < 0 or v_group_size < 0:
            raise ValueError(
                f"group sizes must be >= 0; got k={k_group_size}, "
                f"v={v_group_size}"
            )
        if not (2 <= bits <= 8):
            raise ValueError(f"bits must be in [2, 8]; got {bits}")
        if sink_size < 0:
            raise ValueError(f"sink_size must be >= 0; got {sink_size}")
        if num_kv_heads is not None and num_kv_heads < 1:
            raise ValueError(
                f"num_kv_heads must be >= 1 or None; got {num_kv_heads}"
            )
        if kernel_backend not in _VALID_BACKENDS:
            raise ValueError(
                f"kernel_backend must be one of {_VALID_BACKENDS}; "
                f"got {kernel_backend!r}"
            )
        if kernel_backend == BACKEND_FUSED_V2:
            if max_seq_len is None or max_seq_len < 1:
                raise ValueError(
                    "kernel_backend='fused_v2' requires max_seq_len >= 1 "
                    "(preallocated parallel cache size per layer). See "
                    "KERNEL_6C3A_DESIGN.md §3.3."
                )
            if cache_k_group_size != 1:
                # v1 only: per-token K. Loud refusal so the §20.4
                # group=32 number can't accidentally ride this code
                # path without an explicit v2 upgrade.
                raise ValueError(
                    f"kernel_backend='fused_v2' v1 requires "
                    f"cache_k_group_size=1 (per-token K); got "
                    f"{cache_k_group_size}. This is a 6c.3A "
                    "SIMPLIFICATION, not the §20.4 measured "
                    "compression config — see KERNEL_6C3A_DESIGN.md §2."
                )
            if not (0.0 <= protect_fraction <= 1.0):
                raise ValueError(
                    f"protect_fraction must be in [0, 1]; got "
                    f"{protect_fraction}"
                )
        self._k_group_size = int(k_group_size)
        self._v_group_size = int(v_group_size)
        self._asymmetric = bool(asymmetric)
        self._bits = int(bits)
        self._sink_size = int(sink_size)
        self._num_kv_heads = (
            int(num_kv_heads) if num_kv_heads is not None else None
        )
        self._kernel_backend = kernel_backend
        self._max_seq_len = (
            int(max_seq_len) if max_seq_len is not None else None
        )
        self._protect_fraction = float(protect_fraction)
        self._cache_k_group_size = int(cache_k_group_size)
        self._cache_v_group_size = int(cache_v_group_size)
        self._forward_calls = 0
        self._tokens_compressed = 0
        self._sink_tokens_passed_through = 0
        # Counts forwards skipped because a 2-D K/V arrived but
        # num_kv_heads is unknown — surfaced in stats so a silent
        # no-op is detectable.
        self._skipped_unknown_shape = 0
        # fused_v2-specific state.
        self._caches: Dict[int, "ProtectedKINT4Cache"] = {}
        self._fused_v2_decodes = 0
        self._fused_v2_prefills_sidecar = 0
        self._fused_v2_fallbacks: Dict[str, int] = {}
        # Profiling state (fused_v2 only). When ``_profile_enabled`` is
        # True, the decode branch records CUDA events per section; the
        # events are aggregated by ``get_profile_stats``. Off by default
        # — adds ~6 event allocations per call, plus a cuda.synchronize
        # on stats read.
        self._profile_enabled = False
        # section -> list[(start_event, end_event)]
        self._profile_events: Dict[str, list] = {
            "reshape_kv": [],
            "cache_append": [],
            "readskip_decision": [],
            "kernel_inputs": [],
            "kernel_call": [],
            "cast_back": [],
            "total_bypass": [],
        }

        # READ-SKIP (Phase-9 build): which historical KV positions the fused
        # decode reads. "off" = read all ([:s], identity — default, no behavior
        # change). "retain_all" = explicitly pass range(s) — the byte-eq gate that
        # the active_positions plumbing is transparent. "retention" (P2) =
        # sink+recent+attention-selected blocks via kv_policy.readskip_select.
        self._readskip_mode = os.environ.get("INT4_READSKIP_MODE", "off")
        self._readskip_calls = 0

        def _ri(name: str, dflt: int) -> int:
            try:
                return int(os.environ.get(name, dflt))
            except ValueError:
                return dflt
        # Retention knobs (env-overridable) — defaults match the GREEN harness.
        self._readskip_block_size = _ri("INT4_READSKIP_BLOCK", 32)
        self._readskip_sink_tokens = _ri("INT4_READSKIP_SINK", 256)
        self._readskip_recent_tokens = _ri("INT4_READSKIP_RECENT", 2048)
        self._readskip_budget_tokens = _ri("INT4_READSKIP_BUDGET", 2048)
        self._readskip_neighbor = _ri("INT4_READSKIP_NEIGHBOR", 1)
        self._readskip_observe = _ri("INT4_READSKIP_OBSERVE", 8)
        self._readskip_refresh = _ri("INT4_READSKIP_REFRESH", 16)
        try:
            self._readskip_decay = float(os.environ.get("INT4_READSKIP_DECAY", 0.8))
        except ValueError:
            self._readskip_decay = 0.8
        self._readskip_controllers: Dict[int, Any] = {}

    def _readskip_active_positions(self, cache, query=None) -> "Optional[List[int]]":
        """READ-SKIP: retained KV positions for this decode step, or None (read
        all). "off" -> None (identity). "retain_all" -> range(s) (byte-eq gate).
        "retention" -> per-cache ReadSkipController fed decode-attention block
        scores (sink+recent+top-attention+neighbors); observe/refresh steps read
        all. Fail-open: any scoring error -> read all this step."""
        mode = self._readskip_mode
        if mode == "off":
            return None
        s = cache.seq_len
        if mode == "retain_all":
            self._readskip_calls += 1
            return list(range(s))          # must be byte-identical to "off"
        if mode == "retention":
            self._readskip_calls += 1
            from kv_policy.readskip_select import ReadSkipController
            ctrl = self._readskip_controllers.get(id(cache))
            if ctrl is None:
                ctrl = ReadSkipController(
                    block_size=self._readskip_block_size,
                    sink_tokens=self._readskip_sink_tokens,
                    recent_tokens=self._readskip_recent_tokens,
                    attention_budget_tokens=self._readskip_budget_tokens,
                    neighbor_blocks=self._readskip_neighbor,
                    observe_steps=self._readskip_observe,
                    refresh_every=self._readskip_refresh,
                    score_decay=self._readskip_decay)
                self._readskip_controllers[id(cache)] = ctrl
            scores = None
            if ctrl.needs_scores() and query is not None:
                try:
                    scores = cache.block_attention_scores(
                        query, self._readskip_block_size)
                except Exception:  # noqa: BLE001 — fail-open: read all this step
                    logger.exception(
                        "read-skip block scoring failed; reading all this step")
                    scores = None
            return ctrl.active_positions(s, block_scores=scores)
        return None

    @property
    def kernel_backend(self) -> str:
        return self._kernel_backend

    @property
    def caches(self) -> "Dict[int, ProtectedKINT4Cache]":
        """Per-layer parallel caches (fused_v2 only). Keyed by ``id(module)``."""
        return self._caches

    @property
    def config(self) -> dict:
        return {
            "route": "A",
            "quant": "int4-per-channel",
            "k_group_size": self._k_group_size,
            "v_group_size": self._v_group_size,
            "asymmetric": self._asymmetric,
            "bits": self._bits,
            "sink_size": self._sink_size,
            "num_kv_heads": self._num_kv_heads,
            "kernel_backend": self._kernel_backend,
            "max_seq_len": self._max_seq_len,
            "protect_fraction": self._protect_fraction,
            "cache_k_group_size": self._cache_k_group_size,
            "cache_v_group_size": self._cache_v_group_size,
            "scheme": (
                f"K=per-channel INT{self._bits}, V=per-token INT{self._bits}, "
                f"{'asymmetric' if self._asymmetric else 'symmetric'}, "
                f"k_group={self._k_group_size}, v_group={self._v_group_size}"
                + (f", sink_size={self._sink_size}"
                   if self._sink_size > 0 else "")
                + f", backend={self._kernel_backend}"
                + (
                    f", cache_k_group={self._cache_k_group_size}"
                    f" (6c.3A v1 simplification, NOT §20.4 group=32),"
                    f" cache_v_group={self._cache_v_group_size},"
                    f" protect_fraction={self._protect_fraction},"
                    f" max_seq_len={self._max_seq_len}"
                    if self._kernel_backend == BACKEND_FUSED_V2 else ""
                )
            ),
        }

    @property
    def stats(self) -> dict:
        cache_stats = {
            mid: c.stats for mid, c in self._caches.items()
        } if self._kernel_backend == BACKEND_FUSED_V2 else {}
        return {
            "forward_calls": self._forward_calls,
            "tokens_compressed": self._tokens_compressed,
            "sink_tokens_passed_through": self._sink_tokens_passed_through,
            "skipped_unknown_shape": self._skipped_unknown_shape,
            "kernel_backend": self._kernel_backend,
            "fused_v2_decodes": self._fused_v2_decodes,
            "fused_v2_prefills_sidecar": self._fused_v2_prefills_sidecar,
            "fused_v2_fallbacks": dict(self._fused_v2_fallbacks),
            "fused_v2_layers": len(self._caches),
            "fused_v2_cache_stats": cache_stats,
            "readskip_mode": getattr(self, "_readskip_mode", "off"),
            "readskip_calls": getattr(self, "_readskip_calls", 0),
            "readskip_controllers": len(getattr(self, "_readskip_controllers", {})),
        }

    # ------------------------------------------------------------------ #
    # fused_v2 cache management                                          #
    # ------------------------------------------------------------------ #

    def get_or_create_cache(self, module_id: int) -> "ProtectedKINT4Cache":
        """Return the per-layer cache for ``module_id``, creating it on
        first access. fused_v2 only; raises if called on a manager
        configured with a different backend.
        """
        if self._kernel_backend != BACKEND_FUSED_V2:
            raise ValueError(
                "get_or_create_cache only valid for kernel_backend="
                f"'{BACKEND_FUSED_V2}'; got '{self._kernel_backend}'"
            )
        if module_id not in self._caches:
            # Local import keeps this file CPU-importable without
            # pulling in Triton via the kernel module.
            from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache
            self._caches[module_id] = ProtectedKINT4Cache(
                max_seq_len=self._max_seq_len,
                protect_fraction=self._protect_fraction,
                k_group_size=self._cache_k_group_size,
                v_group_size=self._cache_v_group_size,
                asymmetric=self._asymmetric,
                bits=self._bits,
            )
        return self._caches[module_id]

    def reset(self) -> None:
        """Clear per-sequence state on every cache + the read-skip controllers.
        Keeps buffers. MUST be called between requests for fused_v2 (the cache is
        single-sequence; without a reset, each prefill appends on top of the last
        and overflows max_seq_len). No-op for dequant_fallback (stateless).
        """
        for cache in self._caches.values():
            cache.reset()
        getattr(self, "_readskip_controllers", {}).clear()

    def set_readskip_mode(self, mode: str) -> None:
        """Switch the read-skip mode at RUNTIME and clear per-sequence controllers.

        Enables a WITHIN-PROCESS paired A/B (e.g. off vs retention on a single
        warm engine), which removes the cross-run GPU-clock/warmup drift that made
        separate-process comparisons noisy in Phase 9 (off drifted 10.75 -> 8.9 ->
        7.29 across processes). The retention KNOBS (sink/recent/budget/observe/
        refresh/decay) are fixed at ``__init__`` from the env — this only flips
        WHICH policy runs, never the policy's parameters. Clearing the controllers
        makes the next sequence re-observe from scratch (no stale EMA bleeding from
        the previously-measured mode).
        """
        valid = ("off", "retain_all", "retention")
        if mode not in valid:
            raise ValueError(
                f"unknown read-skip mode {mode!r}; expected one of {valid}")
        self._readskip_mode = mode
        getattr(self, "_readskip_controllers", {}).clear()

    def _record_fused_v2_fallback(self, reason: str) -> None:
        self._fused_v2_fallbacks[reason] = (
            self._fused_v2_fallbacks.get(reason, 0) + 1
        )

    # ------------------------------------------------------------------ #
    # Profiling (fused_v2 only)                                          #
    # ------------------------------------------------------------------ #

    def set_profiling(self, enabled: bool) -> None:
        """Enable / disable per-component CUDA-event timing on the
        fused_v2 decode bypass. Off by default. When enabling on a
        previously-profiled run, call ``clear_profile`` first.
        """
        self._profile_enabled = bool(enabled)

    def clear_profile(self) -> None:
        """Drop all recorded profiling events. Call before re-arming
        ``set_profiling(True)`` for a fresh measurement."""
        for events in self._profile_events.values():
            events.clear()

    def get_profile_stats(self) -> dict:
        """Read the recorded per-section CUDA-event timings. Forces
        ``torch.cuda.synchronize`` so the events have fired. Returns
        a dict ``{section: {n_calls, mean_ms, p50_ms, p99_ms, total_ms}}``.
        """
        if torch is None:
            return {}
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        stats: Dict[str, dict] = {}
        for section, events in self._profile_events.items():
            if not events:
                continue
            times_ms = [start.elapsed_time(end) for start, end in events]
            times_ms.sort()
            n = len(times_ms)
            stats[section] = {
                "n_calls": n,
                "mean_ms": sum(times_ms) / n,
                "p50_ms": times_ms[n // 2],
                "p99_ms": times_ms[min(n - 1, int(0.99 * n))],
                "total_ms": sum(times_ms),
            }
        return stats

    def round_trip_kv(
        self,
        key: "torch.Tensor",
        value: "torch.Tensor",
    ) -> "Tuple[torch.Tensor, torch.Tensor]":
        """Run K/V through the KIVI INT4 compress→decompress.

        Accepts BOTH layouts vLLM uses at the attention boundary:

        * **2-D** ``(num_tokens, num_kv_heads * head_dim)`` — the
          common case. vLLM's ``qkv_proj → split → rotary_emb →
          self.attn(q,k,v)`` flow hands ``Attention.forward`` flat
          2-D K/V (confirmed by the repo's GPU-validated
          ``triattention.py`` Phase 4 hook, which asserts the same
          ``key must be 2D [num_tokens, num_kv_heads*head_dim]``).
          Requires ``num_kv_heads`` to have been set on the manager;
          the tensor is reshaped to 3-D for the quantizer and
          reshaped back to 2-D on return.
        * **3-D** ``(num_tokens, num_kv_heads, head_dim)`` — already
          the quantizer's ``(S, H, D)``; used directly.

        Returns the lossy ``(key, value)`` — SAME shape and dtype as
        the inputs (2-D in, 2-D out; 3-D in, 3-D out). When
        ``sink_size > 0`` and the forward carries more than
        ``sink_size`` tokens, the first ``sink_size`` positions pass
        through bit-identical FP16 and only positions ``[sink_size:]``
        are quantized (StreamingLLM sink protection, the §20.2 path).

        If a 2-D tensor arrives but ``num_kv_heads`` is unknown, the
        inputs are returned UNCHANGED and ``stats['skipped_unknown_shape']``
        is incremented — a detectable no-op rather than a crash.
        """
        from kv_policy.int4_per_channel_kv import (
            quantize_per_channel_int4, dequantize_per_channel_int4,
            quantize_per_token_int4, dequantize_per_token_int4,
        )
        if key.ndim not in (2, 3) or value.ndim not in (2, 3):
            raise ValueError(
                "INT4CacheKVRouteA.round_trip_kv expects 2-D "
                "(num_tokens, num_kv_heads*head_dim) or 3-D "
                "(num_tokens, num_kv_heads, head_dim) tensors; got "
                f"K {tuple(key.shape)}, V {tuple(value.shape)}."
            )

        # Normalise to 3-D (S, H, D) for the quantizer. Remember
        # whether to flatten back on return.
        was_2d = key.ndim == 2
        if was_2d:
            if self._num_kv_heads is None:
                # Can't reshape — surface a detectable no-op.
                self._skipped_unknown_shape += 1
                logger.warning(
                    "route-A INT4 got 2-D K/V (shape %s) but "
                    "num_kv_heads is unknown — passing through "
                    "UNCHANGED. Set num_kv_heads on the manager / via "
                    "install_int4_cache_kv_route_a so the 2-D vLLM "
                    "layout can be reshaped.",
                    tuple(key.shape),
                )
                return key, value
            h = self._num_kv_heads
            if key.shape[-1] % h != 0 or value.shape[-1] % h != 0:
                self._skipped_unknown_shape += 1
                logger.warning(
                    "route-A INT4: 2-D K/V last dim %d not divisible "
                    "by num_kv_heads=%d — passing through unchanged.",
                    key.shape[-1], h,
                )
                return key, value
            num_tokens = key.shape[0]
            d = key.shape[-1] // h
            key = key.reshape(num_tokens, h, d)
            value = value.reshape(num_tokens, h, d)

        num_tokens = key.shape[0]
        self._forward_calls += 1

        def _rt(k: "torch.Tensor", v: "torch.Tensor"):
            kq, ks, ko = quantize_per_channel_int4(
                k, group_size=self._k_group_size,
                asymmetric=self._asymmetric, bits=self._bits,
            )
            k_back = dequantize_per_channel_int4(
                kq, ks, dtype=k.dtype,
                group_size=self._k_group_size, offset=ko,
            )
            vq, vs, vo = quantize_per_token_int4(
                v, group_size=self._v_group_size,
                asymmetric=self._asymmetric, bits=self._bits,
            )
            v_back = dequantize_per_token_int4(
                vq, vs, dtype=v.dtype,
                group_size=self._v_group_size, offset=vo,
            )
            return k_back, v_back

        if self._sink_size > 0 and num_tokens > self._sink_size:
            sink = self._sink_size
            k_sink, v_sink = key[:sink], value[:sink]
            k_rest, v_rest = (
                key[sink:].contiguous(), value[sink:].contiguous(),
            )
            k_rest_lossy, v_rest_lossy = _rt(k_rest, v_rest)
            k_out = torch.cat([k_sink, k_rest_lossy], dim=0)
            v_out = torch.cat([v_sink, v_rest_lossy], dim=0)
            self._sink_tokens_passed_through += sink
            self._tokens_compressed += num_tokens - sink
        else:
            k_out, v_out = _rt(key, value)
            self._tokens_compressed += num_tokens

        # Flatten back to the 2-D layout vLLM gave us, so the wrapped
        # Attention.forward sees the shape it expects.
        if was_2d:
            k_out = k_out.reshape(num_tokens, -1)
            v_out = v_out.reshape(num_tokens, -1)
        return k_out, v_out


def _looks_like_attention(module: Any) -> bool:
    """Heuristic: is this module a vLLM attention layer?

    Identified by class name ENDING in 'Attention' AND the module
    exposing a ``forward`` method. ``endswith`` (not substring `in`)
    so a model wrapper named e.g. ``NoAttentionModel`` isn't a false
    positive — vLLM's attention layer class is exactly ``Attention``
    (``vllm/attention/layer.py``) and model-specific subclasses are
    named ``<Model>Attention``; both satisfy ``endswith``.

    Deliberately a heuristic (not ``isinstance(m, vllm...)``) so this
    file stays CPU-importable without vllm — matches
    ``triattention._walk_rotary_emb_modules``.
    """
    cls_name = type(module).__name__
    if not cls_name.endswith("Attention"):
        return False
    return callable(getattr(module, "forward", None))


def _wrap_attention_forward_with_kv_rewrite(
    module: Any,
    *,
    manager: INT4CacheKVRouteA,
    key_arg_index: int,
    value_arg_index: int,
    teardown_list: List[Callable[[], None]],
) -> None:
    """Replace ``module.forward`` so the K/V positional args are
    INT4-round-tripped before the original ``forward`` sees them.

    Unlike ``triattention._wrap_module_forward`` (whose ``before`` hook
    is fire-and-forget and cannot rewrite args), this wrapper REWRITES
    ``args[key_arg_index]`` / ``args[value_arg_index]`` in place. That
    is the route-A interception: the attention math then computes on
    the lossy (INT4-faithful) K/V.

    Robustness:
      * If the positional args are too short, or the K/V slots don't
        hold 2-D / 3-D tensors, the wrapper passes the call through
        untouched (a malformed interception must never crash the
        engine mid-decode). vLLM passes K/V as 2-D
        ``(num_tokens, num_kv_heads*head_dim)`` — the common case —
        or 3-D ``(num_tokens, num_kv_heads, head_dim)``;
        ``round_trip_kv`` handles both.
      * A round-trip exception is swallowed (logged) and the original
        K/V are used — fail-open, same posture as
        ``_capture_pre_rope_k_to_evictor``.
    """
    original_forward = module.forward

    def wrapped_forward(*args, **kwargs):
        new_args = args
        try:
            if (
                len(args) > key_arg_index
                and len(args) > value_arg_index
                and torch is not None
                and isinstance(args[key_arg_index], torch.Tensor)
                and isinstance(args[value_arg_index], torch.Tensor)
                and args[key_arg_index].ndim in (2, 3)
                and args[value_arg_index].ndim in (2, 3)
            ):
                k_lossy, v_lossy = manager.round_trip_kv(
                    args[key_arg_index], args[value_arg_index],
                )
                mutable = list(args)
                mutable[key_arg_index] = k_lossy
                mutable[value_arg_index] = v_lossy
                new_args = tuple(mutable)
        except Exception:
            logger.exception(
                "route-A INT4 K/V rewrite raised on %s; passing "
                "the call through with original K/V",
                type(module).__name__,
            )
            new_args = args
        return original_forward(*new_args, **kwargs)

    module.forward = wrapped_forward
    teardown_list.append(
        lambda: setattr(module, "forward", original_forward)
    )


def _reshape_kv_2d_to_3d(
    tensor: "torch.Tensor", num_kv_heads: int,
) -> "Optional[torch.Tensor]":
    """Reshape a 2-D (T, H_kv * D) tensor to 3-D (T, H_kv, D).

    Returns None if the reshape isn't possible (mismatched last dim).
    """
    if tensor.ndim == 3:
        return tensor
    if tensor.ndim != 2:
        return None
    if tensor.shape[-1] % num_kv_heads != 0:
        return None
    T = tensor.shape[0]
    D = tensor.shape[-1] // num_kv_heads
    return tensor.reshape(T, num_kv_heads, D)


def _wrap_attention_forward_with_fused_v2(
    module: Any,
    *,
    manager: INT4CacheKVRouteA,
    query_arg_index: int,
    key_arg_index: int,
    value_arg_index: int,
    teardown_list: List[Callable[[], None]],
) -> None:
    """Install the 6c.3A model-level fused-decode bypass wrapper.

    Behaviour per ``KERNEL_6C3A_DESIGN.md`` §3.4–§3.5:

    * **Prefill** (``num_tokens > 1``): sidecar K/V into the per-layer
      ``ProtectedKINT4Cache`` AND run the original ``forward`` with
      the ``round_trip_kv`` lossy K/V (the ``dequant_fallback`` path).
      vLLM's prefill attention runs normally on the lossy
      reconstruction; our cache holds the same K/V in INT4-packed
      form for decode to read.
    * **Decode** (``num_tokens == 1``): append the K/V into the
      cache, run ``fused_protected_k_decode_attention`` over the
      accumulated cache, return its output. vLLM's original
      ``forward`` is NOT called.

    Fail-open posture: on ANY exception in either branch, log it and
    fall back to a safe path — the prefill path falls back to running
    the original ``forward`` (possibly with unrewritten K/V); the
    decode path falls back to ``round_trip_kv`` + original ``forward``
    (the ``dequant_fallback`` behaviour). A prefill sidecar failure
    additionally marks the cache as poisoned so subsequent decodes
    on this sequence skip the bypass — the cache may be out of sync.

    v1 scope (locked):
    * ``num_tokens == 1`` only for the decode bypass (multi-token
      decode falls back to ``dequant_fallback``).
    * Batch=1 single-sequence; no per-sequence slot mapping.
    * ``cache_k_group_size=1`` is a 6c.3A SIMPLIFICATION, NOT the
      §20.4 measured config (group=32).
    """
    original_forward = module.forward
    module_id = id(module)

    def wrapped_forward(*args, **kwargs):
        if torch is None:
            return original_forward(*args, **kwargs)
        # Validate arg layout. Fall through to original on malformed
        # input (a malformed interception must never crash inference).
        if (
            len(args) <= max(query_arg_index, key_arg_index, value_arg_index)
            or not isinstance(args[key_arg_index], torch.Tensor)
            or not isinstance(args[value_arg_index], torch.Tensor)
            or args[key_arg_index].ndim not in (2, 3)
            or args[value_arg_index].ndim not in (2, 3)
        ):
            manager._record_fused_v2_fallback("malformed_args")
            return original_forward(*args, **kwargs)

        key = args[key_arg_index]
        value = args[value_arg_index]
        was_2d = (key.ndim == 2)

        # Reshape K/V to 3-D for the cache.
        if was_2d:
            h = manager._num_kv_heads
            if h is None:
                manager._record_fused_v2_fallback("unknown_num_kv_heads")
                return original_forward(*args, **kwargs)
            key_3d = _reshape_kv_2d_to_3d(key, h)
            value_3d = _reshape_kv_2d_to_3d(value, h)
            if key_3d is None or value_3d is None:
                manager._record_fused_v2_fallback("unreshapeable_kv")
                return original_forward(*args, **kwargs)
        else:
            key_3d = key
            value_3d = value

        T = key_3d.shape[0]
        if T < 1:
            return original_forward(*args, **kwargs)

        cache = manager.get_or_create_cache(module_id)

        if T > 1:
            # ---- Prefill path: sidecar + dequant_fallback. ----
            sidecar_ok = True
            try:
                cache.append(key_3d, value_3d)
                manager._fused_v2_prefills_sidecar += 1
            except Exception:  # noqa: BLE001 — fail-open
                logger.exception(
                    "fused_v2 prefill sidecar failed on %s; cache may "
                    "be out of sync. Marking poisoned; subsequent "
                    "decodes will fall back to dequant_fallback.",
                    type(module).__name__,
                )
                cache.mark_poisoned("prefill_sidecar_exception")
                manager._record_fused_v2_fallback("prefill_sidecar_exception")
                sidecar_ok = False
            # Always run the dequant_fallback rewrite for vLLM's
            # prefill attention. (Even if sidecar failed, prefill
            # still proceeds — the model needs the prefill output.)
            try:
                k_lossy, v_lossy = manager.round_trip_kv(key, value)
                mutable = list(args)
                mutable[key_arg_index] = k_lossy
                mutable[value_arg_index] = v_lossy
                return original_forward(*mutable, **kwargs)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "fused_v2 prefill round_trip_kv failed on %s; "
                    "running original forward with unrewritten K/V.",
                    type(module).__name__,
                )
                manager._record_fused_v2_fallback("prefill_round_trip_exception")
                return original_forward(*args, **kwargs)

        # ---- Decode path: T == 1, fused kernel bypass. ----
        if cache.is_poisoned:
            manager._record_fused_v2_fallback("poisoned_cache")
            return _decode_fallback(
                manager, args, key, value,
                key_arg_index, value_arg_index,
                original_forward, kwargs, module,
            )

        try:
            query = args[query_arg_index]
            if not isinstance(query, torch.Tensor):
                raise ValueError("query arg is not a tensor")
            out_dtype = query.dtype

            # Profiling: record per-section CUDA events. Off by default;
            # enabled via manager.set_profiling(True) for diagnostic runs.
            prof = manager._profile_enabled and torch.cuda.is_available()

            def _new_event_pair():
                if not prof:
                    return None, None
                start = torch.cuda.Event(enable_timing=True)
                end = torch.cuda.Event(enable_timing=True)
                return start, end

            tot_s, tot_e = _new_event_pair()
            if prof:
                tot_s.record()

            # ---- Section: cache append ----
            sec_s, sec_e = _new_event_pair()
            if prof:
                sec_s.record()
            cache.append(key_3d, value_3d)
            if prof:
                sec_e.record()
                manager._profile_events["cache_append"].append((sec_s, sec_e))

            # ---- Section: read-skip decision (scoring + block selection) ----
            sec_s, sec_e = _new_event_pair()
            if prof:
                sec_s.record()
            active_positions = manager._readskip_active_positions(cache, query)
            if prof:
                sec_e.record()
                manager._profile_events["readskip_decision"].append((sec_s, sec_e))

            # ---- Section: kernel inputs (gather/compaction + contiguous copies) ----
            sec_s, sec_e = _new_event_pair()
            if prof:
                sec_s.record()
            inputs = cache.kernel_inputs(active_positions=active_positions)
            if prof:
                sec_e.record()
                manager._profile_events["kernel_inputs"].append((sec_s, sec_e))

            # ---- Section: query reshape / cast ----
            sec_s, sec_e = _new_event_pair()
            if prof:
                sec_s.record()
            query_was_2d = (query.ndim == 2)
            if cache.head_dim is None:
                raise ValueError(
                    "cache head_dim still None after append — alloc bug"
                )
            D = cache.head_dim
            if query_was_2d:
                if query.shape[-1] % D != 0:
                    raise ValueError(
                        f"2-D query last dim {query.shape[-1]} not "
                        f"divisible by head_dim {D}"
                    )
                H_q = query.shape[-1] // D
                if query.shape[0] != 1:
                    raise ValueError(
                        f"decode bypass requires query num_tokens==1; "
                        f"got {query.shape[0]}"
                    )
                q_kernel = query.reshape(1, H_q, D)
            else:
                if query.shape[0] != 1:
                    raise ValueError(
                        f"decode bypass requires query num_tokens==1; "
                        f"got 3-D query shape {tuple(query.shape)}"
                    )
                q_kernel = query
                H_q = query.shape[1]

            if q_kernel.dtype != torch.float16:
                q_kernel = q_kernel.to(torch.float16)
            q_kernel = q_kernel.contiguous()
            if prof:
                sec_e.record()
                manager._profile_events["reshape_kv"].append((sec_s, sec_e))

            # ---- Section: fused kernel ----
            sec_s, sec_e = _new_event_pair()
            if prof:
                sec_s.record()
            from kv_policy.int4_fused_attention_kernel import (
                fused_protected_k_decode_attention,
            )
            out = fused_protected_k_decode_attention(
                q=q_kernel,
                k_packed=inputs["k_packed"],
                k_scale=inputs["k_scale"],
                k_offset=inputs["k_offset"],
                k_fp16=inputs["k_fp16"],
                protect_mask=inputs["protect_mask"],
                v_packed=inputs["v_packed"],
                v_scale=inputs["v_scale"],
                v_offset=inputs["v_offset"],
                group_size_k=cache.k_group_size,
                group_size_v=cache.v_group_size,
                asymmetric=cache.asymmetric,
            )  # (1, H_q, D) fp16
            if prof:
                sec_e.record()
                manager._profile_events["kernel_call"].append((sec_s, sec_e))
            manager._fused_v2_decodes += 1

            # ---- Section: cast back + reshape ----
            sec_s, sec_e = _new_event_pair()
            if prof:
                sec_s.record()
            if out.dtype != out_dtype:
                out = out.to(out_dtype)
            if query_was_2d:
                out = out.reshape(1, H_q * D)
            if prof:
                sec_e.record()
                manager._profile_events["cast_back"].append((sec_s, sec_e))
                tot_e.record()
                manager._profile_events["total_bypass"].append((tot_s, tot_e))
            return out
        except Exception:  # noqa: BLE001 — fail-open per fail-safe posture
            logger.exception(
                "fused_v2 decode bypass failed on %s; falling back to "
                "dequant_fallback for this call. (Note: cache may now "
                "be partially populated for this token; correctness "
                "of subsequent decodes is not guaranteed.)",
                type(module).__name__,
            )
            manager._record_fused_v2_fallback("decode_exception")
            return _decode_fallback(
                manager, args, key, value,
                key_arg_index, value_arg_index,
                original_forward, kwargs, module,
            )

    module.forward = wrapped_forward
    teardown_list.append(
        lambda: setattr(module, "forward", original_forward)
    )


def _decode_fallback(
    manager: "INT4CacheKVRouteA",
    args: tuple,
    key: "torch.Tensor",
    value: "torch.Tensor",
    key_arg_index: int,
    value_arg_index: int,
    original_forward: Callable,
    kwargs: dict,
    module: Any,
):
    """Best-effort dequant_fallback for a single decode call when the
    fused_v2 bypass can't run. Used by the fused_v2 wrapper only."""
    try:
        k_lossy, v_lossy = manager.round_trip_kv(key, value)
        mutable = list(args)
        mutable[key_arg_index] = k_lossy
        mutable[value_arg_index] = v_lossy
        return original_forward(*mutable, **kwargs)
    except Exception:  # noqa: BLE001
        logger.exception(
            "decode fallback round_trip_kv also failed on %s; using "
            "original K/V (lossless).",
            type(module).__name__,
        )
        return original_forward(*args, **kwargs)


def _detect_num_kv_heads(model: Any) -> Optional[int]:
    """Best-effort read of the KV-head count from a model's config.

    vLLM models expose ``model.config`` (the HF config). KV-head field
    names vary: ``num_key_value_heads`` (Llama/Qwen/Mistral GQA),
    falling back to ``num_attention_heads`` (MHA models where KV heads
    == attention heads). Returns None if neither is found — the caller
    then requires an explicit ``num_kv_heads``.
    """
    cfg = getattr(model, "config", None)
    if cfg is None:
        return None
    for attr in ("num_key_value_heads", "num_attention_heads", "n_head"):
        val = getattr(cfg, attr, None)
        if isinstance(val, int) and val > 0:
            return val
    return None


def install_int4_cache_kv_route_a(
    *,
    model: Any,
    k_group_size: int = 32,
    v_group_size: int = 32,
    asymmetric: bool = True,
    bits: int = 4,
    sink_size: int = 0,
    num_kv_heads: Optional[int] = None,
    query_arg_index: int = 0,
    key_arg_index: int = 1,
    value_arg_index: int = 2,
    kernel_backend: str = BACKEND_DEQUANT_FALLBACK,
    max_seq_len: Optional[int] = None,
    protect_fraction: float = 0.04,
    cache_k_group_size: int = 1,
    cache_v_group_size: int = 32,
) -> "Tuple[INT4CacheKVRouteA, Callable[[], None]]":
    """Install the route-A INT4 KV-cache interception on ``model``.

    Walks ``model.named_modules()`` for vLLM attention layers and
    wraps each one's ``forward`` according to ``kernel_backend``.

    Args:
        model: the torch model (vLLM exposes it via
            ``runner_vllm_streaming.AsyncEngineDriver._extract_model_from_engine``
            — the ``model_executor → driver_worker → worker →
            model_runner → model`` walk).
        k_group_size / v_group_size / asymmetric / bits / sink_size:
            KIVI config used by the ``round_trip_kv`` path.
        num_kv_heads: KV-head count. REQUIRED for vLLM's 2-D K/V
            layout. When ``None``, auto-detected from ``model.config``.
        query_arg_index / key_arg_index / value_arg_index: positional
            indices of Q/K/V in the attention module's ``forward(self,
            query, key, value, ...)`` signature. Defaults (0, 1, 2)
            match the bound-method ``args`` layout for the classic
            vLLM signature.
        kernel_backend: ``"dequant_fallback"`` (default, §20.3 quality
            path — wraps ``forward`` to rewrite K/V via
            ``round_trip_kv``) or ``"fused_v2"`` (6c.3A model-level
            fused-decode bypass — sidecars prefill K/V into a parallel
            ``ProtectedKINT4Cache``, replaces decode ``forward`` with
            ``fused_protected_k_decode_attention``).
        max_seq_len: REQUIRED for ``fused_v2``; preallocated cache size
            per layer.
        protect_fraction: ``fused_v2`` only — top-fraction of K
            channels kept FP16 in the parallel cache (default 0.04,
            the §20.4.2 win).
        cache_k_group_size: ``fused_v2`` only — K group size for the
            parallel cache. v1 requires 1 (per-token K — a 6c.3A
            SIMPLIFICATION, NOT the §20.4 measured group=32 config).
        cache_v_group_size: ``fused_v2`` only — V group size for the
            parallel cache (default 32, matches §20.4).

    Returns ``(manager, teardown)``:
        * ``manager`` — the ``INT4CacheKVRouteA``; read ``.stats`` /
          ``.config`` off it. After a run, ``stats['forward_calls']``
          (dequant_fallback) or ``stats['fused_v2_decodes']``
          (fused_v2) should be > 0; if it's 0 the interception never
          fired (wrong arg indices, or a vLLM version whose attention
          layer doesn't take Q/K/V positionally).
        * ``teardown`` — call to revert every wrapped ``forward``
          (LIFO). Used by tests and by clean engine shutdown.

    Raises ``ValueError`` if no attention modules are found, or if
    ``kernel_backend='fused_v2'`` and ``max_seq_len`` is missing.
    """
    if torch is None:
        raise ImportError("install_int4_cache_kv_route_a requires PyTorch.")
    resolved_num_kv_heads = (
        num_kv_heads if num_kv_heads is not None
        else _detect_num_kv_heads(model)
    )
    if resolved_num_kv_heads is None:
        logger.warning(
            "install_int4_cache_kv_route_a: num_kv_heads not given and "
            "not auto-detectable from model.config. vLLM's 2-D K/V "
            "layout cannot be reshaped — 2-D forwards will pass "
            "through uncompressed. Pass num_kv_heads explicitly."
        )
    manager = INT4CacheKVRouteA(
        k_group_size=k_group_size,
        v_group_size=v_group_size,
        asymmetric=asymmetric,
        bits=bits,
        sink_size=sink_size,
        num_kv_heads=resolved_num_kv_heads,
        kernel_backend=kernel_backend,
        max_seq_len=max_seq_len,
        protect_fraction=protect_fraction,
        cache_k_group_size=cache_k_group_size,
        cache_v_group_size=cache_v_group_size,
    )
    teardown_list: List[Callable[[], None]] = []

    n_wrapped = 0
    if hasattr(model, "named_modules"):
        for _name, module in model.named_modules():
            if not _looks_like_attention(module):
                continue
            if kernel_backend == BACKEND_FUSED_V2:
                _wrap_attention_forward_with_fused_v2(
                    module,
                    manager=manager,
                    query_arg_index=query_arg_index,
                    key_arg_index=key_arg_index,
                    value_arg_index=value_arg_index,
                    teardown_list=teardown_list,
                )
            else:
                _wrap_attention_forward_with_kv_rewrite(
                    module,
                    manager=manager,
                    key_arg_index=key_arg_index,
                    value_arg_index=value_arg_index,
                    teardown_list=teardown_list,
                )
            n_wrapped += 1
    if n_wrapped == 0:
        raise ValueError(
            "install_int4_cache_kv_route_a found no attention modules "
            "on the model. The class-name heuristic "
            "(endswith 'Attention') missed — either the model argument "
            "is wrong, or this vLLM version names its attention class "
            "differently. Adjust `_looks_like_attention` or pass the "
            "correct model."
        )
    logger.info(
        "route-A INT4 KV-cache installed: %d attention modules wrapped "
        "(%s, num_kv_heads=%s)",
        n_wrapped, manager.config["scheme"], resolved_num_kv_heads,
    )

    def teardown() -> None:
        # LIFO revert.
        for revert in reversed(teardown_list):
            revert()
        teardown_list.clear()

    return manager, teardown
