"""Kubernetes Actuator — the reference scaling actuator behind the recommendation loop.

Containment (ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING, D-2):

  * This module loads **no** kubeconfig and **no** in-cluster configuration and
    imports **no** Kubernetes SDK. A client is *injected* by whoever constructs the
    actuator, or it is absent — mirroring ``KubernetesScalingExecutor``. Asking the
    actuator to discover credentials is not a mode it has.
  * ``RecommendEngine`` refuses this actuator in any mode but ``DRY_RUN`` (D-1), and
    ``RollbackMonitor`` accepts its ``scale`` only when :attr:`K8sActuator.mutates` is
    ``False``. The ``SCALE_PATCH`` mode survives for a caller that injects a client
    deliberately, outside any recommendation loop; live scaling under governance goes
    through ``BoundedExecutionSeam`` → ``ControlledScalingExecutor``.

Modes:
  1. ``DRY_RUN`` — log the proposed change; the default.
  2. ``SCALE_PATCH`` — PATCH the deployment's replica count through the injected client.
  3. ``HPA_METRIC`` — log only; the action score is expected to be exposed as a metric
     for a HorizontalPodAutoscaler to consume.

Safety: replica bounds are enforced upstream by recommend/safety.py. This module
trusts its inputs.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class ActuatorMode(Enum):
    """How the actuator applies scaling decisions."""
    DRY_RUN = "dry_run"          # Log only, no mutations
    SCALE_PATCH = "scale_patch"  # PATCH deployment replicas through an injected client
    HPA_METRIC = "hpa_metric"    # Expose action_score as custom metric for HPA


@dataclass
class ActuatorConfig:
    """Configuration for the K8s actuator.

    There is deliberately no ``kubeconfig_path`` and no ``context``: the actuator
    never discovers credentials. Pass a client to :class:`K8sActuator` instead.
    """
    # Operating mode
    mode: ActuatorMode = ActuatorMode.DRY_RUN
    # Retry on transient K8s API failures
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    # Timeout for K8s API calls
    timeout_seconds: float = 10.0


@dataclass
class ExecutionResult:
    """Result of executing a scaling action."""
    success: bool
    mode: str                          # "dry_run", "scale_patch", "hpa_metric"
    deployment: str
    namespace: str
    previous_replicas: int
    target_replicas: int
    delta: int
    timestamp: float = 0.0
    error: str = ""
    retries: int = 0
    # For audit trail
    recommendation_id: str = ""

    def format_log(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        status = "OK" if self.success else f"FAILED ({self.error})"
        return (
            f"[{ts}] EXECUTE [{self.mode}] {self.namespace}/{self.deployment}: "
            f"{self.previous_replicas} -> {self.target_replicas} ({self.delta:+d}) "
            f"— {status}"
        )


class K8sActuator:
    """Executes scaling decisions against an *injected* Kubernetes AppsV1 client.

    Usage (dry run — the only shape a recommendation loop may hold):
        actuator = K8sActuator(ActuatorConfig())
        result = actuator.scale("api-gateway", "prod", 5, 7)

    Usage (deliberate, outside any recommendation loop):
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH),
                               apps_api=apps_v1_client)
    """

    def __init__(self, config: Optional[ActuatorConfig] = None, *, apps_api: Optional[object] = None):
        self.config = config or ActuatorConfig()
        # The one way a client arrives. Nothing here opens a kubeconfig, reads a
        # service-account token or imports the kubernetes package.
        self._apps_api: Optional[object] = apps_api
        self._lock = threading.Lock()
        self._history: List[ExecutionResult] = []
        self._max_history = 1000

    @property
    def mutates(self) -> bool:
        """Whether a ``scale`` call can change infrastructure. Read by RollbackMonitor."""
        return self.config.mode is not ActuatorMode.DRY_RUN

    @property
    def has_client(self) -> bool:
        return self._apps_api is not None

    def scale(
        self,
        deployment: str,
        namespace: str,
        current_replicas: int,
        target_replicas: int,
        recommendation_id: str = "",
    ) -> ExecutionResult:
        """Execute a scaling action.

        Args:
            deployment: K8s deployment name.
            namespace: K8s namespace.
            current_replicas: Current replica count (for audit trail).
            target_replicas: Desired replica count after scaling.
            recommendation_id: ID of the approved recommendation (for audit).

        Returns:
            ExecutionResult with success/failure and details.
        """
        delta = target_replicas - current_replicas
        now = time.time()

        if delta == 0:
            result = ExecutionResult(
                success=True,
                mode=self.config.mode.value,
                deployment=deployment,
                namespace=namespace,
                previous_replicas=current_replicas,
                target_replicas=target_replicas,
                delta=0,
                timestamp=now,
                recommendation_id=recommendation_id,
            )
            self._record(result)
            return result

        if self.config.mode == ActuatorMode.DRY_RUN:
            result = self._dry_run(
                deployment, namespace, current_replicas, target_replicas,
                delta, now, recommendation_id,
            )
        elif self.config.mode == ActuatorMode.SCALE_PATCH:
            result = self._scale_patch(
                deployment, namespace, current_replicas, target_replicas,
                delta, now, recommendation_id,
            )
        elif self.config.mode == ActuatorMode.HPA_METRIC:
            result = self._dry_run(
                deployment, namespace, current_replicas, target_replicas,
                delta, now, recommendation_id,
            )
            result.mode = "hpa_metric"
            logger.info(
                "HPA_METRIC mode: action_score should be exposed as Prometheus "
                "metric for HPA to consume"
            )
        else:
            result = ExecutionResult(
                success=False,
                mode=self.config.mode.value,
                deployment=deployment,
                namespace=namespace,
                previous_replicas=current_replicas,
                target_replicas=target_replicas,
                delta=delta,
                timestamp=now,
                error=f"Unknown mode: {self.config.mode}",
                recommendation_id=recommendation_id,
            )

        self._record(result)
        logger.info(result.format_log())
        return result

    def _dry_run(
        self,
        deployment: str,
        namespace: str,
        current_replicas: int,
        target_replicas: int,
        delta: int,
        timestamp: float,
        recommendation_id: str,
    ) -> ExecutionResult:
        """Log the scaling action without executing it."""
        logger.info(
            "DRY RUN: would scale %s/%s from %d to %d (%+d)",
            namespace, deployment, current_replicas, target_replicas, delta,
        )
        return ExecutionResult(
            success=True,
            mode="dry_run",
            deployment=deployment,
            namespace=namespace,
            previous_replicas=current_replicas,
            target_replicas=target_replicas,
            delta=delta,
            timestamp=timestamp,
            recommendation_id=recommendation_id,
        )

    def _scale_patch(
        self,
        deployment: str,
        namespace: str,
        current_replicas: int,
        target_replicas: int,
        delta: int,
        timestamp: float,
        recommendation_id: str,
    ) -> ExecutionResult:
        """PATCH the deployment's replica count through the injected client."""
        if self._apps_api is None:
            # Fail closed: no client was injected and none will be discovered.
            return ExecutionResult(
                success=False,
                mode="scale_patch",
                deployment=deployment,
                namespace=namespace,
                previous_replicas=current_replicas,
                target_replicas=target_replicas,
                delta=delta,
                timestamp=timestamp,
                error="no injected Kubernetes client (the actuator discovers none)",
                recommendation_id=recommendation_id,
            )

        body = {"spec": {"replicas": target_replicas}}
        last_error = ""

        for attempt in range(self.config.max_retries + 1):
            try:
                self._apps_api.patch_namespaced_deployment_scale(
                    name=deployment,
                    namespace=namespace,
                    body=body,
                    _request_timeout=self.config.timeout_seconds,
                )
                return ExecutionResult(
                    success=True,
                    mode="scale_patch",
                    deployment=deployment,
                    namespace=namespace,
                    previous_replicas=current_replicas,
                    target_replicas=target_replicas,
                    delta=delta,
                    timestamp=timestamp,
                    retries=attempt,
                    recommendation_id=recommendation_id,
                )
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.max_retries:
                    logger.warning(
                        "K8s scale patch retry %d/%d for %s/%s: %s",
                        attempt + 1, self.config.max_retries, namespace, deployment, e,
                    )
                    time.sleep(self.config.retry_delay_seconds)

        return ExecutionResult(
            success=False,
            mode="scale_patch",
            deployment=deployment,
            namespace=namespace,
            previous_replicas=current_replicas,
            target_replicas=target_replicas,
            delta=delta,
            timestamp=timestamp,
            error=f"Failed after {self.config.max_retries + 1} attempts: {last_error}",
            retries=self.config.max_retries,
            recommendation_id=recommendation_id,
        )

    def _record(self, result: ExecutionResult) -> None:
        """Record execution result for audit trail."""
        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    @property
    def history(self) -> List[ExecutionResult]:
        """All execution results."""
        with self._lock:
            return list(self._history)

    @property
    def recent_successes(self) -> List[ExecutionResult]:
        """Successful executions in the last 10 minutes."""
        cutoff = time.time() - 600
        with self._lock:
            return [r for r in self._history if r.success and r.timestamp > cutoff]

    def reset(self) -> None:
        """Clear execution history. The injected client, if any, is kept."""
        with self._lock:
            self._history.clear()
