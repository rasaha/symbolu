"""
COHERA Python SDK

Software stack for PA-VPU / Universal Coherence Processor

Example:
    >>> import cohera
    >>> device = cohera.Device(0)
    >>> tensor = cohera.Tensor([32, 1024, 768], device=device)
"""

from .device import (
    Device,
    ModelDeviceContext,
    get_device_count,
    initialize_for_model,
    set_device,
    synchronize,
)
from .memory import malloc, free, memcpy_h2d, memcpy_d2h
from .tensor import Tensor, CognitiveState, SovereignState, KoshaMode, DType
from .stream import Stream
from .attention import PhaseAttention, phase_attention, phase_attention_fused, AttentionConfig
from .ontology import (
    OntologyProjector,
    project_to_cognitive_state,
    SovereignStateProjector,
    project_to_sovereign_state,
)
from .models import (
    HybridOntologicalAccelerator,
    HybridOntologicalConfig,
    MistralCGAccelerator,
    MistralCGConfig,
)
from .mistral_integration import bind_mistral_to_cohera, load_mistral_tokenizer
from .tcu import TCU, reset_tcu, get_frame_count
from .metrics import get_metrics, Metrics, VrittiState, Kosha

__version__ = "1.0.0"
__all__ = [
    # Device
    "Device",
    "get_device_count",
    "set_device",
    "synchronize",
    # Memory
    "malloc",
    "free",
    "memcpy_h2d",
    "memcpy_d2h",
    # Tensor
    "Tensor",
    "CognitiveState",
    "SovereignState",
    "KoshaMode",
    "DType",
    # Stream
    "Stream",
    # Attention
    "PhaseAttention",
    "phase_attention",
    "phase_attention_fused",
    "AttentionConfig",
    # Ontology
    "OntologyProjector",
    "project_to_cognitive_state",
    "SovereignStateProjector",
    "project_to_sovereign_state",
    # Model accelerators
    "MistralCGAccelerator",
    "MistralCGConfig",
    "HybridOntologicalAccelerator",
    "HybridOntologicalConfig",
    "ModelDeviceContext",
    "initialize_for_model",
    # Mistral integration
    "bind_mistral_to_cohera",
    "load_mistral_tokenizer",
    # TCU
    "TCU",
    "reset_tcu",
    "get_frame_count",
    # Metrics
    "get_metrics",
    "Metrics",
    "VrittiState",
    "Kosha",
]
