"""
HuggingFace Mistral <-> COHERA binding helpers.

Thin adapter that inspects an HF Mistral config (or a dict), maps it to the
COHERA ``ModelDeviceContext`` + ``MistralCGConfig``, and constructs a ready
``MistralCGAccelerator``. Keeps the hard dependency on ``transformers`` /
``torch`` optional — the SDK itself stays framework-free.

Usage:
    >>> from transformers import AutoModelForCausalLM, AutoTokenizer
    >>> backbone = AutoModelForCausalLM.from_pretrained("mistralai/Mistral-7B-v0.3")
    >>> acc, tok = bind_mistral_to_cohera(backbone)
"""

from typing import Any, Dict, Optional, Tuple

from .device import Device, ModelDeviceContext, initialize_for_model
from .models import MistralCGAccelerator, MistralCGConfig
from .tensor import DType


def load_mistral_tokenizer(model_name: str = "mistralai/Mistral-7B-v0.3"):
    """
    Load a Mistral tokenizer via HuggingFace transformers.

    Imported lazily so the SDK has no hard dependency on ``transformers``.
    """
    try:
        from transformers import AutoTokenizer  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "load_mistral_tokenizer requires the `transformers` package. "
            "Install with: pip install transformers"
        ) from exc
    return AutoTokenizer.from_pretrained(model_name)


def _extract_hf_config(source: Any) -> Dict[str, Any]:
    """
    Accept an HF model, HF config, or plain dict and return a normalized
    config dict with the fields COHERA cares about.
    """
    if isinstance(source, dict):
        cfg = source
    elif hasattr(source, "config"):           # HF model -> PretrainedConfig
        cfg = vars(source.config)
    elif hasattr(source, "to_dict"):          # PretrainedConfig -> dict
        cfg = source.to_dict()
    else:                                     # assume it's already attr-ish
        cfg = {k: getattr(source, k) for k in dir(source) if not k.startswith("_")}

    # Mistral HF names -> normalized keys
    num_attention_heads = cfg.get("num_attention_heads", 32)
    num_kv_heads = cfg.get("num_key_value_heads", num_attention_heads)
    hidden_dim = cfg.get("hidden_size", 4096)
    head_dim = hidden_dim // num_attention_heads
    rope_dim = cfg.get("rope_dim", head_dim)  # Mistral rotates the full head
    rope_base = cfg.get("rope_theta", 10000.0)
    sliding_window = cfg.get("sliding_window", None)
    if sliding_window is None:
        sliding_window = -1

    return {
        "hidden_dim": int(hidden_dim),
        "num_heads": int(num_attention_heads),
        "num_kv_heads": int(num_kv_heads),
        "rope_dim": int(rope_dim),
        "rope_base": float(rope_base),
        "window_size": int(sliding_window),
        "torch_dtype": str(cfg.get("torch_dtype", "bfloat16")),
    }


def _normalize_dtype(torch_dtype_name: str) -> DType:
    name = torch_dtype_name.lower()
    if "bfloat16" in name or "bf16" in name:
        return DType.BF16
    if "float16" in name or "fp16" in name or "half" in name:
        return DType.FP16
    return DType.FP32


def bind_mistral_to_cohera(
    mistral_backbone: Any,
    device: Optional[Device] = None,
    tokenizer: Optional[Any] = None,
    model_type: str = "mistral_cg",
    overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[MistralCGAccelerator, Any]:
    """
    Build a ``MistralCGAccelerator`` that matches the given HF Mistral model.

    Args:
        mistral_backbone: HF model, HF config, or a plain dict with
            ``hidden_size`` / ``num_attention_heads`` / ``num_key_value_heads``
            / ``sliding_window`` / ``rope_theta`` / ``torch_dtype``.
        device: COHERA device (defaults to the current device).
        tokenizer: optional HF tokenizer returned alongside the accelerator.
        model_type: "mistral_cg" (full CG stack) or "mistral_hybrid"
            (phase layers only, no CG adapter).
        overrides: dict merged on top of the extracted HF config (useful
            to pin ``dtype``, ``coherence_threshold``, etc.).

    Returns:
        (accelerator, tokenizer)
    """
    extracted = _extract_hf_config(mistral_backbone)
    if overrides:
        extracted.update(overrides)

    dtype = _normalize_dtype(extracted.get("torch_dtype", "bfloat16"))

    context = initialize_for_model(
        model_type,
        {
            "hidden_dim": extracted["hidden_dim"],
            "num_heads": extracted["num_heads"],
            "num_kv_heads": extracted["num_kv_heads"],
            "rope_dim": extracted["rope_dim"],
            "rope_base": extracted["rope_base"],
            "window_size": extracted["window_size"],
            "dtype": dtype,
        },
        device=device,
    )

    mistral_cfg = MistralCGConfig(
        hidden_dim=extracted["hidden_dim"],
        num_heads=extracted["num_heads"],
        num_kv_heads=extracted["num_kv_heads"],
        rope_dim=extracted["rope_dim"],
        rope_base=extracted["rope_base"],
        window_size=extracted["window_size"],
        dtype=dtype,
    )

    accelerator = MistralCGAccelerator(config=mistral_cfg, context=context)
    return accelerator, tokenizer
