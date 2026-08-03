"""Framework-agnostic helpers — re-exported from the Decision Governance kernel.

Extracted in Phase 5A. AI Hiring now consumes these from ``ugence_decision_authority``;
this module preserves the historical ``ugence_ai_hiring.common`` import path so existing
callers and tests are unaffected.
"""

from __future__ import annotations

from ugence_decision_authority.api.common import (  # noqa: F401
    Clock,
    IdFactory,
    canonical_hash,
    new_id,
    utc_now,
)
