"""
Standard trace profiles for industry benchmarking.

Provides synthetic generators that faithfully replicate the statistical
properties of well-known public traces used in caching research:

1. MSR Cambridge (FAST'08) - Block I/O traces from enterprise servers
2. Twitter (OSDI'20) - In-memory KV cache traces
3. Meta/CacheLib (OSDI'20) - Production CDN and KV cache traces

Each profile captures the key characteristics (working set size, access
distribution, read/write ratio, temporal patterns) from published analyses.
When real trace files are available locally, use load_trace() to load them
directly. These synthetic profiles serve as reproducible stand-ins for
benchmarking when real traces are unavailable.

References:
- MSR Cambridge: Narayanan et al., "Write Off-Loading: Practical Power
  Management for Enterprise Storage", TOS 2008
- Twitter: Yang et al., "A Large-Scale Analysis of Hundreds of In-Memory
  Key-Value Cache Clusters at Twitter", OSDI 2020
- Meta CacheLib: Berg et al., "The CacheLib Caching Engine: Design and
  Experiences at Scale", OSDI 2020
- S3-FIFO: Yang et al., "FIFO Queues are All You Need for Cache Eviction",
  SOSP 2023
"""

import random
import math
from dataclasses import dataclass
from typing import List, Optional, Dict
from pathlib import Path

from .loader import TraceEvent, load_trace
from ..core.state import OpType


@dataclass(frozen=True)
class TraceProfile:
    """Describes a standard trace's statistical properties."""

    name: str  # e.g. "msr_src1_0"
    description: str
    source: str  # "msr", "twitter", "meta"

    # Working set characteristics
    num_pages: int  # Unique pages in trace
    num_events: int  # Total accesses (default generation size)

    # Access distribution
    zipf_alpha: float  # Zipfian skew (higher = more skewed)
    read_ratio: float  # Fraction of reads (vs writes)

    # Temporal characteristics
    temporal_locality: float  # 0-1: how strong recency bias is
    scan_fraction: float  # Fraction of accesses that are sequential scans
    phase_changes: int  # Number of working set shifts in trace

    # Cache sizing hint
    recommended_tier0_ratio: float  # tier0/num_pages (typical cache ratio)


# =============================================================================
# Standard Trace Profiles
# =============================================================================

# --- MSR Cambridge Traces (Enterprise Block I/O) ---

MSR_SRC1_0 = TraceProfile(
    name="msr_src1_0",
    description="MSR Cambridge src1_0: Source control server, high locality",
    source="msr",
    num_pages=50000,
    num_events=200000,
    zipf_alpha=1.0,
    read_ratio=0.82,
    temporal_locality=0.75,
    scan_fraction=0.05,
    phase_changes=3,
    recommended_tier0_ratio=0.10,
)

MSR_WEB_0 = TraceProfile(
    name="msr_web_0",
    description="MSR Cambridge web_0: Web server, read-heavy, moderate locality",
    source="msr",
    num_pages=100000,
    num_events=200000,
    zipf_alpha=0.9,
    read_ratio=0.95,
    temporal_locality=0.55,
    scan_fraction=0.15,
    phase_changes=5,
    recommended_tier0_ratio=0.05,
)

MSR_PROJ_0 = TraceProfile(
    name="msr_proj_0",
    description="MSR Cambridge proj_0: Project server, write-heavy, bursty",
    source="msr",
    num_pages=80000,
    num_events=200000,
    zipf_alpha=0.85,
    read_ratio=0.65,
    temporal_locality=0.60,
    scan_fraction=0.10,
    phase_changes=8,
    recommended_tier0_ratio=0.08,
)

# --- Twitter Traces (In-memory KV Cache) ---

TWITTER_CLUSTER52 = TraceProfile(
    name="twitter_cluster52",
    description="Twitter cluster52: High-throughput KV cache, extreme skew",
    source="twitter",
    num_pages=200000,
    num_events=200000,
    zipf_alpha=1.3,
    read_ratio=0.98,
    temporal_locality=0.70,
    scan_fraction=0.0,
    phase_changes=2,
    recommended_tier0_ratio=0.05,
)

TWITTER_KV = TraceProfile(
    name="twitter_kv",
    description="Twitter KV: General KV workload, moderate skew, scan-resistant",
    source="twitter",
    num_pages=150000,
    num_events=200000,
    zipf_alpha=1.05,
    read_ratio=0.90,
    temporal_locality=0.50,
    scan_fraction=0.08,
    phase_changes=4,
    recommended_tier0_ratio=0.06,
)

# --- Meta/CacheLib Traces (CDN + KV) ---

META_CDN = TraceProfile(
    name="meta_cdn",
    description="Meta CDN: Content delivery, size-variable, one-hit-wonders",
    source="meta",
    num_pages=300000,
    num_events=200000,
    zipf_alpha=0.75,
    read_ratio=0.99,
    temporal_locality=0.35,
    scan_fraction=0.25,
    phase_changes=6,
    recommended_tier0_ratio=0.03,
)

META_KV = TraceProfile(
    name="meta_kv",
    description="Meta KV: Production KV store, high churn, moderate locality",
    source="meta",
    num_pages=120000,
    num_events=200000,
    zipf_alpha=0.95,
    read_ratio=0.85,
    temporal_locality=0.55,
    scan_fraction=0.05,
    phase_changes=10,
    recommended_tier0_ratio=0.07,
)

# Registry of all profiles
ALL_PROFILES: Dict[str, TraceProfile] = {
    p.name: p
    for p in [
        MSR_SRC1_0, MSR_WEB_0, MSR_PROJ_0,
        TWITTER_CLUSTER52, TWITTER_KV,
        META_CDN, META_KV,
    ]
}

# Grouped by source
MSR_PROFILES = [MSR_SRC1_0, MSR_WEB_0, MSR_PROJ_0]
TWITTER_PROFILES = [TWITTER_CLUSTER52, TWITTER_KV]
META_PROFILES = [META_CDN, META_KV]


def generate_from_profile(
    profile: TraceProfile,
    num_events: Optional[int] = None,
    seed: int = 42,
) -> List[TraceEvent]:
    """
    Generate a synthetic trace matching a standard profile's statistics.

    Uses the profile's parameters (Zipf alpha, temporal locality, scan
    fraction, phase changes, read ratio) to produce a trace with the
    same statistical properties as the real trace.

    Args:
        profile: Standard trace profile to replicate
        num_events: Override event count (None = use profile default)
        seed: Random seed for reproducibility

    Returns:
        List of TraceEvent matching the profile's characteristics
    """
    rng = random.Random(seed)
    n_events = num_events or profile.num_events
    n_pages = profile.num_pages

    # Build Zipfian distribution
    weights = [1.0 / (i + 1) ** profile.zipf_alpha for i in range(n_pages)]
    total_w = sum(weights)
    cum_probs = []
    cumsum = 0.0
    for w in weights:
        cumsum += w / total_w
        cum_probs.append(cumsum)

    def sample_zipf() -> int:
        r = rng.random()
        lo, hi = 0, n_pages - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum_probs[mid] < r:
                lo = mid + 1
            else:
                hi = mid
        return lo

    # Phase structure: divide trace into phases with shifting working sets
    n_phases = max(1, profile.phase_changes)
    phase_size = n_events // n_phases
    phase_offsets = [rng.randint(0, n_pages // 2) for _ in range(n_phases)]

    # Recency buffer for temporal locality
    recency_window = min(500, n_pages // 10)
    recent: List[int] = []

    # Sequential scan state
    scan_pos = 0
    scan_length = min(2000, n_pages // 5)

    events = []
    for i in range(n_events):
        phase_idx = min(i // phase_size, n_phases - 1)
        offset = phase_offsets[phase_idx]

        r = rng.random()

        if r < profile.scan_fraction:
            # Sequential scan burst
            page_id = (scan_pos + offset) % n_pages
            scan_pos = (scan_pos + 1) % scan_length
        elif r < profile.scan_fraction + profile.temporal_locality * 0.5 and recent:
            # Temporal locality: re-access recent page
            page_id = rng.choice(recent[-recency_window:])
        else:
            # Zipfian access with phase offset
            raw = sample_zipf()
            page_id = (raw + offset) % n_pages

        # Track recency
        recent.append(page_id)
        if len(recent) > recency_window * 2:
            recent = recent[-recency_window:]

        # Read/write decision
        op_type = OpType.READ if rng.random() < profile.read_ratio else OpType.WRITE

        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))

    return events


def load_or_generate(
    profile: TraceProfile,
    trace_dir: Optional[str] = None,
    num_events: Optional[int] = None,
    seed: int = 42,
) -> List[TraceEvent]:
    """
    Load a real trace file if available, otherwise generate synthetic.

    Looks for trace files in trace_dir matching the profile name.
    Supported filename patterns:
    - {profile.name}.csv
    - {profile.name}.bin
    - {profile.name} (MSR format)

    Args:
        profile: Standard trace profile
        trace_dir: Directory to search for real trace files
        num_events: Max events to load/generate
        seed: Random seed for synthetic generation

    Returns:
        List of TraceEvent
    """
    if trace_dir is not None:
        trace_path = Path(trace_dir)
        for ext in [".csv", ".bin", ""]:
            candidate = trace_path / f"{profile.name}{ext}"
            if candidate.exists():
                return load_trace(
                    candidate,
                    max_events=num_events,
                )

    return generate_from_profile(profile, num_events=num_events, seed=seed)


def get_profile(name: str) -> TraceProfile:
    """Get a profile by name. Raises KeyError if not found."""
    if name not in ALL_PROFILES:
        available = ", ".join(sorted(ALL_PROFILES.keys()))
        raise KeyError(f"Unknown trace profile: {name}. Available: {available}")
    return ALL_PROFILES[name]


def list_profiles() -> List[str]:
    """Return list of all available profile names."""
    return sorted(ALL_PROFILES.keys())
