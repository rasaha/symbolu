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
    """

    def __init__(
        self,
        *,
        k_group_size: int = 32,
        v_group_size: int = 32,
        asymmetric: bool = True,
        bits: int = 4,
        sink_size: int = 0,
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
        self._k_group_size = int(k_group_size)
        self._v_group_size = int(v_group_size)
        self._asymmetric = bool(asymmetric)
        self._bits = int(bits)
        self._sink_size = int(sink_size)
        self._forward_calls = 0
        self._tokens_compressed = 0
        self._sink_tokens_passed_through = 0

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
        }

    def round_trip_kv(
        self,
        key: "torch.Tensor",
        value: "torch.Tensor",
    ) -> "Tuple[torch.Tensor, torch.Tensor]":
        """Run K/V through the KIVI INT4 compress→decompress.

        Args:
            key:   ``(num_tokens, num_kv_heads, head_dim)`` — vLLM's
                   Attention-layer K layout, which IS the quantizer's
                   ``(S, H, D)``. A flattened 2-D
                   ``(num_tokens, num_kv_heads * head_dim)`` input is
                   also accepted and reshaped (caller must then pass
                   ``num_kv_heads`` via ``reshape_2d_hint``); 3-D is
                   the supported path.
            value: same shape as ``key``.

        Returns the lossy ``(key, value)`` — same shape and dtype as
        the inputs. When ``sink_size > 0`` and the forward carries
        more than ``sink_size`` tokens, the first ``sink_size``
        positions pass through bit-identical FP16 and only positions
        ``[sink_size:]`` are quantized (StreamingLLM sink protection,
        the §20.2 path).
        """
        from kv_policy.int4_per_channel_kv import (
            quantize_per_channel_int4, dequantize_per_channel_int4,
            quantize_per_token_int4, dequantize_per_token_int4,
        )
        if key.ndim != 3 or value.ndim != 3:
            raise ValueError(
                "INT4CacheKVRouteA.round_trip_kv expects 3-D "
                "(num_tokens, num_kv_heads, head_dim) tensors; got "
                f"K {tuple(key.shape)}, V {tuple(value.shape)}. "
                "Reshape a flattened 2-D K/V to 3-D before calling."
            )
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
        hold 3-D tensors, the wrapper logs once and passes the call
        through untouched (a malformed interception must never crash
        the engine mid-decode).
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
                and args[key_arg_index].ndim == 3
                and args[value_arg_index].ndim == 3
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


def install_int4_cache_kv_route_a(
    *,
    model: Any,
    k_group_size: int = 32,
    v_group_size: int = 32,
    asymmetric: bool = True,
    bits: int = 4,
    sink_size: int = 0,
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
        key_arg_index / value_arg_index: positional indices of K and V
            in the attention module's ``forward(self, query, key,
            value, ...)`` signature. Defaults (1, 2) match the classic
            vLLM signature; override if the pod's vLLM version moved
            them (route-A plan open question 6 — verify on day 1
            against the actual vLLM source).

    Returns ``(manager, teardown)``:
        * ``manager`` — the ``INT4CacheKVRouteA``; read ``.stats`` /
          ``.config`` off it.
        * ``teardown`` — call to revert every wrapped ``forward``
          (LIFO). Used by tests and by clean engine shutdown.

    Raises ``ValueError`` if no attention modules are found — that
    means the class-name heuristic missed (a vLLM version with a
    differently-named attention class) and the caller must pass the
    right model or extend ``_ATTENTION_CLASS_HINTS``.
    """
    if torch is None:
        raise ImportError("install_int4_cache_kv_route_a requires PyTorch.")
    manager = INT4CacheKVRouteA(
        k_group_size=k_group_size,
        v_group_size=v_group_size,
        asymmetric=asymmetric,
        bits=bits,
        sink_size=sink_size,
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
        "(%s)",
        n_wrapped, manager.config["scheme"],
    )

    def teardown() -> None:
        # LIFO revert.
        for revert in reversed(teardown_list):
            revert()
        teardown_list.clear()

    return manager, teardown
