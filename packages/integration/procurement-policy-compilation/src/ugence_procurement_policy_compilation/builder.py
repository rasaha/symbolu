"""The Procurement family's mapping from its artifact to a `policy_pack.v2` pack.

Deterministic and total: identical artifacts produce identical packs, byte for byte,
including object ids. Nothing is invented — every object traces to something the
artifact stated, and where the artifact is silent the pack is silent too. That is
the same rule the compiler's own enrichment follows, applied one layer earlier.

This module knows nothing about Policy Authority. It maps a typed artifact, so the
composition root supplies the authoritative-source reference and this builder never
touches it (ruling X1-B: on the authoritative path a reference is derived, never
authored).
"""

from __future__ import annotations

from typing import List, Tuple

from ugence_policy_workflow_compiler.api import (
    SCHEMA_VERSION_V2,
    ActionConstraint,
    ApprovalPath,
    ApprovalStep,
    AuthorityRequirement,
    AuthorityType,
    BlockBehavior,
    Comparator,
    ConstraintKind,
    DecisionRule,
    EvidenceKind,
    ObjectType,
    Predicate,
    ProhibitedCondition,
    ProvenanceSourceType,
    PolicyPack,
    PolicyPackStatus,
    RequiredEvidence,
    SemanticDeclaration,
    SourceDocument,
)

from .artifact import ProcurementPolicyArtifact

#: Object-id prefixes. Stable and derived from the artifact's own policy id, so a
#: pack is reproducible from the artifact alone.
_SOURCE = "src.procurement_policy"
_AUTHORITY = "auth.purchase_decision"
_PATH = "path.purchase_approval"


def _source_document(artifact: ProcurementPolicyArtifact) -> SourceDocument:
    return SourceDocument(
        object_id=_SOURCE,
        name=artifact.title,
        source_type=ProvenanceSourceType.POLICY_CLAUSE,
        title=artifact.title,
        document_version=artifact.document_version,
        authority_level=artifact.authority_level,
        description=f"Procurement policy {artifact.policy_id}",
    )


def _authority(artifact: ProcurementPolicyArtifact) -> AuthorityRequirement:
    return AuthorityRequirement(
        object_id=_AUTHORITY,
        name="purchase decision authority",
        provenance_refs=(_SOURCE,),
        decision_scope=artifact.action_type,
        authority_type=AuthorityType.HUMAN_APPROVER,
        # A binding business decision is never satisfied by a machine actor.
        allow_non_human=False,
    )


def _approval(artifact) -> Tuple[Tuple[ApprovalStep, ...], Tuple[ApprovalPath, ...]]:
    """Ordered steps and their path — only when the policy states roles."""
    if not artifact.approval_roles:
        return (), ()
    steps = tuple(
        ApprovalStep(
            object_id=f"step.{role.role_label}",
            name=f"{role.role_label} approval",
            provenance_refs=(_SOURCE,),
            order=index,
            authority_requirement_id=_AUTHORITY,
            role_label=role.role_label,
        )
        for index, role in enumerate(artifact.approval_roles, start=1)
    )
    # Segregation of duties between consecutive declared roles: the policy states
    # distinct roles, so distinct identities must satisfy them.
    pairs = tuple(
        (steps[i].role_label, steps[i + 1].role_label) for i in range(len(steps) - 1)
    )
    path = ApprovalPath(
        object_id=_PATH,
        name="purchase approval path",
        provenance_refs=(_SOURCE,),
        related_object_ids=tuple(s.object_id for s in steps),
        step_ids=tuple(s.object_id for s in steps),
        segregation_pairs=pairs,
    )
    return steps, (path,)


def _decision_rule(artifact: ProcurementPolicyArtifact) -> DecisionRule:
    """Amounts at or below the stated threshold may advance."""
    return DecisionRule(
        object_id="rule.within_threshold",
        name="amount within approval threshold",
        provenance_refs=(_SOURCE,),
        conditions=(
            Predicate(
                fact_key=artifact.amount_fact_key,
                comparator=Comparator.LTE,
                value=artifact.approval_threshold,
            ),
        ),
        authority_requirement_id=_AUTHORITY,
    )


def _constraints(artifact: ProcurementPolicyArtifact) -> Tuple[ActionConstraint, ...]:
    return (
        ActionConstraint(
            object_id="act.hard_limit",
            name="amount hard limit",
            provenance_refs=(_SOURCE,),
            action_type=artifact.action_type,
            parameter=artifact.amount_fact_key,
            kind=ConstraintKind.HARD_LIMIT,
            max_value=artifact.hard_limit,
            authority_requirement_id=_AUTHORITY,
        ),
    )


def _evidence(artifact: ProcurementPolicyArtifact) -> Tuple[RequiredEvidence, ...]:
    return tuple(
        RequiredEvidence(
            object_id=f"ev.{requirement.fact_key}",
            name=requirement.description or requirement.fact_key,
            provenance_refs=(_SOURCE,),
            evidence_kind=EvidenceKind.FIELD_VALUE,
            fact_key=requirement.fact_key,
            on_missing=BlockBehavior.BLOCK,
        )
        for requirement in artifact.evidence_requirements
    )


def _prohibitions(artifact) -> Tuple[ProhibitedCondition, ...]:
    return tuple(
        ProhibitedCondition(
            object_id=f"proh.{fact.fact_key}",
            name=f"prohibited: {fact.fact_key}",
            provenance_refs=(_SOURCE,),
            conditions=(
                Predicate(
                    fact_key=fact.fact_key,
                    comparator=Comparator(fact.comparator),
                    value=fact.value,
                ),
            ),
            behavior=BlockBehavior.BLOCK,
        )
        for fact in artifact.prohibited_facts
    )


def _declarations(artifact, subject_id: str) -> Tuple[SemanticDeclaration, ...]:
    """Source-declared semantics — emitted only when the policy states them."""
    if not (
        artifact.declared_data_classifications
        or artifact.declared_permission_intents
        or artifact.declared_required_tools
    ):
        return ()
    return (
        SemanticDeclaration(
            object_id="decl.purchase_decision",
            name="declared semantics for the purchase decision",
            provenance_refs=(_SOURCE,),
            subject_object_id=subject_id,
            data_classification_refs=artifact.declared_data_classifications,
            permission_intent_refs=artifact.declared_permission_intents,
            required_tool_refs=artifact.declared_required_tools,
        ),
    )


def build_procurement_pack(
    artifact: ProcurementPolicyArtifact,
    *,
    status: PolicyPackStatus = PolicyPackStatus.APPROVED,
) -> PolicyPack:
    """Map a Procurement policy artifact to a `policy_pack.v2` pack.

    The pack carries no ``authoritative_source``: on the authoritative path that
    reference is derived by the composition root from a verified resolution, and a
    builder that supplied one would be refused.
    """
    steps, paths = _approval(artifact)
    rule = _decision_rule(artifact)
    return PolicyPack(
        pack_id=f"pack.{artifact.policy_id}",
        name=artifact.title,
        schema_version=SCHEMA_VERSION_V2,
        status=status,
        domain="procurement",
        description=f"Compiled from Procurement policy {artifact.policy_id} "
                    f"version {artifact.document_version}",
        source_documents=(_source_document(artifact),),
        decision_rules=(rule,),
        required_evidence=_evidence(artifact),
        authority_requirements=(_authority(artifact),),
        approval_paths=paths,
        approval_steps=steps,
        prohibited_conditions=_prohibitions(artifact),
        action_constraints=_constraints(artifact),
        semantic_declarations=_declarations(artifact, rule.object_id),
    )


def procurement_pack_builder(resolved_artifact) -> PolicyPack:
    """A ``PolicyPackBuilder`` for the X1 composition root.

    Accepts either a parsed :class:`ProcurementPolicyArtifact` or the canonical
    projection a resolution carries.
    """
    from .artifact import artifact_from_projection

    if isinstance(resolved_artifact, ProcurementPolicyArtifact):
        return build_procurement_pack(resolved_artifact)
    return build_procurement_pack(artifact_from_projection(resolved_artifact))


__all__ = ["build_procurement_pack", "procurement_pack_builder"]
