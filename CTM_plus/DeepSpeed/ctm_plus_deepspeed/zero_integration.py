"""
CTM+ ZeRO-Offload Integration for DeepSpeed.

Provides intelligent offloading for ZeRO optimizer states and gradients.
"""

from typing import Dict, List, Optional, Any, Callable
import threading

from .offload_manager import CTMOffloadManager, TensorLocation
from .config import CTMDeepSpeedConfig


class CTMZeROOffload:
    """
    CTM+ enhanced ZeRO-Offload manager.

    Wraps DeepSpeed's ZeRO offload with CTM+ intelligence for:
    - Optimizer state placement
    - Gradient accumulation
    - Parameter prefetching
    """

    def __init__(
        self,
        gpu_memory_bytes: int,
        cpu_memory_bytes: int,
        config: Optional[CTMDeepSpeedConfig] = None,
        zero_stage: int = 2,
    ):
        """
        Initialize ZeRO offload with CTM+.

        Args:
            gpu_memory_bytes: Available GPU memory.
            cpu_memory_bytes: Available CPU memory.
            config: CTM+ configuration.
            zero_stage: ZeRO stage (1, 2, or 3).
        """
        self.config = config or CTMDeepSpeedConfig.for_zero_offload()
        self.zero_stage = zero_stage

        self.offload_manager = CTMOffloadManager(
            gpu_memory_bytes=gpu_memory_bytes,
            cpu_memory_bytes=cpu_memory_bytes,
            config=self.config,
        )

        # Track parameter groups
        self.param_groups: Dict[str, List[str]] = {}  # group_name -> [param_ids]
        self.param_to_optimizer: Dict[str, List[str]] = {}  # param_id -> [opt_state_ids]

        # Forward/backward tracking
        self.current_phase = "idle"  # idle, forward, backward
        self._lock = threading.RLock()

    def register_parameter(
        self,
        param_id: str,
        name: str,
        size_bytes: int,
        group_name: str = "default",
    ) -> None:
        """Register a model parameter."""
        with self._lock:
            self.offload_manager.register_tensor(
                tensor_id=param_id,
                name=name,
                size_bytes=size_bytes,
                is_gradient=False,
                is_optimizer_state=False,
                initial_location=TensorLocation.GPU,
            )

            if group_name not in self.param_groups:
                self.param_groups[group_name] = []
            self.param_groups[group_name].append(param_id)

    def register_optimizer_state(
        self,
        state_id: str,
        name: str,
        size_bytes: int,
        param_id: str,
        state_type: str = "momentum",  # momentum, variance, etc.
    ) -> None:
        """Register an optimizer state tensor."""
        with self._lock:
            # ZeRO-Offload: optimizer states start on CPU
            initial_location = (
                TensorLocation.CPU if self.zero_stage >= 2
                else TensorLocation.GPU
            )

            self.offload_manager.register_tensor(
                tensor_id=state_id,
                name=f"{name}.{state_type}",
                size_bytes=size_bytes,
                is_gradient=False,
                is_optimizer_state=True,
                initial_location=initial_location,
            )

            if param_id not in self.param_to_optimizer:
                self.param_to_optimizer[param_id] = []
            self.param_to_optimizer[param_id].append(state_id)

    def register_gradient(
        self,
        grad_id: str,
        name: str,
        size_bytes: int,
        param_id: str,
    ) -> None:
        """Register a gradient tensor."""
        with self._lock:
            self.offload_manager.register_tensor(
                tensor_id=grad_id,
                name=f"{name}.grad",
                size_bytes=size_bytes,
                is_gradient=True,
                is_optimizer_state=False,
                initial_location=TensorLocation.GPU,
            )

    def begin_forward(self) -> None:
        """Called at start of forward pass."""
        with self._lock:
            self.current_phase = "forward"
            # Parameters needed on GPU for forward
            for group_params in self.param_groups.values():
                for param_id in group_params:
                    self.offload_manager.on_access(param_id, in_compute_graph=True)

    def end_forward(self) -> None:
        """Called at end of forward pass."""
        with self._lock:
            # Release compute graph flag
            for group_params in self.param_groups.values():
                for param_id in group_params:
                    self.offload_manager.set_compute_graph([param_id], False)

    def begin_backward(self) -> None:
        """Called at start of backward pass."""
        with self._lock:
            self.current_phase = "backward"

    def on_backward_layer(self, layer_params: List[str]) -> List[str]:
        """
        Called when backward reaches a layer.

        Returns list of tensors to prefetch for next layer.
        """
        with self._lock:
            prefetch_list = []

            for param_id in layer_params:
                # Access parameter and its optimizer states
                self.offload_manager.on_access(param_id, in_compute_graph=True)

                # Access optimizer states for this parameter
                if param_id in self.param_to_optimizer:
                    for opt_id in self.param_to_optimizer[param_id]:
                        _, prefetches = self.offload_manager.on_access(
                            opt_id, in_compute_graph=True
                        )
                        prefetch_list.extend(prefetches)

            return prefetch_list

    def end_backward(self) -> None:
        """Called at end of backward pass."""
        with self._lock:
            self.current_phase = "idle"
            # Release all compute graph flags
            for tensor_id in self.offload_manager.tensors:
                self.offload_manager.set_compute_graph([tensor_id], False)

    def step(self) -> None:
        """Called during optimizer step."""
        with self._lock:
            # All optimizer states needed
            for param_id, opt_ids in self.param_to_optimizer.items():
                for opt_id in opt_ids:
                    self.offload_manager.on_access(opt_id, in_compute_graph=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get offload statistics."""
        stats = self.offload_manager.get_stats()
        stats["zero_stage"] = self.zero_stage
        stats["current_phase"] = self.current_phase
        stats["param_groups"] = len(self.param_groups)
        stats["total_params"] = sum(len(p) for p in self.param_groups.values())
        return stats


def get_deepspeed_config_with_ctm(
    offload_manager: CTMOffloadManager,
    base_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate DeepSpeed config with CTM+ offload settings.

    Args:
        offload_manager: CTM+ offload manager instance.
        base_config: Optional base DeepSpeed config to extend.

    Returns:
        DeepSpeed configuration dictionary.
    """
    config = base_config.copy() if base_config else {}

    # Get memory info
    memory = offload_manager.get_memory_stats()

    # Configure ZeRO
    if "zero_optimization" not in config:
        config["zero_optimization"] = {}

    zero_config = config["zero_optimization"]

    # Stage 2 with CPU offload
    zero_config.setdefault("stage", 2)
    zero_config.setdefault("offload_optimizer", {
        "device": "cpu",
        "pin_memory": True,
        "buffer_count": 4,
        "fast_init": True,
    })

    # Memory efficiency
    zero_config.setdefault("contiguous_gradients", True)
    zero_config.setdefault("overlap_comm", True)
    zero_config.setdefault("reduce_scatter", True)
    zero_config.setdefault("reduce_bucket_size", 5e8)
    zero_config.setdefault("allgather_bucket_size", 5e8)

    # CTM+ specific hints
    config["ctm_plus"] = {
        "enabled": True,
        "victim_sample_size": offload_manager.config.victim_sample_size,
        "prefetch_ahead": offload_manager.config.prefetch_ahead,
        "async_offload": offload_manager.config.async_offload,
    }

    return config


class CTMPartitionedParameterCoordinator:
    """
    CTM+ enhanced parameter coordinator for ZeRO-3.

    Manages parameter partitioning and all-gather with CTM+ prefetching.
    """

    def __init__(
        self,
        offload_manager: CTMOffloadManager,
        world_size: int,
        rank: int,
    ):
        """
        Initialize coordinator.

        Args:
            offload_manager: CTM+ offload manager.
            world_size: Number of processes in distributed group.
            rank: This process's rank.
        """
        self.offload_manager = offload_manager
        self.world_size = world_size
        self.rank = rank

        # Track which parameters this rank owns
        self.owned_params: Dict[str, Tuple[int, int]] = {}  # param_id -> (start, end)
        self.full_params: Dict[str, bool] = {}  # param_id -> is_gathered

    def register_partitioned_param(
        self,
        param_id: str,
        name: str,
        full_size_bytes: int,
        partition_start: int,
        partition_end: int,
    ) -> None:
        """Register a partitioned parameter."""
        partition_size = partition_end - partition_start

        self.offload_manager.register_tensor(
            tensor_id=param_id,
            name=name,
            size_bytes=partition_size,
            initial_location=TensorLocation.GPU,
        )

        self.owned_params[param_id] = (partition_start, partition_end)
        self.full_params[param_id] = False

    def prefetch_params(self, param_ids: List[str]) -> None:
        """Prefetch parameters before they're needed."""
        for param_id in param_ids:
            self.offload_manager.on_access(param_id, in_compute_graph=False)

    def gather_param(self, param_id: str) -> None:
        """Mark parameter as gathered (full tensor available)."""
        self.full_params[param_id] = True
        self.offload_manager.on_access(param_id, in_compute_graph=True)

    def release_param(self, param_id: str) -> None:
        """Release gathered parameter back to partition."""
        self.full_params[param_id] = False
        self.offload_manager.set_compute_graph([param_id], False)

    def get_params_to_prefetch(self, current_layer: int, total_layers: int) -> List[str]:
        """Get parameters to prefetch for upcoming layers."""
        prefetch_list = []
        ahead = self.offload_manager.config.prefetch_ahead

        for i in range(current_layer + 1, min(current_layer + ahead + 1, total_layers)):
            # This would need layer->param mapping from the model
            pass

        return prefetch_list
