"""Recommend Mode — human-in-the-loop scaling recommendations.

Stage 4 of the Neural Cloud Controller. The controller generates
actionable recommendations, sends notifications via webhooks,
and waits for human approval before execution.

Flow: Controller decision → Confidence check → Safety bounds →
      Webhook notification → Human approval → Execute (Stage 5)
"""

from ugence_cloud_scaling_controller.recommend.confidence import (
    ConfidenceLevel,
    ConfidenceConfig,
    ConfidenceScorer,
)
from ugence_cloud_scaling_controller.recommend.safety import (
    SafetyConfig,
    SafetyBounds,
    SafetyResult,
)
from ugence_cloud_scaling_controller.recommend.webhook import (
    WebhookConfig,
    WebhookTarget,
    WebhookDispatcher,
    SlackFormatter,
    PagerDutyFormatter,
    OpsGenieFormatter,
)
from ugence_cloud_scaling_controller.recommend.approval import (
    ApprovalState,
    Recommendation,
    ApprovalManager,
)
from ugence_cloud_scaling_controller.recommend.engine import (
    RecommendConfig,
    RecommendEngine,
)

__all__ = [
    "ConfidenceLevel",
    "ConfidenceConfig",
    "ConfidenceScorer",
    "SafetyConfig",
    "SafetyBounds",
    "SafetyResult",
    "WebhookConfig",
    "WebhookTarget",
    "WebhookDispatcher",
    "SlackFormatter",
    "PagerDutyFormatter",
    "OpsGenieFormatter",
    "ApprovalState",
    "Recommendation",
    "ApprovalManager",
    "RecommendConfig",
    "RecommendEngine",
]
