"""
Multimodal model component types and importance maps for DeepSpeed CTM+.

When training vision-language models (VLMs), audio-language models, or
any multimodal architecture, different model components have different
offloading priorities:

  - Cross-attention layers bridge modalities and are critical
  - Vision encoder patch projections are redundant and can be offloaded
  - Language model backbone follows standard transformer priority
  - Audio encoders have sparse onset-important patterns

This module defines the component taxonomy and importance scoring.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Set


class ModalityType(Enum):
    """Which modality a model component belongs to."""
    LANGUAGE = "language"
    VISION = "vision"
    AUDIO = "audio"
    VIDEO = "video"
    CROSS_MODAL = "cross_modal"
    SHARED = "shared"        # Shared embeddings, output heads


class ComponentRole(Enum):
    """Functional role of a tensor within a modality."""
    # Language
    ATTENTION_QKV = "attention_qkv"
    ATTENTION_OUTPUT = "attention_output"
    MLP_UP = "mlp_up"
    MLP_DOWN = "mlp_down"
    NORM = "norm"
    EMBEDDING = "embedding"
    LM_HEAD = "lm_head"
    # Vision
    PATCH_EMBED = "patch_embed"
    VISION_ENCODER = "vision_encoder"
    VISION_POOLER = "vision_pooler"
    VISION_PROJECTION = "vision_projection"
    # Audio
    AUDIO_FRONTEND = "audio_frontend"
    AUDIO_ENCODER = "audio_encoder"
    AUDIO_PROJECTION = "audio_projection"
    # Video
    TEMPORAL_EMBED = "temporal_embed"
    VIDEO_ENCODER = "video_encoder"
    VIDEO_PROJECTION = "video_projection"
    # Cross-modal
    CROSS_ATTENTION = "cross_attention"
    CROSS_PROJECTION = "cross_projection"
    GATING = "gating"


# ---------------------------------------------------------------------------
# Component Importance Map
# ---------------------------------------------------------------------------
# Higher = more important = resist offloading to CPU
# These weights add a modality signal to the existing CTM+ scoring

COMPONENT_IMPORTANCE: Dict[ComponentRole, float] = {
    # Cross-modal (highest priority - bridges modalities)
    ComponentRole.CROSS_ATTENTION:    1.00,
    ComponentRole.CROSS_PROJECTION:   0.90,
    ComponentRole.GATING:             0.85,
    # Language backbone
    ComponentRole.EMBEDDING:          0.95,
    ComponentRole.LM_HEAD:            0.90,
    ComponentRole.ATTENTION_QKV:      0.75,
    ComponentRole.ATTENTION_OUTPUT:   0.70,
    ComponentRole.MLP_UP:             0.55,
    ComponentRole.MLP_DOWN:           0.55,
    ComponentRole.NORM:               0.80,
    # Vision encoder
    ComponentRole.VISION_PROJECTION:  0.85,
    ComponentRole.VISION_POOLER:      0.80,
    ComponentRole.VISION_ENCODER:     0.50,
    ComponentRole.PATCH_EMBED:        0.40,
    # Audio encoder
    ComponentRole.AUDIO_PROJECTION:   0.80,
    ComponentRole.AUDIO_ENCODER:      0.55,
    ComponentRole.AUDIO_FRONTEND:     0.45,
    # Video encoder
    ComponentRole.VIDEO_PROJECTION:   0.80,
    ComponentRole.VIDEO_ENCODER:      0.50,
    ComponentRole.TEMPORAL_EMBED:     0.60,
}

MODALITY_BASE_PRIORITY: Dict[ModalityType, float] = {
    ModalityType.CROSS_MODAL: 1.0,
    ModalityType.LANGUAGE:    0.8,
    ModalityType.SHARED:      0.9,
    ModalityType.VISION:      0.5,
    ModalityType.AUDIO:       0.55,
    ModalityType.VIDEO:       0.5,
}


@dataclass
class MultimodalTensorInfo:
    """Extended metadata for a tensor in a multimodal model."""
    modality: ModalityType
    role: ComponentRole
    layer_idx: int = -1

    @property
    def importance(self) -> float:
        return COMPONENT_IMPORTANCE.get(self.role, 0.5)

    @property
    def modality_priority(self) -> float:
        return MODALITY_BASE_PRIORITY.get(self.modality, 0.5)


def classify_tensor_name(name: str) -> Optional[MultimodalTensorInfo]:
    """
    Auto-classify a tensor by its name into modality + role.

    Supports common naming conventions in VLMs like LLaVA, Flamingo,
    Qwen-VL, Whisper-LLM, etc.

    Returns None if the tensor can't be classified.
    """
    n = name.lower()

    # Cross-modal components
    if "cross_attn" in n or "cross_attention" in n or "xattn" in n:
        return MultimodalTensorInfo(ModalityType.CROSS_MODAL, ComponentRole.CROSS_ATTENTION)
    if "gate" in n and ("cross" in n or "modal" in n):
        return MultimodalTensorInfo(ModalityType.CROSS_MODAL, ComponentRole.GATING)
    if ("mm_projector" in n or "multi_modal_projector" in n or
            "cross_proj" in n or "connector" in n):
        return MultimodalTensorInfo(ModalityType.CROSS_MODAL, ComponentRole.CROSS_PROJECTION)

    # Vision components
    if "vision" in n or "visual" in n or "vit" in n or "image_encoder" in n:
        if "patch_embed" in n or "patch_projection" in n:
            return MultimodalTensorInfo(ModalityType.VISION, ComponentRole.PATCH_EMBED)
        if "pooler" in n or "pool" in n:
            return MultimodalTensorInfo(ModalityType.VISION, ComponentRole.VISION_POOLER)
        if "proj" in n or "projection" in n or "head" in n:
            return MultimodalTensorInfo(ModalityType.VISION, ComponentRole.VISION_PROJECTION)
        return MultimodalTensorInfo(ModalityType.VISION, ComponentRole.VISION_ENCODER)

    # Audio components
    if "audio" in n or "whisper" in n or "speech" in n:
        if "frontend" in n or "feature" in n or "mel" in n:
            return MultimodalTensorInfo(ModalityType.AUDIO, ComponentRole.AUDIO_FRONTEND)
        if "proj" in n or "projection" in n:
            return MultimodalTensorInfo(ModalityType.AUDIO, ComponentRole.AUDIO_PROJECTION)
        return MultimodalTensorInfo(ModalityType.AUDIO, ComponentRole.AUDIO_ENCODER)

    # Video components
    if "video" in n or "temporal" in n:
        if "temporal_embed" in n:
            return MultimodalTensorInfo(ModalityType.VIDEO, ComponentRole.TEMPORAL_EMBED)
        if "proj" in n or "projection" in n:
            return MultimodalTensorInfo(ModalityType.VIDEO, ComponentRole.VIDEO_PROJECTION)
        return MultimodalTensorInfo(ModalityType.VIDEO, ComponentRole.VIDEO_ENCODER)

    # Language components
    if "embed" in n and "patch" not in n:
        return MultimodalTensorInfo(ModalityType.LANGUAGE, ComponentRole.EMBEDDING)
    if "lm_head" in n or "output_proj" in n:
        return MultimodalTensorInfo(ModalityType.SHARED, ComponentRole.LM_HEAD)
    if "norm" in n or "layernorm" in n or "rmsnorm" in n:
        return MultimodalTensorInfo(ModalityType.LANGUAGE, ComponentRole.NORM)
    if "q_proj" in n or "k_proj" in n or "v_proj" in n or "qkv" in n:
        return MultimodalTensorInfo(ModalityType.LANGUAGE, ComponentRole.ATTENTION_QKV)
    if "o_proj" in n or "out_proj" in n:
        return MultimodalTensorInfo(ModalityType.LANGUAGE, ComponentRole.ATTENTION_OUTPUT)
    if "up_proj" in n or "gate_proj" in n or "fc1" in n or "mlp.up" in n:
        return MultimodalTensorInfo(ModalityType.LANGUAGE, ComponentRole.MLP_UP)
    if "down_proj" in n or "fc2" in n or "mlp.down" in n:
        return MultimodalTensorInfo(ModalityType.LANGUAGE, ComponentRole.MLP_DOWN)

    return None
