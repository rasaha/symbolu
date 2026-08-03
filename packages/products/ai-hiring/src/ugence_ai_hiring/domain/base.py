"""Shared base for immutable, validated models — re-exported from the DGM kernel.

Extracted in Phase 5A. ``DomainModel`` now lives in ``ugence_decision_authority.base``;
this module keeps the historical ``ugence_ai_hiring.domain.base`` path pointing at the
identical class object, so every model across the codebase shares one base.
"""

from __future__ import annotations

from ugence_decision_authority.api.contracts import DomainModel  # noqa: F401
