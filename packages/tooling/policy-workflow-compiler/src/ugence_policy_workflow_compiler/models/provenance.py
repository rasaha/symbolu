"""Provenance objects.

Every substantive policy object must cite at least one provenance source. A
source is a typed, addressable reference back to the material an object was
derived from (policy clause, regulation, authority matrix, API schema, incident
report). Objects with no provenance are ``PROPOSED_ONLY`` (see
:class:`~ugence_policy_workflow_compiler.models.common.ProvenanceStatus`) and are
excluded from deterministic synthesis unless a reviewer explicitly approves the
gap. The compiler never fabricates provenance.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from .common import CompilerModel, ObjectType, PolicyObject


class ProvenanceSourceType(str, Enum):
    POLICY_CLAUSE = "POLICY_CLAUSE"
    REGULATION = "REGULATION"
    STANDARD = "STANDARD"
    AUTHORITY_MATRIX = "AUTHORITY_MATRIX"
    API_SCHEMA = "API_SCHEMA"
    CONNECTOR_METADATA = "CONNECTOR_METADATA"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    REFERENCE_IMPLEMENTATION = "REFERENCE_IMPLEMENTATION"
    INTERNAL_MEMO = "INTERNAL_MEMO"


class ProvenanceReference(CompilerModel):
    """A single citation back to authoritative source material.

    This is not a :class:`PolicyObject`; it is an embeddable citation. Objects
    reference it (and :class:`SourceDocument`) by ``source_id``.
    """

    source_id: str = Field(..., min_length=1)
    source_type: ProvenanceSourceType
    title: str = Field(..., min_length=1)
    version: str = ""
    content_digest: str = ""
    location: str = ""
    clause: str = ""
    page: Optional[int] = None
    section: str = ""
    effective_date: str = ""  # ISO date string; kept as text to stay deterministic
    authority_level: str = ""


class SourceDocument(PolicyObject):
    """A reviewed source document registered in the pack.

    A ``SourceDocument`` gives ``ProvenanceReference.source_id`` values a home in
    the pack. Its ``content_digest`` binds the citation to exact reviewed content.
    """

    object_type: ObjectType = ObjectType.SOURCE_DOCUMENT
    source_type: ProvenanceSourceType
    title: str = Field(..., min_length=1)
    document_version: str = ""
    content_digest: str = ""
    effective_date: str = ""
    authority_level: str = ""
