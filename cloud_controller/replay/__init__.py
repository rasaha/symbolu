"""Track B — offline replay of real production traces through the unmodified
cloud-controller control core.

Public API:
    TraceReplayHarness, ReplayResult        — the replay engine
    EfficiencyObserver                       — read-only estimator+guard (shared with Track A)
    ReplayPrometheusClient                   — drives the existing Stage-2/3 pipeline from a trace
    adapters.*                               — real-trace → workload-series converters
"""

from cloud_controller.replay.adapters.base import (
    AdapterStatus,
    TraceAdapter,
    TraceSeries,
)
from cloud_controller.replay.efficiency_observer import (
    EfficiencyObserver,
    ObservedCycle,
)
from cloud_controller.replay.harness import (
    ReplayResult,
    ReplayRun,
    TraceReplayHarness,
)
from cloud_controller.replay.replay_source import ReplayPrometheusClient

__all__ = [
    "AdapterStatus",
    "TraceAdapter",
    "TraceSeries",
    "EfficiencyObserver",
    "ObservedCycle",
    "ReplayResult",
    "ReplayRun",
    "TraceReplayHarness",
    "ReplayPrometheusClient",
]
