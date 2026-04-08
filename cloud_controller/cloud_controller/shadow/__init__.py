"""Shadow Mode — run controller alongside HPA, log divergence, prove value.

Stage 3: Purely observational. Zero write permissions.
Compares controller recommendations against HPA actions,
tracks outcomes, and generates proof-of-value reports.
"""

from cloud_controller.shadow.divergence import (
    DivergenceTracker,
    DivergenceRecord,
    Verdict,
)
from cloud_controller.shadow.hpa_watcher import (
    HPAWatcher,
    HPASnapshot,
    HPAAction,
)
from cloud_controller.shadow.reporter import (
    ShadowReporter,
    ShadowReport,
)
from cloud_controller.shadow.runner import (
    ShadowRunner,
    ShadowConfig,
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
    "ShadowRunner",
    "ShadowConfig",
]
