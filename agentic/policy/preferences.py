"""
Preferences — Dormant facade for policy-coupled preference models.

STATUS: DORMANT (Policy P0-cleanup, 2026-04)

    This facade has ZERO runtime consumers anywhere in the codebase.
    The actual preference consumer (``agentic/policy/policy_engine.py``
    line 394) imports directly from ``symbolu_core.service.preferences``,
    bypassing this facade entirely.

    This module is retained on disk as a reserved import path for
    future use. It is deliberately excluded from the ``agentic.policy``
    public API (``__init__.py`` / ``__all__``).

    Do NOT add logic here.
    Do NOT import from here in new code.
    Use the canonical preference source directly:
        ``from symbolu_core.service.preferences import ...``

    This facade will either be promoted to active status (if the
    external governance API needs a preference-import surface) or
    deleted entirely in a future cleanup phase.

Re-exports UserPreference, AdminPreference, and PreferenceStore from
symbolu_core.service.preferences. These models are tightly coupled to
agentic.policy.interaction_modes (AdminPreference.forced_interaction_mode,
domain_constraints, audit_log_level).
"""

# Facade status marker — checked by tests and audit tooling.
# Values: "dormant" (zero consumers, kept for reference) |
#         "provisional" (pre-cleanup) | "active" (real consumers)
_FACADE_STATUS = "dormant"

from symbolu_core.service.preferences import (
    UserPreference,
    AdminPreference,
    PreferenceStore,
    get_preference_store,
)

__all__ = [
    "UserPreference",
    "AdminPreference",
    "PreferenceStore",
    "get_preference_store",
    "_FACADE_STATUS",
]
