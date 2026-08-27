"""Part F — Equations 1 and 2: pure, deterministic, total functions.

Neither reads a clock, a file, an environment variable, a network or a random
source. All parameters are keyword-only. Each returns an actual ``bool`` via
``all((...))`` rather than chained ``and``, so a caller comparing ``is True`` /
``is False`` never sees a truthy non-Boolean by surprise.
"""
from __future__ import annotations

import typing
from datetime import datetime

if typing.TYPE_CHECKING:
    from .contracts import (
        AdvisoryCandidateSet,
        AgentIdentityRef,
        BoundedContextEnvelope,
        CandidateAdvisory,
        CognitiveRoleContract,
        ToolObservation,
        WorkMandate,
    )
from .vocabulary import (
    AgentLifecycleState,
    CandidateDisposition,
    DomainCheckCompletion,
    ReviewAction,
    RoleActivationStatus,
    ToolOperationClass,
)

__all__ = ["evaluate_eligibility", "evaluate_readiness"]


def evaluate_eligibility(
    *,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
    disposition: CandidateDisposition,
    requested_review_action: ReviewAction,
    referenced_observation_ids: list[str],
    evaluated_at: datetime,
) -> bool:
    """Equation 1. ``evaluated_at`` is the only time source for every comparison
    inside this function."""
    referenced = [o for o in observations if o.observation_id in set(referenced_observation_ids)]

    identity_active = identity.lifecycle_state is AgentLifecycleState.ACTIVE

    role_match = (
        mandate.assigned_role_contract_id == identity.bound_role_contract_id
        == role.role_contract_id
        and role.activation_status is RoleActivationStatus.ACTIVE
    )

    mandate_valid = (
        identity.tenant_id == mandate.tenant_id == role.tenant_id == context.tenant_id
        and mandate.expires_at > evaluated_at
        and bool(mandate.case_ref)
        and bool(mandate.purpose)
    )

    context_allowed = (
        context.mandate_id == mandate.mandate_id
        and context.expires_at > evaluated_at
        and all(o.source_ref in context.allowed_record_refs for o in referenced)
    )

    tools_allowed = all(
        o.tool_name in role.permitted_tool_scopes
        and o.operation_class is ToolOperationClass.READ_ONLY
        for o in referenced
    )

    output_permitted = (
        disposition in role.permitted_candidate_dispositions
        and requested_review_action in role.permitted_review_actions
    )

    return all((identity_active, role_match, mandate_valid,
                context_allowed, tools_allowed, output_permitted))


def evaluate_readiness(
    *,
    candidate: CandidateAdvisory,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
) -> bool:
    """Equation 2. Returns ``False`` for every candidate this package can construct,
    because C7 makes ``DomainCheckCompletion.COMPLETE`` unconstructible. That is
    intended and fail-closed pending a separately ratified S2 domain evaluator; it is
    what makes B3 bite."""
    eligible = candidate.is_eligible is True

    required_fields_present = True  # guaranteed by successful pydantic construction

    observation_refs_present = (
        len(candidate.observation_refs) > 0
        if candidate.disposition is CandidateDisposition.RECOMMEND_MATCHED_FOR_APPROVAL
        else True
    )

    uncertainty_disclosed = candidate.uncertainties is not None  # structural only

    lineage_complete = (
        identity.bound_role_contract_id == role.role_contract_id
        == mandate.assigned_role_contract_id
        and context.mandate_id == mandate.mandate_id
    )

    domain_checks_complete = candidate.domain_check_completion is DomainCheckCompletion.COMPLETE

    return all((eligible, required_fields_present, observation_refs_present,
                uncertainty_disclosed, lineage_complete, domain_checks_complete))
