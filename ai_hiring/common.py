"""Framework-agnostic helpers — re-exported from the Decision Governance kernel.

Extracted in Phase 5A. AI Hiring now consumes these from ``decision_governance``;
this module preserves the historical ``ai_hiring.common`` import path so existing
callers and tests are unaffected.
"""

from __future__ import annotations

from decision_governance.common import (  # noqa: F401
    Clock,
    IdFactory,
    canonical_hash,
    new_id,
    utc_now,
)
