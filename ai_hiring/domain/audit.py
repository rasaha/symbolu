"""Append-only audit event contract — extracted to the DGM kernel in Phase 5B.

``AuditEvent`` now lives in ``decision_governance.audit``; this shim preserves the
historical ``ai_hiring.domain.audit`` import path pointing at the identical class.
"""

from __future__ import annotations

from decision_governance.api.audit import AuditEvent  # noqa: F401
