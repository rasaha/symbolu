"""Kubernetes Actuator — executes scaling decisions via K8s API.

Two scaling mechanisms:
  1. Deployment scale patch — directly sets replica count
  2. HPA target override — adjusts HPA's custom metric target

Uses the K8s Python client or raw HTTP. Falls back gracefully when
the cluster is unreachable (logs error, does not crash).

Safety: all mutations are gated by the recommend/safety.py bounds
BEFORE reaching this module. This module trusts its inputs.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Attempt K8s client import — optional dependency.
# When unavailable, the actuator runs in dry-run mode.
try:
    from kubernetes import client as k8s_client, config as k8s_config
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False


class ActuatorMode(Enum):
    """How the actuator applies scaling decisions."""
    DRY_RUN = "dry_run"          # Log only, no mutations
    SCALE_PATCH = "scale_patch"  # PATCH deployment replicas directly
    HPA_METRIC = "hpa_metric"    # Expose action_score as custom metric for HPA


@dataclass
class ActuatorConfig:
    """Configuration for the K8s actuator."""
    # Operating mode
    mode: ActuatorMode = ActuatorMode.DRY_RUN
    # K8s context (None = in-cluster or default kubeconfig)
    kubeconfig_path: Optional[str] = None
    context: Optional[str] = None
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
    """Executes scaling decisions against the Kubernetes API.

    Usage:
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))
        result = actuator.scale(
            deployment="api-gateway",
            namespace="prod",
            current_replicas=5,
            target_replicas=7,
        )
        if result.success:
            print(f"Scaled {result.deployment} to {result.target_replicas}")
    """

    def __init__(self, config: Optional[ActuatorConfig] = None):
        self.config = config or ActuatorConfig()
        self._apps_api: Optional[object] = None
        self._initialized = False
        self._lock = threading.Lock()
        self._history: List[ExecutionResult] = []
        self._max_history = 1000

    def _ensure_client(self) -> bool:
        """Lazily initialize the K8s client.

        Returns True if client is ready, False if unavailable.
        """
        if self._initialized:
            return self._apps_api is not None

        self._initialized = True

        if self.config.mode == ActuatorMode.DRY_RUN:
            return True  # No client needed for dry run

        if not K8S_AVAILABLE:
            logger.warning(
                "kubernetes package not installed — actuator forced to dry_run. "
                "Install with: pip install kubernetes"
            )
            return False

        try:
            if self.config.kubeconfig_path:
                k8s_config.load_kube_config(
                    config_file=self.config.kubeconfig_path,
                    context=self.config.context,
                )
            else:
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config(context=self.config.context)

            self._apps_api = k8s_client.AppsV1Api()
            logger.info("K8s client initialized (mode=%s)", self.config.mode.value)
            return True
        except Exception as e:
            logger.error("Failed to initialize K8s client: %s", e)
            self._apps_api = None
            return False

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
        """PATCH the deployment's replica count via K8s API."""
        if not self._ensure_client() or self._apps_api is None:
            return ExecutionResult(
                success=False,
                mode="scale_patch",
                deployment=deployment,
                namespace=namespace,
                previous_replicas=current_replicas,
                target_replicas=target_replicas,
                delta=delta,
                timestamp=timestamp,
                error="K8s client not available",
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
        """Clear execution history."""
        with self._lock:
            self._history.clear()
        self._initialized = False
        self._apps_api = None
