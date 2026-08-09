"""Frozen BTRR typed schema (Amendment 002 caps enforced). Torch-free.

Extends the single-hop typed contract with Event, Condition, Policy, Constraints, ReasoningQuery,
ReasoningContext, ReasoningOutput. All records ASCII, immutable, deterministic. The authoritative gold
output is stored on the context but is NEVER part of visible_canonical()/fact_hash()/serialization.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .config import CAPS, OUTCOME_VOCAB, STATUS_VALUES
from .tokenizer import BTRRTokenizer

_TOK = BTRRTokenizer()

_REQUESTED_PROPERTY = frozenset({"approval_requirement", "target_attribute", "latest_state"})
_POLICY_SCOPE = frozenset({"vendor_risk", "contract_state", "assignment"})
_EVENT_TYPES = frozenset({"risk", "status", "tier"})
_OPERATIONS = frozenset({
    "resolve_attribute", "resolve_path_target", "latest_event_value", "path_then_latest", "apply_policy",
})
_PATH_MODES = frozenset({"PATH_GIVEN", "PATH_DISCOVERY", "NOT_APPLICABLE"})
_OPERATORS = frozenset({"EQ", "GT", "GE", "LT", "LE", "NE"})
_STANCES = frozenset({"supports", "contradicts"})


class SchemaError(ValueError):
    """Raised on any cap violation, FK break, tenant impurity, or gold leakage."""


def _ascii(v: str, name: str) -> str:
    if not isinstance(v, str) or not v:
        raise SchemaError(f"{name} must be a non-empty string")
    try:
        v.encode("ascii")
    except UnicodeEncodeError as exc:
        raise SchemaError(f"{name} must be ASCII") from exc
    return v


def _check_id(v: str, name: str) -> str:
    _ascii(v, name)
    if len(v) > CAPS["max_id_len"]:
        raise SchemaError(f"{name} exceeds max_id_len={CAPS['max_id_len']}: {v!r}")
    return v


def _check_value(v: str, name: str) -> str:
    _ascii(v, name)
    if _TOK.count(v, add_bos=False) > CAPS["max_value_len_tokens"]:
        raise SchemaError(f"{name} exceeds max_value_len_tokens={CAPS['max_value_len_tokens']}: {v!r}")
    if v.isdigit() and len(v) > CAPS["max_numeric_digits"]:
        raise SchemaError(f"{name} numeric literal exceeds max_numeric_digits: {v!r}")
    return v


@dataclass(frozen=True)
class Entity:
    entity_type: str
    entity_id: str
    tenant_id: str
    attributes: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _ascii(self.entity_type, "entity_type")
        _check_id(self.entity_id, "entity_id")
        _check_id(self.tenant_id, "tenant_id")
        if len(self.attributes) > CAPS["max_attributes_per_entity"]:
            raise SchemaError("entity exceeds max_attributes_per_entity")
        keys = [k for k, _ in self.attributes]
        if len(keys) != len(set(keys)):
            raise SchemaError("duplicate attribute key")
        for k, v in self.attributes:
            _ascii(k, "attribute key")
            _check_value(v, "attribute value")

    def payload(self) -> dict[str, Any]:
        return {"entity_type": self.entity_type, "entity_id": self.entity_id,
                "tenant_id": self.tenant_id, "attributes": dict(self.attributes)}


@dataclass(frozen=True)
class Relation:
    relation_type: str
    source_entity_id: str
    target_entity_id: str
    tenant_id: str
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        _ascii(self.relation_type, "relation_type")
        _check_id(self.source_entity_id, "source_entity_id")
        _check_id(self.target_entity_id, "target_entity_id")
        _check_id(self.tenant_id, "tenant_id")
        if self.evidence_ref is not None:
            _check_id(self.evidence_ref, "evidence_ref")

    def key(self) -> tuple[str, str, str]:
        return (self.source_entity_id, self.relation_type, self.target_entity_id)

    def payload(self) -> dict[str, Any]:
        return {"relation_type": self.relation_type, "source_entity_id": self.source_entity_id,
                "target_entity_id": self.target_entity_id, "tenant_id": self.tenant_id,
                "evidence_ref": self.evidence_ref}


@dataclass(frozen=True)
class Event:
    event_id: str
    entity_id: str
    event_type: str
    sequence: int
    value: str
    tenant_id: str
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        _check_id(self.event_id, "event_id")
        _check_id(self.entity_id, "entity_id")
        if self.event_type not in _EVENT_TYPES:
            raise SchemaError(f"unknown event_type: {self.event_type}")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise SchemaError("sequence must be a non-negative int")
        if len(str(self.sequence)) > CAPS["max_sequence_digits"]:
            raise SchemaError("sequence exceeds max_sequence_digits")
        _check_value(self.value, "event value")
        _check_id(self.tenant_id, "tenant_id")
        if self.evidence_ref is not None:
            _check_id(self.evidence_ref, "evidence_ref")

    def payload(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "entity_id": self.entity_id, "event_type": self.event_type,
                "sequence": self.sequence, "value": self.value, "tenant_id": self.tenant_id,
                "evidence_ref": self.evidence_ref}


@dataclass(frozen=True)
class Condition:
    field_name: str
    operator: str
    literal: str

    def __post_init__(self) -> None:
        _ascii(self.field_name, "condition field")
        if self.operator not in _OPERATORS:
            raise SchemaError(f"unknown operator: {self.operator}")
        _check_value(self.literal, "condition literal")

    def payload(self) -> dict[str, Any]:
        return {"field": self.field_name, "op": self.operator, "literal": self.literal}


@dataclass(frozen=True)
class Policy:
    policy_id: str
    conditions: tuple[Condition, ...]
    outcome: str
    tenant_id: str

    def __post_init__(self) -> None:
        _check_id(self.policy_id, "policy_id")
        if not (1 <= len(self.conditions) <= CAPS["max_conditions_per_policy"]):
            raise SchemaError("policy conditions out of [1, max_conditions_per_policy]")
        if self.outcome not in OUTCOME_VOCAB:
            raise SchemaError(f"policy outcome not in OUTCOME_VOCAB: {self.outcome}")
        _check_id(self.tenant_id, "tenant_id")

    def payload(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "conditions": [c.payload() for c in self.conditions],
                "outcome": self.outcome, "tenant_id": self.tenant_id}


@dataclass(frozen=True)
class Evidence:
    evidence_ref: str
    stance: str
    supports_ref: str
    tenant_id: str
    admissible: bool = True

    def __post_init__(self) -> None:
        _check_id(self.evidence_ref, "evidence_ref")
        if self.stance not in _STANCES:
            raise SchemaError("evidence stance must be supports/contradicts")
        _ascii(self.supports_ref, "supports_ref")
        _check_id(self.tenant_id, "tenant_id")

    def payload(self) -> dict[str, Any]:
        return {"evidence_ref": self.evidence_ref, "stance": self.stance,
                "supports_ref": self.supports_ref, "admissible": self.admissible,
                "tenant_id": self.tenant_id}


@dataclass(frozen=True)
class Constraints:
    max_hops: int
    temporal: bool
    policy: bool

    def __post_init__(self) -> None:
        if not (0 <= self.max_hops <= CAPS["max_hops"]):
            raise SchemaError("max_hops out of range")

    def payload(self) -> dict[str, Any]:
        return {"max_hops": self.max_hops, "temporal": self.temporal, "policy": self.policy}


@dataclass(frozen=True)
class ReasoningQuery:
    operation: str
    path_mode: str
    root_entity_id: str
    relation_chain: tuple[str, ...] = ()
    requested_property: str | None = None
    event_type: str | None = None
    policy_scope: str | None = None

    def __post_init__(self) -> None:
        if self.operation not in _OPERATIONS:
            raise SchemaError(f"unknown operation: {self.operation}")
        if self.path_mode not in _PATH_MODES:
            raise SchemaError(f"unknown path_mode: {self.path_mode}")
        _check_id(self.root_entity_id, "root_entity_id")
        if len(self.relation_chain) > CAPS["max_hops"]:
            raise SchemaError("relation_chain exceeds max_hops")
        if self.path_mode == "PATH_GIVEN" and not self.relation_chain:
            raise SchemaError("PATH_GIVEN requires a non-empty relation_chain")
        if self.path_mode == "PATH_DISCOVERY" and self.relation_chain:
            raise SchemaError("PATH_DISCOVERY must have an empty relation_chain")
        if self.requested_property is not None and self.requested_property not in _REQUESTED_PROPERTY:
            raise SchemaError("requested_property not in frozen label vocabulary")
        if self.event_type is not None and self.event_type not in _EVENT_TYPES:
            raise SchemaError("query event_type unknown")
        if self.policy_scope is not None and self.policy_scope not in _POLICY_SCOPE:
            raise SchemaError("policy_scope not in frozen label vocabulary")

    def payload(self) -> dict[str, Any]:
        return {"operation": self.operation, "path_mode": self.path_mode,
                "root_entity_id": self.root_entity_id, "relation_chain": list(self.relation_chain),
                "requested_property": self.requested_property, "event_type": self.event_type,
                "policy_scope": self.policy_scope}


@dataclass(frozen=True)
class ReasoningOutput:
    answer: str | None
    reasoning_path: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    status: str

    def __post_init__(self) -> None:
        if self.status not in STATUS_VALUES:
            raise SchemaError(f"invalid status: {self.status}")
        if len(self.reasoning_path) > CAPS["max_reasoning_path_nodes"]:
            raise SchemaError("reasoning_path exceeds max_reasoning_path_nodes")
        if len(self.evidence_ids) > CAPS["max_evidence_ids_in_output"]:
            raise SchemaError("evidence_ids exceeds cap")

    def payload(self) -> dict[str, Any]:
        return {"answer": self.answer, "reasoning_path": list(self.reasoning_path),
                "evidence_ids": list(self.evidence_ids), "status": self.status}


@dataclass(frozen=True)
class ReasoningContext:
    context_id: str
    tenant_id: str
    query: ReasoningQuery
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    events: tuple[Event, ...]
    policies: tuple[Policy, ...]
    evidence: tuple[Evidence, ...]
    constraints: Constraints
    authoritative_output: ReasoningOutput  # gold; NEVER serialized to the model
    split: str = "R1"

    def __post_init__(self) -> None:
        self.validate()

    # ---- validation: caps + FK + tenant purity + PATH_DISCOVERY exclusion ----
    def validate(self) -> None:
        c = CAPS
        if not (c["min_entities"] <= len(self.entities) <= c["max_entities"]):
            raise SchemaError("entity count outside frozen density 6..12")
        if len(self.relations) > c["max_relations"]:
            raise SchemaError("relation count exceeds cap")
        if len(self.events) > c["max_events_total"]:
            raise SchemaError("event count exceeds cap")
        if len(self.policies) > c["max_policies"]:
            raise SchemaError("policy count exceeds cap")
        if len(self.evidence) > c["max_evidence"]:
            raise SchemaError("evidence count exceeds cap")

        entity_ids = [e.entity_id for e in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise SchemaError("duplicate entity id")
        ids = set(entity_ids)
        # tenant purity: every visible record shares the context tenant
        for rec in (*self.entities, *self.relations, *self.events, *self.policies, *self.evidence):
            if rec.tenant_id != self.tenant_id:
                raise SchemaError("tenant impurity: visible record from a different tenant")
        # per-entity event cap
        per_entity: dict[str, int] = {}
        for ev in self.events:
            if ev.entity_id not in ids:
                raise SchemaError("event references unknown entity")
            per_entity[ev.entity_id] = per_entity.get(ev.entity_id, 0) + 1
        if any(n > c["max_events_per_entity"] for n in per_entity.values()):
            raise SchemaError("events per entity exceed cap")
        # relation FK + uniqueness
        rel_keys = set()
        for r in self.relations:
            if r.source_entity_id not in ids or r.target_entity_id not in ids:
                raise SchemaError("relation references unknown entity")
            if r.key() in rel_keys:
                raise SchemaError("duplicate relation identity")
            rel_keys.add(r.key())
        # evidence FK: supports_ref must be a known relation-key string or event id
        ev_ids = {e.event_id for e in self.events}
        rel_ref_strings = {f"{r.source_entity_id}|{r.relation_type}|{r.target_entity_id}" for r in self.relations}
        ev_refs = {e.evidence_ref for e in self.evidence}
        if len(ev_refs) != len(self.evidence):
            raise SchemaError("duplicate evidence ref")
        for e in self.evidence:
            if e.supports_ref not in ev_ids and e.supports_ref not in rel_ref_strings:
                raise SchemaError("evidence supports_ref does not resolve")
        # query root exists
        if self.query.root_entity_id not in ids:
            raise SchemaError("query root entity does not exist")
        # PATH_DISCOVERY mechanical exclusion of gold path / intermediate ids / policy id / outcome
        if self.query.path_mode == "PATH_DISCOVERY":
            if self.query.relation_chain:
                raise SchemaError("PATH_DISCOVERY leaks a relation chain")
            self._assert_no_gold_leak_in_query()
        # authoritative output tenant + gold-key exclusion
        if not isinstance(self.authoritative_output, ReasoningOutput):
            raise SchemaError("authoritative_output must be a ReasoningOutput")
        # gold must not be discoverable from visible payload keys
        _assert_no_forbidden_keys(self.visible_canonical())

    def _assert_no_gold_leak_in_query(self) -> None:
        q = self.query
        fields = [q.operation, q.path_mode, q.root_entity_id, q.requested_property or "",
                  q.event_type or "", q.policy_scope or "", *q.relation_chain]
        gold_answer = self.authoritative_output.answer
        non_root_ids = {e.entity_id for e in self.entities if e.entity_id != q.root_entity_id}
        policy_ids = {p.policy_id for p in self.policies}
        for f in fields:
            if gold_answer is not None and f == gold_answer:
                raise SchemaError("query leaks the gold outcome")
            if f in non_root_ids:
                raise SchemaError("query leaks an intermediate entity id")
            if f in policy_ids:
                raise SchemaError("query leaks the target policy id")
            if f in OUTCOME_VOCAB:
                raise SchemaError("query leaks an outcome token")

    def visible_canonical(self) -> dict[str, Any]:
        q = self.query.payload()
        if self.query.path_mode == "PATH_DISCOVERY":
            q = {k: v for k, v in q.items() if k != "relation_chain"}
        return {
            "tenant_id": self.tenant_id,
            "query": q,
            "constraints": self.constraints.payload(),
            "entities": [e.payload() for e in sorted(self.entities, key=lambda x: x.entity_id)],
            "relations": [r.payload() for r in sorted(self.relations, key=lambda x: x.key())],
            "events": [e.payload() for e in sorted(self.events, key=lambda x: x.event_id)],
            "policies": [p.payload() for p in sorted(self.policies, key=lambda x: x.policy_id)],
            "evidence": [e.payload() for e in sorted(self.evidence, key=lambda x: x.evidence_ref)],
        }

    def fact_hash(self) -> str:
        blob = json.dumps(self.visible_canonical(), ensure_ascii=True, sort_keys=True,
                          separators=(",", ":")).encode("ascii")
        return hashlib.sha256(blob).hexdigest()


def _assert_no_forbidden_keys(value: Any) -> None:
    from .config import FORBIDDEN_MODEL_VISIBLE_KEYS
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).lower() in FORBIDDEN_MODEL_VISIBLE_KEYS:
                raise SchemaError(f"forbidden model-visible key: {k}")
            _assert_no_forbidden_keys(v)
    elif isinstance(value, list):
        for it in value:
            _assert_no_forbidden_keys(it)
