"""Route-A INT4 KV-cache integration for vLLM.

Route-B (``int4_per_channel_hf_cache.INT4PerChannelCache``) subclasses
HF transformers' ``DynamicCache`` — it is the **measurement vehicle**
for the §18/§19 quality numbers but cannot deploy on vLLM.

Route-A (this module) is the vLLM-side integration: a monkey-patch of
the ``Attention`` modules' ``forward`` that runs K/V through the
KIVI INT4 round-trip before attention computes on them. The algorithm
ops (``quantize_per_channel_int4`` etc. in ``int4_per_channel_kv.py``)
are reused **unchanged** — route-A and route-B are the same algorithm,
differing only in the integration point.

What this module IS
-------------------

* ``INT4CacheKVRouteA`` — the per-call compress→decompress manager.
  Reuses the route-B quantizer ops directly. vLLM passes K/V at the
  Attention layer as ``(num_tokens, num_kv_heads, head_dim)``, which
  is exactly the ``(S, H, D)`` layout the quantizer ops expect — no
  transpose needed (route-B had to transpose ``(B,H,S,D)``).

* ``install_int4_cache_kv_route_a(model, **config)`` — walks the
  model's ``Attention`` modules and wraps each one's ``forward`` so
  the K/V it receives are INT4-round-tripped. Returns ``(manager,
  teardown)``. CPU-importable (no ``vllm`` import; identifies
  Attention modules by class-name heuristic, the same approach
  ``triattention.py`` uses).

What this module IS NOT (the deferred GPU work)
-----------------------------------------------

* It does **not yet realize the memory saving**. This tier runs the
  INT4 *quality* path under vLLM — the compressed K/V flow through
  attention so the per-block-layout quality effect (route-A open
  question 3) is measurable. Realizing the 3.2× HBM saving needs
  vLLM's paged KV buffer to be allocated INT4-width and the FlashAttn
  read path to dequant from it — the "alternate paged buffer" in
  ``ROUTE_A_VLLM_CACHE_KV_PLAN.md``. That is the Marlin-kernel /
  paged-buffer follow-up (§20.6 + plan §"secondary patches").

* The real-vLLM call-site verification + GPU correctness run is
  deferred — this is a CPU dev pod with no ``vllm`` and no GPU. The
  install path is CPU-validated against faked ``Attention`` modules
  (the ``test_vllm_protocol_fixture.py`` pattern). Days 4-5 of the
  route-A plan (GPU smoke + chat_32k) remain.

This mirrors the repo's established staging: TurboQuant §15 landed
its PyTorch-ops port "as CPU-correct, GPU-ready code in a no-GPU
session" with the ``cache_kv`` monkey-patch deferred. Route-A INT4
goes one step further — the monkey-patch install itself lands here,
CPU-tested; only the GPU verification is deferred.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional, Tuple

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover - guarded at the caller
    torch = None  # type: ignore


logger = logging.getLogger("int4_cache_kv_route_a")


class INT4CacheKVRouteA:
    """Per-call KIVI INT4 compress→decompress for the vLLM Attention
    layer.

    Holds the KIVI config and applies the round-trip to K/V tensors as
    they pass through ``Attention.forward``. Stateless across calls
    (each forward's K/V are quantized independently — matching vLLM's
    per-block write model); the only state is the running stats.

    Constructor args mirror ``INT4PerChannelCache`` so route-A and
    route-B are configured identically:

        k_group_size / v_group_size : KIVI group quantization sizes.
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
        self._k_group_size = int(k_group_size)
        self._v_group_size = int(v_group_size)
        self._asymmetric = bool(asymmetric)
        self._bits = int(bits)
        self._sink_size = int(sink_size)
        self._num_kv_heads = (
            int(num_kv_heads) if num_kv_heads is not None else None
        )
        self._forward_calls = 0
        self._tokens_compressed = 0
        self._sink_tokens_passed_through = 0
        # Counts forwards skipped because a 2-D K/V arrived but
        # num_kv_heads is unknown — surfaced in stats so a silent
        # no-op is detectable.
        self._skipped_unknown_shape = 0

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
            "scheme": (
                f"K=per-channel INT{self._bits}, V=per-token INT{self._bits}, "
                f"{'asymmetric' if self._asymmetric else 'symmetric'}, "
                f"k_group={self._k_group_size}, v_group={self._v_group_size}"
                + (f", sink_size={self._sink_size}"
                   if self._sink_size > 0 else "")
            ),
        }

    @property
    def stats(self) -> dict:
        return {
            "forward_calls": self._forward_calls,
            "tokens_compressed": self._tokens_compressed,
            "sink_tokens_passed_through": self._sink_tokens_passed_through,
            "skipped_unknown_shape": self._skipped_unknown_shape,
        }

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
    key_arg_index: int = 1,
    value_arg_index: int = 2,
) -> "Tuple[INT4CacheKVRouteA, Callable[[], None]]":
    """Install the route-A INT4 KV-cache interception on ``model``.

    Walks ``model.named_modules()`` for vLLM attention layers and
    wraps each one's ``forward`` so the K/V it receives are KIVI INT4
    round-tripped.

    Args:
        model: the torch model (vLLM exposes it via
            ``runner_vllm_streaming.AsyncEngineDriver._extract_model_from_engine``
            — the ``model_executor → driver_worker → worker →
            model_runner → model`` walk).
        k_group_size / v_group_size / asymmetric / bits / sink_size:
            KIVI config — same knobs as ``INT4PerChannelCache``.
        num_kv_heads: KV-head count. REQUIRED for vLLM's 2-D K/V
            layout — vLLM hands ``Attention.forward`` flat 2-D K/V
            ``(num_tokens, num_kv_heads*head_dim)`` (the common case;
            confirmed by ``triattention.py``'s GPU-validated Phase 4
            hook). When ``None``, auto-detected from ``model.config``
            (``num_key_value_heads`` / ``num_attention_heads``). If
            auto-detection fails AND no explicit value is given, the
            install still succeeds but 2-D K/V will pass through
            uncompressed (logged + counted in
            ``manager.stats['skipped_unknown_shape']``).
        key_arg_index / value_arg_index: positional indices of K and V
            in the attention module's ``forward(self, query, key,
            value, ...)`` signature. Defaults (1, 2) match the classic
            vLLM signature; override if the pod's vLLM version moved
            them (route-A plan open question — verify on day 1
            against the actual vLLM source).

    Returns ``(manager, teardown)``:
        * ``manager`` — the ``INT4CacheKVRouteA``; read ``.stats`` /
          ``.config`` off it. After a run, ``stats['forward_calls']``
          should be > 0; if it's 0 the interception never fired
          (wrong arg indices, or a vLLM version whose attention layer
          doesn't take K/V positionally).
        * ``teardown`` — call to revert every wrapped ``forward``
          (LIFO). Used by tests and by clean engine shutdown.

    Raises ``ValueError`` if no attention modules are found — the
    class-name heuristic missed (a vLLM version with a differently-
    named attention class); the caller must pass the right model or
    adjust ``_looks_like_attention``.
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
    )
    teardown_list: List[Callable[[], None]] = []

    n_wrapped = 0
    if hasattr(model, "named_modules"):
        for _name, module in model.named_modules():
            if _looks_like_attention(module):
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
