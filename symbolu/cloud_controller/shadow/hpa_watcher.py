"""HPA Watcher — monitors Kubernetes HPA scaling decisions.

Polls kube_hpa_status_desired_replicas and kube_hpa_status_current_replicas
from Prometheus to detect when HPA initiates a scaling action.

Purely observational — no K8s write access needed.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from symbolu.cloud_controller.signals.prometheus import PrometheusClient

logger = logging.getLogger(__name__)


@dataclass
class HPASnapshot:
    """Point-in-time HPA state."""
    timestamp: float
    current_replicas: int
    desired_replicas: int

    @property
    def is_scaling(self) -> bool:
        """Whether HPA is actively trying to change replica count."""
        return self.current_replicas != self.desired_replicas

    @property
    def delta(self) -> int:
        """Replica change HPA is requesting."""
        return self.desired_replicas - self.current_replicas


@dataclass
class HPAAction:
    """A detected HPA scaling event."""
    timestamp: float
    from_replicas: int
    to_replicas: int
    delta: int  # positive = scale out, negative = scale in

    @property
    def direction(self) -> str:
        if self.delta > 0:
            return "scale_out"
        elif self.delta < 0:
            return "scale_in"
        return "no_change"


class HPAWatcher:
    """Watches HPA for scaling actions by polling Prometheus.

    Detects scaling events by comparing consecutive snapshots.
    An event is recorded when desired_replicas changes from the
    previous observation.

    Usage:
        watcher = HPAWatcher(prometheus_client)
        snapshot = watcher.poll()
        actions = watcher.get_recent_actions(since=time.time() - 300)
    """

    def __init__(
        self,
        prometheus: PrometheusClient,
        namespace: Optional[str] = None,
        deployment: Optional[str] = None,
    ):
        self.prometheus = prometheus
        self.namespace = namespace
        self.deployment = deployment
        self._prev_snapshot: Optional[HPASnapshot] = None
        self._actions: List[HPAAction] = []
        self._snapshots: List[HPASnapshot] = []
        # Keep at most 2000 actions/snapshots (~8 hours at 15s intervals)
        self._max_history = 2000

    def poll(self) -> Optional[HPASnapshot]:
        """Poll current HPA state from Prometheus.

        Returns:
            HPASnapshot if query succeeded, None on failure.
        """
        k8s_state = self.prometheus.query_k8s_state(
            namespace=self.namespace,
            deployment=self.deployment,
        )

        current_raw = k8s_state.get("current_replicas")
        desired_raw = k8s_state.get("desired_replicas")

        if current_raw is None or desired_raw is None:
            logger.debug("HPA state unavailable — current=%s desired=%s", current_raw, desired_raw)
            return None

        try:
            current = int(round(float(current_raw)))
            desired = int(round(float(desired_raw)))
        except (ValueError, TypeError):
            logger.warning("Invalid HPA replica values: current=%s desired=%s", current_raw, desired_raw)
            return None

        now = time.time()
        snapshot = HPASnapshot(
            timestamp=now,
            current_replicas=current,
            desired_replicas=desired,
        )

        # Detect scaling action: desired changed from previous snapshot
        # NOTE: If HPA changes desired multiple times between polls,
        # intermediate actions are lost — only the net change is captured.
        if self._prev_snapshot is not None:
            prev_desired = self._prev_snapshot.desired_replicas
            if desired != prev_desired:
                action = HPAAction(
                    timestamp=now,
                    from_replicas=prev_desired,
                    to_replicas=desired,
                    delta=desired - prev_desired,
                )
                self._actions.append(action)
                logger.info(
                    "HPA scaling detected: %d → %d (%+d)",
                    prev_desired, desired, action.delta,
                )

        self._prev_snapshot = snapshot
        self._snapshots.append(snapshot)

        # Trim history
        if len(self._actions) > self._max_history:
            self._actions = self._actions[-self._max_history:]
        if len(self._snapshots) > self._max_history:
            self._snapshots = self._snapshots[-self._max_history:]

        return snapshot

    def get_recent_actions(self, since: float) -> List[HPAAction]:
        """Get HPA actions since a given timestamp."""
        return [a for a in self._actions if a.timestamp >= since]

    def get_latest_snapshot(self) -> Optional[HPASnapshot]:
        """Get the most recent HPA snapshot."""
        return self._prev_snapshot

    @property
    def total_actions(self) -> int:
        return len(self._actions)

    @property
    def actions(self) -> List[HPAAction]:
        return list(self._actions)

    def reset(self) -> None:
        self._prev_snapshot = None
        self._actions.clear()
        self._snapshots.clear()
