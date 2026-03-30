"""Gate Actuator — controls deployment gates via ArgoCD or K8s Admission Webhooks.

Two gating mechanisms:
  1. ArgoCD Sync Gate — POST /api/v1/applications/{name}/sync to trigger
     or hold back ArgoCD application syncs based on scaling decisions.
  2. Admission Webhook — validates or mutates pod specs at admission time
     to enforce scaling policy (e.g., reject scale-up during incident).

Like the K8s actuator, this module trusts its inputs — safety bounds are
enforced upstream by recommend/safety.py.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional HTTP dependency for ArgoCD API calls
try:
    import urllib.request
    import urllib.error
    import json as _json
    _HTTP_AVAILABLE = True
except ImportError:
    _HTTP_AVAILABLE = False


class GateMode(Enum):
    """How the gate actuator controls deployments."""
    DRY_RUN = "dry_run"            # Log only
    ARGOCD_SYNC = "argocd_sync"    # Trigger/hold ArgoCD sync
    ADMISSION_WEBHOOK = "admission_webhook"  # K8s admission control


class GateAction(Enum):
    """What gate action to take."""
    ALLOW = "allow"    # Allow the deployment/sync to proceed
    HOLD = "hold"      # Hold back the deployment/sync
    SYNC = "sync"      # Actively trigger a sync (ArgoCD only)


@dataclass
class GateConfig:
    """Configuration for the gate actuator."""
    mode: GateMode = GateMode.DRY_RUN
    # ArgoCD settings
    argocd_url: str = ""           # e.g., "https://argocd.internal:8080"
    argocd_token: str = ""         # Bearer token for ArgoCD API
    argocd_insecure: bool = False  # Skip TLS verification (dev only)
    # Timeout for API calls
    timeout_seconds: float = 10.0
    # Retry settings
    max_retries: int = 2
    retry_delay_seconds: float = 1.0


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
    """Controls deployment gates for scaling coordination.

    Usage:
        gate = GateActuator(GateConfig(
            mode=GateMode.ARGOCD_SYNC,
            argocd_url="https://argocd.internal:8080",
            argocd_token="...",
        ))
        result = gate.execute(
            action=GateAction.HOLD,
            application="api-gateway",
            namespace="prod",
        )
    """

    def __init__(self, config: Optional[GateConfig] = None):
        self.config = config or GateConfig()
        self._lock = threading.Lock()
        self._history: List[GateResult] = []
        self._max_history = 1000

    def execute(
        self,
        action: GateAction,
        application: str,
        namespace: str,
        recommendation_id: str = "",
    ) -> GateResult:
        """Execute a gate action.

        Args:
            action: What gate action to take (ALLOW, HOLD, SYNC).
            application: ArgoCD application or deployment name.
            namespace: K8s namespace.
            recommendation_id: Linked recommendation ID (for audit).

        Returns:
            GateResult with success/failure details.
        """
        now = time.time()

        if self.config.mode == GateMode.DRY_RUN:
            result = self._dry_run(action, application, namespace, now, recommendation_id)
        elif self.config.mode == GateMode.ARGOCD_SYNC:
            result = self._argocd_sync(action, application, namespace, now, recommendation_id)
        elif self.config.mode == GateMode.ADMISSION_WEBHOOK:
            # Admission webhook is passive — it responds to K8s API server calls,
            # not initiated by us. Log the policy decision for the webhook to read.
            result = self._admission_policy(action, application, namespace, now, recommendation_id)
        else:
            result = GateResult(
                success=False,
                mode=self.config.mode.value,
                action=action.value,
                application=application,
                namespace=namespace,
                timestamp=now,
                error=f"Unknown mode: {self.config.mode}",
                recommendation_id=recommendation_id,
            )

        self._record(result)
        logger.info(result.format_log())
        return result

    def _dry_run(
        self,
        action: GateAction,
        application: str,
        namespace: str,
        timestamp: float,
        recommendation_id: str,
    ) -> GateResult:
        """Log gate action without executing."""
        logger.info(
            "DRY RUN: would %s gate for %s/%s",
            action.value, namespace, application,
        )
        return GateResult(
            success=True,
            mode="dry_run",
            action=action.value,
            application=application,
            namespace=namespace,
            timestamp=timestamp,
            recommendation_id=recommendation_id,
        )

    def _argocd_sync(
        self,
        action: GateAction,
        application: str,
        namespace: str,
        timestamp: float,
        recommendation_id: str,
    ) -> GateResult:
        """Execute gate action via ArgoCD API."""
        if not self.config.argocd_url:
            return GateResult(
                success=False,
                mode="argocd_sync",
                action=action.value,
                application=application,
                namespace=namespace,
                timestamp=timestamp,
                error="ArgoCD URL not configured",
                recommendation_id=recommendation_id,
            )

        if action == GateAction.SYNC:
            return self._argocd_trigger_sync(application, namespace, timestamp, recommendation_id)
        elif action == GateAction.HOLD:
            # For HOLD, we don't trigger sync — just log that we're holding
            logger.info(
                "ArgoCD HOLD: deferring sync for %s/%s until conditions improve",
                namespace, application,
            )
            return GateResult(
                success=True,
                mode="argocd_sync",
                action="hold",
                application=application,
                namespace=namespace,
                timestamp=timestamp,
                recommendation_id=recommendation_id,
            )
        else:
            # ALLOW — no active action needed, sync proceeds normally
            return GateResult(
                success=True,
                mode="argocd_sync",
                action="allow",
                application=application,
                namespace=namespace,
                timestamp=timestamp,
                recommendation_id=recommendation_id,
            )

    def _argocd_trigger_sync(
        self,
        application: str,
        namespace: str,
        timestamp: float,
        recommendation_id: str,
    ) -> GateResult:
        """POST to ArgoCD to trigger an application sync."""
        url = f"{self.config.argocd_url.rstrip('/')}/api/v1/applications/{application}/sync"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.argocd_token}",
        }
        body = _json.dumps({"prune": False, "dryRun": False}).encode("utf-8")

        last_error = ""
        for attempt in range(self.config.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                if self.config.argocd_insecure:
                    import ssl
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    urllib.request.urlopen(req, timeout=self.config.timeout_seconds, context=ctx)
                else:
                    urllib.request.urlopen(req, timeout=self.config.timeout_seconds)

                return GateResult(
                    success=True,
                    mode="argocd_sync",
                    action="sync",
                    application=application,
                    namespace=namespace,
                    timestamp=timestamp,
                    retries=attempt,
                    recommendation_id=recommendation_id,
                )
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.max_retries:
                    logger.warning(
                        "ArgoCD sync retry %d/%d for %s: %s",
                        attempt + 1, self.config.max_retries, application, e,
                    )
                    time.sleep(self.config.retry_delay_seconds)

        return GateResult(
            success=False,
            mode="argocd_sync",
            action="sync",
            application=application,
            namespace=namespace,
            timestamp=timestamp,
            error=f"Failed after {self.config.max_retries + 1} attempts: {last_error}",
            retries=self.config.max_retries,
            recommendation_id=recommendation_id,
        )

    def _admission_policy(
        self,
        action: GateAction,
        application: str,
        namespace: str,
        timestamp: float,
        recommendation_id: str,
    ) -> GateResult:
        """Record admission policy decision.

        The actual admission webhook server reads this state to make
        allow/deny decisions. This method just updates the policy.
        """
        logger.info(
            "Admission policy set: %s for %s/%s (rec=%s)",
            action.value, namespace, application, recommendation_id,
        )
        return GateResult(
            success=True,
            mode="admission_webhook",
            action=action.value,
            application=application,
            namespace=namespace,
            timestamp=timestamp,
            recommendation_id=recommendation_id,
        )

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
