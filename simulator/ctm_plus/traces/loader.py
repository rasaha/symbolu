"""
Trace loading utilities for CTM+ simulator.

Supports multiple trace formats:
- CSV: Simple comma-separated format
- MSR Cambridge: Microsoft Research block I/O traces
- Custom binary: Compact format for large traces

Also provides synthetic trace generators for testing.
"""

import csv
import random
import math
from dataclasses import dataclass
from typing import List, Iterator, Optional, Union
from pathlib import Path
from enum import IntEnum

from ..core.state import OpType


@dataclass
class TraceEvent:
    """
    A single memory access event.

    This is the standard internal format - all trace loaders
    convert to this format.
    """

    timestamp: int  # Relative timestamp (could be access count or ns)
    page_id: int  # Page being accessed
    op_type: OpType  # READ, WRITE, or PREFETCH
    size_bytes: int = 4096  # Size of access (default = 1 page)
    tenant_id: Optional[str] = None  # Owning tenant for multi-tenancy QoS
    numa_node: Optional[int] = None  # NUMA node of the accessing CPU

    @classmethod
    def from_csv_row(cls, row: dict) -> "TraceEvent":
        """Create from CSV row."""
        numa_raw = row.get("numa_node", row.get("node", None))
        return cls(
            timestamp=int(row.get("timestamp", row.get("time", 0))),
            page_id=int(row.get("page_id", row.get("page", row.get("address", 0)))),
            op_type=OpType(int(row.get("op_type", row.get("op", 0)))),
            size_bytes=int(row.get("size", 4096)),
            tenant_id=row.get("tenant_id", row.get("tenant", None)),
            numa_node=int(numa_raw) if numa_raw is not None else None,
        )


def load_trace(
    path: Union[str, Path],
    format: str = "auto",
    max_events: Optional[int] = None,
    page_size: int = 4096,
) -> List[TraceEvent]:
    """
    Load a trace file.

    Args:
        path: Path to trace file
        format: Trace format ("auto", "csv", "msr", "binary")
        max_events: Maximum number of events to load (None = all)
        page_size: Page size for address-to-page conversion

    Returns:
        List of TraceEvent objects
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    # Auto-detect format
    if format == "auto":
        if path.suffix == ".csv":
            format = "csv"
        elif path.suffix == ".bin":
            format = "binary"
        else:
            # Try to detect MSR format
            format = "msr"

    if format == "csv":
        return _load_csv_trace(path, max_events)
    elif format == "msr":
        return _load_msr_trace(path, max_events, page_size)
    elif format == "binary":
        return _load_binary_trace(path, max_events)
    else:
        raise ValueError(f"Unknown trace format: {format}")


def _load_csv_trace(path: Path, max_events: Optional[int]) -> List[TraceEvent]:
    """Load CSV format trace."""
    events = []

    with open(path, "r") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if max_events and i >= max_events:
                break

            try:
                event = TraceEvent.from_csv_row(row)
                events.append(event)
            except (ValueError, KeyError) as e:
                # Skip malformed rows
                continue

    return events


def _load_msr_trace(
    path: Path, max_events: Optional[int], page_size: int
) -> List[TraceEvent]:
    """
    Load MSR Cambridge trace format.

    MSR format: timestamp,hostname,disk,type,offset,size,response_time
    Type: 0=write, 1=read
    """
    events = []

    with open(path, "r") as f:
        for i, line in enumerate(f):
            if max_events and i >= max_events:
                break

            parts = line.strip().split(",")
            if len(parts) < 6:
                continue

            try:
                timestamp = int(parts[0])
                op_code = int(parts[3])
                offset = int(parts[4])
                size = int(parts[5])

                # Convert to page ID
                page_id = offset // page_size

                # MSR: 0=write, 1=read
                op_type = OpType.WRITE if op_code == 0 else OpType.READ

                events.append(TraceEvent(
                    timestamp=timestamp,
                    page_id=page_id,
                    op_type=op_type,
                    size_bytes=size,
                ))
            except (ValueError, IndexError):
                continue

    return events


def _load_binary_trace(path: Path, max_events: Optional[int]) -> List[TraceEvent]:
    """
    Load compact binary trace format.

    Format: 16 bytes per event
    - 8 bytes: timestamp (uint64)
    - 4 bytes: page_id (uint32)
    - 2 bytes: op_type (uint16)
    - 2 bytes: size_kb (uint16, size in KB)
    """
    import struct

    events = []
    record_format = "<QIHH"  # Little-endian: uint64, uint32, uint16, uint16
    record_size = struct.calcsize(record_format)

    with open(path, "rb") as f:
        i = 0
        while True:
            if max_events and i >= max_events:
                break

            data = f.read(record_size)
            if len(data) < record_size:
                break

            timestamp, page_id, op_type, size_kb = struct.unpack(record_format, data)
            events.append(TraceEvent(
                timestamp=timestamp,
                page_id=page_id,
                op_type=OpType(op_type),
                size_bytes=size_kb * 1024,
            ))
            i += 1

    return events


# =============================================================================
# Synthetic Trace Generators
# =============================================================================


def generate_synthetic_trace(
    pattern: str,
    num_events: int = 100000,
    num_pages: int = 10000,
    seed: int = 42,
) -> List[TraceEvent]:
    """
    Generate synthetic trace for testing.

    Args:
        pattern: Workload pattern
            - "uniform": Uniform random access
            - "zipf": Zipfian (power-law) access
            - "sequential": Sequential scan
            - "hotspot": Hot/cold with 80/20 rule
            - "temporal": Temporal locality (recent pages more likely)
            - "mixed": Mix of patterns
        num_events: Number of events to generate
        num_pages: Number of unique pages in working set
        seed: Random seed for reproducibility

    Returns:
        List of TraceEvent objects
    """
    random.seed(seed)

    generators = {
        "uniform": _gen_uniform,
        "zipf": _gen_zipf,
        "sequential": _gen_sequential,
        "hotspot": _gen_hotspot,
        "temporal": _gen_temporal,
        "mixed": _gen_mixed,
        "clustered": _gen_clustered,  # Tests cluster/group behavior
        "correlated": _gen_correlated,  # Tests pairwise correlations
    }

    if pattern not in generators:
        raise ValueError(f"Unknown pattern: {pattern}. Available: {list(generators.keys())}")

    return generators[pattern](num_events, num_pages)


def _gen_uniform(num_events: int, num_pages: int) -> List[TraceEvent]:
    """Uniform random access."""
    events = []
    for i in range(num_events):
        page_id = random.randint(0, num_pages - 1)
        op_type = OpType.READ if random.random() < 0.8 else OpType.WRITE
        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))
    return events


def _gen_zipf(num_events: int, num_pages: int, alpha: float = 1.2) -> List[TraceEvent]:
    """Zipfian (power-law) access - few pages get most accesses."""
    # Precompute Zipf distribution
    weights = [1.0 / (i + 1) ** alpha for i in range(num_pages)]
    total = sum(weights)
    probs = [w / total for w in weights]

    # Cumulative distribution for sampling
    cum_probs = []
    cumsum = 0
    for p in probs:
        cumsum += p
        cum_probs.append(cumsum)

    def sample_zipf() -> int:
        r = random.random()
        for i, cp in enumerate(cum_probs):
            if r <= cp:
                return i
        return num_pages - 1

    events = []
    for i in range(num_events):
        page_id = sample_zipf()
        op_type = OpType.READ if random.random() < 0.8 else OpType.WRITE
        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))
    return events


def _gen_sequential(num_events: int, num_pages: int) -> List[TraceEvent]:
    """Sequential scan (worst case for caching)."""
    events = []
    for i in range(num_events):
        page_id = i % num_pages
        op_type = OpType.READ
        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))
    return events


def _gen_hotspot(
    num_events: int,
    num_pages: int,
    hot_fraction: float = 0.2,
    hot_access_fraction: float = 0.8,
) -> List[TraceEvent]:
    """Hotspot: 20% of pages get 80% of accesses."""
    hot_pages = int(num_pages * hot_fraction)

    events = []
    for i in range(num_events):
        if random.random() < hot_access_fraction:
            # Access hot page
            page_id = random.randint(0, hot_pages - 1)
        else:
            # Access cold page
            page_id = random.randint(hot_pages, num_pages - 1)

        op_type = OpType.READ if random.random() < 0.8 else OpType.WRITE
        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))
    return events


def _gen_temporal(num_events: int, num_pages: int, window: int = 100) -> List[TraceEvent]:
    """Temporal locality: recently accessed pages more likely."""
    recent: List[int] = []
    events = []

    for i in range(num_events):
        if recent and random.random() < 0.7:
            # Access recent page
            page_id = random.choice(recent[-window:])
        else:
            # Access random page
            page_id = random.randint(0, num_pages - 1)

        recent.append(page_id)
        if len(recent) > window * 2:
            recent = recent[-window:]

        op_type = OpType.READ if random.random() < 0.8 else OpType.WRITE
        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))
    return events


def _gen_clustered(
    num_events: int,
    num_pages: int,
    num_clusters: int = 50,
    cluster_size: int = 20,
    intra_cluster_prob: float = 0.8,
    cluster_switch_prob: float = 0.02,
) -> List[TraceEvent]:
    """
    Clustered workload: pages grouped into clusters that get hot together.

    This tests CTM+'s ability to exploit correlated structure that LRU can't see.
    When one page in a cluster is accessed, other pages in the same cluster
    are likely to be accessed soon.

    Args:
        num_events: Number of events to generate
        num_pages: Total number of unique pages
        num_clusters: Number of clusters
        cluster_size: Pages per cluster
        intra_cluster_prob: Probability of staying in current cluster (0.8 = 80%)
        cluster_switch_prob: Probability of switching active cluster

    This workload challenges LRU because:
    - LRU only sees recency, not cluster membership
    - A cluster-aware algorithm can prefetch/protect related pages
    """
    # Create clusters (overlapping allowed)
    clusters = []
    for c in range(num_clusters):
        # Each cluster is a set of related page IDs
        base = (c * cluster_size) % num_pages
        cluster = [(base + i) % num_pages for i in range(cluster_size)]
        clusters.append(cluster)

    events = []
    active_cluster = 0
    recent_in_cluster = []

    for i in range(num_events):
        # Maybe switch active cluster (scene change)
        if random.random() < cluster_switch_prob:
            active_cluster = random.randint(0, num_clusters - 1)
            recent_in_cluster = []

        # Decide: access within cluster or random
        if random.random() < intra_cluster_prob:
            # Access page from active cluster
            cluster = clusters[active_cluster]

            # Bias toward recently accessed pages within cluster
            if recent_in_cluster and random.random() < 0.5:
                page_id = random.choice(recent_in_cluster[-5:])
            else:
                page_id = random.choice(cluster)

            recent_in_cluster.append(page_id)
            if len(recent_in_cluster) > 20:
                recent_in_cluster = recent_in_cluster[-10:]
        else:
            # Random access (noise)
            page_id = random.randint(0, num_pages - 1)

        op_type = OpType.READ if random.random() < 0.8 else OpType.WRITE
        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))

    return events


def _gen_correlated(
    num_events: int,
    num_pages: int,
    correlation_strength: float = 0.7,
    group_size: int = 8,
) -> List[TraceEvent]:
    """
    Correlated workload: accessing page A makes page B likely.

    This creates explicit pairwise correlations that CTM+'s coherence
    computation should be able to detect and exploit.

    Args:
        num_events: Number of events
        num_pages: Total pages
        correlation_strength: How strongly correlated accesses follow
        group_size: Size of correlated groups
    """
    # Create correlation groups
    num_groups = num_pages // group_size
    groups = [list(range(g * group_size, (g + 1) * group_size)) for g in range(num_groups)]

    # Build correlation map: page -> list of correlated pages
    correlations = {}
    for group in groups:
        for page in group:
            # Correlated with other pages in same group
            correlations[page] = [p for p in group if p != page]

    events = []
    last_page = random.randint(0, num_pages - 1)

    for i in range(num_events):
        if random.random() < correlation_strength and last_page in correlations:
            # Access correlated page
            page_id = random.choice(correlations[last_page])
        else:
            # Random access
            page_id = random.randint(0, num_pages - 1)

        last_page = page_id
        op_type = OpType.READ if random.random() < 0.8 else OpType.WRITE
        events.append(TraceEvent(timestamp=i, page_id=page_id, op_type=op_type))

    return events


def _gen_mixed(num_events: int, num_pages: int) -> List[TraceEvent]:
    """Mixed workload: phases of different patterns."""
    events = []
    phase_size = num_events // 4

    # Phase 1: Zipfian
    events.extend(_gen_zipf(phase_size, num_pages))

    # Phase 2: Sequential scan
    seq_events = _gen_sequential(phase_size, num_pages // 10)
    for e in seq_events:
        e.timestamp += phase_size
    events.extend(seq_events)

    # Phase 3: Hotspot
    hot_events = _gen_hotspot(phase_size, num_pages)
    for e in hot_events:
        e.timestamp += phase_size * 2
    events.extend(hot_events)

    # Phase 4: Temporal
    temp_events = _gen_temporal(phase_size, num_pages)
    for e in temp_events:
        e.timestamp += phase_size * 3
    events.extend(temp_events)

    return events


def save_trace_csv(events: List[TraceEvent], path: Union[str, Path]) -> None:
    """Save trace to CSV file."""
    path = Path(path)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "page_id", "op_type", "size"])

        for event in events:
            writer.writerow([
                event.timestamp,
                event.page_id,
                int(event.op_type),
                event.size_bytes,
            ])
