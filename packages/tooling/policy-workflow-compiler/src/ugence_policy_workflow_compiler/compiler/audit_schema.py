"""Deterministic audit-schema generation (Stage 4).

Builds an :class:`AuditSchema` from the baseline audit fields plus any fields
named by the pack's :class:`AuditRequirement` objects. The schema declares a
deterministic, canonical event-digest chain — explicitly **not** a
cryptographic-immutability claim.
"""

from __future__ import annotations

from typing import Dict

from ..models.audit import (
    BASELINE_AUDIT_FIELDS,
    AuditFieldDefinition,
    AuditSchema,
)
from ..models.policy_pack import PolicyPack

#: Field type hints for a few well-known audit fields; everything else is a string.
_FIELD_TYPES: Dict[str, str] = {
    "policy_pack_version": "integer",
    "source_object_ids": "array<string>",
    "evidence_references": "array<string>",
    "reason_codes": "array<string>",
    "timestamp_field_definition": "timestamp",
}


class AuditSchemaGenerator:
    """Deterministically generates the audit schema for a compiled pack."""

    def generate(self, pack: PolicyPack) -> AuditSchema:
        names: list[str] = list(BASELINE_AUDIT_FIELDS)
        for req in pack.audit_requirements:
            if not req.enabled:
                continue
            for field in req.required_fields:
                if field not in names:
                    names.append(field)
        fields = tuple(
            AuditFieldDefinition(
                name=name,
                type=_FIELD_TYPES.get(name, "string"),
                required=True,
                description="",
            )
            for name in names
        )
        return AuditSchema(
            policy_pack_id=pack.pack_id,
            policy_pack_version=pack.version,
            fields=fields,
            digest_chain_enabled=True,
            digest_algorithm="sha256",
        )
