"""Required-evidence objects.

Evidence fields that must be present and admissible before a recommendation may
become binding. Compiles to evidence collectors plus TAP admissibility. A
``RequiredEvidence`` object with no authoritative connector field is a
compile-time gap surfaced to the reviewer.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from .common import BlockBehavior, CapabilityId, ObjectType, PolicyObject


class EvidenceKind(str, Enum):
    DOCUMENT = "DOCUMENT"
    ASSESSMENT = "ASSESSMENT"
    ATTESTATION = "ATTESTATION"
    SYSTEM_RECORD = "SYSTEM_RECORD"
    FIELD_VALUE = "FIELD_VALUE"


class RequiredEvidence(PolicyObject):
    """An evidence field that must be present/valid, with fail-closed behavior."""

    object_type: ObjectType = ObjectType.REQUIRED_EVIDENCE
    evidence_kind: EvidenceKind = EvidenceKind.FIELD_VALUE
    #: The scenario fact key that carries this evidence.
    fact_key: str = Field(..., min_length=1)
    #: Connector mapping object id that designates the authoritative field.
    connector_mapping_id: str = ""
    #: Behavior when the evidence is absent/invalid — never silently proceed.
    on_missing: BlockBehavior = BlockBehavior.BLOCK
    #: Whether admissibility (freshness/quarantine) must be checked via TAP.
    requires_admissibility_check: bool = True
    #: The capability that admits the evidence (TAP for admissibility).
    admissibility_capability: CapabilityId = CapabilityId.TAP
