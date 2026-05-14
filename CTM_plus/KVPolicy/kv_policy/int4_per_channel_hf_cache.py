"""HuggingFace ``DynamicCache`` subclass that applies INT4 per-channel
quantization to K and per-token quantization to V (KIVI-style).

Drop-in alternative to ``TurboQuantCache``. Same surface, same call
signature, same Track E integration — so the eval script can swap
between them via the ``--quant`` flag.

Why this exists separately from TurboQuant: KIVI's INT4 per-channel
scheme is fundamentally different from PolarQuant. No rotation step,
no polar decomposition, no random-grid quantizer. Each (head,
head_dim) channel keeps its own INT4 scale; each (seq, head) token
position keeps its own INT4 scale for V. This is the literature-
validated approach for KV-cache compression on transformer LMs and
the path forward after the PolarQuant negative result in
``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §17.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

try:
    from transformers.cache_utils import DynamicCache  # type: ignore
except ImportError:  # pragma: no cover
    DynamicCache = None  # type: ignore


def _compress_decompress_kv_int4(
    k: "torch.Tensor",
    v: "torch.Tensor",
    *,
    store: Any,
) -> "Tuple[torch.Tensor, torch.Tensor]":
    """Round-trip ``(B, H, S, D)`` K/V through the INT4 kvstore.

    Identical interface to ``turboquant_hf_cache._compress_decompress_kv``.
    The kvstore expects per-block tensors of shape ``(S, H, D)`` (vLLM
    layout); we transpose for the call and transpose back on the way
    out, exactly as the TurboQuant wrapper does.
    """
    if k.ndim != 4 or v.ndim != 4:
        raise ValueError(
            f"_compress_decompress_kv_int4 expected 4-D (B, H, S, D) "
            f"tensors, got K.shape={tuple(k.shape)}, V.shape={tuple(v.shape)}"
        )
    b = k.shape[0]
    if v.shape[0] != b:
        raise ValueError(f"K batch {b} != V batch {v.shape[0]}")

    k_out = torch.empty_like(k)
    v_out = torch.empty_like(v)
    for batch_idx in range(b):
        k_block = k[batch_idx].transpose(0, 1).contiguous()  # (S, H, D)
        v_block = v[batch_idx].transpose(0, 1).contiguous()
        store.write_block(0, k_block, v_block)
        k_back, v_back = store.read_block(0)
        store.remove_block(0)
        k_out[batch_idx] = k_back.transpose(0, 1)
        v_out[batch_idx] = v_back.transpose(0, 1)
    return k_out, v_out


class INT4PerChannelCache(DynamicCache if DynamicCache is not None else object):
    """``DynamicCache`` that quantizes K per-channel and V per-token to
    INT4 on every update.

    Constructor args:
        torch_device: optional device override for the kvstore.
        sink_size: optional StreamingLLM-style sink protection. When
            > 0 and the update's seq axis is longer than sink_size,
            the first sink_size positions pass through uncompressed;
            only positions [sink_size:] are quantized. Default 0
            (no sink protection). KIVI's published quality numbers
            don't use sink-skip — pure per-channel/per-token INT4 is
            already sufficient. Sink-skip is exposed as an opt-in for
            symmetry with ``TurboQuantCache`` and for future
            experimentation.
    """

    def __init__(
        self,
        *,
        torch_device: Optional[Any] = None,
        sink_size: int = 0,
    ) -> None:
        if DynamicCache is None:
            raise ImportError(
                "INT4PerChannelCache requires HuggingFace transformers."
            )
        if torch is None:
            raise ImportError("INT4PerChannelCache requires PyTorch.")
        super().__init__()
        from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore
        self._int4_store = INT4PerChannelKVStore(torch_device=torch_device)
        self._cfg = dict(
            torch_device=str(torch_device),
            sink_size=int(sink_size),
            scheme="int4_per_channel_k_per_token_v",
        )
        self._sink_size = int(sink_size)
        if self._sink_size < 0:
            raise ValueError(f"sink_size must be >= 0, got {sink_size}")
        self._updates = 0
        self._total_kv_elements = 0
        self._sink_elements_passed_through = 0

    def update(
        self,
        key_states: "torch.Tensor",
        value_states: "torch.Tensor",
        layer_idx: int,
        *args,
        **kwargs,
    ) -> "Tuple[torch.Tensor, torch.Tensor]":
        sink = self._sink_size
        if sink > 0 and key_states.shape[2] > sink:
            k_sink = key_states[:, :, :sink, :]
            v_sink = value_states[:, :, :sink, :]
            k_rest = key_states[:, :, sink:, :].contiguous()
            v_rest = value_states[:, :, sink:, :].contiguous()
            k_rest_lossy, v_rest_lossy = _compress_decompress_kv_int4(
                k_rest, v_rest, store=self._int4_store,
            )
            k_lossy = torch.cat([k_sink, k_rest_lossy], dim=2)
            v_lossy = torch.cat([v_sink, v_rest_lossy], dim=2)
            self._sink_elements_passed_through += int(
                k_sink.numel() + v_sink.numel()
            )
        else:
            k_lossy, v_lossy = _compress_decompress_kv_int4(
                key_states, value_states, store=self._int4_store,
            )
        self._updates += 1
        self._total_kv_elements += int(key_states.numel() + value_states.numel())
        return super().update(k_lossy, v_lossy, layer_idx, *args, **kwargs)

    @property
    def int4_config(self) -> dict:
        return dict(self._cfg)

    @property
    def int4_stats(self) -> dict:
        s = self._int4_store.get_stats()
        s["updates"] = self._updates
        s["total_kv_elements_seen"] = self._total_kv_elements
        s["sink_size"] = self._sink_size
        s["sink_elements_passed_through"] = self._sink_elements_passed_through
        return s
