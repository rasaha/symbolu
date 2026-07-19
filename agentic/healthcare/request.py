"""
HealthcareAccessRequest — the domain request object.

PHI-minimization is a design rule: this structure carries *classifications,
references, policy facts, hashes, and scoped evidence IDs* — never raw
protected medical text. ``patient_ref`` / ``encounter_ref`` are opaque
identifiers (or hashes), not names or clinical content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from agentic.healthcare.taxonomy import (
    ConsentState,
    DataCategory,
    DestinationClass,
    Operation,
    Purpose,
    RecipientType,
    Role,
)


@dataclass(frozen=True)
class HealthcareAccessRequest:
    """A request to read/summarize/search/redact/disclose/export patient data.

    Only classifications and references are stored — no raw PHI. ``declared_facts``
    are caller assertions that the deterministic classifier may use to PROMOTE
    criticality; they are never trusted to downgrade it, and caller-declared
    risk/criticality labels are ignored entirely.
    """

    # Identity / tenancy
    tenant_id: str
    actor_id: str
    actor_role: Role
    operation: Operation
    purpose: Purpose
    requested_categories: Tuple[DataCategory, ...]

    # Optional agent identity (for AI automations)
    agent_id: Optional[str] = None
    agent_version: Optional[str] = None
    model_version: Optional[str] = None

    # Patient / encounter scope (opaque references, not content)
    patient_ref: Optional[str] = None
    encounter_ref: Optional[str] = None
    patient_tenant_id: Optional[str] = None  # tenant that owns the record

    # Recipient / destination
    recipient_type: RecipientType = RecipientType.INTERNAL
    destination_class: DestinationClass = DestinationClass.INTERNAL
    destination_ref: Optional[str] = None  # opaque destination system id

    # Consent posture (state only; policy decides if consent is required)
    consent_state: ConsentState = ConsentState.UNKNOWN

    # Volume / boundary indicators
    record_count: int = 1
    bulk: bool = False
    cross_tenant: bool = False
    external_side_effect: bool = False

    # Approvals / verification (deterministic facts, not model output)
    destination_approved: bool = False
    research_authorization: bool = False  # IRB / approved research protocol
    deidentified: bool = False
    identity_verified: bool = False
    own_record: bool = False  # patient accessing their own record

    urgency: str = "routine"  # routine | urgent | emergency

    # Caller-declared facts — may PROMOTE criticality only. Reserved control
    # keys (e.g. hc_critical/hc_non_critical) are stripped by the adapter so a
    # caller cannot self-classify.
    declared_facts: Mapping[str, Any] = field(default_factory=dict)

    # Scoped evidence references (IDs/hashes only)
    evidence_refs: Tuple[str, ...] = ()

    # Advisory model signals (OPTIONAL). These are model-authored confidence
    # inputs to the generic engine — advisory only; they can tighten a BASELINE
    # decision and can flag applicability, but never override human policy nor
    # downgrade criticality. Defaults are conservative (0.5).
    model_quality: float = 0.5
    model_coherence: float = 0.5
    model_consistency: float = 0.5
    model_goal_alignment: float = 0.5
    model_trajectory_confidence: float = 0.5
    # Advisory model applicability challenge: the model suspects the request does
    # not really belong to the matched rule's class (e.g. a "read" that is really
    # exfiltration). Advisory only — it can escalate, never silently override.
    model_flags_reclassification: bool = False

    def safe_reference(self) -> Dict[str, Any]:
        """A PHI-free reference view for audit (IDs/classifications only)."""
        return {
            "tenant_id": self.tenant_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role.value,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "model_version": self.model_version,
            "operation": self.operation.value,
            "purpose": self.purpose.value,
            "requested_categories": [c.value for c in self.requested_categories],
            "patient_ref": self.patient_ref,
            "encounter_ref": self.encounter_ref,
            "recipient_type": self.recipient_type.value,
            "destination_class": self.destination_class.value,
            "destination_ref": self.destination_ref,
            "consent_state": self.consent_state.value,
            "record_count": self.record_count,
            "bulk": self.bulk,
            "cross_tenant": self.cross_tenant,
            "urgency": self.urgency,
            "evidence_refs": list(self.evidence_refs),
        }
