"""
CTM+ Inference Manager for DeepSpeed Inference.

Provides intelligent memory management for DeepSpeed inference,
including KV cache and model weight offloading.
"""

from typing import Dict, List, Optional, Any, Tuple
import threading
from enum import Enum

from .offload_manager import CTMOffloadManager, TensorLocation
from .config import CTMDeepSpeedConfig


class LayerType(Enum):
    ATTENTION = "attention"
    MLP = "mlp"
    NORM = "norm"
    EMBEDDING = "embedding"
    OUTPUT = "output"


class CTMInferenceManager:
    """
    CTM+ enhanced inference manager for DeepSpeed.

    Manages:
    - Model weight offloading for large models
    - KV cache management
    - Layer prefetching during generation
    """

    def __init__(
        self,
        gpu_memory_bytes: int,
        cpu_memory_bytes: int,
        config: Optional[CTMDeepSpeedConfig] = None,
        num_layers: int = 32,
    ):
        """
        Initialize inference manager.

        Args:
            gpu_memory_bytes: Available GPU memory.
            cpu_memory_bytes: Available CPU memory.
            config: CTM+ configuration.
            num_layers: Number of transformer layers.
        """
        self.config = config or CTMDeepSpeedConfig.for_inference()
        self.num_layers = num_layers

        self.offload_manager = CTMOffloadManager(
            gpu_memory_bytes=gpu_memory_bytes,
            cpu_memory_bytes=cpu_memory_bytes,
            config=self.config,
        )

        # Layer information
        self.layers: Dict[int, Dict[str, str]] = {}  # layer_idx -> {component: tensor_id}
        self.kv_cache: Dict[int, Dict[str, str]] = {}  # layer_idx -> {k: id, v: id}

        # Generation state
        self.current_layer = 0
        self.is_generating = False
        self._lock = threading.RLock()

    def register_layer(
        self,
        layer_idx: int,
        weights: Dict[str, Tuple[str, int]],  # component -> (tensor_id, size_bytes)
        initial_on_gpu: bool = True,
    ) -> None:
        """
        Register a transformer layer.

        Args:
            layer_idx: Layer index (0-indexed).
            weights: Dict of component name to (tensor_id, size_bytes).
            initial_on_gpu: Whether to place on GPU initially.
        """
        with self._lock:
            self.layers[layer_idx] = {}

            for component, (tensor_id, size_bytes) in weights.items():
                self.offload_manager.register_tensor(
                    tensor_id=tensor_id,
                    name=f"layer.{layer_idx}.{component}",
                    size_bytes=size_bytes,
                    initial_location=(
                        TensorLocation.GPU if initial_on_gpu
                        else TensorLocation.CPU
                    ),
                )
                self.layers[layer_idx][component] = tensor_id

    def register_kv_cache(
        self,
        layer_idx: int,
        k_tensor_id: str,
        v_tensor_id: str,
        cache_size_bytes: int,
    ) -> None:
        """Register KV cache for a layer."""
        with self._lock:
            self.offload_manager.register_tensor(
                tensor_id=k_tensor_id,
                name=f"layer.{layer_idx}.k_cache",
                size_bytes=cache_size_bytes,
                initial_location=TensorLocation.GPU,
            )
            self.offload_manager.register_tensor(
                tensor_id=v_tensor_id,
                name=f"layer.{layer_idx}.v_cache",
                size_bytes=cache_size_bytes,
                initial_location=TensorLocation.GPU,
            )

            self.kv_cache[layer_idx] = {
                "k": k_tensor_id,
                "v": v_tensor_id,
            }

    def begin_generation(self) -> None:
        """Called at start of generation."""
        with self._lock:
            self.is_generating = True
            self.current_layer = 0

            # Prefetch first layers
            self._prefetch_layers(0, self.config.prefetch_ahead)

    def on_layer_forward(self, layer_idx: int) -> List[str]:
        """
        Called when forward pass reaches a layer.

        Returns list of tensors that need to be fetched.
        """
        with self._lock:
            self.current_layer = layer_idx
            needs_fetch = []

            # Access layer weights
            if layer_idx in self.layers:
                for component, tensor_id in self.layers[layer_idx].items():
                    fetched, _ = self.offload_manager.on_access(
                        tensor_id, in_compute_graph=True
                    )
                    if fetched:
                        needs_fetch.append(tensor_id)

            # Access KV cache
            if layer_idx in self.kv_cache:
                for cache_type, tensor_id in self.kv_cache[layer_idx].items():
                    fetched, _ = self.offload_manager.on_access(
                        tensor_id, in_compute_graph=True
                    )
                    if fetched:
                        needs_fetch.append(tensor_id)

            # Prefetch next layers
            next_layer = layer_idx + 1
            if next_layer < self.num_layers:
                self._prefetch_layers(next_layer, self.config.prefetch_ahead)

            # Release previous layer from compute graph
            if layer_idx > 0:
                self._release_layer(layer_idx - 1)

            return needs_fetch

    def _prefetch_layers(self, start_layer: int, count: int) -> None:
        """Prefetch upcoming layers."""
        for i in range(start_layer, min(start_layer + count, self.num_layers)):
            if i in self.layers:
                for tensor_id in self.layers[i].values():
                    self.offload_manager.on_access(tensor_id, in_compute_graph=False)

    def _release_layer(self, layer_idx: int) -> None:
        """Release layer from compute graph."""
        if layer_idx in self.layers:
            tensor_ids = list(self.layers[layer_idx].values())
            self.offload_manager.set_compute_graph(tensor_ids, False)

    def end_generation(self) -> None:
        """Called at end of generation."""
        with self._lock:
            self.is_generating = False
            # Release all layers
            for layer_idx in self.layers:
                self._release_layer(layer_idx)

    def evict_kv_cache(self, layer_idx: int) -> bool:
        """
        Manually evict KV cache for a layer to CPU.

        Returns True if evicted successfully.
        """
        with self._lock:
            if layer_idx not in self.kv_cache:
                return False

            success = True
            for tensor_id in self.kv_cache[layer_idx].values():
                if not self.offload_manager._offload_tensor(tensor_id):
                    success = False

            return success

    def pin_layer(self, layer_idx: int) -> None:
        """Pin a layer to prevent offloading."""
        with self._lock:
            if layer_idx in self.layers:
                for tensor_id in self.layers[layer_idx].values():
                    self.offload_manager.pin_tensor(tensor_id)

    def unpin_layer(self, layer_idx: int) -> None:
        """Unpin a layer to allow offloading."""
        with self._lock:
            if layer_idx in self.layers:
                for tensor_id in self.layers[layer_idx].values():
                    self.offload_manager.unpin_tensor(tensor_id)

    def get_layer_location(self, layer_idx: int) -> Dict[str, str]:
        """Get location of each component in a layer."""
        with self._lock:
            result = {}
            if layer_idx in self.layers:
                for component, tensor_id in self.layers[layer_idx].items():
                    if tensor_id in self.offload_manager.tensors:
                        state = self.offload_manager.tensors[tensor_id]
                        result[component] = state.location.value
            return result

    def get_stats(self) -> Dict[str, Any]:
        """Get inference statistics."""
        stats = self.offload_manager.get_stats()
        stats["num_layers"] = self.num_layers
        stats["is_generating"] = self.is_generating
        stats["current_layer"] = self.current_layer

        # Layer distribution
        gpu_layers = 0
        cpu_layers = 0
        for layer_idx in self.layers:
            locations = self.get_layer_location(layer_idx)
            if all(loc == "gpu" for loc in locations.values()):
                gpu_layers += 1
            elif all(loc == "cpu" for loc in locations.values()):
                cpu_layers += 1

        stats["gpu_layers"] = gpu_layers
        stats["cpu_layers"] = cpu_layers
        stats["mixed_layers"] = self.num_layers - gpu_layers - cpu_layers

        return stats


class CTMAutoTensorParallel:
    """
    CTM+ enhanced auto tensor parallelism for inference.

    Automatically partitions model across GPUs with CTM+ memory management.
    """

    def __init__(
        self,
        inference_managers: List[CTMInferenceManager],
        tp_size: int,
    ):
        """
        Initialize tensor parallel manager.

        Args:
            inference_managers: One manager per GPU.
            tp_size: Tensor parallel size.
        """
        self.managers = inference_managers
        self.tp_size = tp_size
        self.tp_rank_to_layers: Dict[int, List[int]] = {}

    def assign_layers(self, strategy: str = "balanced") -> None:
        """
        Assign layers to tensor parallel ranks.

        Args:
            strategy: Assignment strategy ("balanced", "memory", "compute").
        """
        if len(self.managers) == 0:
            return

        num_layers = self.managers[0].num_layers
        layers_per_rank = num_layers // self.tp_size

        for rank in range(self.tp_size):
            start = rank * layers_per_rank
            end = start + layers_per_rank
            if rank == self.tp_size - 1:
                end = num_layers  # Last rank gets remainder

            self.tp_rank_to_layers[rank] = list(range(start, end))

            # Pin assigned layers on this rank
            if rank < len(self.managers):
                for layer_idx in self.tp_rank_to_layers[rank]:
                    self.managers[rank].pin_layer(layer_idx)

    def get_layer_rank(self, layer_idx: int) -> int:
        """Get which rank owns a layer."""
        for rank, layers in self.tp_rank_to_layers.items():
            if layer_idx in layers:
                return rank
        return 0

    def get_aggregate_stats(self) -> Dict[str, Any]:
        """Get aggregated stats across all ranks."""
        total_stats = {
            "gpu_hits": 0,
            "cpu_hits": 0,
            "offloads": 0,
            "prefetches": 0,
            "gpu_used_bytes": 0,
            "cpu_used_bytes": 0,
        }

        for manager in self.managers:
            stats = manager.get_stats()
            for key in total_stats:
                if key in stats:
                    total_stats[key] += stats[key]

        total_accesses = total_stats["gpu_hits"] + total_stats["cpu_hits"]
        total_stats["gpu_hit_rate"] = (
            total_stats["gpu_hits"] / total_accesses if total_accesses > 0 else 0.0
        )
        total_stats["tp_size"] = self.tp_size
        total_stats["num_ranks"] = len(self.managers)

        return total_stats
