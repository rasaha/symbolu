"""Metric rollup for benchmark runs.

The runner produces a :class:`RunResult` per (workload, policy)
cell. :func:`summarize` rolls a list of results into a JSON
blob suitable for pinning in CI; :func:`markdown_table` produces
the human-readable cell intended for the pitch deck.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class RunResult:
    """One (workload, policy, tier-config) cell."""

    workload_name: str
    policy_name: str
    tier_config_name: str

    n_decode_tokens: int

    # Per-tier counters.
    bytes_read: Mapping[str, int]
    bytes_written: Mapping[str, int]
    accesses_served: Mapping[str, int]
    cumulative_latency_ns: Mapping[str, float]
    evictions_to_tier: Mapping[str, int]

    # Derived headline numbers.
    hbm_hit_rate: float
    slow_tier_bytes_per_decode_token: float
    avg_access_latency_ns: float

    # Wall-clock + reproducer.
    wall_clock_seconds: float
    seed: int

    # Mode B provenance: identifies which counter-extraction
    # path actually populated the per-tier byte counts. Empty
    # string for Mode A runs (synthetic — no extraction needed).
    # Used by the runbook to diagnose when a Mode B cell shows
    # all-zero counters: "unavailable" → API path didn't match,
    # "vllm_0_7_no_swaps_observed" → API works but workload
    # didn't spill, "vllm_0_7_block_allocator_swaps" → real
    # measurements present.
    counter_source: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "workload_name": self.workload_name,
            "policy_name": self.policy_name,
            "tier_config_name": self.tier_config_name,
            "n_decode_tokens": self.n_decode_tokens,
            "bytes_read": dict(self.bytes_read),
            "bytes_written": dict(self.bytes_written),
            "accesses_served": dict(self.accesses_served),
            "cumulative_latency_ns": dict(self.cumulative_latency_ns),
            "evictions_to_tier": dict(self.evictions_to_tier),
            "hbm_hit_rate": self.hbm_hit_rate,
            "slow_tier_bytes_per_decode_token": self.slow_tier_bytes_per_decode_token,
            "avg_access_latency_ns": self.avg_access_latency_ns,
            "wall_clock_seconds": self.wall_clock_seconds,
            "seed": self.seed,
            "counter_source": self.counter_source,
        }


def summarize(results: Sequence[RunResult]) -> Dict[str, object]:
    """Roll a list of results into a dict structured for JSON
    output. Top level keys: 'cells' (list of per-result dicts)
    plus 'pairs' (list of (workload, baseline=lru) → CTM+ deltas).
    """
    cells: List[Dict[str, object]] = [r.to_dict() for r in results]
    by_workload_policy: Dict[str, Dict[str, RunResult]] = {}
    for r in results:
        by_workload_policy.setdefault(r.workload_name, {})[r.policy_name] = r

    pairs: List[Dict[str, object]] = []
    for workload_name, policy_map in by_workload_policy.items():
        baseline = policy_map.get("lru")
        if baseline is None:
            continue
        for policy_name, r in policy_map.items():
            if policy_name == "lru":
                continue
            base = baseline.slow_tier_bytes_per_decode_token
            policy_val = r.slow_tier_bytes_per_decode_token
            if base == 0:
                # LRU had no slow-tier reads on this workload (working
                # set fit in tier 0). Reduction is undefined when the
                # baseline is zero; we report None rather than ±inf so
                # the JSON output is well-formed (allow_nan=False).
                pct: Optional[float] = None if policy_val > 0 else 0.0
            else:
                pct = ((base - policy_val) / base) * 100.0
            pairs.append(
                {
                    "workload": workload_name,
                    "baseline": "lru",
                    "policy": policy_name,
                    "lru_slow_tier_bytes_per_token": base,
                    "policy_slow_tier_bytes_per_token": r.slow_tier_bytes_per_decode_token,
                    "reduction_pct_vs_lru": pct,
                }
            )
    return {"cells": cells, "pairs": pairs}


def to_json(summary: Mapping[str, object], *, sort_keys: bool = True) -> str:
    return json.dumps(
        summary, sort_keys=sort_keys, indent=2, allow_nan=False
    )


def markdown_table(results: Sequence[RunResult]) -> str:
    """Render the headline table. Columns: workload, policy,
    HBM hit rate, slow-tier bytes per decode token, avg latency."""
    if not results:
        return "| (no results) |\n"
    header = (
        "| Workload | Policy | Tier config | HBM hit rate | "
        "Slow-tier bytes/token | Avg access latency |\n"
        "|---|---|---|---:|---:|---:|\n"
    )
    rows = []
    for r in sorted(
        results,
        key=lambda x: (x.workload_name, x.tier_config_name, x.policy_name),
    ):
        rows.append(
            f"| {r.workload_name} | {r.policy_name} | {r.tier_config_name} "
            f"| {r.hbm_hit_rate*100:.1f}% "
            f"| {r.slow_tier_bytes_per_decode_token:,.0f} B "
            f"| {r.avg_access_latency_ns:,.0f} ns |\n"
        )
    return header + "".join(rows)
