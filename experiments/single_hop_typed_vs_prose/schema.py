"""Immutable canonical episode and shared structured-output schemas."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .config import OUTPUT_FIELDS, STATUS_VALUES


def _ascii(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must be ASCII") from exc
    return value


def _attributes(value: Mapping[str, str] | Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    pairs = tuple(value.items()) if isinstance(value, Mapping) else tuple(value)
    normalized = tuple(
        sorted(
            (_ascii(str(key), "attribute key"), _ascii(str(item), "attribute value"))
            for key, item in pairs
        )
    )
    if len({key for key, _ in normalized}) != len(normalized):
        raise ValueError("attribute keys must be unique")
    return normalized


@dataclass(frozen=True)
class Entity:
    entity_type: str
    entity_id: str
    tenant_id: str
    display_name: str | None = None
    attributes: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_type", _ascii(self.entity_type, "entity_type"))
        object.__setattr__(self, "entity_id", _ascii(self.entity_id, "entity_id"))
        object.__setattr__(self, "tenant_id", _ascii(self.tenant_id, "tenant_id"))
        if self.display_name is not None:
            object.__setattr__(self, "display_name", _ascii(self.display_name, "display_name"))
        object.__setattr__(self, "attributes", _attributes(self.attributes))

    def payload(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "display_name": self.display_name,
            "attributes": dict(self.attributes),
            "tenant_id": self.tenant_id,
        }


@dataclass(frozen=True)
class Query:
    operation: str
    entity_type: str
    entity_id: str
    relation_type: str | None = None

    def __post_init__(self) -> None:
        allowed = {
            "select_entity",
            "select_relation_target",
            "validate_relation",
            "select_evidence",
        }
        if self.operation not in allowed:
            raise ValueError(f"unsupported query operation: {self.operation}")
        object.__setattr__(self, "entity_type", _ascii(self.entity_type, "query entity_type"))
        object.__setattr__(self, "entity_id", _ascii(self.entity_id, "query entity_id"))
        if self.relation_type is not None:
            object.__setattr__(
                self,
                "relation_type",
                _ascii(self.relation_type, "query relation_type"),
            )

    def payload(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "relation_type": self.relation_type,
        }


@dataclass(frozen=True)
class Relation:
    relation_type: str
    source_entity_type: str
    source_entity_id: str
    target_entity_type: str
    target_entity_id: str
    evidence_ref: str | None
    tenant_id: str

    def __post_init__(self) -> None:
        for name in (
            "relation_type",
            "source_entity_type",
            "source_entity_id",
            "target_entity_type",
            "target_entity_id",
            "tenant_id",
        ):
            object.__setattr__(self, name, _ascii(getattr(self, name), name))
        if self.evidence_ref is not None:
            object.__setattr__(self, "evidence_ref", _ascii(self.evidence_ref, "evidence_ref"))

    def payload(self) -> dict[str, Any]:
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
    stance: str = "supports"
    admissible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ref", _ascii(self.evidence_ref, "evidence_ref"))
        object.__setattr__(
            self,
            "supports_relation",
            _ascii(self.supports_relation, "supports_relation"),
        )
        object.__setattr__(self, "tenant_id", _ascii(self.tenant_id, "tenant_id"))
        if self.stance not in {"supports", "contradicts"}:
            raise ValueError("evidence stance must be supports or contradicts")

    def payload(self) -> dict[str, Any]:
        return {
            "evidence_ref": self.evidence_ref,
            "supports_relation": self.supports_relation,
            "stance": self.stance,
            "admissible": self.admissible,
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
        if self.status not in STATUS_VALUES:
            raise ValueError(f"invalid output status: {self.status}")
        for name in ("selected_entity_id", "selected_relation_type"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _ascii(value, name))
        refs = tuple(_ascii(ref, "evidence_ref") for ref in self.evidence_refs)
        if len(set(refs)) != len(refs):
            raise ValueError("evidence_refs must be unique")
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "tenant_id", _ascii(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "reason_code", _ascii(self.reason_code, "reason_code"))
        if self.status == "INSUFFICIENT_EVIDENCE" and (
            self.selected_entity_id is not None or self.evidence_refs
        ):
            raise ValueError(
                "insufficient-evidence output cannot select an entity or evidence"
            )

    def payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_entity_id": self.selected_entity_id,
            "selected_relation_type": self.selected_relation_type,
            "relation_supported": self.relation_supported,
            "evidence_refs": list(self.evidence_refs),
            "tenant_id": self.tenant_id,
            "reason_code": self.reason_code,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.payload(), ensure_ascii=True, separators=(",", ":"))

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "StructuredOutput":
        if tuple(payload.keys()) != OUTPUT_FIELDS:
            raise ValueError(
                "structured output fields or field order do not match the shared contract"
            )
        refs = payload["evidence_refs"]
        if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
            raise ValueError("evidence_refs must be a JSON string array")
        supported = payload["relation_supported"]
        if supported is not None and not isinstance(supported, bool):
            raise ValueError("relation_supported must be true, false, or null")
        return cls(
            status=payload["status"],
            selected_entity_id=payload["selected_entity_id"],
            selected_relation_type=payload["selected_relation_type"],
            relation_supported=supported,
            evidence_refs=tuple(refs),
            tenant_id=payload["tenant_id"],
            reason_code=payload["reason_code"],
        )


@dataclass(frozen=True)
class CanonicalEpisode:
    episode_id: str
    scenario_id: str
    tenant_id: str
    query: Query
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    evidence: tuple[Evidence, ...]
    authoritative_output: StructuredOutput

    def __post_init__(self) -> None:
        object.__setattr__(self, "episode_id", _ascii(self.episode_id, "episode_id"))
        object.__setattr__(self, "scenario_id", _ascii(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "tenant_id", _ascii(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        self.validate()

    def validate(self) -> None:
        entity_ids = [item.entity_id for item in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entity IDs must be unique")
        entities = {item.entity_id: item for item in self.entities}
        if self.query.entity_id not in entities:
            raise ValueError("query entity must exist")
        evidence_refs = [item.evidence_ref for item in self.evidence]
        if len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("evidence references must be unique")
        evidence_map = {item.evidence_ref: item for item in self.evidence}
        relation_keys: set[tuple[str, str, str]] = set()
        for relation in self.relations:
            key = (
                relation.source_entity_id,
                relation.relation_type,
                relation.target_entity_id,
            )
            if key in relation_keys:
                raise ValueError("duplicate relation identity")
            relation_keys.add(key)
            if (
                relation.source_entity_id not in entities
                or relation.target_entity_id not in entities
            ):
                raise ValueError("relation references an unknown entity")
            if (
                relation.evidence_ref is not None
                and relation.evidence_ref not in evidence_map
            ):
                raise ValueError("relation references unknown evidence")
            if relation.evidence_ref is not None:
                evidence = evidence_map[relation.evidence_ref]
                if evidence.supports_relation != relation.relation_type:
                    raise ValueError("evidence relation type mismatch")
        if self.authoritative_output.tenant_id != self.tenant_id:
            raise ValueError("authoritative output tenant mismatch")

    def visible_canonical(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "query": self.query.payload(),
            "entities": [
                item.payload()
                for item in sorted(self.entities, key=lambda entity: entity.entity_id)
            ],
            "relations": [
                item.payload()
                for item in sorted(
                    self.relations,
                    key=lambda relation: (
                        relation.source_entity_id,
                        relation.relation_type,
                        relation.target_entity_id,
                    ),
                )
            ],
            "evidence": [
                item.payload()
                for item in sorted(
                    self.evidence,
                    key=lambda evidence: evidence.evidence_ref,
                )
            ],
        }

    def fact_hash(self) -> str:
        payload = json.dumps(
            self.visible_canonical(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()
