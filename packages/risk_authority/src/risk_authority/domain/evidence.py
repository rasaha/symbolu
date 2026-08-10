"""Evidence metadata and admission records (spec §9).

Only *admissible* evidence may back a passing control. This module owns the
typed records; the admission decision itself is a contract (TAP-compatible)
consumed from ``integrations.tap`` and layered in RA-5 — the domain shape is
defined now so control results can reference admitted evidence from day one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

from .enums import EvidenceState

__all__ = ["EvidenceAdmission", "ControlEvidenceRecord"]


@dataclass(frozen=True)
class EvidenceAdmission:
    status: EvidenceState
    reason: str = ""


@dataclass(frozen=True)
class ControlEvidenceRecord:
    """Admissible evidence with provenance, validity and subject binding."""

    evidence_id: str
    tenant_id: str
    type: str
    subject_id: str
    issuer: str
    created_at: datetime
    valid_until: Optional[datetime]
    digest: str
    admission: EvidenceAdmission
    provenance: Mapping[str, str] = field(default_factory=dict)

    def is_admitted(self) -> bool:
        return self.admission.status is EvidenceState.ADMITTED

    def is_current(self, now: datetime) -> bool:
        return self.valid_until is None or now <= self.valid_until
