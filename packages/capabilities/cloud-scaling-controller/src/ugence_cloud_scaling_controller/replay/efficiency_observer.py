"""Back-compat shim — EfficiencyObserver now lives in observability/.

Kept so `from ugence_cloud_scaling_controller.replay.efficiency_observer import ...` keeps
working. New imports should use ugence_cloud_scaling_controller.observability.efficiency_observer.
"""
from ugence_cloud_scaling_controller.observability.efficiency_observer import (  # noqa: F401
    EfficiencyObserver,
    ObservedCycle,
)

__all__ = ["EfficiencyObserver", "ObservedCycle"]
