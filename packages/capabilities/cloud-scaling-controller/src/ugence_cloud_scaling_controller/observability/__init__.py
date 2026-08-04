"""Observability — offline decision audit trail, benchmarks, edge-case harness.

Advisory-only: these components analyze and report; they do not open a network
listener or export telemetry. Live telemetry (HTTP metrics server, Prometheus push,
OpenTelemetry export) is NOT part of the advisory distribution — it lives in the
monorepo-only ``cloud_scaling_operations.observability`` namespace.
"""

from ugence_cloud_scaling_controller.observability.decision_log import (
    DecisionLogEntry,
    DecisionLogFormatter,
    DecisionPhase,
)
from ugence_cloud_scaling_controller.observability.benchmark import (
    BenchmarkConfig,
    BenchmarkHarness,
    BenchmarkReport,
    HPASimulator,
    ParameterSweep,
    PatternType,
    ScenarioScore,
    SweepReport,
    SweepVariant,
)
from ugence_cloud_scaling_controller.observability.edge_cases import (
    EdgeCaseHarness,
    EdgeCaseReport,
    EdgeCaseResult,
    EdgeScenario,
    FailureAttribution,
    FailureClass,
    InternalStateTrace,
    StateSnapshot,
)

__all__ = [
    "BenchmarkConfig",
    "BenchmarkHarness",
    "BenchmarkReport",
    "EdgeCaseHarness",
    "EdgeCaseReport",
    "EdgeCaseResult",
    "EdgeScenario",
    "FailureAttribution",
    "FailureClass",
    "InternalStateTrace",
    "StateSnapshot",
    "DecisionLogEntry",
    "DecisionLogFormatter",
    "DecisionPhase",
    "HPASimulator",
    "ParameterSweep",
    "PatternType",
    "ScenarioScore",
    "SweepReport",
    "SweepVariant",
]
