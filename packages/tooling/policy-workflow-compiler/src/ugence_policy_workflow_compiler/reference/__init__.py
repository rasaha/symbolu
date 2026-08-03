"""Shipped reference policy packs.

These are pure data builders (they depend only on the compiler's own object model,
never on a capability runtime). They back the CLI ``demo`` command and the
Procurement equivalence harness. The Procurement pack encodes the existing
ugence-procurement reference workflow.
"""

from __future__ import annotations

from .procurement import (
    APPROVAL_THRESHOLD,
    HARD_LIMIT,
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)

__all__ = [
    "build_procurement_policy_pack",
    "build_procurement_approval_fixture",
    "HARD_LIMIT",
    "APPROVAL_THRESHOLD",
]
