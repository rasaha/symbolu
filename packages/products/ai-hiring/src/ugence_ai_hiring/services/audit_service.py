"""Audit service — extracted to the DGM kernel in Phase 5B.

``AuditService`` now lives in ``ugence_decision_authority.audit``; this shim preserves the
historical ``ugence_ai_hiring.services.audit_service`` import path (identical class).
"""

from __future__ import annotations

from ugence_decision_authority.audit.service import AuditService  # noqa: F401
