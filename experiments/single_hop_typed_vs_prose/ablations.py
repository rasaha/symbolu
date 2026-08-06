"""Evaluation-only causal transformations A1–A6."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from .dataset import PairedEpisode, make_pair
from .schema import CanonicalEpisode, Entity, Evidence, Relation, StructuredOutput

Behavior = Literal[
    "MOVE_WITH_REPRESENTATION",
    "ABSTAIN",
    "REJECT_UNAUTHORIZED",
    "ROBUST_TO_LEXICAL_DECOY",
]


@dataclass(frozen=True)
class AblationCase:
    code: str
    clean: PairedEpisode
    perturbed: PairedEpisode
    clean_output: StructuredOutput
    represented_output: StructuredOutput
    required_behavior: Behavior


def _replace_entity_id(episode: CanonicalEpisode, old: str, new: str) -> CanonicalEpisode:
    entities = tuple(
        replace(item, entity_id=new) if item.entity_id == old else item for item in episode.entities
    )
    relations = tuple(
        replace(
            item,
            source_entity_id=new if item.source_entity_id == old else item.source_entity_id,
            target_entity_id=new if item.target_entity_id == old else item.target_entity_id,
        )
        for item in episode.relations
    )
    query = replace(episode.query, entity_id=new if episode.query.entity_id == old else episode.query.entity_id)
    output = episode.authoritative_output
    if output.selected_entity_id == old:
        output = replace(output, selected_entity_id=new)
    return replace(
        episode, entities=entities, relations=relations, query=query, authoritative_output=output
    )


def build_ablation(clean: PairedEpisode, code: str) -> AblationCase:
    if code not in {f"A{i}" for i in range(1, 7)}:
        raise ValueError(f"unsupported ablation: {code}")
    episode = clean.episode
    gold = episode.authoritative_output

    if code == "A1":
        selected = gold.selected_entity_id
        decoys = [item for item in episode.entities if item.entity_id != selected]
        if selected is None or not decoys:
            raise ValueError("A1 requires a selected entity and at least one decoy")
        decoy = decoys[0].entity_id
        temp = f"__swap__{episode.episode_id}"
        swapped = _replace_entity_id(episode, selected, temp)
        swapped = _replace_entity_id(swapped, decoy, selected)
        swapped = _replace_entity_id(swapped, temp, decoy)
        represented = replace(gold, selected_entity_id=decoy, reason_code="A1_REPRESENTED_ID")
        perturbed = replace(swapped, authoritative_output=represented, episode_id=f"{episode.episode_id}-a1")
        return AblationCase(code, clean, make_pair(perturbed), gold, represented, "MOVE_WITH_REPRESENTATION")

    if code == "A2":
        if not episode.relations:
            raise ValueError("A2 requires a relation")
        relation = episode.relations[0]
        candidates = [
            item
            for item in episode.entities
            if item.entity_type == relation.target_entity_type and item.entity_id != relation.target_entity_id
        ]
        if not candidates:
            raise ValueError("A2 requires an alternate target")
        target = candidates[0].entity_id
        changed = replace(relation, target_entity_id=target)
        relations = (changed, *episode.relations[1:])
        represented = replace(gold, selected_entity_id=target, reason_code="A2_REPRESENTED_TARGET")
        perturbed = replace(
            episode,
            episode_id=f"{episode.episode_id}-a2",
            relations=relations,
            authoritative_output=represented,
        )
        return AblationCase(code, clean, make_pair(perturbed), gold, represented, "MOVE_WITH_REPRESENTATION")

    if code == "A3":
        retained = tuple(
            item
            for item in episode.relations
            if not (
                item.source_entity_id == episode.query.entity_id
                and item.relation_type == episode.query.relation_type
            )
        )
        retained_refs = {item.evidence_ref for item in retained}
        retained_evidence = tuple(item for item in episode.evidence if item.evidence_ref in retained_refs)
        represented = StructuredOutput(
            "INSUFFICIENT_EVIDENCE",
            None,
            episode.query.relation_type,
            None,
            (),
            episode.tenant_id,
            "RELATION_MISSING",
        )
        perturbed = replace(
            episode,
            episode_id=f"{episode.episode_id}-a3",
            relations=retained,
            evidence=retained_evidence,
            authoritative_output=represented,
        )
        return AblationCase(code, clean, make_pair(perturbed), gold, represented, "ABSTAIN")

    if code == "A4":
        if len(episode.relations) < 2:
            raise ValueError("A4 requires at least two relations")
        first, second, *rest = episode.relations
        changed_first = replace(first, evidence_ref=second.evidence_ref)
        changed_second = replace(second, evidence_ref=first.evidence_ref)
        evidence_by_ref = {item.evidence_ref: item for item in episode.evidence}
        changed_evidence = tuple(
            replace(
                item,
                supports_relation=(
                    first.relation_type
                    if item.evidence_ref == second.evidence_ref
                    else second.relation_type
                    if item.evidence_ref == first.evidence_ref
                    else item.supports_relation
                ),
            )
            for item in episode.evidence
        )
        if first.evidence_ref not in evidence_by_ref or second.evidence_ref not in evidence_by_ref:
            raise ValueError("A4 relation evidence must exist")
        represented = replace(
            gold,
            evidence_refs=(second.evidence_ref,),
            reason_code="A4_REPRESENTED_EVIDENCE",
        )
        perturbed = replace(
            episode,
            episode_id=f"{episode.episode_id}-a4",
            relations=(changed_first, changed_second, *rest),
            evidence=changed_evidence,
            authoritative_output=represented,
        )
        return AblationCase(code, clean, make_pair(perturbed), gold, represented, "MOVE_WITH_REPRESENTATION")

    if code == "A5":
        if not episode.relations:
            raise ValueError("A5 requires a relation")
        relation = episode.relations[0]
        cross = Entity(
            relation.target_entity_type,
            f"{relation.target_entity_id}-cross",
            "unauthorized-tenant",
            attributes=(("status", "active"),),
        )
        cross_evidence = Evidence(
            f"{relation.evidence_ref}-cross", relation.relation_type, "unauthorized-tenant"
        )
        changed = replace(
            relation,
            target_entity_id=cross.entity_id,
            evidence_ref=cross_evidence.evidence_ref,
            tenant_id="unauthorized-tenant",
        )
        represented = StructuredOutput(
            "INSUFFICIENT_EVIDENCE",
            None,
            relation.relation_type,
            None,
            (),
            episode.tenant_id,
            "CROSS_TENANT_REJECTED",
        )
        perturbed = replace(
            episode,
            episode_id=f"{episode.episode_id}-a5",
            entities=(*episode.entities, cross),
            relations=(changed, *episode.relations[1:]),
            evidence=(
                *(item for item in episode.evidence if item.evidence_ref != relation.evidence_ref),
                cross_evidence,
            ),
            authoritative_output=represented,
        )
        return AblationCase(code, clean, make_pair(perturbed), gold, represented, "REJECT_UNAUTHORIZED")

    selected = gold.selected_entity_id
    if selected is None:
        raise ValueError("A6 requires a selected entity")
    selected_entity = next(item for item in episode.entities if item.entity_id == selected)
    decoy = replace(
        selected_entity,
        entity_id=f"{selected_entity.entity_id}-lexical-decoy",
        tenant_id=episode.tenant_id,
    )
    represented = gold
    perturbed = replace(
        episode,
        episode_id=f"{episode.episode_id}-a6",
        entities=(*episode.entities, decoy),
        authoritative_output=represented,
    )
    return AblationCase(code, clean, make_pair(perturbed), gold, gold, "ROBUST_TO_LEXICAL_DECOY")
