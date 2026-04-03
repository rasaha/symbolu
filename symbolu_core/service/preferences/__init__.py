"""
Phase 15B — User/Admin Preference Store v1.0

Provides in-memory storage for user and admin interaction mode preferences
that integrate with the Phase 15A interaction mode layer.

Public API:
    - UserPreference: User-level preference model
    - AdminPreference: Admin-level preference model
    - PreferenceStore: Thread-safe preference storage
    - get_preference_store: Singleton accessor for global store

Usage:
    from symbolu_core.service.preferences import (
        UserPreference,
        AdminPreference,
        get_preference_store,
    )
    from agentic.policy.interaction_modes import InteractionMode

    # Get global store
    store = get_preference_store()

    # Set user preference
    user_pref = UserPreference(
        user_id="user123",
        preferred_interaction_mode=InteractionMode.SMART_INSIGHT
    )
    store.set_user_preference(user_pref)

    # Retrieve user preference
    pref = store.get_user_preference("user123")
"""

from .preference_models import UserPreference, AdminPreference
from .preference_store import PreferenceStore, get_preference_store

__all__ = [
    'UserPreference',
    'AdminPreference',
    'PreferenceStore',
    'get_preference_store',
]
