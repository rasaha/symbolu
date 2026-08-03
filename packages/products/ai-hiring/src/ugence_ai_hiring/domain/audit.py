"""Append-only audit event contract — extracted to the DGM kernel in Phase 5B.

``AuditEvent`` now lives in ``ugence_decision_authority.audit``; this shim preserves the
historical ``ugence_ai_hiring.domain.audit`` import path pointing at the identical class.
"""

from __future__ import annotations

from ugence_decision_authority.api.audit import AuditEvent  # noqa: F401
