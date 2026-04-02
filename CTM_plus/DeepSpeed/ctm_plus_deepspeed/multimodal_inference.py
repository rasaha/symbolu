"""
Multimodal-Aware Inference Manager for DeepSpeed CTM+.

Extends CTMInferenceManager to understand VLM architecture:
  - Vision encoder layers are prefetched before image tokens
  - Cross-attention layers are pinned during cross-modal processing
  - Audio encoder layers are prefetched before speech segments
  - Language model layers follow standard layer-by-layer prefetching
"""

from typing import Dict, List, Optional, Any, Tuple
import threading

from .inference import CTMInferenceManager, LayerType
from .multimodal_offload import MultimodalOffloadManager
from .multimodal_types import (
    ModalityType,
    ComponentRole,
    MultimodalTensorInfo,
)
from .offload_manager import TensorLocation
from .config import CTMDeepSpeedConfig


class MultimodalLayerType:
    """Extended layer types for VLM architectures."""
    # Vision encoder
    VISION_PATCH_EMBED = "vision_patch_embed"
    VISION_ENCODER = "vision_encoder"
    VISION_POOLER = "vision_pooler"
    # Audio encoder
    AUDIO_FRONTEND = "audio_frontend"
    AUDIO_ENCODER = "audio_encoder"
    # Video encoder
    VIDEO_ENCODER = "video_encoder"
    # Cross-modal
    CROSS_ATTENTION = "cross_attention"
    # Language (same as base)
    LANGUAGE_ATTENTION = "language_attention"
    LANGUAGE_MLP = "language_mlp"


class MultimodalInferenceManager:
    """
    VLM-aware inference manager.

    Manages a multimodal model with separate encoder stages:
      1. Vision encoder (processes image patches)
      2. Audio encoder (processes mel spectrograms)
      3. Language model with interleaved cross-attention

    Key differences from base CTMInferenceManager:
      - Separate prefetch schedules per modality encoder
      - Cross-attention layers pinned during cross-modal decoding
      - Modality-aware offload scoring via MultimodalOffloadManager
    """

    def __init__(
        self,
        gpu_memory_bytes: int,
        cpu_memory_bytes: int,
        config: Optional[CTMDeepSpeedConfig] = None,
        weight_modality: float = 0.10,
    ):
        self.config = config or CTMDeepSpeedConfig.for_inference()
        self.offload_manager = MultimodalOffloadManager(
            gpu_memory_bytes=gpu_memory_bytes,
            cpu_memory_bytes=cpu_memory_bytes,
            config=self.config,
            weight_modality=weight_modality,
        )

        # Modality-specific layer registries
        self.vision_layers: Dict[int, Dict[str, str]] = {}
        self.audio_layers: Dict[int, Dict[str, str]] = {}
        self.video_layers: Dict[int, Dict[str, str]] = {}
        self.language_layers: Dict[int, Dict[str, str]] = {}
        self.cross_attention_layers: Dict[int, Dict[str, str]] = {}

        self.is_generating = False
        self.current_phase = "idle"  # idle, vision, audio, video, language
        self._lock = threading.RLock()

    def register_vision_layer(
        self,
        layer_idx: int,
        weights: Dict[str, Tuple[str, int]],
        initial_on_gpu: bool = True,
    ) -> None:
        """Register a vision encoder layer."""
        with self._lock:
            self.vision_layers[layer_idx] = {}
            role = ComponentRole.VISION_ENCODER
            if layer_idx == 0:
                role = ComponentRole.PATCH_EMBED

            for component, (tensor_id, size_bytes) in weights.items():
                self.offload_manager.register_multimodal_tensor(
                    tensor_id=tensor_id,
                    name=f"vision.{layer_idx}.{component}",
                    size_bytes=size_bytes,
                    modality=ModalityType.VISION,
                    role=role,
                    layer_idx=layer_idx,
                    initial_location=(
                        TensorLocation.GPU if initial_on_gpu
                        else TensorLocation.CPU
                    ),
                )
                self.vision_layers[layer_idx][component] = tensor_id

    def register_audio_layer(
        self,
        layer_idx: int,
        weights: Dict[str, Tuple[str, int]],
        initial_on_gpu: bool = True,
    ) -> None:
        """Register an audio encoder layer."""
        with self._lock:
            self.audio_layers[layer_idx] = {}
            role = (ComponentRole.AUDIO_FRONTEND if layer_idx == 0
                    else ComponentRole.AUDIO_ENCODER)

            for component, (tensor_id, size_bytes) in weights.items():
                self.offload_manager.register_multimodal_tensor(
                    tensor_id=tensor_id,
                    name=f"audio.{layer_idx}.{component}",
                    size_bytes=size_bytes,
                    modality=ModalityType.AUDIO,
                    role=role,
                    layer_idx=layer_idx,
                    initial_location=(
                        TensorLocation.GPU if initial_on_gpu
                        else TensorLocation.CPU
                    ),
                )
                self.audio_layers[layer_idx][component] = tensor_id

    def register_language_layer(
        self,
        layer_idx: int,
        weights: Dict[str, Tuple[str, int]],
        has_cross_attention: bool = False,
        initial_on_gpu: bool = True,
    ) -> None:
        """Register a language model layer (optionally with cross-attention)."""
        with self._lock:
            self.language_layers[layer_idx] = {}

            for component, (tensor_id, size_bytes) in weights.items():
                # Classify component role
                if "cross" in component.lower():
                    role = ComponentRole.CROSS_ATTENTION
                    modality = ModalityType.CROSS_MODAL
                elif "q_proj" in component or "k_proj" in component or "v_proj" in component:
                    role = ComponentRole.ATTENTION_QKV
                    modality = ModalityType.LANGUAGE
                elif "o_proj" in component:
                    role = ComponentRole.ATTENTION_OUTPUT
                    modality = ModalityType.LANGUAGE
                elif "up" in component or "gate" in component:
                    role = ComponentRole.MLP_UP
                    modality = ModalityType.LANGUAGE
                elif "down" in component:
                    role = ComponentRole.MLP_DOWN
                    modality = ModalityType.LANGUAGE
                elif "norm" in component:
                    role = ComponentRole.NORM
                    modality = ModalityType.LANGUAGE
                else:
                    role = ComponentRole.MLP_DOWN
                    modality = ModalityType.LANGUAGE

                self.offload_manager.register_multimodal_tensor(
                    tensor_id=tensor_id,
                    name=f"language.{layer_idx}.{component}",
                    size_bytes=size_bytes,
                    modality=modality,
                    role=role,
                    layer_idx=layer_idx,
                    initial_location=(
                        TensorLocation.GPU if initial_on_gpu
                        else TensorLocation.CPU
                    ),
                )
                self.language_layers[layer_idx][component] = tensor_id

                # Track cross-attention separately
                if role == ComponentRole.CROSS_ATTENTION:
                    if layer_idx not in self.cross_attention_layers:
                        self.cross_attention_layers[layer_idx] = {}
                    self.cross_attention_layers[layer_idx][component] = tensor_id

    def begin_generation(self) -> None:
        """Start generation."""
        with self._lock:
            self.is_generating = True
            self.current_phase = "idle"

    def process_vision(self) -> List[str]:
        """
        Process vision encoder layers sequentially.
        Prefetches ahead within vision encoder.
        Returns list of tensors that needed fetching.
        """
        with self._lock:
            self.current_phase = "vision"
            fetched = []

            for layer_idx in sorted(self.vision_layers.keys()):
                # Access current layer
                for tensor_id in self.vision_layers[layer_idx].values():
                    needs_fetch, _ = self.offload_manager.on_access(
                        tensor_id, in_compute_graph=True
                    )
                    if needs_fetch:
                        fetched.append(tensor_id)

                # Release previous layer
                if layer_idx > 0:
                    prev = layer_idx - 1
                    if prev in self.vision_layers:
                        ids = list(self.vision_layers[prev].values())
                        self.offload_manager.set_compute_graph(ids, False)

            # Release last vision layer
            if self.vision_layers:
                last = max(self.vision_layers.keys())
                ids = list(self.vision_layers[last].values())
                self.offload_manager.set_compute_graph(ids, False)

            return fetched

    def process_audio(self) -> List[str]:
        """Process audio encoder layers."""
        with self._lock:
            self.current_phase = "audio"
            fetched = []

            for layer_idx in sorted(self.audio_layers.keys()):
                for tensor_id in self.audio_layers[layer_idx].values():
                    needs_fetch, _ = self.offload_manager.on_access(
                        tensor_id, in_compute_graph=True
                    )
                    if needs_fetch:
                        fetched.append(tensor_id)

                if layer_idx > 0:
                    prev = layer_idx - 1
                    if prev in self.audio_layers:
                        ids = list(self.audio_layers[prev].values())
                        self.offload_manager.set_compute_graph(ids, False)

            if self.audio_layers:
                last = max(self.audio_layers.keys())
                ids = list(self.audio_layers[last].values())
                self.offload_manager.set_compute_graph(ids, False)

            return fetched

    def process_language_layer(self, layer_idx: int) -> List[str]:
        """
        Process a single language model layer.

        If this layer has cross-attention, those tensors are pinned
        during processing to prevent eviction.
        """
        with self._lock:
            self.current_phase = "language"
            fetched = []

            # Pin cross-attention for this layer
            if layer_idx in self.cross_attention_layers:
                for tid in self.cross_attention_layers[layer_idx].values():
                    self.offload_manager.pin_tensor(tid)

            # Access all layer components
            if layer_idx in self.language_layers:
                for tensor_id in self.language_layers[layer_idx].values():
                    needs_fetch, _ = self.offload_manager.on_access(
                        tensor_id, in_compute_graph=True
                    )
                    if needs_fetch:
                        fetched.append(tensor_id)

            # Release previous layer
            if layer_idx > 0:
                prev = layer_idx - 1
                if prev in self.language_layers:
                    ids = list(self.language_layers[prev].values())
                    self.offload_manager.set_compute_graph(ids, False)
                # Unpin previous cross-attention
                if prev in self.cross_attention_layers:
                    for tid in self.cross_attention_layers[prev].values():
                        self.offload_manager.unpin_tensor(tid)

            return fetched

    def end_generation(self) -> None:
        """End generation, release all tensors."""
        with self._lock:
            self.is_generating = False
            self.current_phase = "idle"

            # Release all from compute graph
            for layer_map in [self.vision_layers, self.audio_layers,
                              self.language_layers]:
                for layer_idx, components in layer_map.items():
                    ids = list(components.values())
                    self.offload_manager.set_compute_graph(ids, False)

            # Unpin all cross-attention
            for layer_idx, components in self.cross_attention_layers.items():
                for tid in components.values():
                    self.offload_manager.unpin_tensor(tid)

    def get_stats(self) -> Dict[str, Any]:
        """Get combined stats."""
        stats = self.offload_manager.get_stats()
        stats["current_phase"] = self.current_phase
        stats["is_generating"] = self.is_generating
        stats["num_vision_layers"] = len(self.vision_layers)
        stats["num_audio_layers"] = len(self.audio_layers)
        stats["num_language_layers"] = len(self.language_layers)
        stats["num_cross_attention_layers"] = len(self.cross_attention_layers)
        return stats
