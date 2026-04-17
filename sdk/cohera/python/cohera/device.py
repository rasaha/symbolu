"""
COHERA Device Management
"""

from typing import Any, Dict, Optional, Sequence
from dataclasses import dataclass, field


@dataclass
class DeviceCaps:
    """Device capabilities."""
    device_id: int
    num_pau: int
    num_tcu: int
    hbm_size_mb: int
    max_seq_len: int
    ontology_layers: int = 12
    phase_precision_ps: int = 100
    firmware_version: int = 0
    device_name: str = "PA-VPU"


class Device:
    """
    COHERA device handle.

    Example:
        >>> device = Device(0)
        >>> print(device.caps)
        >>> device.synchronize()
    """

    def __init__(self, device_id: int = 0):
        """
        Initialize a COHERA device.

        Args:
            device_id: Device index (0-based)
        """
        self._device_id = device_id
        self._caps: Optional[DeviceCaps] = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the device (stub)."""
        # TODO: Call libcohera.so via ctypes/cffi
        self._caps = DeviceCaps(
            device_id=self._device_id,
            num_pau=16,
            num_tcu=4,
            hbm_size_mb=81920,  # 80GB
            max_seq_len=32768,
        )

    @property
    def device_id(self) -> int:
        """Get device ID."""
        return self._device_id

    @property
    def caps(self) -> DeviceCaps:
        """Get device capabilities."""
        if self._caps is None:
            raise RuntimeError("Device not initialized")
        return self._caps

    def synchronize(self) -> None:
        """Wait for all operations on this device to complete."""
        # TODO: Call cohera_device_synchronize()
        pass

    def __repr__(self) -> str:
        return f"Device({self._device_id}, name='{self.caps.device_name}')"


def get_device_count() -> int:
    """
    Get the number of available COHERA devices.

    Returns:
        Number of devices
    """
    # TODO: Call cohera_get_device_count()
    return 1


def set_device(device_id: int) -> None:
    """
    Set the current device for subsequent operations.

    Args:
        device_id: Device index
    """
    # TODO: Call cohera_set_device()
    pass


def synchronize() -> None:
    """Synchronize the current device."""
    # TODO: Call cohera_device_synchronize()
    pass


# ---------------------------------------------------------------------------
# Model-aware device initialization
# ---------------------------------------------------------------------------

_SUPPORTED_MODEL_TYPES = ("mistral_cg", "mistral_hybrid", "hybrid", "fscs_mistral")


@dataclass
class ModelDeviceContext:
    """
    Persistent device-side state for a single model binding.

    Holds handles to precomputed RoPE tables, GQA ratios, per-layer harmonic
    frequencies, and the default attention dtype. Passed into
    ``MistralCGAccelerator`` / ``HybridOntologicalAccelerator`` so the
    accelerator doesn't have to re-upload anything per call.
    """
    model_type: str
    hidden_dim: int
    num_heads: int
    num_kv_heads: int
    head_dim: int
    rope_dim: int = 0
    rope_base: float = 10000.0
    rope_freqs_handle: Optional[Any] = None   # opaque device tensor handle
    layer_harmonics: Sequence[float] = field(default_factory=tuple)
    window_size: int = -1
    dtype: Optional[Any] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def _compute_rope_inv_freqs(rope_dim: int, base: float = 10000.0):
    """Return the standard HF RoPE inverse-frequency table (rope_dim/2 floats)."""
    if rope_dim <= 0 or rope_dim % 2 != 0:
        return ()
    return tuple(1.0 / (base ** (2.0 * i / rope_dim)) for i in range(rope_dim // 2))


def _default_layer_harmonics(num_layers: int = 12) -> Sequence[float]:
    """
    Hybrid ontology per-layer frequency ratios: log-spaced from 1e5 Hz at layer 0
    down to 1 Hz at layer 11 (matches UnifyingBlock / harmonic table usage).
    """
    if num_layers <= 1:
        return (1.0,)
    import math
    start, end = math.log(1e5), math.log(1.0)
    step = (end - start) / (num_layers - 1)
    return tuple(math.exp(start + i * step) for i in range(num_layers))


def initialize_for_model(
    model_type: str,
    model_config: Optional[Dict[str, Any]] = None,
    device: Optional[Device] = None,
) -> ModelDeviceContext:
    """
    Prepare the current COHERA device for a specific model.

    Uploads (stub: precomputes) RoPE inverse-frequency tables, resolves the
    GQA query:KV ratio, and caches per-layer harmonic frequencies for the
    hybrid ontological accelerator. The returned context is passed to
    ``MistralCGAccelerator`` / ``HybridOntologicalAccelerator`` so they
    don't re-upload anything per forward pass.

    Args:
        model_type:   one of "mistral_cg", "mistral_hybrid", "hybrid",
                      "fscs_mistral"
        model_config: dict with ``hidden_dim``, ``num_heads``, and (optional)
                      ``num_kv_heads``, ``rope_dim``, ``rope_base``,
                      ``window_size``, ``num_ontology_layers``.
        device:       optional Device (defaults to current).

    Example:
        >>> ctx = initialize_for_model("mistral_cg", {
        ...     "hidden_dim": 4096, "num_heads": 32, "num_kv_heads": 8,
        ...     "rope_dim": 128, "window_size": 4096,
        ... })
    """
    if model_type not in _SUPPORTED_MODEL_TYPES:
        raise ValueError(
            f"Unsupported model_type {model_type!r}; "
            f"expected one of {_SUPPORTED_MODEL_TYPES}"
        )
    cfg = dict(model_config or {})
    hidden_dim = int(cfg.get("hidden_dim", 4096))
    num_heads = int(cfg.get("num_heads", 32))
    num_kv_heads = int(cfg.get("num_kv_heads", num_heads))
    if num_kv_heads <= 0:
        num_kv_heads = num_heads
    if num_heads % num_kv_heads != 0:
        raise ValueError(
            f"num_heads ({num_heads}) must be divisible by num_kv_heads ({num_kv_heads})"
        )
    if hidden_dim % num_heads != 0:
        raise ValueError(
            f"hidden_dim ({hidden_dim}) must be divisible by num_heads ({num_heads})"
        )
    head_dim = hidden_dim // num_heads

    rope_dim = int(cfg.get("rope_dim", 0))
    rope_base = float(cfg.get("rope_base", 10000.0))
    rope_freqs = _compute_rope_inv_freqs(rope_dim, rope_base) if rope_dim > 0 else ()

    num_ontology_layers = int(cfg.get("num_ontology_layers", 12))
    layer_harmonics = (
        _default_layer_harmonics(num_ontology_layers)
        if model_type in ("hybrid", "mistral_hybrid")
        else ()
    )

    return ModelDeviceContext(
        model_type=model_type,
        hidden_dim=hidden_dim,
        num_heads=num_heads,
        num_kv_heads=num_kv_heads,
        head_dim=head_dim,
        rope_dim=rope_dim,
        rope_base=rope_base,
        # In the real runtime this would be a cohera_tensor_t* allocated via
        # cohera_malloc + cohera_memcpy_h2d(rope_freqs_table); the tuple stays
        # addressable from Python for the stub path.
        rope_freqs_handle=rope_freqs if rope_freqs else None,
        layer_harmonics=layer_harmonics,
        window_size=int(cfg.get("window_size", -1)),
        dtype=cfg.get("dtype"),
        extra={k: v for k, v in cfg.items() if k not in {
            "hidden_dim", "num_heads", "num_kv_heads", "rope_dim", "rope_base",
            "num_ontology_layers", "window_size", "dtype",
        }},
    )
