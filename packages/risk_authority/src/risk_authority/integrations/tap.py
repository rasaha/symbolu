"""TAP-compatible evidence-admission contract (spec §9, roadmap RA-5).

``risk_authority`` consumes evidence admission through this port rather than
re-implementing TAP. The reference admitter is intentionally minimal — it
enforces the fail-closed admissibility rule (provenance/integrity/freshness)
over already-populated :class:`ControlEvidenceRecord`s so the domain has a
working default before the full TAP provider is wired in at RA-5.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ..domain.enums import EvidenceState
from ..domain.evidence import ControlEvidenceRecord

__all__ = ["EvidenceAdmissionPort", "ReferenceEvidenceAdmission"]


@runtime_checkable
class EvidenceAdmissionPort(Protocol):
    """Decide whether an evidence record is admissible for control evaluation."""

    def is_admissible(
        self, evidence: ControlEvidenceRecord, *, now: datetime
    ) -> bool: ...


class ReferenceEvidenceAdmission:
    """A minimal admitter: admitted status plus current validity window."""

    def is_admissible(
        self, evidence: ControlEvidenceRecord, *, now: datetime
    ) -> bool:
        if evidence.admission.status is not EvidenceState.ADMITTED:
            return False
        return evidence.is_current(now)
