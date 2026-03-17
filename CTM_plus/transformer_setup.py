"""
CTM+ Transformer Setup
======================

Unified setup for wiring CTM+ memory management into standard transformer
training and inference pipelines. Provides a single entry point that
configures the appropriate CTM+ backend (CUDA, vLLM, DeepSpeed, Database)
based on your hardware and workload.

Training example (DeepSpeed + CUDA):
    from CTM_plus.transformer_setup import CTMTransformerSetup

    setup = CTMTransformerSetup.for_training(
        model=model,
        gpu_memory_gb=80,
        cpu_memory_gb=256,
        zero_stage=2,
    )
    ds_config = setup.get_deepspeed_config()

    # In training loop:
    setup.begin_forward()
    loss = model(batch)
    setup.end_forward()
    setup.begin_backward()
    loss.backward()
    setup.end_backward()
    setup.step()

Inference example (vLLM):
    setup = CTMTransformerSetup.for_inference(
        model=model,
        num_gpu_blocks=2000,
        num_cpu_blocks=20000,
        block_size=16,
    )
    manager = setup.get_block_manager()

Checkpoint caching (Database):
    setup = CTMTransformerSetup.for_checkpoint_cache(
        cache_size_mb=4096,
    )
    cache = setup.get_checkpoint_cache()
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)


class CTMBackend(Enum):
    """Available CTM+ backends."""
    DEEPSPEED = "deepspeed"
    VLLM = "vllm"
    CUDA = "cuda"
    DATABASE = "database"


class WorkloadType(Enum):
    """Workload type for auto-configuration."""
    TRAINING = "training"
    INFERENCE = "inference"
    BATCH_INFERENCE = "batch_inference"
    STREAMING = "streaming"
    CHECKPOINT_CACHE = "checkpoint_cache"


@dataclass
class CTMTransformerConfig:
    """
    Unified configuration for CTM+ transformer integration.

    Covers all backends and workloads. Use the class methods on
    CTMTransformerSetup for preset configurations.
    """
    # General
    workload: WorkloadType = WorkloadType.TRAINING
    backends: List[CTMBackend] = field(default_factory=lambda: [CTMBackend.DEEPSPEED])

    # Hardware
    gpu_memory_gb: float = 40.0
    cpu_memory_gb: float = 256.0
    num_gpus: int = 1

    # Model
    num_layers: int = 32
    hidden_dim: int = 4096
    num_heads: int = 32
    vocab_size: int = 50257
    max_seq_len: int = 2048

    # DeepSpeed
    zero_stage: int = 2
    async_offload: bool = True
    prefetch_ahead: int = 2
    pin_optimizer_states: bool = True
    pin_gradients: bool = False

    # vLLM
    block_size: int = 16
    num_gpu_blocks: int = 1000
    num_cpu_blocks: int = 10000
    watermark: float = 0.1

    # Database / checkpoint cache
    cache_size_mb: int = 4096
    page_size_bytes: int = 8192

    # CTM+ tuning
    victim_sample_size: int = 48
    promotion_threshold: float = 0.3
    enable_smart_victim: bool = True
    shadow_size: int = 2048


class CTMTransformerSetup:
    """
    Unified CTM+ setup for standard transformer training and inference.

    Wires together the appropriate CTM+ packages (CUDA, vLLM, DeepSpeed,
    Database) based on the workload type and available hardware.
    """

    def __init__(self, config: CTMTransformerConfig):
        self.config = config
        self._deepspeed_zero: Any = None
        self._deepspeed_inference: Any = None
        self._vllm_manager: Any = None
        self._db_cache: Any = None
        self._initialized_backends: Dict[CTMBackend, bool] = {}

    # =========================================================================
    # Factory methods
    # =========================================================================

    @classmethod
    def for_training(
        cls,
        model: Any = None,
        gpu_memory_gb: float = 40.0,
        cpu_memory_gb: float = 256.0,
        zero_stage: int = 2,
        num_layers: int = 32,
        hidden_dim: int = 4096,
        num_heads: int = 32,
        num_gpus: int = 1,
        max_seq_len: int = 2048,
        vocab_size: int = 50257,
    ) -> "CTMTransformerSetup":
        """
        Configure CTM+ for transformer training with DeepSpeed ZeRO-Offload.

        Args:
            model: PyTorch model (optional, used to auto-detect architecture).
            gpu_memory_gb: GPU memory per device in GB.
            cpu_memory_gb: CPU memory in GB.
            zero_stage: DeepSpeed ZeRO stage (1, 2, or 3).
            num_layers: Number of transformer layers.
            hidden_dim: Hidden dimension.
            num_heads: Number of attention heads.
            num_gpus: Number of GPUs.
            max_seq_len: Maximum sequence length.
            vocab_size: Vocabulary size.

        Returns:
            Configured CTMTransformerSetup.
        """
        if model is not None:
            num_layers, hidden_dim, num_heads, vocab_size = _detect_model_arch(model)

        config = CTMTransformerConfig(
            workload=WorkloadType.TRAINING,
            backends=[CTMBackend.DEEPSPEED],
            gpu_memory_gb=gpu_memory_gb,
            cpu_memory_gb=cpu_memory_gb,
            zero_stage=zero_stage,
            num_layers=num_layers,
            hidden_dim=hidden_dim,
            num_heads=num_heads,
            num_gpus=num_gpus,
            max_seq_len=max_seq_len,
            vocab_size=vocab_size,
            async_offload=True,
            prefetch_ahead=3 if zero_stage >= 2 else 1,
            pin_optimizer_states=zero_stage < 3,
            pin_gradients=True,
            victim_sample_size=64,
            promotion_threshold=0.25,
        )

        setup = cls(config)
        setup._init_deepspeed_training()
        return setup

    @classmethod
    def for_inference(
        cls,
        model: Any = None,
        num_gpu_blocks: int = 2000,
        num_cpu_blocks: int = 20000,
        block_size: int = 16,
        gpu_memory_gb: float = 40.0,
        cpu_memory_gb: float = 256.0,
        num_layers: int = 32,
        hidden_dim: int = 4096,
        num_heads: int = 32,
        vocab_size: int = 50257,
        max_seq_len: int = 2048,
        streaming: bool = False,
    ) -> "CTMTransformerSetup":
        """
        Configure CTM+ for transformer inference with vLLM KV cache management.

        Args:
            model: PyTorch model (optional).
            num_gpu_blocks: Number of KV cache blocks on GPU.
            num_cpu_blocks: Number of KV cache blocks on CPU.
            block_size: Tokens per block.
            gpu_memory_gb: GPU memory per device in GB.
            cpu_memory_gb: CPU memory in GB.
            num_layers: Number of transformer layers.
            hidden_dim: Hidden dimension.
            num_heads: Number of attention heads.
            vocab_size: Vocabulary size.
            max_seq_len: Maximum sequence length.
            streaming: Whether this is streaming inference.

        Returns:
            Configured CTMTransformerSetup.
        """
        if model is not None:
            num_layers, hidden_dim, num_heads, vocab_size = _detect_model_arch(model)

        workload = WorkloadType.STREAMING if streaming else WorkloadType.INFERENCE

        config = CTMTransformerConfig(
            workload=workload,
            backends=[CTMBackend.VLLM, CTMBackend.DEEPSPEED],
            gpu_memory_gb=gpu_memory_gb,
            cpu_memory_gb=cpu_memory_gb,
            num_layers=num_layers,
            hidden_dim=hidden_dim,
            num_heads=num_heads,
            vocab_size=vocab_size,
            max_seq_len=max_seq_len,
            block_size=block_size,
            num_gpu_blocks=num_gpu_blocks,
            num_cpu_blocks=num_cpu_blocks,
            victim_sample_size=32 if streaming else 48,
            promotion_threshold=0.25 if streaming else 0.30,
        )

        setup = cls(config)
        setup._init_vllm()
        setup._init_deepspeed_inference()
        return setup

    @classmethod
    def for_large_model_inference(
        cls,
        model: Any = None,
        gpu_memory_gb: float = 80.0,
        cpu_memory_gb: float = 512.0,
        num_layers: int = 80,
        hidden_dim: int = 8192,
        num_heads: int = 64,
        tp_size: int = 1,
        num_gpu_blocks: int = 4000,
        num_cpu_blocks: int = 40000,
        block_size: int = 16,
    ) -> "CTMTransformerSetup":
        """
        Configure CTM+ for large model inference (70B+) with weight offloading
        and KV cache management.

        Uses both DeepSpeed (weight offloading) and vLLM (KV cache).
        """
        if model is not None:
            num_layers, hidden_dim, num_heads, _ = _detect_model_arch(model)

        config = CTMTransformerConfig(
            workload=WorkloadType.INFERENCE,
            backends=[CTMBackend.DEEPSPEED, CTMBackend.VLLM],
            gpu_memory_gb=gpu_memory_gb,
            cpu_memory_gb=cpu_memory_gb,
            num_gpus=tp_size,
            num_layers=num_layers,
            hidden_dim=hidden_dim,
            num_heads=num_heads,
            block_size=block_size,
            num_gpu_blocks=num_gpu_blocks,
            num_cpu_blocks=num_cpu_blocks,
            victim_sample_size=96,
            promotion_threshold=0.40,
            shadow_size=4096,
            prefetch_ahead=4,
            async_offload=True,
        )

        setup = cls(config)
        setup._init_deepspeed_inference()
        setup._init_vllm()
        return setup

    @classmethod
    def for_checkpoint_cache(
        cls,
        cache_size_mb: int = 4096,
        page_size_bytes: int = 8192,
    ) -> "CTMTransformerSetup":
        """
        Configure CTM+ as a checkpoint/weight cache using the Database backend.

        Useful for caching model weights, optimizer states, or KV cache
        snapshots to disk with intelligent eviction.
        """
        config = CTMTransformerConfig(
            workload=WorkloadType.CHECKPOINT_CACHE,
            backends=[CTMBackend.DATABASE],
            cache_size_mb=cache_size_mb,
            page_size_bytes=page_size_bytes,
        )

        setup = cls(config)
        setup._init_database()
        return setup

    # =========================================================================
    # Backend initialization
    # =========================================================================

    def _init_deepspeed_training(self) -> None:
        """Initialize DeepSpeed ZeRO-Offload with CTM+."""
        from CTM_plus.DeepSpeed.ctm_plus_deepspeed import (
            CTMZeROOffload,
            CTMDeepSpeedConfig,
        )

        gpu_bytes = int(self.config.gpu_memory_gb * 1024**3)
        cpu_bytes = int(self.config.cpu_memory_gb * 1024**3)

        if self.config.zero_stage >= 3:
            ds_config = CTMDeepSpeedConfig.for_large_model()
        else:
            ds_config = CTMDeepSpeedConfig.for_training()

        # Override with user-specified values
        ds_config.victim_sample_size = self.config.victim_sample_size
        ds_config.promotion_threshold = self.config.promotion_threshold
        ds_config.prefetch_ahead = self.config.prefetch_ahead
        ds_config.async_offload = self.config.async_offload
        ds_config.pin_optimizer_states = self.config.pin_optimizer_states
        ds_config.pin_gradients = self.config.pin_gradients

        self._deepspeed_zero = CTMZeROOffload(
            gpu_memory_bytes=gpu_bytes,
            cpu_memory_bytes=cpu_bytes,
            config=ds_config,
            zero_stage=self.config.zero_stage,
        )

        self._initialized_backends[CTMBackend.DEEPSPEED] = True
        logger.info(
            f"CTM+ DeepSpeed training initialized: ZeRO-{self.config.zero_stage}, "
            f"GPU={self.config.gpu_memory_gb}GB, CPU={self.config.cpu_memory_gb}GB"
        )

    def _init_deepspeed_inference(self) -> None:
        """Initialize DeepSpeed inference with CTM+ weight offloading."""
        from CTM_plus.DeepSpeed.ctm_plus_deepspeed import (
            CTMInferenceManager,
            CTMDeepSpeedConfig,
        )

        gpu_bytes = int(self.config.gpu_memory_gb * 1024**3)
        cpu_bytes = int(self.config.cpu_memory_gb * 1024**3)

        ds_config = CTMDeepSpeedConfig.for_inference()
        ds_config.victim_sample_size = self.config.victim_sample_size
        ds_config.promotion_threshold = self.config.promotion_threshold
        ds_config.prefetch_ahead = self.config.prefetch_ahead
        ds_config.async_offload = self.config.async_offload

        self._deepspeed_inference = CTMInferenceManager(
            gpu_memory_bytes=gpu_bytes,
            cpu_memory_bytes=cpu_bytes,
            config=ds_config,
            num_layers=self.config.num_layers,
        )

        self._initialized_backends[CTMBackend.DEEPSPEED] = True
        logger.info(
            f"CTM+ DeepSpeed inference initialized: "
            f"{self.config.num_layers} layers, prefetch_ahead={self.config.prefetch_ahead}"
        )

    def _init_vllm(self) -> None:
        """Initialize vLLM block manager with CTM+ eviction."""
        from CTM_plus.vLLM.ctm_plus_vllm import CTMBlockSpaceManager, CTMvLLMConfig

        if self.config.workload == WorkloadType.STREAMING:
            vllm_config = CTMvLLMConfig.for_streaming()
        elif self.config.workload == WorkloadType.BATCH_INFERENCE:
            vllm_config = CTMvLLMConfig.for_batch_inference()
        else:
            vllm_config = CTMvLLMConfig.for_llm_inference()

        vllm_config.victim_sample_size = self.config.victim_sample_size
        vllm_config.promotion_threshold = self.config.promotion_threshold

        self._vllm_manager = CTMBlockSpaceManager(
            block_size=self.config.block_size,
            num_gpu_blocks=self.config.num_gpu_blocks,
            num_cpu_blocks=self.config.num_cpu_blocks,
            watermark=self.config.watermark,
            ctm_config=vllm_config,
        )

        self._initialized_backends[CTMBackend.VLLM] = True
        logger.info(
            f"CTM+ vLLM initialized: {self.config.num_gpu_blocks} GPU blocks, "
            f"{self.config.num_cpu_blocks} CPU blocks, block_size={self.config.block_size}"
        )

    def _init_database(self) -> None:
        """Initialize Database backend for checkpoint caching."""
        from CTM_plus.Database.ctm_plus_db import GenericKVCache, CTMDBConfig

        db_config = CTMDBConfig.for_mixed()
        db_config.victim_sample_size = self.config.victim_sample_size

        pool_pages = (self.config.cache_size_mb * 1024 * 1024) // self.config.page_size_bytes

        self._db_cache = GenericKVCache(
            max_entries=pool_pages,
            config=db_config,
        )

        self._initialized_backends[CTMBackend.DATABASE] = True
        logger.info(
            f"CTM+ Database cache initialized: {self.config.cache_size_mb}MB, "
            f"{pool_pages} pages"
        )

    # =========================================================================
    # Training API (DeepSpeed)
    # =========================================================================

    def register_model(self, model: Any) -> None:
        """
        Register all model parameters with CTM+ for offload tracking.

        Call this after model creation but before training starts.

        Args:
            model: PyTorch nn.Module.
        """
        if self._deepspeed_zero is None:
            raise RuntimeError("DeepSpeed training not initialized. Use for_training().")

        for name, param in model.named_parameters():
            size_bytes = param.numel() * param.element_size()
            param_id = f"param.{name}"
            self._deepspeed_zero.register_parameter(
                param_id=param_id,
                name=name,
                size_bytes=size_bytes,
            )
        logger.info(f"Registered {sum(1 for _ in model.parameters())} parameters with CTM+")

    def register_optimizer(self, optimizer: Any) -> None:
        """
        Register optimizer states with CTM+ for offload tracking.

        Call after optimizer creation.

        Args:
            optimizer: PyTorch optimizer with state_dict().
        """
        if self._deepspeed_zero is None:
            raise RuntimeError("DeepSpeed training not initialized. Use for_training().")

        for group_idx, group in enumerate(optimizer.param_groups):
            for param_idx, param in enumerate(group["params"]):
                param_id = f"param.group{group_idx}.{param_idx}"
                # Register momentum and variance placeholders
                size_bytes = param.numel() * param.element_size()
                self._deepspeed_zero.register_optimizer_state(
                    state_id=f"opt.{param_id}.momentum",
                    name=f"group{group_idx}.param{param_idx}",
                    size_bytes=size_bytes,
                    param_id=param_id,
                    state_type="momentum",
                )
                self._deepspeed_zero.register_optimizer_state(
                    state_id=f"opt.{param_id}.variance",
                    name=f"group{group_idx}.param{param_idx}",
                    size_bytes=size_bytes,
                    param_id=param_id,
                    state_type="variance",
                )

    def begin_forward(self) -> None:
        """Call at start of forward pass."""
        if self._deepspeed_zero:
            self._deepspeed_zero.begin_forward()

    def end_forward(self) -> None:
        """Call at end of forward pass."""
        if self._deepspeed_zero:
            self._deepspeed_zero.end_forward()

    def begin_backward(self) -> None:
        """Call at start of backward pass."""
        if self._deepspeed_zero:
            self._deepspeed_zero.begin_backward()

    def end_backward(self) -> None:
        """Call at end of backward pass."""
        if self._deepspeed_zero:
            self._deepspeed_zero.end_backward()

    def step(self) -> None:
        """Call during optimizer step."""
        if self._deepspeed_zero:
            self._deepspeed_zero.step()

    def get_deepspeed_config(self, base_config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate DeepSpeed config dict with CTM+ settings.

        Can be passed directly to deepspeed.initialize().

        Args:
            base_config: Optional base config to extend.

        Returns:
            DeepSpeed configuration dictionary.
        """
        from CTM_plus.DeepSpeed.ctm_plus_deepspeed import get_deepspeed_config_with_ctm

        if self._deepspeed_zero is None:
            raise RuntimeError("DeepSpeed training not initialized. Use for_training().")

        return get_deepspeed_config_with_ctm(
            self._deepspeed_zero.offload_manager,
            base_config=base_config,
        )

    # =========================================================================
    # Inference API (vLLM + DeepSpeed)
    # =========================================================================

    def register_inference_model(self, model: Any) -> None:
        """
        Register model layers for inference with weight offloading.

        Args:
            model: PyTorch nn.Module with transformer layers.
        """
        if self._deepspeed_inference is None:
            return

        layer_idx = 0
        for name, module in model.named_modules():
            # Detect transformer layers by common patterns
            if _is_transformer_layer(name, module):
                weights = {}
                for pname, param in module.named_parameters(recurse=False):
                    tensor_id = f"layer.{layer_idx}.{pname}"
                    weights[pname] = (tensor_id, param.numel() * param.element_size())
                for cname, child in module.named_children():
                    for pname, param in child.named_parameters(recurse=False):
                        tensor_id = f"layer.{layer_idx}.{cname}.{pname}"
                        weights[f"{cname}.{pname}"] = (
                            tensor_id,
                            param.numel() * param.element_size(),
                        )

                if weights:
                    self._deepspeed_inference.register_layer(
                        layer_idx=layer_idx,
                        weights=weights,
                        initial_on_gpu=True,
                    )
                    layer_idx += 1

        logger.info(f"Registered {layer_idx} transformer layers for inference offloading")

    def get_block_manager(self) -> Any:
        """
        Get the CTM+ vLLM block manager for KV cache management.

        Returns:
            CTMBlockSpaceManager instance.
        """
        if self._vllm_manager is None:
            raise RuntimeError("vLLM not initialized. Use for_inference().")
        return self._vllm_manager

    def begin_generation(self) -> None:
        """Call at start of generation (inference)."""
        if self._deepspeed_inference:
            self._deepspeed_inference.begin_generation()

    def on_layer_forward(self, layer_idx: int) -> List[str]:
        """
        Call when forward pass reaches a transformer layer during inference.

        Returns list of tensor IDs that need fetching from CPU.
        """
        if self._deepspeed_inference:
            return self._deepspeed_inference.on_layer_forward(layer_idx)
        return []

    def end_generation(self) -> None:
        """Call at end of generation."""
        if self._deepspeed_inference:
            self._deepspeed_inference.end_generation()

    def allocate_kv_blocks(self, sequence_id: int, num_blocks: int) -> List[int]:
        """Allocate KV cache blocks for a sequence."""
        if self._vllm_manager is None:
            raise RuntimeError("vLLM not initialized. Use for_inference().")
        return self._vllm_manager.allocate(sequence_id, num_blocks)

    def access_kv_blocks(
        self, sequence_id: int, block_indices: Optional[List[int]] = None
    ) -> List[int]:
        """Access KV cache blocks (triggers CTM+ tracking). Returns promoted block IDs."""
        if self._vllm_manager is None:
            raise RuntimeError("vLLM not initialized. Use for_inference().")
        return self._vllm_manager.access(sequence_id, block_indices)

    def free_kv_blocks(self, sequence_id: int) -> None:
        """Free KV cache blocks for a completed sequence."""
        if self._vllm_manager is None:
            return
        self._vllm_manager.free(sequence_id)

    # =========================================================================
    # Checkpoint cache API (Database)
    # =========================================================================

    def get_checkpoint_cache(self) -> Any:
        """
        Get the CTM+ database-backed checkpoint cache.

        Returns:
            GenericKVCache instance.
        """
        if self._db_cache is None:
            raise RuntimeError("Database not initialized. Use for_checkpoint_cache().")
        return self._db_cache

    # =========================================================================
    # Stats and monitoring
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated stats from all active backends."""
        stats: Dict[str, Any] = {
            "workload": self.config.workload.value,
            "backends": [b.value for b in self._initialized_backends],
        }

        if self._deepspeed_zero:
            stats["deepspeed_training"] = self._deepspeed_zero.get_stats()

        if self._deepspeed_inference:
            stats["deepspeed_inference"] = self._deepspeed_inference.get_stats()

        if self._vllm_manager:
            stats["vllm"] = self._vllm_manager.get_stats()

        if self._db_cache:
            stats["database"] = (
                self._db_cache.get_stats()
                if hasattr(self._db_cache, "get_stats")
                else {}
            )

        return stats

    def reset_stats(self) -> None:
        """Reset stats on all active backends."""
        if self._deepspeed_zero:
            self._deepspeed_zero.offload_manager.reset_stats()
        if self._deepspeed_inference:
            self._deepspeed_inference.offload_manager.reset_stats()
        if self._vllm_manager:
            self._vllm_manager.ctm.reset_stats()

    def log_stats(self, step: Optional[int] = None) -> str:
        """Format stats as a human-readable string."""
        stats = self.get_stats()
        lines = [f"CTM+ Stats (step={step})" if step else "CTM+ Stats"]

        if "deepspeed_training" in stats:
            ds = stats["deepspeed_training"]
            lines.append(
                f"  DeepSpeed: GPU hit={ds.get('gpu_hit_rate', 0):.1%}, "
                f"offloads={ds.get('offloads', 0)}, "
                f"phase={ds.get('current_phase', 'idle')}"
            )

        if "deepspeed_inference" in stats:
            ds = stats["deepspeed_inference"]
            lines.append(
                f"  Inference: GPU hit={ds.get('gpu_hit_rate', 0):.1%}, "
                f"GPU layers={ds.get('gpu_layers', 0)}/{ds.get('num_layers', 0)}"
            )

        if "vllm" in stats:
            vl = stats["vllm"]
            lines.append(
                f"  vLLM: free GPU={vl.get('free_gpu_blocks', 0)}/{vl.get('num_gpu_blocks', 0)}, "
                f"evictions={vl.get('num_evictions', 0)}, "
                f"sequences={vl.get('active_sequences', 0)}"
            )

        return "\n".join(lines)


# =============================================================================
# Helpers
# =============================================================================

def _detect_model_arch(model: Any) -> Tuple[int, int, int, int]:
    """
    Auto-detect transformer architecture from a PyTorch model.

    Returns:
        (num_layers, hidden_dim, num_heads, vocab_size)
    """
    num_layers = 32
    hidden_dim = 4096
    num_heads = 32
    vocab_size = 50257

    # Try common attribute names
    config = getattr(model, "config", None)
    if config is not None:
        num_layers = getattr(config, "num_layers", None) or getattr(
            config, "n_layer", None) or getattr(config, "num_hidden_layers", num_layers)
        hidden_dim = getattr(config, "hidden_size", None) or getattr(
            config, "embed_dim", None) or getattr(config, "n_embd", hidden_dim)
        num_heads = getattr(config, "num_attention_heads", None) or getattr(
            config, "num_heads", None) or getattr(config, "n_head", num_heads)
        vocab_size = getattr(config, "vocab_size", vocab_size)
    else:
        # Count transformer layers by detecting repeated blocks
        layer_count = 0
        for name, _ in model.named_modules():
            parts = name.split(".")
            for i, part in enumerate(parts):
                if part in ("layers", "blocks", "h") and i + 1 < len(parts):
                    try:
                        idx = int(parts[i + 1])
                        layer_count = max(layer_count, idx + 1)
                    except ValueError:
                        pass
        if layer_count > 0:
            num_layers = layer_count

        # Detect hidden dim from embedding
        for name, param in model.named_parameters():
            if "embed" in name and "weight" in name and param.dim() == 2:
                vocab_size, hidden_dim = param.shape
                break

    return num_layers, hidden_dim, num_heads, vocab_size


def _is_transformer_layer(name: str, module: Any) -> bool:
    """Check if a module is a transformer layer."""
    # Check by class name
    class_name = type(module).__name__.lower()
    layer_patterns = [
        "transformerlayer", "transformerblock", "decoderlayer",
        "encoderlayer", "block", "layer",
    ]
    if any(p in class_name for p in layer_patterns):
        # Verify it has attention-like submodules
        child_names = {n for n, _ in module.named_children()}
        has_attn = any(
            "attn" in n or "attention" in n or "self_attn" in n
            for n in child_names
        )
        has_mlp = any(
            "mlp" in n or "ffn" in n or "feed_forward" in n or "fc" in n
            for n in child_names
        )
        return has_attn or has_mlp

    # Check by module path pattern
    for pattern in [".layers.", ".blocks.", ".h."]:
        if pattern in f".{name}.":
            parts = name.split(".")
            for i, part in enumerate(parts):
                if part in ("layers", "blocks", "h"):
                    # This is a direct child of the layer container
                    if i + 1 < len(parts):
                        try:
                            int(parts[i + 1])
                            # Only match the layer itself, not its children
                            return len(parts) == i + 2
                        except ValueError:
                            pass

    return False
