"""
Preferences — Governance facade for policy-coupled preference models.

Re-exports UserPreference, AdminPreference, and PreferenceStore from
symbolu_core.service.preferences. These models are tightly coupled to
agentic.policy.interaction_modes (AdminPreference.forced_interaction_mode,
domain_constraints, audit_log_level).

Usage:
    from agentic.policy.preferences import AdminPreference, get_preference_store
    from agentic.policy.interaction_modes import InteractionMode

    store = get_preference_store()
    admin_pref = AdminPreference(
        org_id="org1",
        forced_interaction_mode=InteractionMode.SAFETY_FIRST,
    )
    store.set_admin_preference(admin_pref)
"""

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
]
