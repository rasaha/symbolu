"""Kernel policy — permissions, access grants, and the access-authorization policy.

Generic permission enforcement and grant-based tenant/subject-scoped access.
The kernel owns permission *enforcement*; policy *content* is supplied by the
consuming domain/application.
"""

from __future__ import annotations

from .access import (
    AccessDecision,
    AccessGrant,
    AccessRequest,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)

__all__ = [
    "Permission",
    "AccessRequest",
    "AccessDecision",
    "AccessGrant",
    "GrantStore",
    "EvidenceAccessPolicy",
]
