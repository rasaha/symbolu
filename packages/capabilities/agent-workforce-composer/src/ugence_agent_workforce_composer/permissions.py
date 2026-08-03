"""Least-privilege permission-BOUND PROPOSAL layer.

P2 may PROPOSE a permission bound. It never grants, authorizes, provisions or
executes any permission (P2-I12). The proposed set is the intersection of what the
role requires, what the enterprise policy allows, and what the agent supports,
minus prohibited/governance-owned permissions — never the agent's full requested
set. If a required permission cannot be safely proposed, the assignment is
infeasible.
"""
from __future__ import annotations

from typing import Optional, Tuple

from .agents import AgentProfile
from .canonical import AwcModel
from .composition_contracts import PermissionCategory
from .fingerprint import stamp_fingerprint
from .policy import EnterpriseAgentPolicy
from .version import COMPOSITION_CONTRACT_VERSION
from .workflow import WorkflowRoleRequirement

PROPOSAL_NOTICE = (
    "This is a planning-time permission-bound proposal. It does not grant, "
    "authorize, provision or execute any permission."
)


class PermissionBoundingPolicy(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    policy_id: str
    policy_version: str
    #: Permissions whose proposal must be flagged for human review.
    human_review_permissions: Tuple[str, ...] = ()
    #: Permissions owned by governance capabilities — never proposed to an agent.
    governance_owned_permissions: Tuple[str, ...] = ()
    policy_digest: str = ""


class ProposedPermission(AwcModel):
    permission: str
    category: PermissionCategory
    detail: str = ""


class PermissionBoundProposal(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    role_id: str
    agent_id: str
    agent_version: str
    proposed_permissions: Tuple[str, ...] = ()
    categorized: Tuple[ProposedPermission, ...] = ()
    proposed_authority_scope: int = 0
    feasible: bool = True
    infeasible_reasons: Tuple[str, ...] = ()
    requires_human_review: bool = False
    notice: str = PROPOSAL_NOTICE
    permission_policy_digest: str = ""
    role_fingerprint: str = ""
    proposal_fingerprint: str = ""


def _ceiling(role_ceiling: int, enterprise_ceiling: int, agent_scope: int) -> int:
    """Proposed authority ≤ every applicable ceiling and ≤ what the agent has."""
    caps = [c for c in (role_ceiling, enterprise_ceiling) if c > 0]
    ceiling = min(caps) if caps else agent_scope
    return min(agent_scope, ceiling)


def propose_permission_bound(
    role: WorkflowRoleRequirement,
    profile: AgentProfile,
    enterprise_policy: EnterpriseAgentPolicy,
    permission_policy: PermissionBoundingPolicy,
) -> PermissionBoundProposal:
    required = list(role.required_permissions)
    agent_supported = set(profile.requested_permissions)
    enterprise_allowed = set(enterprise_policy.maximum_permission_scope)  # empty => unrestricted
    prohibited = (set(role.prohibited_permissions)
                  | set(permission_policy.governance_owned_permissions))
    review = set(permission_policy.human_review_permissions)

    categorized = []
    proposed = []
    infeasible = []

    for perm in required:
        if perm in prohibited:
            categorized.append(ProposedPermission(permission=perm,
                                                  category=PermissionCategory.PROHIBITED,
                                                  detail="required permission is prohibited/governance-owned"))
            infeasible.append(f"required permission {perm!r} is prohibited")
        elif enterprise_allowed and perm not in enterprise_allowed:
            categorized.append(ProposedPermission(permission=perm,
                                                  category=PermissionCategory.PROHIBITED,
                                                  detail="required permission not in enterprise scope"))
            infeasible.append(f"required permission {perm!r} exceeds enterprise scope")
        elif perm not in agent_supported:
            categorized.append(ProposedPermission(permission=perm,
                                                  category=PermissionCategory.UNSUPPORTED,
                                                  detail="agent does not support a required permission"))
            infeasible.append(f"agent does not support required permission {perm!r}")
        else:
            categorized.append(ProposedPermission(permission=perm,
                                                  category=PermissionCategory.PROPOSED))
            proposed.append(perm)

    # excessive requested permissions the role does not need are excluded, not proposed.
    for perm in sorted(agent_supported - set(required)):
        categorized.append(ProposedPermission(permission=perm,
                                              category=PermissionCategory.EXCESSIVE_REQUESTED,
                                              detail="agent requests a permission the role does not require"))
    for perm in sorted(review & set(proposed)):
        categorized.append(ProposedPermission(permission=perm,
                                              category=PermissionCategory.REQUIRES_HUMAN_REVIEW))

    proposed_authority = _ceiling(role.authority_ceiling, enterprise_policy.maximum_authority_scope,
                                  profile.maximum_authority_scope)
    feasible = not infeasible

    prop = PermissionBoundProposal(
        role_id=role.role_id, agent_id=profile.agent_id, agent_version=profile.agent_version,
        proposed_permissions=tuple(sorted(set(proposed))),
        categorized=tuple(sorted(categorized, key=lambda p: (p.category.value, p.permission))),
        proposed_authority_scope=proposed_authority, feasible=feasible,
        infeasible_reasons=tuple(infeasible),
        requires_human_review=bool(review & set(proposed)),
        permission_policy_digest=permission_policy.policy_digest,
        role_fingerprint=role.role_fingerprint)
    return stamp_fingerprint(prop, "proposal_fingerprint")


__all__ = [
    "PROPOSAL_NOTICE",
    "PermissionBoundingPolicy",
    "ProposedPermission",
    "PermissionBoundProposal",
    "propose_permission_bound",
]
