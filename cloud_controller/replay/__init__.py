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
from cloud_controller.replay.tier_a import (
    DEFAULT_TIER_A_SPEC,
    APCYEstimate,
    ClusterTierAResult,
    IncidentWindow,
    TierAEpisode,
    TierASpec,
    TierBEvent,
    compute_apcy,
    detect_tier_a,
    emit_worksheet,
    emit_worksheets,
    observe_trace,
)

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
    # Tier-A detector + APCY (pre-registered; see TIER_A_DETECTOR_SPEC.md)
    "DEFAULT_TIER_A_SPEC",
    "TierASpec",
    "IncidentWindow",
    "TierAEpisode",
    "TierBEvent",
    "ClusterTierAResult",
    "APCYEstimate",
    "observe_trace",
    "detect_tier_a",
    "compute_apcy",
    "emit_worksheet",
    "emit_worksheets",
]
