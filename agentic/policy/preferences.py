"""
Preferences — Governance facade for policy-coupled preference models.

STATUS: PROVISIONAL (Policy Phase P0)

    This module has ZERO runtime consumers as of Policy Phase P0.
    The actual preference consumers (policy_engine.py line 394)
    import directly from symbolu_core.service.preferences, bypassing
    this facade entirely.

    This facade exists as a potential future convenience import path
    for governance API consumers that need preference types. It will
    be promoted when the external governance API is built, or deprecated
    if direct imports from symbolu_core are preferred.

    Do not add new logic here. Do not assume this module is active.

Re-exports UserPreference, AdminPreference, and PreferenceStore from
symbolu_core.service.preferences. These models are tightly coupled to
agentic.policy.interaction_modes (AdminPreference.forced_interaction_mode,
domain_constraints, audit_log_level).
"""

# Facade status marker — checked by tests and audit tooling
_FACADE_STATUS = "provisional"

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
