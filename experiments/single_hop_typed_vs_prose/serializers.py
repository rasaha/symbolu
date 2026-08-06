"""Frozen deterministic B0/B1 serializers."""
from __future__ import annotations

import json
from typing import Any

from .schema import CanonicalEpisode, Relation

_FORBIDDEN_KEYS = {
    "answer",
    "correct",
    "expected",
    "gold",
    "label",
    "target_rank",
    "validity_result",
}


def relation_phrase(relation_type: str) -> str:
    return relation_type.replace("_", " ")


def _attribute_clause(attributes: dict[str, str]) -> str:
    if not attributes:
        return "no listed attributes"
    return ", ".join(f"{key} {attributes[key]}" for key in sorted(attributes))


def _relation_for_evidence(episode: CanonicalEpisode, evidence_ref: str) -> Relation:
    matches = [item for item in episode.relations if item.evidence_ref == evidence_ref]
    if len(matches) != 1:
        raise ValueError(f"evidence {evidence_ref} must map to exactly one relation")
    return matches[0]


def serialize_b0(episode: CanonicalEpisode) -> str:
    sentences: list[str] = [
        f"Within tenant {episode.tenant_id}, the following records are authorized.",
        f"The question concerns {episode.query.entity_type} {episode.query.entity_id}.",
    ]
    for entity in sorted(episode.entities, key=lambda item: item.entity_id):
        attrs = _attribute_clause(dict(entity.attributes))
        sentences.append(
            f"{entity.entity_type} {entity.entity_id} is a {entity.entity_type} with {attrs}."
        )
        if entity.tenant_id != episode.tenant_id:
            sentences.append(
                f"{entity.entity_type} {entity.entity_id} belongs to a different tenant and is not authorized here."
            )
    for relation in sorted(
        episode.relations,
        key=lambda item: (item.source_entity_id, item.relation_type, item.target_entity_id),
    ):
        sentences.append(
            f"{relation.source_entity_type} {relation.source_entity_id} is associated with "
            f"{relation.target_entity_type} {relation.target_entity_id} through the relation "
            f'"{relation_phrase(relation.relation_type)}".'
        )
    for evidence in sorted(episode.evidence, key=lambda item: item.evidence_ref):
        relation = _relation_for_evidence(episode, evidence.evidence_ref)
        sentences.append(
            f"Evidence reference {evidence.evidence_ref} supports the relation between "
            f"{relation.source_entity_type} {relation.source_entity_id} and "
            f"{relation.target_entity_type} {relation.target_entity_id}."
        )
    query_matches = [
        item
        for item in episode.relations
        if item.source_entity_id == episode.query.entity_id
        and item.relation_type == episode.query.relation_type
    ]
    if episode.query.relation_type is not None and not query_matches:
        sentences.append(
            f'No relation of type "{relation_phrase(episode.query.relation_type)}" is recorded for '
            f"{episode.query.entity_type} {episode.query.entity_id}."
        )
    return " ".join(sentences)


def serialize_b1(episode: CanonicalEpisode) -> str:
    payload = episode.visible_canonical()
    _assert_no_forbidden_keys(payload)
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _assert_no_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValueError(f"forbidden model-visible key: {key}")
            _assert_no_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)


def assert_information_equivalent(episode: CanonicalEpisode) -> str:
    """Return the shared semantic digest after deterministic serialization checks."""
    b0_first = serialize_b0(episode)
    b0_second = serialize_b0(episode)
    b1_first = serialize_b1(episode)
    b1_second = serialize_b1(episode)
    if b0_first != b0_second or b1_first != b1_second:
        raise AssertionError("serializer replay was not byte-identical")
    digest = episode.fact_hash()
    if len(digest) != 64:
        raise AssertionError("invalid SHA-256 fact digest")
    return digest
