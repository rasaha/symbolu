"""Audit requirements and the generated audit schema.

An :class:`AuditRequirement` states what must be recorded to reconstruct a
decision. The compiler generates an :class:`AuditSchema` (field definitions) and,
optionally, a deterministic event-digest chain based on canonical serialization.
The compiler does **not** claim cryptographic immutability — only a deterministic,
canonical digest chain.
"""

from __future__ import annotations

from typing import Tuple

from pydantic import Field

from .common import CompilerModel, ObjectType, PolicyObject


class AuditRequirement(PolicyObject):
    """What must be recorded to reconstruct a decision."""

    object_type: ObjectType = ObjectType.AUDIT_REQUIREMENT
    #: Field names that must be present in the audit record for the governed nodes
    #: this requirement applies to.
    required_fields: Tuple[str, ...] = ()
    #: The workflow node kinds this requirement applies to (declarative labels).
    applies_to_node_kinds: Tuple[str, ...] = ()


class AuditFieldDefinition(CompilerModel):
    """One field in the generated audit schema."""

    name: str = Field(..., min_length=1)
    type: str = "string"
    required: bool = True
    description: str = ""


#: The baseline audit fields every compiled schema includes, per the spec.
BASELINE_AUDIT_FIELDS: Tuple[str, ...] = (
    "policy_pack_id",
    "policy_pack_version",
    "compiled_package_digest",
    "workflow_node_id",
    "source_object_ids",
    "evidence_references",
    "actor_identity",
    "actor_role",
    "authority_reference",
    "recommendation_reference",
    "decision_reference",
    "action_reference",
    "constraint_digest",
    "override_reference",
    "exception_reference",
    "outcome",
    "reason_codes",
    "timestamp_field_definition",
    "previous_event_digest",
    "event_digest",
)


class AuditSchema(CompilerModel):
    """The generated audit schema for a compiled pack."""

    policy_pack_id: str
    policy_pack_version: int
    fields: Tuple[AuditFieldDefinition, ...] = ()
    #: Whether a deterministic event-digest chain is defined (canonical, not a
    #: cryptographic-immutability claim).
    digest_chain_enabled: bool = True
    #: The hash algorithm used for the digest chain.
    digest_algorithm: str = "sha256"
