"""H3 governance integration — bind hiring recommendations to the DGM kernel."""

from __future__ import annotations

from .binding import GovernanceBindingStatus, GovernanceCaseBinding
from .linked_record import HiringRecommendationLinkedRecordAdapter
from .outcomes import (
    HiringDecisionIntent,
    decision_outcome_for,
    is_override,
    proposed_outcome_for,
)
from .reconstruction import GovernanceCaseReconstruction, GovernanceCaseReconstructionService
from .views import (
    GovernanceDashboardView,
    GovernanceViewService,
    RecommendationHistoryView,
    ReviewWorkspaceView,
)

__all__ = [
    "GovernanceCaseBinding", "GovernanceBindingStatus",
    "HiringRecommendationLinkedRecordAdapter",
    "HiringDecisionIntent", "proposed_outcome_for", "decision_outcome_for", "is_override",
    "GovernanceCaseReconstructionService", "GovernanceCaseReconstruction",
    "GovernanceViewService", "ReviewWorkspaceView", "GovernanceDashboardView",
    "RecommendationHistoryView",
]
