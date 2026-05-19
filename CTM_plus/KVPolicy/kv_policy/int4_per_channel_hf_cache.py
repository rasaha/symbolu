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


def _select_outlier_mask(
    k: "torch.Tensor", fraction: float,
) -> "torch.Tensor":
    """Return an ``(H, D)`` bool mask of the top-``fraction`` K channels
    by per-channel max-abs magnitude (max-abs over batch and sequence).

    A "channel" is an ``(h, d)`` pair — the unit per-channel
    quantization scales over. K (post-RoPE) carries a few channels
    with disproportionate magnitude; one INT4 scale per channel still
    crushes the normal channels to resolve the outlier's range. The
    §20.4 mechanism analysis attributes the long-context K-INT4
    failure largely to these outlier channels.
    """
    h, d = int(k.shape[1]), int(k.shape[3])
    n_channels = h * d
    n_protect = min(max(1, round(fraction * n_channels)), n_channels)
    mag = k.abs().amax(dim=2).amax(dim=0)  # (H, D)
    protect_idx = torch.topk(mag.reshape(-1), k=n_protect).indices
    mask = torch.zeros(n_channels, dtype=torch.bool, device=k.device)
    mask[protect_idx] = True
    return mask.reshape(h, d)


def _restore_outlier_channels(
    k_orig: "torch.Tensor",
    k_quant: "torch.Tensor",
    *,
    fraction: float = 0.0,
    mask: "Optional[torch.Tensor]" = None,
) -> "torch.Tensor":
    """Outlier-protected K: keep the protected K channels at their
    original FP16 values, take the INT4 round-trip for the rest.
    Protecting the largest-magnitude channels at FP16 costs almost
    nothing in memory (e.g. 1% of channels → +~0.1 bit/elem) while
    removing the dominant K-INT4 error.

    When ``mask`` (an ``(H, D)`` bool tensor) is given it is used
    directly — the *static* path, where the protected set was frozen
    once per layer rather than recomputed per block. When ``mask`` is
    None the set is selected *dynamically* from ``k_orig`` by
    ``fraction`` (the optimistic per-block upper bound).

    ``k_orig`` / ``k_quant`` are ``(B, H, S, D)``; returns the merged
    tensor of the same shape.
    """
    if mask is None:
        mask = _select_outlier_mask(k_orig, fraction)
    # Broadcast over (B, ·, S, ·): protected channels take the FP16
    # original, the rest take the INT4 round-trip.
    return torch.where(mask[None, :, None, :], k_orig, k_quant)


def _compress_decompress_kv_int4(
    k: "torch.Tensor",
    v: "torch.Tensor",
    *,
    store: Any,
    static_k_scale: "Optional[torch.Tensor]" = None,
    static_k_offset: "Optional[torch.Tensor]" = None,
    static_v_scale: "Optional[torch.Tensor]" = None,
    static_v_offset: "Optional[torch.Tensor]" = None,
    quantize_k: bool = True,
    quantize_v: bool = True,
    k_protect_fraction: float = 0.0,
    k_protect_mask: "Optional[torch.Tensor]" = None,
) -> "Tuple[torch.Tensor, torch.Tensor]":
    """Round-trip ``(B, H, S, D)`` K/V through the INT4 kvstore.

    Identical interface to ``turboquant_hf_cache._compress_decompress_kv``.
    The kvstore expects per-block tensors of shape ``(S, H, D)`` (vLLM
    layout); we transpose for the call and transpose back on the way
    out, exactly as the TurboQuant wrapper does.

    Optional ``static_*_scale`` / ``static_*_offset`` tensors come from
    a calibration file and short-circuit the dynamic max-based scale
    computation inside the kvstore.

    ``quantize_k`` / ``quantize_v`` are the §20.4 diagnostic ablation
    toggles. When ``quantize_k`` is False the original FP16 K is
    returned unchanged (K passes through at full precision); same for
    ``quantize_v``. This isolates which channel — K or V — is
    responsible for the long-context decode degradation. The store
    still round-trips both internally; only the returned tensor for
    the disabled channel is swapped back to the FP16 source. Keeping
    the store call uniform is intentional: it is the minimal patch and
    avoids a second code path through the kvstore.

    ``k_protect_fraction`` > 0 enables outlier-protected K: the
    top-fraction K channels keep their FP16 values, the rest are INT4
    (see ``_restore_outlier_channels``). Applied only when
    ``quantize_k`` is True. ``k_protect_mask`` (an ``(H, D)`` bool
    tensor), when given, is a pre-frozen protected set — the static
    path; when None the set is selected dynamically per call.
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
        store.write_block(
            0, k_block, v_block,
            static_k_scale=static_k_scale,
            static_k_offset=static_k_offset,
            static_v_scale=static_v_scale,
            static_v_offset=static_v_offset,
        )
        k_back, v_back = store.read_block(0)
        store.remove_block(0)
        k_out[batch_idx] = k_back.transpose(0, 1)
        v_out[batch_idx] = v_back.transpose(0, 1)
    k_final = k_out if quantize_k else k
    if quantize_k and k_protect_fraction > 0.0:
        k_final = _restore_outlier_channels(
            k, k_final, fraction=k_protect_fraction, mask=k_protect_mask,
        )
    return k_final, (v_out if quantize_v else v)


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
        k_group_size: int = 0,
        v_group_size: int = 0,
        asymmetric: bool = False,
        bits: int = 4,
        k_bits: Optional[int] = None,
        v_bits: Optional[int] = None,
        calibration_path: Optional[str] = None,
        quantize_k: bool = True,
        quantize_v: bool = True,
        k_protect_fraction: float = 0.0,
        k_protect_static: bool = False,
    ) -> None:
        if DynamicCache is None:
            raise ImportError(
                "INT4PerChannelCache requires HuggingFace transformers."
            )
        if torch is None:
            raise ImportError("INT4PerChannelCache requires PyTorch.")
        super().__init__()
        from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore
        self._int4_store = INT4PerChannelKVStore(
            torch_device=torch_device,
            k_group_size=k_group_size,
            v_group_size=v_group_size,
            asymmetric=asymmetric,
            bits=bits,
            k_bits=k_bits,
            v_bits=v_bits,
        )
        # Effective per-channel bit widths: ``bits`` is the shared
        # default, k_bits / v_bits override it (adaptive precision).
        eff_k_bits = int(k_bits if k_bits is not None else bits)
        eff_v_bits = int(v_bits if v_bits is not None else bits)

        # Optional GPTQ/AWQ-style static calibration: per-layer scales
        # pre-computed offline on a calibration set (see
        # ``Bench/ctm_bench/scripts/calibrate_int4_scales.py``). When
        # loaded, ``update()`` looks up the calibrated scales by
        # ``layer_idx`` and skips dynamic max-based scale computation.
        self._calibration: Optional[dict] = None
        if calibration_path is not None:
            self._calibration = torch.load(calibration_path, map_location="cpu")
            if not isinstance(self._calibration, dict):
                raise ValueError(
                    f"calibration file must load to a dict; got {type(self._calibration).__name__}"
                )
            # Validate the schema: top-level keys are int layer indices,
            # each value is a dict with at least 'k_scale' (and 'k_offset'
            # if the original calibration was asymmetric).
            for layer_idx, entry in self._calibration.items():
                if not isinstance(entry, dict) or "k_scale" not in entry:
                    raise ValueError(
                        f"calibration entry for layer {layer_idx} must have "
                        f"'k_scale'; got keys {list(entry.keys()) if isinstance(entry, dict) else 'non-dict'}"
                    )
            # Calibration is only supported with group_size <= 0 (no
            # group quant) — static scales are PER channel, not
            # per-(channel, group).
            if k_group_size > 0 or v_group_size > 0:
                raise ValueError(
                    f"calibration_path provided but k_group_size={k_group_size}, "
                    f"v_group_size={v_group_size}; static calibration requires "
                    f"both group sizes to be 0 (no group quantisation)."
                )
            if torch_device is not None:
                # Move calibration scales to the target device once at
                # init to avoid repeated host→device transfers in
                # update().
                for layer_idx, entry in self._calibration.items():
                    for key, val in list(entry.items()):
                        if hasattr(val, "to"):
                            entry[key] = val.to(torch_device)
        self._quantize_k = bool(quantize_k)
        self._quantize_v = bool(quantize_v)
        self._k_protect_fraction = float(k_protect_fraction)
        if not (0.0 <= self._k_protect_fraction < 1.0):
            raise ValueError(
                f"k_protect_fraction must be in [0, 1); got {k_protect_fraction}"
            )
        # Static protection: freeze the protected channel set per layer
        # on the first update (from the prefill K) and reuse it, rather
        # than recomputing per block. Tests whether a fixed channel set
        # holds the quality the dynamic per-block set reaches.
        self._k_protect_static = bool(k_protect_static)
        self._k_protect_masks: dict = {}
        self._cfg = dict(
            torch_device=str(torch_device),
            sink_size=int(sink_size),
            k_group_size=int(k_group_size),
            v_group_size=int(v_group_size),
            asymmetric=bool(asymmetric),
            bits=int(bits),
            k_bits=eff_k_bits,
            v_bits=eff_v_bits,
            calibration_path=calibration_path,
            quantize_k=self._quantize_k,
            quantize_v=self._quantize_v,
            k_protect_fraction=self._k_protect_fraction,
            k_protect_static=self._k_protect_static,
            scheme=f"k_int{eff_k_bits}_per_channel_v_int{eff_v_bits}_per_token" + (
                "_asymmetric" if asymmetric else "_symmetric"
            ) + ("_calibrated" if calibration_path is not None else "") + (
                ""
                if (self._quantize_k and self._quantize_v)
                else f"_ablation(K={'int' if self._quantize_k else 'fp16'},"
                     f"V={'int' if self._quantize_v else 'fp16'})"
            ) + (
                f"_protectK{self._k_protect_fraction * 100:g}pct"
                + ("_static" if self._k_protect_static else "_dynamic")
                if self._k_protect_fraction > 0.0 else ""
            ),
        )
        self._sink_size = int(sink_size)
        if self._sink_size < 0:
            raise ValueError(f"sink_size must be >= 0, got {sink_size}")
        self._updates = 0
        self._total_kv_elements = 0
        self._sink_elements_passed_through = 0

    def _resolve_static_scales(self, layer_idx: int) -> dict:
        """Look up the calibration entry for ``layer_idx``. Returns a
        dict of static_k_scale / static_k_offset / static_v_scale /
        static_v_offset (each may be None). Empty dict if no calibration
        is loaded."""
        if self._calibration is None:
            return {}
        # Calibration keys may be int or str (depends on how it was
        # saved); accept both.
        entry = self._calibration.get(layer_idx) or self._calibration.get(str(layer_idx))
        if entry is None:
            raise KeyError(
                f"calibration has no entry for layer {layer_idx}; "
                f"known layers: {sorted(self._calibration.keys())}"
            )
        return {
            "static_k_scale": entry.get("k_scale"),
            "static_k_offset": entry.get("k_offset"),
            "static_v_scale": entry.get("v_scale"),
            "static_v_offset": entry.get("v_offset"),
        }

    def update(
        self,
        key_states: "torch.Tensor",
        value_states: "torch.Tensor",
        layer_idx: int,
        *args,
        **kwargs,
    ) -> "Tuple[torch.Tensor, torch.Tensor]":
        static = self._resolve_static_scales(layer_idx)
        # Static outlier protection: freeze the protected channel set
        # per layer on the first update (from the prefill K), reuse it
        # thereafter. Dynamic (mask=None) lets the round-trip reselect
        # per block.
        k_protect_mask = None
        if (
            self._k_protect_fraction > 0.0
            and self._quantize_k
            and self._k_protect_static
        ):
            k_protect_mask = self._k_protect_masks.get(layer_idx)
            if k_protect_mask is None:
                k_protect_mask = _select_outlier_mask(
                    key_states, self._k_protect_fraction,
                )
                self._k_protect_masks[layer_idx] = k_protect_mask
        toggles = dict(
            quantize_k=self._quantize_k, quantize_v=self._quantize_v,
            k_protect_fraction=self._k_protect_fraction,
            k_protect_mask=k_protect_mask,
        )
        sink = self._sink_size
        if sink > 0 and key_states.shape[2] > sink:
            k_sink = key_states[:, :, :sink, :]
            v_sink = value_states[:, :, :sink, :]
            k_rest = key_states[:, :, sink:, :].contiguous()
            v_rest = value_states[:, :, sink:, :].contiguous()
            k_rest_lossy, v_rest_lossy = _compress_decompress_kv_int4(
                k_rest, v_rest, store=self._int4_store, **static, **toggles,
            )
            k_lossy = torch.cat([k_sink, k_rest_lossy], dim=2)
            v_lossy = torch.cat([v_sink, v_rest_lossy], dim=2)
            self._sink_elements_passed_through += int(
                k_sink.numel() + v_sink.numel()
            )
        else:
            k_lossy, v_lossy = _compress_decompress_kv_int4(
                key_states, value_states, store=self._int4_store,
                **static, **toggles,
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
