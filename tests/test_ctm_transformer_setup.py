"""
Tests for CTM+ Transformer Setup module.

Validates that the unified setup correctly wires together
the DeepSpeed, vLLM, and Database backends for standard
transformer training and inference workflows.

These tests are designed to run without PyTorch installed,
using mock objects where needed.
"""

import sys
import types
import pytest

# ---------------------------------------------------------------------------
# Mock torch so tests run without PyTorch installed
# ---------------------------------------------------------------------------
_torch_mock = types.ModuleType("torch")
_torch_nn = types.ModuleType("torch.nn")


class _FakeModule:
    """Minimal mock of torch.nn.Module."""
    def named_parameters(self, recurse=True):
        return iter([])

    def named_modules(self):
        return iter([])

    def named_children(self):
        return iter([])

    def parameters(self):
        return iter([])


_torch_nn.Module = _FakeModule
_torch_mock.nn = _torch_nn
sys.modules.setdefault("torch", _torch_mock)
sys.modules.setdefault("torch.nn", _torch_nn)
sys.modules.setdefault("torch.nn.functional", types.ModuleType("torch.nn.functional"))
sys.modules.setdefault("torch.utils.checkpoint", types.ModuleType("torch.utils.checkpoint"))

from CTM_plus.transformer_setup import (
    CTMTransformerSetup,
    CTMTransformerConfig,
    CTMBackend,
    WorkloadType,
    _detect_model_arch,
    _is_transformer_layer,
)


# =========================================================================
# Fixtures: fake model for architecture detection
# =========================================================================

class FakeParam:
    """Mock parameter with shape and element_size."""
    def __init__(self, shape, dtype_size=4):
        self.shape = shape
        self._dtype_size = dtype_size

    def numel(self):
        result = 1
        for s in self.shape:
            result *= s
        return result

    def element_size(self):
        return self._dtype_size

    def dim(self):
        return len(self.shape)


class FakeEmbedding:
    pass


class FakeAttention:
    def __init__(self, dim):
        self._params = [("weight", FakeParam((dim, dim)))]

    def named_parameters(self, recurse=False):
        return iter(self._params)

    def named_children(self):
        return iter([])


class FakeMLP:
    def __init__(self, dim):
        self._params = [("weight", FakeParam((dim * 4, dim)))]

    def named_parameters(self, recurse=False):
        return iter(self._params)

    def named_children(self):
        return iter([])


class FakeTransformerBlock(_FakeModule):
    def __init__(self, dim):
        self.attention = FakeAttention(dim)
        self.mlp = FakeMLP(dim)
        self._params = []

    def named_children(self):
        return iter([("attention", self.attention), ("mlp", self.mlp)])

    def named_parameters(self, recurse=False):
        return iter(self._params)


class FakeTransformerModel(_FakeModule):
    """Minimal fake transformer for testing architecture detection."""
    def __init__(self, vocab_size=1000, dim=64, num_layers=4):
        self._vocab_size = vocab_size
        self._dim = dim
        self._num_layers = num_layers
        self._blocks = [FakeTransformerBlock(dim) for _ in range(num_layers)]

    def named_modules(self):
        yield ("", self)
        yield ("embed", FakeEmbedding())
        for i, block in enumerate(self._blocks):
            yield (f"layers.{i}", block)
            yield (f"layers.{i}.attention", block.attention)
            yield (f"layers.{i}.mlp", block.mlp)
        yield ("head", _FakeModule())

    def named_parameters(self, recurse=True):
        yield ("embed.weight", FakeParam((self._vocab_size, self._dim)))
        for i, block in enumerate(self._blocks):
            yield (f"layers.{i}.attention.weight", FakeParam((self._dim, self._dim)))
            yield (f"layers.{i}.mlp.weight", FakeParam((self._dim * 4, self._dim)))

    def parameters(self):
        for _, p in self.named_parameters():
            yield p


class FakeConfigModel(_FakeModule):
    """Model with a config object (HuggingFace style)."""
    class config:
        num_hidden_layers = 12
        hidden_size = 768
        num_attention_heads = 12
        vocab_size = 50257


class FakeGPTConfigModel(_FakeModule):
    """Model with GPT-style config."""
    class config:
        n_layer = 24
        n_embd = 1024
        n_head = 16
        vocab_size = 32000


@pytest.fixture
def fake_model():
    return FakeTransformerModel(vocab_size=1000, dim=64, num_layers=4)


# =========================================================================
# Tests: Configuration
# =========================================================================

class TestCTMTransformerConfig:
    def test_default_config(self):
        config = CTMTransformerConfig()
        assert config.workload == WorkloadType.TRAINING
        assert CTMBackend.DEEPSPEED in config.backends
        assert config.gpu_memory_gb == 40.0
        assert config.num_layers == 32
        assert config.enable_smart_victim is True

    def test_config_values_propagate(self):
        config = CTMTransformerConfig(
            gpu_memory_gb=80.0,
            num_layers=64,
            victim_sample_size=96,
        )
        assert config.gpu_memory_gb == 80.0
        assert config.num_layers == 64
        assert config.victim_sample_size == 96


# =========================================================================
# Tests: Model architecture detection
# =========================================================================

class TestModelDetection:
    def test_detect_from_structure(self, fake_model):
        num_layers, hidden_dim, num_heads, vocab_size = _detect_model_arch(fake_model)
        assert num_layers == 4
        assert hidden_dim == 64
        assert vocab_size == 1000

    def test_detect_from_hf_config(self):
        num_layers, hidden_dim, num_heads, vocab_size = _detect_model_arch(FakeConfigModel())
        assert num_layers == 12
        assert hidden_dim == 768
        assert num_heads == 12
        assert vocab_size == 50257

    def test_detect_from_gpt_config(self):
        num_layers, hidden_dim, num_heads, vocab_size = _detect_model_arch(FakeGPTConfigModel())
        assert num_layers == 24
        assert hidden_dim == 1024
        assert num_heads == 16

    def test_is_transformer_layer_by_children(self):
        block = FakeTransformerBlock(dim=64)
        assert _is_transformer_layer("layers.0", block)

    def test_is_transformer_layer_by_path(self):
        """Module path matching for layers.N pattern."""
        # Direct layer should match
        assert _is_transformer_layer("layers.0", FakeTransformerBlock(64))
        # Sub-modules should not match
        assert not _is_transformer_layer("layers.0.attention", FakeAttention(64))


# =========================================================================
# Tests: Training setup (DeepSpeed)
# =========================================================================

class TestTrainingSetup:
    def test_for_training_basic(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=24.0,
            cpu_memory_gb=128.0,
            zero_stage=2,
            num_layers=12,
            hidden_dim=768,
            num_heads=12,
        )
        assert setup._deepspeed_zero is not None
        assert CTMBackend.DEEPSPEED in setup._initialized_backends
        assert setup.config.workload == WorkloadType.TRAINING

    def test_for_training_with_model(self, fake_model):
        setup = CTMTransformerSetup.for_training(
            model=fake_model,
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        assert setup._deepspeed_zero is not None
        assert setup.config.num_layers == 4
        assert setup.config.hidden_dim == 64

    def test_register_model(self, fake_model):
        setup = CTMTransformerSetup.for_training(
            model=fake_model,
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        setup.register_model(fake_model)
        stats = setup.get_stats()
        assert "deepspeed_training" in stats

    def test_training_lifecycle(self, fake_model):
        setup = CTMTransformerSetup.for_training(
            model=fake_model,
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        setup.register_model(fake_model)

        # Simulate training step
        setup.begin_forward()
        setup.end_forward()
        setup.begin_backward()
        setup.end_backward()
        setup.step()

        stats = setup.get_stats()
        assert stats["deepspeed_training"]["current_phase"] == "idle"

    def test_deepspeed_config_generation(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=40.0,
            cpu_memory_gb=256.0,
            zero_stage=2,
        )
        ds_config = setup.get_deepspeed_config()
        assert "zero_optimization" in ds_config
        assert ds_config["zero_optimization"]["stage"] == 2
        assert "ctm_plus" in ds_config
        assert ds_config["ctm_plus"]["enabled"] is True

    def test_deepspeed_config_extends_base(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=40.0,
            cpu_memory_gb=256.0,
        )
        base = {
            "train_batch_size": 32,
            "fp16": {"enabled": True},
        }
        ds_config = setup.get_deepspeed_config(base_config=base)
        assert ds_config["train_batch_size"] == 32
        assert ds_config["fp16"]["enabled"] is True
        assert "ctm_plus" in ds_config

    def test_zero_stage_3_config(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=80.0,
            cpu_memory_gb=512.0,
            zero_stage=3,
            num_layers=80,
        )
        assert setup.config.zero_stage == 3
        assert setup.config.pin_optimizer_states is False


# =========================================================================
# Tests: Inference setup (vLLM + DeepSpeed)
# =========================================================================

class TestInferenceSetup:
    def test_for_inference_basic(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=1000,
            num_cpu_blocks=5000,
            block_size=16,
        )
        assert setup._vllm_manager is not None
        assert setup._deepspeed_inference is not None
        assert CTMBackend.VLLM in setup._initialized_backends

    def test_for_inference_streaming(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=500,
            num_cpu_blocks=2000,
            streaming=True,
        )
        assert setup.config.workload == WorkloadType.STREAMING
        assert setup.config.victim_sample_size == 32

    def test_block_manager_operations(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=100,
            num_cpu_blocks=500,
            block_size=16,
        )

        # Allocate blocks
        blocks = setup.allocate_kv_blocks(sequence_id=1, num_blocks=5)
        assert len(blocks) == 5

        # Access blocks
        promoted = setup.access_kv_blocks(sequence_id=1, block_indices=[0, 1, 2])
        assert isinstance(promoted, list)

        # Free blocks
        setup.free_kv_blocks(sequence_id=1)

        stats = setup.get_stats()
        assert stats["vllm"]["active_sequences"] == 0

    def test_inference_lifecycle(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=100,
            num_cpu_blocks=500,
            num_layers=4,
        )

        setup.begin_generation()
        for layer_idx in range(4):
            needs_fetch = setup.on_layer_forward(layer_idx)
            assert isinstance(needs_fetch, list)
        setup.end_generation()

    def test_for_large_model_inference(self):
        setup = CTMTransformerSetup.for_large_model_inference(
            gpu_memory_gb=80.0,
            cpu_memory_gb=512.0,
            num_layers=80,
            hidden_dim=8192,
            num_heads=64,
            tp_size=2,
        )
        assert setup.config.num_gpus == 2
        assert setup.config.victim_sample_size == 96
        assert setup.config.shadow_size == 4096

    def test_get_block_manager(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=100,
            num_cpu_blocks=500,
        )
        manager = setup.get_block_manager()
        assert manager is not None
        assert manager.num_gpu_blocks == 100
        assert manager.num_cpu_blocks == 500

    def test_get_block_manager_raises_without_init(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        with pytest.raises(RuntimeError, match="vLLM not initialized"):
            setup.get_block_manager()


# =========================================================================
# Tests: Checkpoint cache (Database)
# =========================================================================

class TestCheckpointCache:
    def test_for_checkpoint_cache(self):
        setup = CTMTransformerSetup.for_checkpoint_cache(
            cache_size_mb=256,
        )
        assert setup._db_cache is not None
        assert CTMBackend.DATABASE in setup._initialized_backends

    def test_get_checkpoint_cache(self):
        setup = CTMTransformerSetup.for_checkpoint_cache(cache_size_mb=128)
        cache = setup.get_checkpoint_cache()
        assert cache is not None

    def test_get_checkpoint_cache_raises_without_init(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        with pytest.raises(RuntimeError, match="Database not initialized"):
            setup.get_checkpoint_cache()


# =========================================================================
# Tests: Stats and monitoring
# =========================================================================

class TestStatsMonitoring:
    def test_get_stats_training(self, fake_model):
        setup = CTMTransformerSetup.for_training(
            model=fake_model,
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        stats = setup.get_stats()
        assert "workload" in stats
        assert stats["workload"] == "training"
        assert "deepspeed_training" in stats

    def test_get_stats_inference(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=100,
            num_cpu_blocks=500,
        )
        stats = setup.get_stats()
        assert "vllm" in stats
        assert "deepspeed_inference" in stats

    def test_log_stats(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        output = setup.log_stats(step=100)
        assert "CTM+ Stats" in output
        assert "step=100" in output

    def test_reset_stats(self, fake_model):
        setup = CTMTransformerSetup.for_training(
            model=fake_model,
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        setup.register_model(fake_model)
        setup.begin_forward()
        setup.end_forward()
        setup.reset_stats()
        stats = setup.get_stats()
        ds_stats = stats["deepspeed_training"]
        # After reset, the underlying offload manager stats should be zeroed
        assert ds_stats.get("total_accesses", 0) == 0


# =========================================================================
# Tests: Error handling
# =========================================================================

class TestErrorHandling:
    def test_register_model_without_deepspeed_training(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=100,
            num_cpu_blocks=500,
        )
        with pytest.raises(RuntimeError):
            setup.register_model(FakeTransformerModel())

    def test_deepspeed_config_without_training(self):
        setup = CTMTransformerSetup.for_inference(
            num_gpu_blocks=100,
            num_cpu_blocks=500,
        )
        with pytest.raises(RuntimeError, match="DeepSpeed training not initialized"):
            setup.get_deepspeed_config()

    def test_allocate_without_vllm(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        with pytest.raises(RuntimeError, match="vLLM not initialized"):
            setup.allocate_kv_blocks(1, 5)

    def test_access_without_vllm(self):
        setup = CTMTransformerSetup.for_training(
            gpu_memory_gb=8.0,
            cpu_memory_gb=32.0,
        )
        with pytest.raises(RuntimeError, match="vLLM not initialized"):
            setup.access_kv_blocks(1, [0])
