"""
CTM+ Training Memory Manager.

Manages GPU/CPU memory during LLM training using CTM+ signals:
- Activation checkpointing: CTM+ decides which layers to checkpoint vs recompute
- Optimizer state offloading: Cold optimizer states move to CPU
- KV-cache pressure: For long-sequence training, manages KV memory

This bridges CTM+ page-level intelligence with PyTorch training memory management.

Usage:
    manager = CTMTrainingMemoryManager(
        gpu_budget_bytes=40 * 1024**3,  # 40GB
        cpu_budget_bytes=128 * 1024**3,  # 128GB
        num_layers=32,
    )

    # During training loop
    for batch in dataloader:
        manager.begin_forward()
        for layer_idx in range(num_layers):
            # Check if activations should be checkpointed
            if manager.should_checkpoint(layer_idx):
                with torch.no_grad():
                    output = layer(input)  # Will recompute in backward
            else:
                output = layer(input)      # Keep activation in GPU
            manager.record_layer_forward(layer_idx, activation_size)

        manager.begin_backward()
        loss.backward()
        manager.step_optimizer()
"""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any


class MemoryTier(Enum):
    GPU = auto()
    CPU = auto()


class TensorCategory(Enum):
    """Categories of tensors in training."""
    PARAMETER = auto()      # Model weights (always on GPU during compute)
    GRADIENT = auto()       # Gradients (needed during backward)
    OPTIMIZER = auto()      # Adam momentum/variance (2x model size)
    ACTIVATION = auto()     # Forward pass activations (for backward)
    KV_CACHE = auto()       # KV cache for causal training


@dataclass
class TensorRecord:
    """Tracked tensor in the memory manager."""
    tensor_id: str
    category: TensorCategory
    size_bytes: int
    layer_idx: int
    location: MemoryTier = MemoryTier.GPU
    last_access_step: int = 0
    access_count: int = 0
    recompute_cost_ms: float = 0.0  # Cost to recompute if checkpointed
    is_pinned: bool = False

    @property
    def offload_priority(self) -> float:
        """Lower = offload first. Based on access recency and category."""
        category_weight = {
            TensorCategory.PARAMETER: 1.0,     # Never offload during compute
            TensorCategory.GRADIENT: 0.8,       # Need during backward
            TensorCategory.KV_CACHE: 0.6,       # May be recomputed
            TensorCategory.ACTIVATION: 0.4,     # Can be checkpointed
            TensorCategory.OPTIMIZER: 0.2,      # Cold between steps
        }
        return category_weight.get(self.category, 0.5)


@dataclass
class LayerProfile:
    """Profile of a transformer layer's memory behavior."""
    layer_idx: int
    activation_size_bytes: int = 0
    param_size_bytes: int = 0
    optimizer_state_size_bytes: int = 0
    forward_time_ms: float = 0.0
    backward_time_ms: float = 0.0
    recompute_ratio: float = 1.0  # recompute_time / forward_time

    # Access pattern tracking
    access_count: int = 0
    last_checkpoint_step: int = 0
    checkpoint_count: int = 0
    recompute_count: int = 0

    @property
    def recompute_cost_ms(self) -> float:
        return self.forward_time_ms * self.recompute_ratio

    @property
    def memory_per_compute_ratio(self) -> float:
        """Bytes saved per ms of recompute cost. Higher = better to checkpoint."""
        if self.recompute_cost_ms <= 0:
            return float('inf')
        return self.activation_size_bytes / self.recompute_cost_ms


class CTMTrainingMemoryManager:
    """
    CTM+ memory manager for LLM training.

    Manages three memory pools across GPU and CPU:
    1. Activations: Checkpoint vs keep, based on recompute cost
    2. Optimizer states: Offload cold states to CPU between steps
    3. KV-cache: For long-sequence causal training

    Key insight: Not all layers are equal. Early layers have small activations
    but are needed longest during backward. Late layers have large activations
    but are consumed quickly. CTM+ learns this and adapts.
    """

    def __init__(
        self,
        gpu_budget_bytes: int,
        cpu_budget_bytes: int,
        num_layers: int,
        checkpoint_ratio: float = 0.5,
        offload_optimizer: bool = True,
        min_gpu_free_ratio: float = 0.10,
    ):
        """
        Args:
            gpu_budget_bytes: Total GPU memory budget for managed tensors.
            cpu_budget_bytes: Total CPU memory budget.
            num_layers: Number of transformer layers.
            checkpoint_ratio: Initial fraction of layers to checkpoint.
            offload_optimizer: Whether to offload optimizer states.
            min_gpu_free_ratio: Keep this fraction of GPU memory free.
        """
        self.gpu_budget = gpu_budget_bytes
        self.cpu_budget = cpu_budget_bytes
        self.num_layers = num_layers
        self.checkpoint_ratio = checkpoint_ratio
        self.offload_optimizer = offload_optimizer
        self.min_gpu_free = int(gpu_budget_bytes * min_gpu_free_ratio)

        # Layer profiles
        self.layers: Dict[int, LayerProfile] = {
            i: LayerProfile(layer_idx=i) for i in range(num_layers)
        }

        # Tensor tracking
        self.tensors: Dict[str, TensorRecord] = {}
        self.gpu_used_bytes: int = 0
        self.cpu_used_bytes: int = 0

        # Checkpoint decisions (adaptive)
        self._checkpoint_layers: Set[int] = set()
        self._init_checkpoint_schedule()

        # Optimizer offload tracking
        self._offloaded_optimizer_layers: Set[int] = set()

        # Training state
        self._current_step: int = 0
        self._in_forward: bool = False
        self._in_backward: bool = False
        self._current_layer: int = 0

        # Stats
        self.stats = {
            "total_checkpoints": 0,
            "total_recomputes": 0,
            "optimizer_offloads": 0,
            "optimizer_fetches": 0,
            "peak_gpu_bytes": 0,
            "checkpoint_savings_bytes": 0,
            "adaptation_count": 0,
        }

        self._lock = threading.RLock()

    # =========================================================================
    # Initialization
    # =========================================================================

    def _init_checkpoint_schedule(self) -> None:
        """
        Initialize checkpoint schedule.

        Strategy: Checkpoint every-other layer (uniform), then adapt based
        on profiling. This is the standard gradient checkpointing baseline.
        """
        num_to_checkpoint = int(self.num_layers * self.checkpoint_ratio)

        if num_to_checkpoint <= 0:
            return

        # Uniform spacing
        step = max(1, self.num_layers // num_to_checkpoint)
        for i in range(0, self.num_layers, step):
            if len(self._checkpoint_layers) < num_to_checkpoint:
                self._checkpoint_layers.add(i)

    def register_layer(
        self,
        layer_idx: int,
        param_size_bytes: int,
        activation_size_bytes: int,
        optimizer_state_size_bytes: int = 0,
    ) -> None:
        """Register a layer's memory profile."""
        with self._lock:
            profile = self.layers[layer_idx]
            profile.param_size_bytes = param_size_bytes
            profile.activation_size_bytes = activation_size_bytes
            profile.optimizer_state_size_bytes = (
                optimizer_state_size_bytes or param_size_bytes * 2  # Adam: m + v
            )

    # =========================================================================
    # Training Loop Integration
    # =========================================================================

    def begin_forward(self) -> None:
        """Called at start of forward pass."""
        with self._lock:
            self._in_forward = True
            self._in_backward = False
            self._current_layer = 0

    def should_checkpoint(self, layer_idx: int) -> bool:
        """
        Should this layer's activations be checkpointed (not stored)?

        Returns True if the layer should be recomputed during backward
        instead of storing activations in GPU memory.
        """
        with self._lock:
            if layer_idx in self._checkpoint_layers:
                self.stats["total_checkpoints"] += 1
                self.layers[layer_idx].checkpoint_count += 1
                return True

            # Dynamic: checkpoint if GPU memory pressure is high
            gpu_free = self.gpu_budget - self.gpu_used_bytes
            if gpu_free < self.min_gpu_free:
                # Emergency checkpoint — not enough memory
                return True

            return False

    def record_layer_forward(
        self,
        layer_idx: int,
        activation_size_bytes: int,
        forward_time_ms: float = 0.0,
    ) -> None:
        """Record a layer's forward pass for profiling."""
        with self._lock:
            profile = self.layers[layer_idx]
            profile.activation_size_bytes = activation_size_bytes
            profile.access_count += 1

            if forward_time_ms > 0:
                # EMA of forward time
                alpha = 0.1
                profile.forward_time_ms = (
                    alpha * forward_time_ms +
                    (1 - alpha) * profile.forward_time_ms
                    if profile.forward_time_ms > 0
                    else forward_time_ms
                )

            # Track GPU usage if not checkpointed
            if layer_idx not in self._checkpoint_layers:
                self.gpu_used_bytes += activation_size_bytes
                self.stats["peak_gpu_bytes"] = max(
                    self.stats["peak_gpu_bytes"], self.gpu_used_bytes
                )
            else:
                self.stats["checkpoint_savings_bytes"] += activation_size_bytes

            self._current_layer = layer_idx

    def begin_backward(self) -> None:
        """Called at start of backward pass."""
        with self._lock:
            self._in_forward = False
            self._in_backward = True
            self._current_layer = self.num_layers - 1

            # Fetch optimizer states that will be needed
            if self.offload_optimizer:
                self._prefetch_optimizer_states()

    def record_layer_backward(
        self,
        layer_idx: int,
        backward_time_ms: float = 0.0,
        recompute_time_ms: float = 0.0,
    ) -> None:
        """Record a layer's backward pass."""
        with self._lock:
            profile = self.layers[layer_idx]

            if backward_time_ms > 0:
                alpha = 0.1
                profile.backward_time_ms = (
                    alpha * backward_time_ms +
                    (1 - alpha) * profile.backward_time_ms
                    if profile.backward_time_ms > 0
                    else backward_time_ms
                )

            # If this layer was checkpointed, record recompute
            if layer_idx in self._checkpoint_layers:
                self.stats["total_recomputes"] += 1
                profile.recompute_count += 1
                if recompute_time_ms > 0 and profile.forward_time_ms > 0:
                    profile.recompute_ratio = recompute_time_ms / profile.forward_time_ms

            # Free activation memory (consumed by backward)
            if layer_idx not in self._checkpoint_layers:
                self.gpu_used_bytes = max(
                    0, self.gpu_used_bytes - profile.activation_size_bytes
                )

            self._current_layer = layer_idx

    def step_optimizer(self) -> None:
        """Called after optimizer.step(). Offload cold optimizer states."""
        with self._lock:
            self._current_step += 1
            self._in_backward = False

            # Offload optimizer states to CPU
            if self.offload_optimizer:
                self._offload_cold_optimizer_states()

            # Adapt checkpoint schedule periodically
            if self._current_step % 10 == 0:
                self._adapt_checkpoint_schedule()

    # =========================================================================
    # Optimizer State Management
    # =========================================================================

    def _offload_cold_optimizer_states(self) -> None:
        """Offload optimizer states to CPU after optimizer step."""
        for layer_idx in range(self.num_layers):
            if layer_idx in self._offloaded_optimizer_layers:
                continue

            profile = self.layers[layer_idx]
            opt_size = profile.optimizer_state_size_bytes

            # Check if CPU has room
            if self.cpu_used_bytes + opt_size > self.cpu_budget:
                break

            self._offloaded_optimizer_layers.add(layer_idx)
            self.gpu_used_bytes = max(0, self.gpu_used_bytes - opt_size)
            self.cpu_used_bytes += opt_size
            self.stats["optimizer_offloads"] += 1

    def _prefetch_optimizer_states(self) -> None:
        """Prefetch optimizer states from CPU before backward."""
        for layer_idx in list(self._offloaded_optimizer_layers):
            profile = self.layers[layer_idx]
            opt_size = profile.optimizer_state_size_bytes

            # Check GPU room
            if self.gpu_used_bytes + opt_size > self.gpu_budget - self.min_gpu_free:
                continue

            self._offloaded_optimizer_layers.discard(layer_idx)
            self.gpu_used_bytes += opt_size
            self.cpu_used_bytes = max(0, self.cpu_used_bytes - opt_size)
            self.stats["optimizer_fetches"] += 1

    # =========================================================================
    # Adaptive Checkpoint Schedule
    # =========================================================================

    def _adapt_checkpoint_schedule(self) -> None:
        """
        Adapt which layers to checkpoint based on profiling data.

        Strategy: Sort layers by memory_per_compute_ratio (bytes saved per ms
        of recompute). Checkpoint layers with highest ratio first — they save
        the most memory for the least recompute cost.
        """
        # Need at least a few steps of profiling data
        if self._current_step < 5:
            return

        # Compute ratio for each layer
        ratios: List[Tuple[int, float]] = []
        for layer_idx, profile in self.layers.items():
            ratio = profile.memory_per_compute_ratio
            ratios.append((layer_idx, ratio))

        # Sort by ratio (highest = best to checkpoint)
        ratios.sort(key=lambda x: x[1], reverse=True)

        # Determine how many to checkpoint based on memory pressure
        gpu_free = self.gpu_budget - self.gpu_used_bytes
        total_activation = sum(
            p.activation_size_bytes for p in self.layers.values()
        )

        if total_activation == 0:
            return

        # Target: keep gpu_free above min_gpu_free
        if gpu_free < self.min_gpu_free:
            # Need to checkpoint more
            needed_savings = self.min_gpu_free - gpu_free
            new_checkpoint = set()
            cumulative_savings = 0

            for layer_idx, _ in ratios:
                new_checkpoint.add(layer_idx)
                cumulative_savings += self.layers[layer_idx].activation_size_bytes
                if cumulative_savings >= needed_savings:
                    break

            if new_checkpoint != self._checkpoint_layers:
                self._checkpoint_layers = new_checkpoint
                self.stats["adaptation_count"] += 1

        elif gpu_free > self.min_gpu_free * 3:
            # Can checkpoint fewer layers (have plenty of memory)
            num_to_keep = max(0, len(self._checkpoint_layers) - 2)
            if num_to_keep < len(self._checkpoint_layers):
                # Remove layers with lowest ratio (least efficient to checkpoint)
                new_checkpoint = set()
                for layer_idx, _ in ratios[:num_to_keep]:
                    new_checkpoint.add(layer_idx)

                if new_checkpoint != self._checkpoint_layers:
                    self._checkpoint_layers = new_checkpoint
                    self.stats["adaptation_count"] += 1

    # =========================================================================
    # Query Interface
    # =========================================================================

    def get_checkpoint_layers(self) -> Set[int]:
        """Get current set of checkpointed layers."""
        return set(self._checkpoint_layers)

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get memory usage summary."""
        with self._lock:
            total_activation = sum(
                p.activation_size_bytes for p in self.layers.values()
            )
            checkpointed_activation = sum(
                self.layers[i].activation_size_bytes
                for i in self._checkpoint_layers
                if i in self.layers
            )

            return {
                "gpu_budget_gb": self.gpu_budget / 1e9,
                "gpu_used_gb": self.gpu_used_bytes / 1e9,
                "gpu_free_gb": (self.gpu_budget - self.gpu_used_bytes) / 1e9,
                "cpu_used_gb": self.cpu_used_bytes / 1e9,
                "total_activation_gb": total_activation / 1e9,
                "checkpointed_activation_gb": checkpointed_activation / 1e9,
                "checkpoint_layers": sorted(self._checkpoint_layers),
                "num_checkpointed": len(self._checkpoint_layers),
                "num_layers": self.num_layers,
                "offloaded_optimizer_layers": len(self._offloaded_optimizer_layers),
                "current_step": self._current_step,
                **self.stats,
            }

    def get_layer_report(self) -> List[Dict[str, Any]]:
        """Get per-layer memory and profiling report."""
        with self._lock:
            report = []
            for layer_idx in range(self.num_layers):
                profile = self.layers[layer_idx]
                report.append({
                    "layer": layer_idx,
                    "activation_mb": profile.activation_size_bytes / 1e6,
                    "param_mb": profile.param_size_bytes / 1e6,
                    "optimizer_mb": profile.optimizer_state_size_bytes / 1e6,
                    "forward_ms": profile.forward_time_ms,
                    "backward_ms": profile.backward_time_ms,
                    "recompute_ratio": profile.recompute_ratio,
                    "memory_per_compute": profile.memory_per_compute_ratio,
                    "checkpointed": layer_idx in self._checkpoint_layers,
                    "optimizer_offloaded": layer_idx in self._offloaded_optimizer_layers,
                    "checkpoint_count": profile.checkpoint_count,
                    "recompute_count": profile.recompute_count,
                })
            return report
