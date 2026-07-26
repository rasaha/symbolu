"""Canonical enumerations for the AI-Assisted Hiring module.

All enums subclass ``str`` for stable, human-readable serialization (mirroring
the repository's ``agentic.governance_models`` convention). The ten capability
layers are fixed identifiers; role-specific weighting is a later phase and does
not change this set.
"""

from __future__ import annotations

from enum import Enum


# ActorType extracted to the DGM kernel in Phase 5B; re-exported here.
from decision_governance.api.identity import ActorType  # noqa: F401,E402

class WorkflowState(str, Enum):
    """Canonical end-to-end hiring workflow states."""

    PLANNED = "PLANNED"
    SOURCED = "SOURCED"
    ASSESSING = "ASSESSING"
    EVALUATED = "EVALUATED"
    IN_REVIEW = "IN_REVIEW"
    ADVANCED = "ADVANCED"
    HOLD = "HOLD"
    REJECTED = "REJECTED"
    OFFERED = "OFFERED"
    ONBOARDED = "ONBOARDED"


class Disposition(str, Enum):
    """A human review outcome."""

    ADVANCE = "ADVANCE"
    HOLD = "HOLD"
    REJECT = "REJECT"


class EvaluationStatus(str, Enum):
    """Whether an evaluation is clean or held back by the fairness gate."""

    EVALUATED = "EVALUATED"
    REVIEW_BLOCKED = "REVIEW_BLOCKED"


class ConfidenceLevel(str, Enum):
    """How much the system trusts its own layer score.

    A low confidence is a signal to the human reviewer, never a reason to lower
    a score. Calibration of these levels is a later phase.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CapabilityLayer(str, Enum):
    """The ten fixed evaluation layers.

    Definition order is the canonical order (layer numbers 1..10); use
    :meth:`ordered` and :attr:`layer_number` rather than hard-coding indices.
    """

    EXECUTION = "EXECUTION"
    QUALIFICATION_AND_IDENTITY = "QUALIFICATION_AND_IDENTITY"
    WORK_PRODUCT_STRUCTURE = "WORK_PRODUCT_STRUCTURE"
    ADAPTIVE_COGNITION = "ADAPTIVE_COGNITION"
    AGENCY_AND_DECISION_OWNERSHIP = "AGENCY_AND_DECISION_OWNERSHIP"
    REASONING_AND_ANALYSIS = "REASONING_AND_ANALYSIS"
    ROLE_PURPOSE = "ROLE_PURPOSE"
    REFLECTION_AND_SELF_CORRECTION = "REFLECTION_AND_SELF_CORRECTION"
    PROFESSIONAL_COHERENCE = "PROFESSIONAL_COHERENCE"
    SYSTEM_AND_STAKEHOLDER_RESPONSIBILITY = "SYSTEM_AND_STAKEHOLDER_RESPONSIBILITY"

    @classmethod
    def ordered(cls) -> tuple["CapabilityLayer", ...]:
        """Return all ten layers in canonical order."""
        return tuple(cls)

    @property
    def layer_number(self) -> int:
        """1-based canonical position of this layer (1..10)."""
        return list(CapabilityLayer).index(self) + 1


# AuditEventType extracted to the DGM kernel in Phase 5B; re-exported here.
from decision_governance.api.audit import AuditEventType  # noqa: F401,E402

