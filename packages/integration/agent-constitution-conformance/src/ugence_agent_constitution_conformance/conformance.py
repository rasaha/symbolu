"""The first-slice structural conformance verifier — the §2.3 predicate, whole.

Presented role facts conform to a resolved constitution **iff**: the role
reference is a member of ``governed_role_refs``; the declared
candidate-disposition set is a subset of its bound; the declared review-action
set is a subset of its bound; and the declared tool-scope set is a subset of its
bound. Set semantics, order-insensitive; empty declared tool scopes conform to
any bound. `[R]` The predicate is part of the ratified fixed surface
(`ACC-S1-BASE`), implemented whole and unamended.

**What the answer is, and is not.** The verifier returns ``True`` or ``False``
and nothing else: it mints no artifact on failure, and it maps nothing to
abstention, hold, escalation or referral — the structural-failure
operational-disposition owner remains deliberately unassigned (`OD-C3=B`).
``True`` proves conformance of the **presented** facts to this constitution's
signed bounds; that the presented facts equal a live role's declarations is the
caller's assertion. ``False`` is a report, never a disposition, a denial or an
instruction to anyone.

**Where tenant fits.** Nowhere, deliberately: the ratified predicate is role
membership plus three subsets, and tenant verification belongs to the resolution
boundary that produced the constitution this predicate reads.
"""

from __future__ import annotations

from ugence_agent_constitution_policy import AgentConstitutionPolicy

from .errors import ConstitutionFactsError
from .facts import GovernedRoleFacts

__all__ = ["role_facts_conform"]


def role_facts_conform(
    *, policy: AgentConstitutionPolicy, facts: GovernedRoleFacts
) -> bool:
    """Whether ``facts`` conform to ``policy``, by the ratified predicate.

    Inputs are exact runtime types — a subclass could carry fields nothing here
    validates, and answering for one would attach this boundary's answer to an
    artifact it never checked.
    """

    if type(policy) is not AgentConstitutionPolicy:
        raise ConstitutionFactsError(
            "role_facts_conform requires exactly an AgentConstitutionPolicy"
        )
    if type(facts) is not GovernedRoleFacts:
        raise ConstitutionFactsError(
            "role_facts_conform requires exactly a GovernedRoleFacts"
        )

    if facts.role_contract_ref not in policy.governed_role_refs:
        return False
    if not set(facts.declared_candidate_dispositions) <= set(
        policy.permitted_candidate_dispositions_bound
    ):
        return False
    if not set(facts.declared_review_actions) <= set(
        policy.permitted_review_actions_bound
    ):
        return False
    # Empty declared tool scopes are a subset of any bound, the empty one included.
    if not set(facts.declared_tool_scopes) <= set(policy.permitted_tool_scopes_bound):
        return False
    return True
