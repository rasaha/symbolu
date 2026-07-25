"""Evidence access-authorization policy.

Placeholder, grant-based authorization consistent with the Phase-1 identity
provider convention. Repositories never decide authorization; the access
*service* authenticates the principal and consults this policy, which is
tenant- and candidate-scoped and treats quarantine as a separate permission.

Denials return a typed decision (audited by the caller), and cross-tenant or
cross-candidate access is denied by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Permission(str, Enum):
    EVIDENCE_READ = "EVIDENCE_READ"
    EVIDENCE_SEARCH = "EVIDENCE_SEARCH"
    EVIDENCE_LINEAGE_READ = "EVIDENCE_LINEAGE_READ"
    EVIDENCE_VERSION_READ = "EVIDENCE_VERSION_READ"
    QUARANTINE_READ = "QUARANTINE_READ"
    QUARANTINE_ADMIN = "QUARANTINE_ADMIN"
    # --- Phase 3B: deterministic assessment runtime (additive) ---
    CREATE_ASSESSMENT_WORKSPACE = "CREATE_ASSESSMENT_WORKSPACE"
    BIND_EVIDENCE = "BIND_EVIDENCE"
    SUBMIT_OBSERVATION = "SUBMIT_OBSERVATION"
    VALIDATE_ASSESSMENT = "VALIDATE_ASSESSMENT"
    FINALIZE_ASSESSMENT = "FINALIZE_ASSESSMENT"
    VIEW_ASSESSMENT = "VIEW_ASSESSMENT"
    SUPERSEDE_ASSESSMENT = "SUPERSEDE_ASSESSMENT"
    CANCEL_ASSESSMENT = "CANCEL_ASSESSMENT"
    # --- Phase 4A: DecisionCase aggregate & lifecycle (additive) ---
    CREATE_DECISION_CASE = "CREATE_DECISION_CASE"
    LINK_ASSESSMENT = "LINK_ASSESSMENT"
    SUBMIT_RECOMMENDATION = "SUBMIT_RECOMMENDATION"
    VIEW_DECISION_CASE = "VIEW_DECISION_CASE"
    ASSIGN_REVIEW = "ASSIGN_REVIEW"
    COMPLETE_REVIEW = "COMPLETE_REVIEW"
    MAKE_DECISION = "MAKE_DECISION"
    OVERRIDE_RECOMMENDATION = "OVERRIDE_RECOMMENDATION"
    SUPERSEDE_DECISION_CASE = "SUPERSEDE_DECISION_CASE"
    CANCEL_DECISION_CASE = "CANCEL_DECISION_CASE"
    CLOSE_DECISION_CASE = "CLOSE_DECISION_CASE"
    # --- Phase 4B: governed action request & CER binding (additive) ---
    CREATE_ACTION_REQUEST = "CREATE_ACTION_REQUEST"
    VIEW_ACTION_REQUEST = "VIEW_ACTION_REQUEST"
    BIND_CER = "BIND_CER"
    VALIDATE_ACTION_REQUEST = "VALIDATE_ACTION_REQUEST"
    SUBMIT_FOR_AUTHORIZATION = "SUBMIT_FOR_AUTHORIZATION"
    VIEW_AUTHORIZATION_RESPONSE = "VIEW_AUTHORIZATION_RESPONSE"
    CANCEL_ACTION_REQUEST = "CANCEL_ACTION_REQUEST"
    SUPERSEDE_ACTION_REQUEST = "SUPERSEDE_ACTION_REQUEST"
    MANAGE_ACTION_MAPPING = "MANAGE_ACTION_MAPPING"


_QUARANTINE_PERMS = frozenset({Permission.QUARANTINE_READ, Permission.QUARANTINE_ADMIN})


@dataclass(frozen=True)
class AccessGrant:
    """What one principal may do within one tenant.

    Empty ``candidate_ids`` means all candidates within the tenant.
    """

    principal_id: str
    tenant_id: str
    permissions: frozenset[Permission]
    candidate_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AccessRequest:
    principal_id: str
    tenant_id: str
    operation: Permission
    candidate_id: Optional[str] = None
    application_id: Optional[str] = None
    role_id: Optional[str] = None
    assessment_id: Optional[str] = None
    include_quarantine: bool = False


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str = ""


class GrantStore:
    """In-memory grant registry (placeholder for a real policy store)."""

    def __init__(self) -> None:
        self._grants: dict[tuple[str, str], AccessGrant] = {}

    def add(self, grant: AccessGrant) -> None:
        self._grants[(grant.principal_id, grant.tenant_id)] = grant

    def get(self, principal_id: str, tenant_id: str) -> Optional[AccessGrant]:
        return self._grants.get((principal_id, tenant_id))


class EvidenceAccessPolicy:
    def __init__(self, grants: Optional[GrantStore] = None) -> None:
        self._grants = grants or GrantStore()

    @property
    def grants(self) -> GrantStore:
        return self._grants

    def authorize(self, request: AccessRequest) -> AccessDecision:
        grant = self._grants.get(request.principal_id, request.tenant_id)
        if grant is None:
            # No cross-tenant leakage: identical message whether the tenant
            # exists or not.
            return AccessDecision(False, "no grant for principal in tenant")
        if request.operation not in grant.permissions:
            return AccessDecision(False, f"missing permission {request.operation.value}")
        if request.include_quarantine and not (grant.permissions & _QUARANTINE_PERMS):
            return AccessDecision(False, "quarantine access requires a quarantine permission")
        if (request.candidate_id is not None and grant.candidate_ids
                and request.candidate_id not in grant.candidate_ids):
            return AccessDecision(False, "principal not scoped to this candidate")
        return AccessDecision(True, "authorized")
