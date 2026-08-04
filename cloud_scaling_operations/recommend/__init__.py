"""Operations recommend pipeline (approval -> execute, notifications).

Monorepo-only. Confidence scoring and safety bounds remain in the advisory package
(``ugence_cloud_scaling_controller.recommend``); this subpackage adds the
approval/execution/notification stages that are NOT advisory.
"""
from cloud_scaling_operations.recommend.approval import (
    ApprovalState, Recommendation, ApprovalManager,
)
from cloud_scaling_operations.recommend.webhook import (
    WebhookConfig, WebhookTarget, WebhookDispatcher,
    SlackFormatter, PagerDutyFormatter, OpsGenieFormatter,
)
from cloud_scaling_operations.recommend.engine import RecommendConfig, RecommendEngine

__all__ = [
    "ApprovalState", "Recommendation", "ApprovalManager",
    "WebhookConfig", "WebhookTarget", "WebhookDispatcher",
    "SlackFormatter", "PagerDutyFormatter", "OpsGenieFormatter",
    "RecommendConfig", "RecommendEngine",
]
