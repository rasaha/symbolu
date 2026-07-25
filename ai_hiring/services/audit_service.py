"""Audit service — extracted to the DGM kernel in Phase 5B.

``AuditService`` now lives in ``decision_governance.audit``; this shim preserves the
historical ``ai_hiring.services.audit_service`` import path (identical class).
"""

from __future__ import annotations

from decision_governance.audit.service import AuditService  # noqa: F401
