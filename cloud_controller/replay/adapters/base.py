"""Trace adapter base — converts a real public trace into the canonical
workload series the controller consumes.

The whole point of Track B is to change **exactly one variable** relative to the
19 synthetic scenarios: the *workload distribution*. So an adapter's job is to
turn a real trace into a `demand` series ∈ [0,1] (the real arrival / utilization
process), which is then mapped to the controller's metric schema by the SAME
`benchmark._demand_to_metrics` transfer function the synthetic suite uses. The
control core (controller + estimator + guard + scorer) is untouched.

Every adapter declares provenance (`CITATION`, `LICENSE`) and an honesty
`STATUS`:
  - EXECUTED     — data is fetchable in this environment; replay numbers are real.
  - PENDING_DATA — adapter + schema are implemented and unit-tested on a fixture,
                   but the full trace lives behind blocked egress / huge files,
                   so it is NOT executed here. Never reported as a real number.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AdapterStatus(Enum):
    EXECUTED = "executed"            # real data fetchable + replayed here
    PENDING_DATA = "pending_data"    # implemented + fixture-tested; data not available here


@dataclass
class TraceSeries:
    """A real workload reduced to the controller's input contract.

    `demand[i]` ∈ [0,1] is the real per-cycle load (the variable Track B makes
    real). `metrics` is optional: if an adapter measured real utilization
    directly it may supply per-cycle metric dicts; otherwise metrics are derived
    from `demand` via the shared `_demand_to_metrics` model.
    """
    name: str
    source: str                      # human citation string
    license: str
    status: AdapterStatus
    cycle_seconds: float
    demand: List[float]
    metrics: Optional[List[Dict[str, float]]] = None
    meta: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Clamp demand defensively — a real trace must never push the controller
        # outside its documented [0,1] input contract.
        self.demand = [max(0.0, min(1.0, float(d))) for d in self.demand]

    @property
    def n_cycles(self) -> int:
        return len(self.demand)

    def to_metrics_series(self) -> List[Dict[str, float]]:
        """Return the per-cycle metric dicts fed to the controller.

        Uses adapter-supplied metrics when present, else derives them from
        `demand` with the same transfer function as the synthetic suite.
        """
        if self.metrics is not None:
            return self.metrics
        # Imported lazily to avoid a hard import cycle at module load.
        from cloud_controller.observability.benchmark import _demand_to_metrics
        return [_demand_to_metrics(d) for d in self.demand]


class TraceAdapter(abc.ABC):
    """Base class for trace adapters."""

    NAME: str = "trace"
    CITATION: str = ""
    LICENSE: str = ""
    SCHEMA: str = ""
    STATUS: AdapterStatus = AdapterStatus.PENDING_DATA

    @abc.abstractmethod
    def load(self, path: str, **kwargs) -> TraceSeries:
        """Parse a trace file/dir into a TraceSeries."""
        raise NotImplementedError

    # --- shared helpers ---

    @staticmethod
    def _normalize_to_demand(
        loads: List[float],
        capacity_percentile: float = 95.0,
        floor: float = 0.0,
    ) -> List[float]:
        """Map a non-negative load series to demand ∈ [0,1].

        `capacity` is the `capacity_percentile`-th percentile of the load — i.e.
        the level the base fleet is treated as provisioned to handle near
        saturation. Buckets at/above that level saturate (demand→1). This is the
        single transparent modelling choice; it is reported in the artifacts.
        """
        if not loads:
            return []
        pos = sorted(v for v in loads if v > 0)
        if not pos:
            return [floor for _ in loads]
        idx = min(len(pos) - 1, max(0, int(round((capacity_percentile / 100.0) * (len(pos) - 1)))))
        capacity = pos[idx]
        if capacity <= 0:
            return [floor for _ in loads]
        return [max(floor, min(1.0, v / capacity)) for v in loads]
