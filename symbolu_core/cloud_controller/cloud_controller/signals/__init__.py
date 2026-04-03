"""Signal ingestion, normalization, and pipeline.

Stage 2: Prometheus → Normalizer → Controller pipeline.
"""

from symbolu_core.cloud_controller.signals.prometheus import (
    PrometheusClient,
    PrometheusConfig,
    DEFAULT_QUERIES,
    K8S_QUERIES,
)
from symbolu_core.cloud_controller.signals.normalizer import (
    SignalNormalizer,
    NormalizerConfig,
    MetricSpec,
    NormalizationResult,
)
from symbolu_core.cloud_controller.signals.pipeline import (
    SignalPipeline,
    PipelineConfig,
    CycleResult,
)

__all__ = [
    "PrometheusClient",
    "PrometheusConfig",
    "DEFAULT_QUERIES",
    "K8S_QUERIES",
    "SignalNormalizer",
    "NormalizerConfig",
    "MetricSpec",
    "NormalizationResult",
    "SignalPipeline",
    "PipelineConfig",
    "CycleResult",
]
