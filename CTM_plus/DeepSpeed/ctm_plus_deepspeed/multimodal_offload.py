"""
Multimodal-Aware Offload Manager for DeepSpeed CTM+.

Extends CTMOffloadManager with modality-aware scoring so that
cross-modal bridge components (cross-attention, projection layers)
are protected from GPU eviction while expendable components
(vision encoder patches, audio frontend) are offloaded first.

Usage:
    from ctm_plus_deepspeed.multimodal_offload import MultimodalOffloadManager

    manager = MultimodalOffloadManager(
        gpu_memory_bytes=40 * 1024**3,
        cpu_memory_bytes=256 * 1024**3,
    )
    manager.register_multimodal_tensor(
        tensor_id="cross_attn.0.weight",
        name="cross_attn.0.weight",
        size_bytes=128 * 1024 * 1024,
    )
"""

import random
import time
from typing import Dict, List, Optional, Set, Tuple, Any

from .config import CTMDeepSpeedConfig
from .offload_manager import (
    CTMOffloadManager,
    TensorState,
    TensorLocation,
)
from .multimodal_types import (
    ModalityType,
    ComponentRole,
    MultimodalTensorInfo,
    COMPONENT_IMPORTANCE,
    MODALITY_BASE_PRIORITY,
    classify_tensor_name,
)


class MultimodalOffloadManager(CTMOffloadManager):
    """
    CTM+ Offload Manager with multimodal model awareness.

    Adds a 6th scoring signal (modality importance) alongside the
    existing 5 (recency, frequency, size, compute, gradient).

    The modality signal protects cross-modal bridge layers from
    eviction while preferentially offloading redundant components
    like vision encoder patch embeddings.
    """

    def __init__(
        self,
        gpu_memory_bytes: int,
        cpu_memory_bytes: int,
        config: Optional[CTMDeepSpeedConfig] = None,
        weight_modality: float = 0.10,
    ):
        super().__init__(gpu_memory_bytes, cpu_memory_bytes, config)
        self.weight_modality = weight_modality

        # Multimodal metadata per tensor
        self.mm_info: Dict[str, MultimodalTensorInfo] = {}

        # Per-modality stats
        self.modality_stats: Dict[str, Dict[str, int]] = {
            m.value: {"registered": 0, "offloaded": 0, "promoted": 0, "gpu_hits": 0}
            for m in ModalityType
        }

    def register_multimodal_tensor(
        self,
        tensor_id: str,
        name: str,
        size_bytes: int,
        is_gradient: bool = False,
        is_optimizer_state: bool = False,
        initial_location: TensorLocation = TensorLocation.GPU,
        modality: Optional[ModalityType] = None,
        role: Optional[ComponentRole] = None,
        layer_idx: int = -1,
    ) -> None:
        """
        Register a tensor with multimodal metadata.

        If modality/role are not provided, auto-classify from the name.
        """
        # Base registration
        self.register_tensor(
            tensor_id=tensor_id,
            name=name,
            size_bytes=size_bytes,
            is_gradient=is_gradient,
            is_optimizer_state=is_optimizer_state,
            initial_location=initial_location,
        )

        # Multimodal classification
        if modality is not None and role is not None:
            info = MultimodalTensorInfo(modality, role, layer_idx)
        else:
            info = classify_tensor_name(name)
            if info is None:
                info = MultimodalTensorInfo(
                    ModalityType.LANGUAGE, ComponentRole.MLP_DOWN, layer_idx
                )
            elif layer_idx >= 0:
                info.layer_idx = layer_idx

        self.mm_info[tensor_id] = info
        self.modality_stats[info.modality.value]["registered"] += 1

    def on_access(
        self,
        tensor_id: str,
        in_compute_graph: bool = False,
    ) -> Tuple[bool, List[str]]:
        """Override to track per-modality GPU hits."""
        needs_fetch, prefetch_list = super().on_access(tensor_id, in_compute_graph)

        if tensor_id in self.mm_info and tensor_id in self.gpu_tensors:
            mod = self.mm_info[tensor_id].modality.value
            self.modality_stats[mod]["gpu_hits"] += 1

        return needs_fetch, prefetch_list

    def _compute_victim_score(
        self,
        tensor_id: str,
        min_time: float,
        time_range: float,
        max_size: int,
        adaptive_p: float,
    ) -> float:
        """
        Extended scoring with modality importance signal.

        The modality signal adds protection for cross-modal components
        (score boost) and reduces protection for expendable components
        (vision patches, audio frontend).
        """
        # Base score from parent (5 signals + adaptive p)
        base_score = super()._compute_victim_score(
            tensor_id, min_time, time_range, max_size, adaptive_p
        )

        # Signal 6: Modality importance
        if tensor_id in self.mm_info:
            info = self.mm_info[tensor_id]
            # Component importance [0, 1] — higher = protect more
            modality_score = info.importance
            base_score += self.weight_modality * modality_score

        return base_score

    def _offload_tensor(self, tensor_id: str) -> bool:
        """Override to track per-modality offloads."""
        if tensor_id in self.mm_info:
            mod = self.mm_info[tensor_id].modality.value
        else:
            mod = ModalityType.LANGUAGE.value

        success = super()._offload_tensor(tensor_id)
        if success:
            self.modality_stats[mod]["offloaded"] += 1
        return success

    def _promote_tensor(self, tensor_id: str) -> bool:
        """Override to track per-modality promotions."""
        if tensor_id in self.mm_info:
            mod = self.mm_info[tensor_id].modality.value
        else:
            mod = ModalityType.LANGUAGE.value

        success = super()._promote_tensor(tensor_id)
        if success:
            self.modality_stats[mod]["promoted"] += 1
        return success

    def get_modality_stats(self) -> Dict[str, Any]:
        """Get per-modality statistics."""
        result = {}
        for mod, stats in self.modality_stats.items():
            reg = stats["registered"]
            # Count currently on GPU
            gpu_count = sum(
                1 for tid in self.gpu_tensors
                if tid in self.mm_info
                and self.mm_info[tid].modality.value == mod
            )
            cpu_count = sum(
                1 for tid in self.cpu_tensors
                if tid in self.mm_info
                and self.mm_info[tid].modality.value == mod
            )
            result[mod] = {
                **stats,
                "gpu_count": gpu_count,
                "cpu_count": cpu_count,
                "gpu_retention": gpu_count / max(1, reg),
            }
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Extended stats with modality breakdown."""
        base_stats = super().get_stats()
        base_stats["modality_breakdown"] = self.get_modality_stats()
        return base_stats
