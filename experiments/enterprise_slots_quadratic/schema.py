"""
schema.py — canonical enterprise evidence schema (procurement & approval governance).

Every evidence record carries the exact, resolvable fields below. Categorical fields are small
ints (ids into bounded vocabularies) so identity-renaming and held-out-id splits are structural,
not string matching. The record is the authoritative unit; slots hold a copy of it plus a learned
representation but never mutate the exact fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# ---- bounded vocabularies ----
SUBJECT_TYPES = ("PurchaseRequest", "Vendor", "Contract", "Budget", "Policy", "Approval",
                 "Employee", "Department", "Exception", "Invoice")
RELATION_TYPES = ("requires_approval", "has_budget", "awarded_to", "governed_by", "supersedes",
                  "grants_exception", "authorized_by", "bills", "belongs_to", "conflicts_with")
OBJECT_TYPES = ("Role", "Amount", "Vendor", "Contract", "Policy", "Boolean", "Employee", "Value")
ROLES = ("role:requester", "role:finance", "role:finance_director", "role:auditor", "role:admin")
STATUSES = ("active", "superseded", "expired", "pending", "revoked")
ACTIVE, SUPERSEDED, EXPIRED, PENDING, REVOKED = range(5)

N_SUBJECT_TYPE = len(SUBJECT_TYPES)
N_RELATION_TYPE = len(RELATION_TYPES)
N_OBJECT_TYPE = len(OBJECT_TYPES)
N_STATUS = len(STATUSES)
N_ROLE = len(ROLES)


@dataclass
class Evidence:
    tenant_id: int
    evidence_id: int                    # unique, resolvable in the ledger
    document_id: int
    section_id: int
    subject_type: int
    subject_id: int
    relation_type: int
    object_type: int
    object_id_or_value: int
    timestamp: int
    valid_from: int
    valid_to: int
    version: int
    status: int
    source_authority: float
    source_span: int                    # page/offset marker
    access_roles: int                   # bitmask over ROLES (which roles may read it)
    # generator bookkeeping (never fed as a runtime feature)
    template: int = 0
    tag: str = ""
    arrival_section: int = 0            # workflow step at which it appears (streaming/multi-step)

    def key_tuple(self):
        """Exact (subject, relation, object) identity for join/dedup — deterministic, not learned."""
        return (self.subject_type, self.subject_id, self.relation_type,
                self.object_type, self.object_id_or_value)

    def readable_by(self, role_idx: int) -> bool:
        return bool(self.access_roles & (1 << role_idx))

    def as_record(self) -> Dict:
        return asdict(self)


# categorical fields fed to the encoder (exact ids); numeric fields handled separately
CAT_FIELDS = ("subject_type", "subject_id", "relation_type", "object_type", "object_id_or_value",
              "status", "version", "section_id", "document_id", "template")


def field_dims(cfg) -> Dict[str, int]:
    return {"subject_type": N_SUBJECT_TYPE, "subject_id": cfg.n_subject_ids,
            "relation_type": N_RELATION_TYPE, "object_type": N_OBJECT_TYPE,
            "object_id_or_value": cfg.n_object_ids, "status": N_STATUS,
            "version": cfg.n_versions, "section_id": cfg.n_sections,
            "document_id": cfg.n_documents, "template": cfg.n_templates}


@dataclass
class DomainCfg:
    n_subject_ids: int = 48
    n_object_ids: int = 48
    n_versions: int = 8
    n_sections: int = 32
    n_documents: int = 16
    n_templates: int = 12
    n_tenants: int = 2
    slot_repr_dim: int = 48
