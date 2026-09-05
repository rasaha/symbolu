"""Gate Actuator — a dry-run recorder of deployment-gate decisions.

Containment (ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING, D-2):
this actuator has exactly one mode, ``DRY_RUN``. The ArgoCD sync mode, the admission
webhook mode, the ArgoCD URL, the bearer token and the insecure-TLS switch are gone:
a bearer token in a config dataclass was credential material held by a module that
no authorization gated. ArgoCD access lives with the authority-gated
``GateExecutor`` (``gate_executor.py``), whose HTTP caller is injected and whose sync
requires an ``ExecutionAuthorization``.

What remains records what a gate decision *would* be, for a recommendation loop to
log, and transmits nothing.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class GateMode(Enum):
    """How the gate actuator controls deployments. One mode: it does not."""
    DRY_RUN = "dry_run"            # Log only


class GateAction(Enum):
    """What gate action to take."""
    ALLOW = "allow"    # Allow the deployment/sync to proceed
    HOLD = "hold"      # Hold back the deployment/sync
    SYNC = "sync"      # Actively trigger a sync (ArgoCD only)


@dataclass
class GateConfig:
    """Configuration for the gate actuator. No URL, no token, no TLS switch."""
    mode: GateMode = GateMode.DRY_RUN


@dataclass
class GateResult:
    """Result of a gate action."""
    success: bool
    mode: str
    action: str                    # "allow", "hold", "sync"
    application: str               # ArgoCD application or deployment name
    namespace: str
    timestamp: float = 0.0
    error: str = ""
    retries: int = 0
    recommendation_id: str = ""

    def format_log(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        status = "OK" if self.success else f"FAILED ({self.error})"
        return (
            f"[{ts}] GATE [{self.mode}] {self.namespace}/{self.application}: "
            f"{self.action} — {status}"
        )


class GateActuator:
    """Records deployment-gate decisions for scaling coordination. Transmits nothing.

    Usage:
        gate = GateActuator()
        result = gate.execute(GateAction.HOLD, application="api-gateway", namespace="prod")
    """

    def __init__(self, config: Optional[GateConfig] = None):
        self.config = config or GateConfig()
        self._lock = threading.Lock()
        self._history: List[GateResult] = []
        self._max_history = 1000

    @property
    def mutates(self) -> bool:
        """Always ``False``: there is no mode in which this actuator changes anything."""
        return False

    def execute(
        self,
        action: GateAction,
        application: str,
        namespace: str,
        recommendation_id: str = "",
    ) -> GateResult:
        """Record a gate decision.

        Args:
            action: What gate action would be taken (ALLOW, HOLD, SYNC).
            application: ArgoCD application or deployment name.
            namespace: K8s namespace.
            recommendation_id: Linked recommendation ID (for audit).

        Returns:
            GateResult describing the decision that was logged, never applied.
        """
        now = time.time()
        logger.info(
            "DRY RUN: would %s gate for %s/%s",
            action.value, namespace, application,
        )
        result = GateResult(
            success=True,
            mode=GateMode.DRY_RUN.value,
            action=action.value,
            application=application,
            namespace=namespace,
            timestamp=now,
            recommendation_id=recommendation_id,
        )
        self._record(result)
        logger.info(result.format_log())
        return result

    def _record(self, result: GateResult) -> None:
        """Record gate result for audit trail."""
        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    @property
    def history(self) -> List[GateResult]:
        with self._lock:
            return list(self._history)

    def reset(self) -> None:
        """Clear history."""
        with self._lock:
            self._history.clear()
