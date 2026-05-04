"""nuScenes-mini dataset adapter — integration contract.

This module documents the integration path from the §6.2 pilot
runner to real nuScenes data. **Importing the module is safe even
when ``nuscenes-devkit`` is not installed**; the heavy dependencies
load lazily inside :class:`NuScenesAdapter.__init__` so the rest of
the pilot test suite is not coupled to dataset access.

Pilot-plan reference: see ``docs/experiments/phase_6_2_pilot_plan.md``.

## Wiring contract

The pilot runner is dataset-agnostic. To swap from
:class:`RealisticNoiseAdapter` to :class:`NuScenesAdapter`:

```python
from symbolu_robotics.bcvf_autonomous.datasets.nuscenes import (
    NuScenesAdapter,
)
from symbolu_robotics.bcvf_autonomous.pilot import run_pilot

adapter = NuScenesAdapter(
    dataroot="/data/nuscenes-mini",
    version="v1.0-mini",
    city="boston-seaport",  # one-city scope per pilot plan §scope
)
result = run_pilot(
    adapter=adapter,
    output_dir="results/phase_6_2_real",
    pilot_label="phase_6_2_real",
)
```

No other code in the runner / scene evaluator / sign test / fleet
analysis changes. The numerical pipeline is identical to the one
validated against ``RealisticNoiseAdapter``.

## What this module does NOT do (yet)

* No actual nuScenes-devkit calls. Implementation requires the
  authenticated dataset on local disk + ``pip install
  nuscenes-devkit``. The pilot plan estimates ~3–4 weeks of
  predictor-implementation work after dataset access.
* No learned-forecaster M3 (CoverNet / Trajectron++). The pilot
  plan documents three options; the choice is execution-time, not
  scaffolding-time.
"""

from __future__ import annotations

from typing import List, Optional

from .base import DatasetAdapter, SceneRecord


class NuScenesAdapter(DatasetAdapter):
    """Real nuScenes-mini adapter — implementation pending dataset access.

    Constructor raises :class:`ImportError` when ``nuscenes-devkit``
    is not installed, with a clear remediation message. This is the
    intended behavior: the pilot runner discovers the missing
    dependency at adapter-construction time, not silently in the
    middle of a multi-hour sweep.

    The adapter is documented but not implemented in this sandbox.
    The class lives here so a calling script (and the pilot plan)
    can import it without conditional logic — the moment the
    dataset and devkit are available, the implementation is filled
    in below the ``__init__`` raise.
    """

    def __init__(
        self,
        dataroot: str,
        version: str = "v1.0-mini",
        city: Optional[str] = None,
        learned_forecaster: Optional[str] = None,
    ) -> None:
        """
        Args:
            dataroot: filesystem path to the nuScenes-mini extraction.
            version: nuScenes split version. Default matches the mini
                release; full nuScenes is "v1.0-trainval" / "v1.0-test".
            city: optional restriction to one of "boston-seaport",
                "singapore-onenorth", "singapore-hollandvillage",
                "singapore-queenstown". Pilot plan recommends scoping
                to one city in the first execution to reduce variance.
            learned_forecaster: optional identifier for the M3 learned
                forecaster ("covernet", "mtp", "trajectron_pp", or None
                for a lightweight in-house LSTM). None is the safe
                pilot-plan fallback that does not require external
                model weights.
        """
        try:
            import nuscenes  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "NuScenesAdapter requires the nuscenes-devkit package "
                "and a local nuScenes-mini extraction. Install with "
                "`pip install nuscenes-devkit` and download the mini "
                "split from https://www.nuscenes.org/. See "
                "`docs/experiments/phase_6_2_pilot_plan.md` for the "
                "step-by-step setup."
            ) from exc

        # Implementation entry point. The pilot plan estimates
        # ~3–4 weeks of follow-on work for the four predictors
        # (M1 HD-map, M2 Kalman, M3 learned, M4 failure-injected)
        # plus the SceneRecord conversion. Until that lands, the
        # adapter raises NotImplementedError so a calling script
        # surfaces a precise message rather than crashing partway
        # through a sweep.
        self._dataroot = dataroot
        self._version = version
        self._city = city
        self._learned_forecaster = learned_forecaster
        raise NotImplementedError(
            "NuScenesAdapter scaffolding is in place but the predictor "
            "implementations are pending the §6.2 follow-on work. See "
            "docs/experiments/phase_6_2_pilot_plan.md §3 (predictor "
            "construction) and §4 (failure-injection protocol). The "
            "pilot runner, scene evaluator, sign test, and fleet "
            "analysis pipeline are all dataset-agnostic and will "
            "work without modification once load_scene() is filled in."
        )

    def scene_ids(self) -> List[str]:
        raise NotImplementedError

    def load_scene(self, scene_id: str) -> SceneRecord:
        raise NotImplementedError
