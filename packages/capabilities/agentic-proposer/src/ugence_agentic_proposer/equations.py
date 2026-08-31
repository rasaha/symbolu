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
    DomainEvaluationOutcome,
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
    """Equation 2, in its ratified seven-term form (OD-7 part 6 added the seventh).

    The seventh term, ``DomainEvaluationSatisfied``, is what replaced C7's structural
    closure of R-2/V13's ``PROPOSAL`` path. C7 made ``DomainCheckCompletion.COMPLETE``
    unconstructible, so this function returned ``False`` for every candidate this
    package could build. With C7 removed, ``domain_checks_complete`` alone would return
    ``True`` for a candidate whose evaluation *ran* and *failed* — ``COMPLETE`` with
    ``NOT_SATISFIED`` or ``INCONCLUSIVE`` — which is R-2's condition for
    ``terminal_outcome=PROPOSAL``, and would be one term compensating for a substantive
    result it does not carry, against Part F's own **No term compensates for another**
    rule.

    Relying on the documented call order instead was rejected: this is an exported
    function with no caller in ``src/``, so "invoked only after selection" is a
    convention this package states and cannot enforce against a consumer calling it
    directly. C7 performed that closure structurally, and its removal hands the closure
    to a term, not to a convention.
    """
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

    #: Whether evaluation RAN — never what it concluded (OD-7 part 3).
    domain_checks_complete = candidate.domain_check_completion is DomainCheckCompletion.COMPLETE

    #: What it CONCLUDED. Separate term, separate field, separate vocabulary.
    domain_evaluation_satisfied = (
        candidate.domain_evaluation_outcome is DomainEvaluationOutcome.SATISFIED)

    return all((eligible, required_fields_present, observation_refs_present,
                uncertainty_disclosed, lineage_complete, domain_checks_complete,
                domain_evaluation_satisfied))
