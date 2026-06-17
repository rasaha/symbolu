"""Back-compat shim — EfficiencyObserver now lives in observability/.

Kept so `from cloud_controller.replay.efficiency_observer import ...` keeps
working. New imports should use cloud_controller.observability.efficiency_observer.
"""
from cloud_controller.observability.efficiency_observer import (  # noqa: F401
    EfficiencyObserver,
    ObservedCycle,
)

__all__ = ["EfficiencyObserver", "ObservedCycle"]
