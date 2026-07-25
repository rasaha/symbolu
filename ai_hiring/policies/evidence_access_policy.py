"""Access-authorization policy — extracted to the DGM kernel in Phase 5B.

Permissions and the grant-based access policy now live in
``decision_governance.policy``; this shim preserves the historical
``ai_hiring.policies.evidence_access_policy`` import path (identical objects).
"""

from __future__ import annotations

from decision_governance.policy.access import (  # noqa: F401
    AccessDecision,
    AccessGrant,
    AccessRequest,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)
