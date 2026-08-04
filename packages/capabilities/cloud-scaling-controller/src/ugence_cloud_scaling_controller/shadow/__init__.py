"""Shadow evaluation — read-only primitives for HPA/controller comparison.

Purely observational, zero write permissions: a divergence tracker, a read-only HPA
state watcher, and a proof-of-value reporter. The live-loop *runners*
(``ShadowRunner``, ``LiveEfficiencyShadow``) that can drive a real cluster and host
an operations RecommendEngine are NOT part of the advisory distribution — they live
in the monorepo-only ``cloud_scaling_operations.shadow`` namespace.
"""

from ugence_cloud_scaling_controller.shadow.divergence import (
    DivergenceTracker,
    DivergenceRecord,
    Verdict,
)
from ugence_cloud_scaling_controller.shadow.hpa_watcher import (
    HPAWatcher,
    HPASnapshot,
    HPAAction,
)
from ugence_cloud_scaling_controller.shadow.reporter import (
    ShadowReporter,
    ShadowReport,
)

__all__ = [
    "DivergenceTracker",
    "DivergenceRecord",
    "Verdict",
    "HPAWatcher",
    "HPASnapshot",
    "HPAAction",
    "ShadowReporter",
    "ShadowReport",
]
