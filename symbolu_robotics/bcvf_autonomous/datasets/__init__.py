"""§6.2 dataset adapters — real-sensor pilot scaffolding.

See ``docs/experiments/phase_6_2_pilot_plan.md`` for the pilot plan.
Adapter classes live in this package. Concrete implementations:

- ``base`` — abstract ``DatasetAdapter`` interface.
- ``synthetic_realistic`` — drop-in adapter that generates realistic-
  noise synthetic traces. Bridges pure-SE(2) synthetic (§6.1) and
  real nuScenes data (§6.2) so numerical correctness under real-like
  noise can be validated before the full pilot's dataset dependencies
  are installed.
- ``nuscenes`` — (future) real-data nuScenes adapter.
- ``kitti`` — (future) fallback dataset adapter.
"""

from .base import DatasetAdapter, SceneRecord

__all__ = ["DatasetAdapter", "SceneRecord"]
