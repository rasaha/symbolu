"""Mode A — synthetic runner.

End-to-end driver: take a workload + a policy + a tier
configuration, walk the workload's trace events, drive the
:class:`TieredCache`, and return a :class:`RunResult`.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

from ctm_bench.policies import (
    AccessContext,
    BenchConfig,
    Policy,
    get_policy,
)
from ctm_bench.metrics import RunResult
from ctm_bench.tier_model import (
    DEFAULT_BLOCK_BYTES,
    TierSpec,
    TieredCache,
)
from ctm_bench.workload import (
    AccessPattern,
    WorkloadSpec,
    generate,
)


# Default fraction of the working set that fits in tier 0. Set
# below 1.0 so spillover always engages — otherwise the
# benchmark is uninformative (no eviction pressure).
DEFAULT_HBM_OVERSUBSCRIPTION: float = 0.4


def _tier_0_capacity_blocks_for(
    spec: WorkloadSpec,
    oversubscription: float,
) -> int:
    """Pick tier-0 capacity that forces spillover.

    capacity = working_set * oversubscription
    Where working_set ≈ all unique blocks across concurrent seqs.
    """
    if not (0.0 < oversubscription < 1.0):
        raise ValueError(
            f"oversubscription must be in (0, 1); got {oversubscription}"
        )
    working_set_blocks = spec.total_unique_blocks()
    capacity = max(8, int(working_set_blocks * oversubscription))
    return capacity


def run_sim(
    spec: WorkloadSpec,
    policy_name: str,
    tier_specs: Tuple[TierSpec, ...],
    *,
    tier_config_name: str = "custom",
    block_bytes: int = DEFAULT_BLOCK_BYTES,
    hbm_oversubscription: float = DEFAULT_HBM_OVERSUBSCRIPTION,
    n_victims_per_evict: int = 4,
    attention_ema_alpha: Optional[float] = None,
) -> RunResult:
    """Drive the workload through the policy + cache and return
    a :class:`RunResult`.

    The tier 0 capacity is set so that the working set spills.
    For a comparable benchmark across policies, every policy
    sees the *same* tier-0 capacity for a given workload — the
    capacity is derived from the workload spec, not the policy.
    """
    if n_victims_per_evict <= 0:
        raise ValueError(
            f"n_victims_per_evict must be positive; got {n_victims_per_evict}"
        )
    # Build tier 0 to fit only a fraction of the working set.
    tier_0_capacity_blocks = _tier_0_capacity_blocks_for(
        spec, hbm_oversubscription
    )
    tier_0_bytes = tier_0_capacity_blocks * block_bytes
    # Override tier 0 capacity in the spec list (immutable, so
    # rebuild the tuple).
    tiers_for_run = (
        TierSpec(
            name=tier_specs[0].name,
            capacity_bytes=tier_0_bytes,
            read_latency_ns=tier_specs[0].read_latency_ns,
            write_latency_ns=tier_specs[0].write_latency_ns,
            read_bw_bytes_per_s=tier_specs[0].read_bw_bytes_per_s,
            write_bw_bytes_per_s=tier_specs[0].write_bw_bytes_per_s,
        ),
        *tier_specs[1:],
    )

    cache = TieredCache(tiers=tiers_for_run, block_bytes=block_bytes)
    policy = get_policy(
        policy_name,
        BenchConfig(
            max_blocks=tier_0_capacity_blocks,
            block_size=spec.block_size_tokens,
            seed=spec.seed,
            attention_ema_alpha=attention_ema_alpha,
        ),
    )
    for sid in range(spec.n_concurrent_seqs):
        policy.register_sequence(sid)

    n_decode_tokens = 0
    wall_start = time.perf_counter()
    for event in generate(spec):
        ctx = AccessContext(
            seq_id=event.seq_id,
            position=event.position,
            seq_len=event.seq_len,
            attention_weight=event.attention_weight,
            is_prefill=event.is_prefill,
        )
        # Inform the policy first so it has up-to-date state for
        # the eviction decision below.
        policy.on_access(event.block_id, ctx)
        # If the block isn't in tier 0 we'll need room to install
        # it — evict if full *before* asking the cache to access
        # the block, so the cache install path doesn't raise.
        if (
            event.block_id not in cache._residency[0]  # noqa: SLF001
            and cache.tier_full(0)
        ):
            victims = policy.select_victims(n_victims_per_evict)
            if not victims:
                # The policy has nothing it's willing to evict;
                # force one out via the LRU-of-residence (cache
                # insertion order). This is the conservative
                # fallback that also ensures forward progress.
                resident = list(cache._residency[0].keys())  # noqa: SLF001
                victims = resident[:1]
            cache.evict_from_tier_0(victims)
            for v in victims:
                policy.on_evict(v)
        cache.access(event.block_id)
        if not event.is_prefill:
            # Each non-prefill event corresponds to exactly one
            # decode-step access from the workload's perspective;
            # we count distinct decode steps via the "newly-
            # generated token" event (position == seq_len-1).
            if event.position == event.seq_len - 1:
                n_decode_tokens += 1
    wall_end = time.perf_counter()

    # Roll counters into RunResult.
    counters = cache.counters
    tier_0_name = tiers_for_run[0].name
    slow_tier_names = [t.name for t in tiers_for_run[1:]]
    slow_tier_total_bytes = sum(
        counters.bytes_read.get(n, 0) for n in slow_tier_names
    )
    total_accesses = sum(counters.accesses_served.values())
    hbm_hits = counters.accesses_served.get(tier_0_name, 0)
    hbm_hit_rate = hbm_hits / total_accesses if total_accesses else 0.0
    total_latency = sum(counters.cumulative_latency_ns.values())
    avg_latency = total_latency / total_accesses if total_accesses else 0.0
    slow_tier_per_token = (
        slow_tier_total_bytes / n_decode_tokens
        if n_decode_tokens
        else 0.0
    )

    return RunResult(
        workload_name=spec.name,
        policy_name=policy_name,
        tier_config_name=tier_config_name,
        n_decode_tokens=n_decode_tokens,
        bytes_read=dict(counters.bytes_read),
        bytes_written=dict(counters.bytes_written),
        accesses_served=dict(counters.accesses_served),
        cumulative_latency_ns=dict(counters.cumulative_latency_ns),
        evictions_to_tier=dict(counters.evictions_to_tier),
        hbm_hit_rate=hbm_hit_rate,
        slow_tier_bytes_per_decode_token=slow_tier_per_token,
        avg_access_latency_ns=avg_latency,
        wall_clock_seconds=wall_end - wall_start,
        seed=spec.seed,
    )
