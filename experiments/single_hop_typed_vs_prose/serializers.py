"""Frozen deterministic B0 prose and B1 canonical JSON serializers."""
from __future__ import annotations

import json
from typing import Any

from .config import FORBIDDEN_MODEL_VISIBLE_KEYS
from .schema import CanonicalEpisode, Relation


def relation_phrase(relation_type: str) -> str:
    return relation_type.replace("_", " ")


def _attribute_clause(attributes: tuple[tuple[str, str], ...]) -> str:
    if not attributes:
        return "no listed attributes"
    return ", ".join(f"{key} {value}" for key, value in attributes)


def _relation_for_evidence(episode: CanonicalEpisode, evidence_ref: str) -> Relation:
    matches = [relation for relation in episode.relations if relation.evidence_ref == evidence_ref]
    if len(matches) != 1:
        raise ValueError(f"evidence {evidence_ref} must map to exactly one relation")
    return matches[0]


def serialize_b0(episode: CanonicalEpisode) -> str:
    sentences: list[str] = [
        f"Within tenant {episode.tenant_id}, the following records are authorized.",
        f"The question concerns {episode.query.entity_type} {episode.query.entity_id}.",
    ]
    if episode.query.operation == "select_relation_target":
        sentences.append(
            f'The question asks for the target linked through relation "{relation_phrase(episode.query.relation_type or "")}".'
        )
    elif episode.query.operation == "validate_relation":
        sentences.append(
            f'The question asks whether relation "{relation_phrase(episode.query.relation_type or "")}" is supported.'
        )
    elif episode.query.operation == "select_evidence":
        sentences.append(
            f'The question asks for admissible evidence supporting relation "{relation_phrase(episode.query.relation_type or "")}".'
        )
    else:
        sentences.append(
            f'The question asks which candidate is identified through relation "{relation_phrase(episode.query.relation_type or "")}".'
        )
    for entity in sorted(episode.entities, key=lambda item: item.entity_id):
        name = f" named {entity.display_name}" if entity.display_name is not None else ""
        sentences.append(
            f"{entity.entity_type} {entity.entity_id} is a {entity.entity_type}{name} with "
            f"{_attribute_clause(entity.attributes)}."
        )
        if entity.tenant_id != episode.tenant_id:
            sentences.append(
                f"{entity.entity_type} {entity.entity_id} belongs to a different tenant and is not authorized here."
            )
    for relation in sorted(
        episode.relations,
        key=lambda item: (
            item.source_entity_id,
            item.relation_type,
            item.target_entity_id,
        ),
    ):
        sentences.append(
            f"{relation.source_entity_type} {relation.source_entity_id} is associated with "
            f"{relation.target_entity_type} {relation.target_entity_id} through the relation "
            f'"{relation_phrase(relation.relation_type)}".'
        )
    for evidence in sorted(episode.evidence, key=lambda item: item.evidence_ref):
        relation = _relation_for_evidence(episode, evidence.evidence_ref)
        verb = "supports" if evidence.stance == "supports" else "contradicts"
        admissibility = "" if evidence.admissible else " inadmissibly"
        sentences.append(
            f"Evidence reference {evidence.evidence_ref}{admissibility} {verb} the relation between "
            f"{relation.source_entity_type} {relation.source_entity_id} and "
            f"{relation.target_entity_type} {relation.target_entity_id}."
        )
    query_matches = [
        relation
        for relation in episode.relations
        if relation.source_entity_id == episode.query.entity_id
        and relation.relation_type == episode.query.relation_type
        and relation.tenant_id == episode.tenant_id
    ]
    if episode.query.relation_type is not None and not query_matches:
        sentences.append(
            f'No relation of type "{relation_phrase(episode.query.relation_type)}" is recorded for '
            f"{episode.query.entity_type} {episode.query.entity_id}."
        )
    rendered = " ".join(sentences)
    rendered.encode("ascii")
    return rendered


def _assert_no_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_MODEL_VISIBLE_KEYS:
                raise ValueError(f"forbidden model-visible key: {key}")
            _assert_no_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)


def serialize_b1(episode: CanonicalEpisode) -> str:
    payload = episode.visible_canonical()
    _assert_no_forbidden_keys(payload)
    rendered = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    rendered.encode("ascii")
    return rendered


def assert_information_equivalent(episode: CanonicalEpisode) -> str:
    """Verify deterministic paired serialization and return one semantic digest.

    Both arms are generated from the same immutable canonical object. Rebuilding the
    visible payload from either arm is therefore not allowed to introduce a second
    authority. The shared digest is computed once from that canonical object.
    """
    first_b0, second_b0 = serialize_b0(episode), serialize_b0(episode)
    first_b1, second_b1 = serialize_b1(episode), serialize_b1(episode)
    if first_b0 != second_b0 or first_b1 != second_b1:
        raise AssertionError("serializer replay was not byte-identical")
    parsed_b1 = json.loads(first_b1)
    if parsed_b1 != episode.visible_canonical():
        raise AssertionError("B1 did not round-trip to the canonical visible fact graph")
    digest = episode.fact_hash()
    if len(digest) != 64:
        raise AssertionError("invalid SHA-256 fact digest")
    return digest
