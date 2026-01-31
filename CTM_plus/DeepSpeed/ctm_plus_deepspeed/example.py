#!/usr/bin/env python3
"""
Example: CTM+ Offload Manager for DeepSpeed

Demonstrates how to use CTM+ for intelligent memory offloading
in DeepSpeed training and inference scenarios.
"""

import random
import time
from typing import List, Dict

from ctm_plus_deepspeed import (
    CTMOffloadManager,
    CTMZeROOffload,
    CTMInferenceManager,
    CTMDeepSpeedConfig,
)


def simulate_model_tensors(
    num_layers: int = 24,
    hidden_size: int = 4096,
    intermediate_size: int = 11008,
) -> Dict[str, Dict]:
    """Generate tensor metadata for a transformer model."""
    tensors = {}
    bytes_per_param = 4  # FP32

    for layer in range(num_layers):
        # Attention weights
        tensors[f"layer.{layer}.self_attn.q_proj"] = {
            "size": hidden_size * hidden_size * bytes_per_param,
            "type": "attention",
        }
        tensors[f"layer.{layer}.self_attn.k_proj"] = {
            "size": hidden_size * hidden_size * bytes_per_param,
            "type": "attention",
        }
        tensors[f"layer.{layer}.self_attn.v_proj"] = {
            "size": hidden_size * hidden_size * bytes_per_param,
            "type": "attention",
        }
        tensors[f"layer.{layer}.self_attn.o_proj"] = {
            "size": hidden_size * hidden_size * bytes_per_param,
            "type": "attention",
        }

        # MLP weights
        tensors[f"layer.{layer}.mlp.gate_proj"] = {
            "size": hidden_size * intermediate_size * bytes_per_param,
            "type": "mlp",
        }
        tensors[f"layer.{layer}.mlp.up_proj"] = {
            "size": hidden_size * intermediate_size * bytes_per_param,
            "type": "mlp",
        }
        tensors[f"layer.{layer}.mlp.down_proj"] = {
            "size": intermediate_size * hidden_size * bytes_per_param,
            "type": "mlp",
        }

        # Norms
        tensors[f"layer.{layer}.input_layernorm"] = {
            "size": hidden_size * bytes_per_param,
            "type": "norm",
        }
        tensors[f"layer.{layer}.post_attention_layernorm"] = {
            "size": hidden_size * bytes_per_param,
            "type": "norm",
        }

    return tensors


def simulate_training_step(
    offload_manager: CTMOffloadManager,
    tensor_ids: List[str],
    num_steps: int = 100,
) -> Dict:
    """Simulate training forward/backward passes."""
    results = {"steps": 0, "total_time": 0.0}

    for step in range(num_steps):
        step_start = time.time()

        # Forward pass - access in order
        for tid in tensor_ids:
            offload_manager.on_access(tid, in_compute_graph=True)

        # Backward pass - access in reverse order
        for tid in reversed(tensor_ids):
            offload_manager.on_access(tid, in_compute_graph=True)

        # Release from compute graph
        offload_manager.set_compute_graph(tensor_ids, False)

        results["steps"] += 1
        results["total_time"] += time.time() - step_start

    return results


def demo_offload_manager():
    """Demonstrate basic CTM+ offload manager."""
    print("=" * 60)
    print("CTM+ Offload Manager Demo")
    print("=" * 60)

    # 40GB GPU, 256GB CPU
    gpu_memory = 40 * 1024**3
    cpu_memory = 256 * 1024**3

    config = CTMDeepSpeedConfig.for_training()
    manager = CTMOffloadManager(
        gpu_memory_bytes=gpu_memory,
        cpu_memory_bytes=cpu_memory,
        config=config,
    )

    print(f"\nConfiguration:")
    print(f"  GPU Memory: {gpu_memory / 1024**3:.1f} GB")
    print(f"  CPU Memory: {cpu_memory / 1024**3:.1f} GB")
    print(f"  Smart Offload: {config.enable_smart_offload}")
    print(f"  Prefetch Ahead: {config.prefetch_ahead}")

    # Register model tensors
    tensors = simulate_model_tensors(num_layers=24)
    tensor_ids = []

    print(f"\nRegistering {len(tensors)} tensors...")
    for name, info in tensors.items():
        tensor_id = name
        manager.register_tensor(
            tensor_id=tensor_id,
            name=name,
            size_bytes=info["size"],
        )
        tensor_ids.append(tensor_id)

    memory = manager.get_memory_stats()
    print(f"\nInitial Memory State:")
    print(f"  GPU: {memory['gpu_used_bytes'] / 1024**3:.2f} / {memory['gpu_total_bytes'] / 1024**3:.1f} GB ({memory['gpu_utilization']:.1%})")
    print(f"  CPU: {memory['cpu_used_bytes'] / 1024**3:.2f} / {memory['cpu_total_bytes'] / 1024**3:.1f} GB")

    # Simulate training
    print("\nRunning training simulation (100 steps)...")
    start = time.time()
    results = simulate_training_step(manager, tensor_ids, num_steps=100)
    elapsed = time.time() - start

    stats = manager.get_stats()
    print(f"\nResults:")
    print(f"  Training Steps: {results['steps']}")
    print(f"  Total Time: {elapsed:.2f}s")
    print(f"  GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
    print(f"  Offloads: {stats['offloads']}")
    print(f"  Prefetches: {stats['prefetches']}")
    print(f"  Smart Selections: {stats['smart_selections']}")
    print(f"  Adaptive p: {stats['adaptive_p']:.3f}")


def demo_zero_offload():
    """Demonstrate ZeRO-Offload integration."""
    print("\n" + "=" * 60)
    print("CTM+ ZeRO-Offload Demo")
    print("=" * 60)

    gpu_memory = 24 * 1024**3  # Smaller GPU
    cpu_memory = 128 * 1024**3

    config = CTMDeepSpeedConfig.for_zero_offload()
    zero = CTMZeROOffload(
        gpu_memory_bytes=gpu_memory,
        cpu_memory_bytes=cpu_memory,
        config=config,
        zero_stage=2,
    )

    print(f"\nConfiguration:")
    print(f"  ZeRO Stage: 2")
    print(f"  GPU Memory: {gpu_memory / 1024**3:.1f} GB")
    print(f"  CPU Memory: {cpu_memory / 1024**3:.1f} GB")

    # Register parameters and optimizer states
    tensors = simulate_model_tensors(num_layers=12)
    param_size = 4096 * 4096 * 4  # Example param size

    print(f"\nRegistering parameters and optimizer states...")
    for name, info in list(tensors.items())[:20]:  # First 20 tensors
        param_id = f"param.{name}"
        zero.register_parameter(
            param_id=param_id,
            name=name,
            size_bytes=info["size"],
        )

        # Adam optimizer states (momentum + variance)
        zero.register_optimizer_state(
            state_id=f"opt.{name}.momentum",
            name=name,
            size_bytes=info["size"],
            param_id=param_id,
            state_type="momentum",
        )
        zero.register_optimizer_state(
            state_id=f"opt.{name}.variance",
            name=name,
            size_bytes=info["size"],
            param_id=param_id,
            state_type="variance",
        )

    # Simulate training
    print("\nSimulating training steps...")
    for step in range(10):
        zero.begin_forward()
        zero.end_forward()
        zero.begin_backward()
        zero.end_backward()
        zero.step()

    stats = zero.get_stats()
    print(f"\nResults:")
    print(f"  GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
    print(f"  Offloads: {stats['offloads']}")
    print(f"  Prefetches: {stats['prefetches']}")
    print(f"  Adaptive p: {stats['adaptive_p']:.3f}")
    print(f"  GPU Usage: {stats['gpu_utilization']:.1%}")


def demo_inference():
    """Demonstrate inference manager."""
    print("\n" + "=" * 60)
    print("CTM+ Inference Manager Demo")
    print("=" * 60)

    gpu_memory = 16 * 1024**3  # Limited GPU
    cpu_memory = 64 * 1024**3
    num_layers = 32

    config = CTMDeepSpeedConfig.for_inference()
    inference = CTMInferenceManager(
        gpu_memory_bytes=gpu_memory,
        cpu_memory_bytes=cpu_memory,
        config=config,
        num_layers=num_layers,
    )

    print(f"\nConfiguration:")
    print(f"  GPU Memory: {gpu_memory / 1024**3:.1f} GB")
    print(f"  Layers: {num_layers}")
    print(f"  Prefetch Ahead: {config.prefetch_ahead}")

    # Register layers
    hidden_size = 4096
    bytes_per_param = 2  # FP16 for inference

    print(f"\nRegistering {num_layers} transformer layers...")
    for layer_idx in range(num_layers):
        weights = {
            "q_proj": (f"layer.{layer_idx}.q", hidden_size * hidden_size * bytes_per_param),
            "k_proj": (f"layer.{layer_idx}.k", hidden_size * hidden_size * bytes_per_param),
            "v_proj": (f"layer.{layer_idx}.v", hidden_size * hidden_size * bytes_per_param),
            "o_proj": (f"layer.{layer_idx}.o", hidden_size * hidden_size * bytes_per_param),
            "mlp": (f"layer.{layer_idx}.mlp", hidden_size * 4 * hidden_size * bytes_per_param),
        }

        # First half on GPU, second half on CPU
        initial_on_gpu = layer_idx < num_layers // 2
        inference.register_layer(layer_idx, weights, initial_on_gpu)

    memory = inference.offload_manager.get_memory_stats()
    print(f"\nInitial Memory State:")
    print(f"  GPU: {memory['gpu_used_bytes'] / 1024**3:.2f} GB ({memory['gpu_utilization']:.1%})")
    print(f"  CPU: {memory['cpu_used_bytes'] / 1024**3:.2f} GB")

    # Simulate generation
    print("\nSimulating generation (100 tokens)...")
    inference.begin_generation()

    for token in range(100):
        for layer_idx in range(num_layers):
            inference.on_layer_forward(layer_idx)

    inference.end_generation()

    stats = inference.get_stats()
    print(f"\nResults:")
    print(f"  GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
    print(f"  Offloads: {stats['offloads']}")
    print(f"  Prefetches: {stats['prefetches']}")
    print(f"  GPU Layers: {stats['gpu_layers']}")
    print(f"  CPU Layers: {stats['cpu_layers']}")
    print(f"  Mixed Layers: {stats['mixed_layers']}")


def compare_configs():
    """Compare different CTM+ configurations."""
    print("\n" + "=" * 60)
    print("CTM+ Configuration Comparison")
    print("=" * 60)

    configs = [
        ("Default", CTMDeepSpeedConfig()),
        ("Training", CTMDeepSpeedConfig.for_training()),
        ("Inference", CTMDeepSpeedConfig.for_inference()),
        ("ZeRO-Offload", CTMDeepSpeedConfig.for_zero_offload()),
        ("Large Model", CTMDeepSpeedConfig.for_large_model()),
    ]

    gpu_memory = 24 * 1024**3
    cpu_memory = 128 * 1024**3

    tensors = simulate_model_tensors(num_layers=16)
    tensor_ids = list(tensors.keys())

    for name, config in configs:
        manager = CTMOffloadManager(
            gpu_memory_bytes=gpu_memory,
            cpu_memory_bytes=cpu_memory,
            config=config,
        )

        for tid, info in tensors.items():
            manager.register_tensor(tid, tid, info["size"])

        # Simulate workload
        for _ in range(50):
            for tid in tensor_ids:
                manager.on_access(tid, in_compute_graph=True)
            manager.set_compute_graph(tensor_ids, False)

        stats = manager.get_stats()
        print(f"\n{name}:")
        print(f"  GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
        print(f"  Offloads: {stats['offloads']}")
        print(f"  Prefetches: {stats['prefetches']}")
        print(f"  Adaptive p: {stats['adaptive_p']:.3f}")


def main():
    print("CTM+ DeepSpeed Integration - Examples")
    print("=" * 60)

    demo_offload_manager()
    demo_zero_offload()
    demo_inference()
    compare_configs()


if __name__ == "__main__":
    main()
