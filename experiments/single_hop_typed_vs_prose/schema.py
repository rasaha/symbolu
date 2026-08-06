"""Canonical typed records shared by B0 and B1."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


_ALLOWED_STATUSES = {"ANSWERED", "INSUFFICIENT_EVIDENCE"}


def _sorted_str_map(values: Mapping[str, str]) -> dict[str, str]:
    return {str(k): str(values[k]) for k in sorted(values)}


@dataclass(frozen=True)
class Query:
    entity_type: str
    entity_id: str
    relation_type: str | None = None

    def canonical(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "relation_type": self.relation_type,
        }


@dataclass(frozen=True)
class Entity:
    entity_type: str
    entity_id: str
    attributes: Mapping[str, str] = field(default_factory=dict)
    tenant_id: str = ""

    def canonical(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "attributes": _sorted_str_map(self.attributes),
            "tenant_id": self.tenant_id,
        }


@dataclass(frozen=True)
class Relation:
    relation_type: str
    source_entity_type: str
    source_entity_id: str
    target_entity_type: str
    target_entity_id: str
    evidence_ref: str
    tenant_id: str

    def canonical(self) -> dict[str, Any]:
        return {
            "relation_type": self.relation_type,
            "source_entity_type": self.source_entity_type,
            "source_entity_id": self.source_entity_id,
            "target_entity_type": self.target_entity_type,
            "target_entity_id": self.target_entity_id,
            "evidence_ref": self.evidence_ref,
            "tenant_id": self.tenant_id,
        }


@dataclass(frozen=True)
class Evidence:
    evidence_ref: str
    supports_relation: str
    tenant_id: str

    def canonical(self) -> dict[str, Any]:
        return {
            "evidence_ref": self.evidence_ref,
            "supports_relation": self.supports_relation,
            "tenant_id": self.tenant_id,
        }


@dataclass(frozen=True)
class StructuredOutput:
    status: str
    selected_entity_id: str | None
    selected_relation_type: str | None
    relation_supported: bool | None
    evidence_refs: tuple[str, ...]
    tenant_id: str
    reason_code: str

    def __post_init__(self) -> None:
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError(f"unsupported output status: {self.status}")
        if tuple(sorted(set(self.evidence_refs))) != self.evidence_refs:
            raise ValueError("evidence_refs must be unique and sorted")
        if self.status == "INSUFFICIENT_EVIDENCE" and self.selected_entity_id is not None:
            raise ValueError("insufficient-evidence output cannot select an entity")

    def canonical(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_entity_id": self.selected_entity_id,
            "selected_relation_type": self.selected_relation_type,
            "relation_supported": self.relation_supported,
            "evidence_refs": list(self.evidence_refs),
            "tenant_id": self.tenant_id,
            "reason_code": self.reason_code,
        }

    def to_json(self) -> str:
        return json.dumps(self.canonical(), ensure_ascii=True, separators=(",", ":"))


@dataclass(frozen=True)
class CanonicalEpisode:
    episode_id: str
    split: str
    tenant_id: str
    query: Query
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    evidence: tuple[Evidence, ...]
    authoritative_output: StructuredOutput
    domain: str = "synthetic"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        entity_ids = [entity.entity_id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entity IDs must be unique")
        evidence_ids = [item.evidence_ref for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence references must be unique")
        entity_index = {entity.entity_id: entity for entity in self.entities}
        evidence_index = {item.evidence_ref: item for item in self.evidence}
        if self.query.entity_id not in entity_index:
            raise ValueError("query entity must be present in entities")
        for relation in self.relations:
            if relation.source_entity_id not in entity_index:
                raise ValueError(f"missing relation source {relation.source_entity_id}")
            if relation.target_entity_id not in entity_index:
                raise ValueError(f"missing relation target {relation.target_entity_id}")
            if relation.evidence_ref not in evidence_index:
                raise ValueError(f"missing evidence {relation.evidence_ref}")
            if evidence_index[relation.evidence_ref].supports_relation != relation.relation_type:
                raise ValueError("evidence relation type does not match relation")
        if self.authoritative_output.tenant_id != self.tenant_id:
            raise ValueError("output tenant must match authorized tenant")
        if self.authoritative_output.selected_entity_id is not None:
            if self.authoritative_output.selected_entity_id not in entity_index:
                raise ValueError("selected entity must be present in entities")
        if not set(self.authoritative_output.evidence_refs).issubset(evidence_index):
            raise ValueError("output references unknown evidence")

    def visible_canonical(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "query": self.query.canonical(),
            "entities": [item.canonical() for item in sorted(self.entities, key=lambda x: x.entity_id)],
            "relations": [
                item.canonical()
                for item in sorted(
                    self.relations,
                    key=lambda x: (x.source_entity_id, x.relation_type, x.target_entity_id, x.evidence_ref),
                )
            ],
            "evidence": [item.canonical() for item in sorted(self.evidence, key=lambda x: x.evidence_ref)],
        }

    def fact_hash(self) -> str:
        payload = json.dumps(
            self.visible_canonical(), ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def ensure_tuple(items: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(items)
