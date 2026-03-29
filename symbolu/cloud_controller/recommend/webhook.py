"""Webhook Dispatcher — sends notifications for scaling recommendations.

Supports Slack, PagerDuty, and OpsGenie out of the box.
Each target has a formatter that produces the appropriate payload.

Purely fire-and-forget — webhook failures are logged but never
block the recommendation pipeline.
"""

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class WebhookTarget(Enum):
    """Supported webhook targets."""
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    GENERIC = "generic"


# Confidence level ordering for min_confidence filtering
VALID_CONFIDENCE_LEVELS = {"none", "low", "medium", "high"}
_CONFIDENCE_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class WebhookConfig:
    """Configuration for a single webhook endpoint."""
    target: WebhookTarget
    url: str
    # Optional extra headers (e.g., auth tokens)
    headers: Dict[str, str] = field(default_factory=dict)
    # Timeout for HTTP requests (seconds)
    timeout_seconds: float = 10.0
    # Only send for these confidence levels
    min_confidence: str = "low"  # "low", "medium", "high"

    def __post_init__(self):
        if self.min_confidence not in VALID_CONFIDENCE_LEVELS:
            raise ValueError(
                f"Invalid min_confidence '{self.min_confidence}'. "
                f"Must be one of: {', '.join(sorted(VALID_CONFIDENCE_LEVELS))}"
            )


class WebhookFormatter(Protocol):
    """Protocol for webhook payload formatters."""

    def format_recommendation(
        self,
        service: str,
        namespace: str,
        current_replicas: int,
        recommended_delta: int,
        target_replicas: int,
        confidence: str,
        signals: Dict[str, Any],
        explanation: str,
        recommendation_id: str,
    ) -> Dict[str, Any]: ...


class SlackFormatter:
    """Formats recommendations as Slack Block Kit messages."""

    def format_recommendation(
        self,
        service: str,
        namespace: str,
        current_replicas: int,
        recommended_delta: int,
        target_replicas: int,
        confidence: str,
        signals: Dict[str, Any],
        explanation: str,
        recommendation_id: str,
    ) -> Dict[str, Any]:
        direction = "Scale Out" if recommended_delta > 0 else "Scale In"
        emoji = "\u26a0\ufe0f" if recommended_delta > 0 else "\u2139\ufe0f"

        signal_lines = []
        for key, val in signals.items():
            if isinstance(val, float):
                signal_lines.append(f"  {key}: {val:.2f}")
            else:
                signal_lines.append(f"  {key}: {val}")

        signal_text = "\n".join(signal_lines) if signal_lines else "  (no signal data)"

        text = (
            f"{emoji} *Neural Cloud Controller — {direction} Recommendation*\n"
            f"Service: `{service}` ({namespace})\n"
            f"Current replicas: {current_replicas}\n"
            f"Recommended: {target_replicas} ({recommended_delta:+d})\n"
            f"Confidence: *{confidence.upper()}*\n\n"
            f"Signals:\n```\n{signal_text}\n```\n"
            f"Reasoning:\n```\n{explanation}\n```\n"
            f"ID: `{recommendation_id}`"
        )

        return {"text": text}


class PagerDutyFormatter:
    """Formats recommendations as PagerDuty Events API v2 payloads."""

    def format_recommendation(
        self,
        service: str,
        namespace: str,
        current_replicas: int,
        recommended_delta: int,
        target_replicas: int,
        confidence: str,
        signals: Dict[str, Any],
        explanation: str,
        recommendation_id: str,
    ) -> Dict[str, Any]:
        severity = "warning" if confidence == "high" else "info"
        direction = "scale-out" if recommended_delta > 0 else "scale-in"

        return {
            "routing_key": "",  # Set via webhook config headers
            "event_action": "trigger",
            "payload": {
                "summary": (
                    f"Neural Cloud Controller: {direction} {recommended_delta:+d} "
                    f"for {service} ({namespace})"
                ),
                "severity": severity,
                "source": f"neural-cloud-controller/{namespace}/{service}",
                "component": service,
                "group": namespace,
                "custom_details": {
                    "current_replicas": current_replicas,
                    "target_replicas": target_replicas,
                    "delta": recommended_delta,
                    "confidence": confidence,
                    "signals": signals,
                    "explanation": explanation,
                    "recommendation_id": recommendation_id,
                },
            },
            "dedup_key": f"{namespace}/{service}/{recommendation_id}",
        }


class OpsGenieFormatter:
    """Formats recommendations as OpsGenie Alert API payloads."""

    def format_recommendation(
        self,
        service: str,
        namespace: str,
        current_replicas: int,
        recommended_delta: int,
        target_replicas: int,
        confidence: str,
        signals: Dict[str, Any],
        explanation: str,
        recommendation_id: str,
    ) -> Dict[str, Any]:
        direction = "Scale Out" if recommended_delta > 0 else "Scale In"
        priority = "P3" if confidence == "high" else "P4"

        return {
            "message": (
                f"Neural Cloud Controller: {direction} {recommended_delta:+d} "
                f"for {service}"
            ),
            "alias": recommendation_id,
            "description": explanation,
            "priority": priority,
            "tags": ["neural-cloud-controller", namespace, service, confidence],
            "details": {
                "service": service,
                "namespace": namespace,
                "current_replicas": str(current_replicas),
                "target_replicas": str(target_replicas),
                "delta": str(recommended_delta),
                "confidence": confidence,
            },
        }


# Formatter registry
_FORMATTERS: Dict[WebhookTarget, WebhookFormatter] = {
    WebhookTarget.SLACK: SlackFormatter(),
    WebhookTarget.PAGERDUTY: PagerDutyFormatter(),
    WebhookTarget.OPSGENIE: OpsGenieFormatter(),
}


class WebhookDispatcher:
    """Dispatches recommendation notifications to configured webhooks.

    Usage:
        dispatcher = WebhookDispatcher([
            WebhookConfig(target=WebhookTarget.SLACK, url="https://hooks.slack.com/..."),
        ])
        dispatcher.send(service="api-gw", ...)
    """

    def __init__(self, configs: List[WebhookConfig] | None = None):
        self._configs = configs or []

    @property
    def targets(self) -> List[WebhookConfig]:
        return list(self._configs)

    def send(
        self,
        service: str,
        namespace: str,
        current_replicas: int,
        recommended_delta: int,
        target_replicas: int,
        confidence: str,
        signals: Dict[str, Any],
        explanation: str,
        recommendation_id: str,
    ) -> int:
        """Send recommendation to all configured webhooks.

        Returns:
            Number of webhooks successfully notified.
        """
        if not self._configs:
            return 0

        sent = 0
        confidence_rank = _CONFIDENCE_ORDER.get(confidence, 0)

        for config in self._configs:
            min_rank = _CONFIDENCE_ORDER.get(config.min_confidence, 0)
            if confidence_rank < min_rank:
                logger.debug(
                    "Skipping %s webhook: confidence %s below minimum %s",
                    config.target.value, confidence, config.min_confidence,
                )
                continue

            formatter = _FORMATTERS.get(config.target)
            if formatter is None:
                # Generic target — send raw JSON
                payload = {
                    "service": service,
                    "namespace": namespace,
                    "current_replicas": current_replicas,
                    "recommended_delta": recommended_delta,
                    "target_replicas": target_replicas,
                    "confidence": confidence,
                    "signals": signals,
                    "explanation": explanation,
                    "recommendation_id": recommendation_id,
                }
            else:
                payload = formatter.format_recommendation(
                    service=service,
                    namespace=namespace,
                    current_replicas=current_replicas,
                    recommended_delta=recommended_delta,
                    target_replicas=target_replicas,
                    confidence=confidence,
                    signals=signals,
                    explanation=explanation,
                    recommendation_id=recommendation_id,
                )

            if self._post(config, payload):
                sent += 1

        return sent

    @staticmethod
    def _post(config: WebhookConfig, payload: Dict[str, Any]) -> bool:
        """POST JSON payload to webhook URL. Returns True on success."""
        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            headers.update(config.headers)

            req = urllib.request.Request(
                config.url,
                data=data,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=config.timeout_seconds) as resp:
                if resp.status < 300:
                    logger.debug("Webhook %s: %d", config.target.value, resp.status)
                    return True
                logger.warning(
                    "Webhook %s returned %d", config.target.value, resp.status,
                )
                return False
        except urllib.error.URLError as e:
            logger.warning("Webhook %s failed: %s", config.target.value, e)
            return False
        except Exception:
            logger.exception("Webhook %s unexpected error", config.target.value)
            return False
