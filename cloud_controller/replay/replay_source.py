"""ReplayPrometheusClient — drives the EXISTING Stage-2/3 pipeline from a trace.

It duck-types `signals.prometheus.PrometheusClient` (the four methods the
pipeline actually calls), so a real `SignalPipeline` / `ShadowRunner` runs
unmodified against replayed trace data instead of a live Prometheus. This is the
"feed the existing pipeline" proof for Track B: the same normalizer → controller
→ HPA-watcher → divergence-tracker → reporter chain that runs in production
ingests a real trace here.

The HPA baseline (current/desired replicas) is produced by the standard
threshold HPA model (`benchmark.HPASimulator`) running on the same replayed
metrics — so the DivergenceTracker has something real-shaped to compare against.
That HPA is a *model*, not real cluster telemetry; the trace is the real part.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from cloud_controller.observability.benchmark import HPASimulator
from cloud_controller.replay.adapters.base import TraceSeries
from cloud_controller.signals.prometheus import DEFAULT_QUERIES

_METRIC_KEYS = ("cpu", "memory", "latency_p99", "error_rate", "queue_depth")


class ReplayPrometheusClient:
    """A PrometheusClient stand-in backed by a TraceSeries cursor."""

    def __init__(
        self,
        series: TraceSeries,
        base_replicas: int = 5,
        hpa: Optional[HPASimulator] = None,
    ):
        self.series = series
        self._metrics = series.to_metrics_series()
        self._cursor = 0
        self._replicas = base_replicas
        self._hpa = hpa or HPASimulator()
        self._exhausted = False

    # ---- the four methods SignalPipeline / HPAWatcher actually call ----

    def query_metrics(
        self,
        queries: Optional[List[Tuple[str, str, str]]] = None,
    ) -> Dict[str, Optional[float]]:
        """Return this cycle's metrics, then advance the cursor by one cycle."""
        if self._cursor >= len(self._metrics):
            self._exhausted = True
            return {k: None for k in _METRIC_KEYS}
        m = self._metrics[self._cursor]
        out = {k: float(m.get(k, 0.0)) for k in _METRIC_KEYS}
        # Advance the HPA model and cursor exactly once per poll cycle.
        cpu = out["cpu"]
        delta = self._hpa.decide({"cpu": cpu}, self._replicas, self._cursor)
        self._replicas = max(1, self._replicas + delta)
        self._cursor += 1
        return out

    def query_k8s_state(
        self,
        namespace: Optional[str] = None,
        deployment: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        # current = replicas before this cycle's HPA decision lands;
        # desired = after — so HPAWatcher sees a real-shaped scaling intent.
        idx = min(self._cursor, len(self._metrics) - 1) if self._metrics else 0
        cpu = float(self._metrics[idx].get("cpu", 0.0)) if self._metrics else 0.0
        desired_delta = self._hpa.decide({"cpu": cpu}, self._replicas, self._cursor)
        return {
            "current_replicas": float(self._replicas),
            "desired_replicas": float(max(1, self._replicas + desired_delta)),
            "pod_restarts": 0.0,
        }

    def range_query(self, query, start, end, step="15s"):
        # No historical bootstrap for replay — return None to disable it.
        return None

    def instant_query(self, query: str, time_: Optional[float] = None) -> Optional[float]:
        idx = min(self._cursor, len(self._metrics) - 1) if self._metrics else 0
        if not self._metrics:
            return None
        for key in _METRIC_KEYS:
            if key in query:
                return float(self._metrics[idx].get(key, 0.0))
        return None

    def health_check(self) -> bool:
        return True

    def close(self) -> None:
        pass

    @property
    def exhausted(self) -> bool:
        return self._exhausted

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
