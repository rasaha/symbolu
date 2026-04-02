"""
CTM+ Integration for DeepSpeed.

Provides intelligent memory offloading decisions for DeepSpeed's
ZeRO-Offload and inference optimizations.

Usage:
    from ctm_plus_deepspeed import CTMOffloadManager, CTMZeROConfig

    # Replace DeepSpeed's default offload manager
    offload_manager = CTMOffloadManager(
        gpu_memory_gb=40,
        cpu_memory_gb=256,
    )

    # Use with ZeRO
    ds_config = get_deepspeed_config_with_ctm(offload_manager)
"""

from .offload_manager import CTMOffloadManager
from .zero_integration import CTMZeROOffload, get_deepspeed_config_with_ctm
from .inference import CTMInferenceManager
from .config import CTMDeepSpeedConfig
from .turboquant_numba import is_numba_available
from .turboquant_offload import (
    TurboQuantOffloadManager,
    TurboQuantTrainingConfig,
    TurboQuantCompressor,
    CompressedTensorBuffer,
    create_turboquant_offload_manager,
)

__version__ = "0.2.0"
__all__ = [
    "CTMOffloadManager",
    "CTMZeROOffload",
    "CTMInferenceManager",
    "CTMDeepSpeedConfig",
    "get_deepspeed_config_with_ctm",
    # TurboQuant integration
    "TurboQuantOffloadManager",
    "TurboQuantTrainingConfig",
    "TurboQuantCompressor",
    "CompressedTensorBuffer",
    "create_turboquant_offload_manager",
    "is_numba_available",
]
