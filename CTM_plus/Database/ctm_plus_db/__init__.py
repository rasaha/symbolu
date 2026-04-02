"""
CTM+ KV Cache Policy Simulator.

A lightweight simulator that models LLM inference access patterns
and evaluates eviction policies. Research tool, not production code.

Usage:
    from ctm_plus_db import KVCacheSimulator, PolicyType, compare_policies

    # Single run
    sim = KVCacheSimulator(max_blocks=256, policy_type=PolicyType.CTM_PLUS)
    sim.add_sequence(seq_id=0, context_length=512)
    sim.prefill_sequence(0)
    for _ in range(128):
        sim.decode_step(0)
    print(sim.get_metrics())

    # Compare all policies
    results = compare_policies(max_blocks=256, num_sequences=4)
"""

from .buffer_pool import (
    KVCacheSimulator,
    PolicyType,
    BlockType,
    Phase,
    compare_policies,
    run_workload,
)
from .config import SimulationConfig

__version__ = "0.3.0"
__all__ = [
    "KVCacheSimulator",
    "PolicyType",
    "BlockType",
    "Phase",
    "SimulationConfig",
    "compare_policies",
    "run_workload",
]
