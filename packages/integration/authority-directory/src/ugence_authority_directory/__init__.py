"""Ugence Authority Directory — time-bounded organizational role grants.

    THIS PACKAGE REPORTS ROLE GRANTS.
    IT NEVER AUTHENTICATES, NEVER APPROVES, NEVER MINTS AUTHORITY,
    AND HOLDS CUSTODY OF NOTHING.

It is deliberately **not** an Authority: every ``…Authority`` package in this
repository decides something, and this one decides nothing. It answers who holds
which role, in which scope, until when — and each consumer applies its own rules to
that answer.

Scoped and ratified by ``docs/architecture/ADR_UGENCE_AUTHORITY_DIRECTORY_SCOPING.md``.
A reported grant is an input to somebody else's decision, not a decision.
"""

from __future__ import annotations

from .delegation import MAX_DELEGATION_HOPS, delegation_refusals
from .directory import AuthorityDirectoryPort, CommitteeReport
from .eligibility_adapter import (
    DirectoryApproverEligibility,
    DirectoryApproverRef,
    EligibilityAnswer,
    projection_of,
)
from .errors import (
    AuthorityDirectoryError,
    ContractViolation,
    DelegationRefused,
    GrantAlreadyExistsError,
    GrantNotFoundError,
    ProductionModeRefused,
    RecordIntegrityError,
    StoreUnavailableError,
)
from .grants import (
    GRANT_ID_PREFIX,
    GrantEvent,
    GrantEventType,
    RoleGrant,
    grant_id_for,
)
from .memory import InMemoryAuthorityDirectory
from .principals import SCOPE_SEPARATOR, PrincipalKind, PrincipalRef, require_scope, scope_covers
from .selection import build_committee_report, select_for_principal, select_holders, valid_at
from .sqlite import SCHEMA_VERSION, SqliteAuthorityDirectory
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED", "SCHEMA_VERSION",
    # principals and scopes
    "PrincipalKind", "PrincipalRef", "scope_covers", "require_scope", "SCOPE_SEPARATOR",
    # grants
    "RoleGrant", "GrantEvent", "GrantEventType", "grant_id_for", "GRANT_ID_PREFIX",
    # delegation
    "delegation_refusals", "MAX_DELEGATION_HOPS",
    # selection
    "valid_at", "select_for_principal", "select_holders", "build_committee_report",
    # the directory seam
    "AuthorityDirectoryPort", "CommitteeReport",
    # the approval-workflow eligibility adapter
    "DirectoryApproverEligibility", "DirectoryApproverRef", "EligibilityAnswer", "projection_of",
    # adapters
    "InMemoryAuthorityDirectory", "SqliteAuthorityDirectory",
    # errors
    "AuthorityDirectoryError", "ContractViolation", "GrantNotFoundError",
    "GrantAlreadyExistsError", "DelegationRefused", "RecordIntegrityError",
    "StoreUnavailableError", "ProductionModeRefused",
]
