"""Admitted-evidence value object consumed by the decision plane.

Evidence admission itself is a shared platform capability (TAP), reached through
:class:`~ugence_ai_hiring.hiring_decision.ports.EvidenceAdmissionPort`; this
package does **not** implement admission. ``AdmittedEvidence`` is the neutral
in-domain representation of one item plus its admission verdict. The gate
evaluator consumes only items whose ``admitted`` is True.
"""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..hiring_policy.enums import HiringEvidenceClass


class AdmittedEvidence(DomainModel):
    """One evidence item and its TAP admission verdict.

    ``attributes`` carries the deterministic facts a mandatory gate reads (e.g.
    ``{"clearance_active": True}``). Unadmitted items are inert: the gate
    evaluator ignores them entirely, so they can never satisfy a gate.
    """

    evidence_id: str
    evidence_class: HiringEvidenceClass
    admitted: bool
    lineage_node_id: str
    attributes: dict[str, Any] = {}
    is_post_hire: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "AdmittedEvidence":
        if not self.evidence_id.strip():
            raise DomainValidationError("evidence_id is required")
        if not self.lineage_node_id.strip():
            raise DomainValidationError("lineage_node_id is required")
        return self
