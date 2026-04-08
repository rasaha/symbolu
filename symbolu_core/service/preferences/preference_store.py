"""
Preference Store for Phase 15B — User/Admin Preference Store v1.0

Thread-safe in-memory storage for user and admin interaction mode preferences.
This is v1.0: in-memory only, no persistence to disk or database.

Design Principles:
    - Thread-safe: Uses RLock for concurrent access
    - Deterministic: No randomness, pure data operations
    - Zero-LLM: No AI logic
    - Singleton pattern: Single global instance via accessor
    - Non-invasive: Doesn't modify pipeline or routing

Future Extensions (v2.0+):
    - Persistent storage (SQLite, Redis, PostgreSQL)
    - TTL/expiration for preferences
    - Audit logging for preference changes
    - Batch operations for bulk updates
"""

import threading
from typing import Dict, Optional

from .preference_models import UserPreference, AdminPreference


class PreferenceStore:
    """
    Thread-safe in-memory preference store.

    Stores user and admin interaction mode preferences with
    concurrent access protection. All operations are atomic
    and deterministic.

    Thread Safety:
        Uses threading.RLock for all read/write operations,
        ensuring safe concurrent access from multiple threads.

    Examples:
        >>> store = PreferenceStore()
        >>> from agentic.policy.interaction_modes import InteractionMode
        >>> user_pref = UserPreference(
        ...     user_id="user123",
        ...     preferred_interaction_mode=InteractionMode.SMART_INSIGHT
        ... )
        >>> store.set_user_preference(user_pref)
        >>> retrieved = store.get_user_preference("user123")
        >>> retrieved.preferred_interaction_mode
        InteractionMode.SMART_INSIGHT
    """

    def __init__(self):
        """Initialize empty preference store with thread-safe locks."""
        self._user_prefs: Dict[str, UserPreference] = {}
        self._admin_prefs: Dict[str, AdminPreference] = {}
        self._lock = threading.RLock()

    def set_user_preference(self, user_pref: UserPreference) -> None:
        """
        Store or update a user preference.

        Last write wins semantics: if a preference already exists
        for this user_id, it will be completely replaced.

        Args:
            user_pref: UserPreference object to store

        Thread Safety:
            Atomic operation protected by RLock

        Examples:
            >>> from agentic.policy.interaction_modes import InteractionMode
            >>> store = PreferenceStore()
            >>> pref = UserPreference("user123", InteractionMode.ANALYTICS_ONLY)
            >>> store.set_user_preference(pref)
        """
        with self._lock:
            self._user_prefs[user_pref.user_id] = user_pref

    def get_user_preference(self, user_id: str) -> Optional[UserPreference]:
        """
        Retrieve a user preference by user_id.

        Args:
            user_id: User identifier to look up

        Returns:
            UserPreference if found, None otherwise

        Thread Safety:
            Atomic operation protected by RLock

        Examples:
            >>> store = PreferenceStore()
            >>> pref = store.get_user_preference("user123")
            >>> pref is None
            True
        """
        with self._lock:
            return self._user_prefs.get(user_id)

    def set_admin_preference(self, admin_pref: AdminPreference) -> None:
        """
        Store or update an admin (organization) preference.

        Last write wins semantics: if a preference already exists
        for this org_id, it will be completely replaced.

        Args:
            admin_pref: AdminPreference object to store

        Thread Safety:
            Atomic operation protected by RLock

        Examples:
            >>> from agentic.policy.interaction_modes import InteractionMode
            >>> store = PreferenceStore()
            >>> pref = AdminPreference("org456", InteractionMode.DEEP_ADAPTIVE)
            >>> store.set_admin_preference(pref)
        """
        with self._lock:
            self._admin_prefs[admin_pref.org_id] = admin_pref

    def get_admin_preference(self, org_id: str) -> Optional[AdminPreference]:
        """
        Retrieve an admin preference by org_id.

        Args:
            org_id: Organization identifier to look up

        Returns:
            AdminPreference if found, None otherwise

        Thread Safety:
            Atomic operation protected by RLock

        Examples:
            >>> store = PreferenceStore()
            >>> pref = store.get_admin_preference("org456")
            >>> pref is None
            True
        """
        with self._lock:
            return self._admin_prefs.get(org_id)

    def clear_user(self, user_id: str) -> None:
        """
        Remove a user preference from the store.

        Silently succeeds if user_id not found (idempotent).

        Args:
            user_id: User identifier to clear

        Thread Safety:
            Atomic operation protected by RLock

        Examples:
            >>> store = PreferenceStore()
            >>> from agentic.policy.interaction_modes import InteractionMode
            >>> store.set_user_preference(UserPreference("user123", InteractionMode.SMART_INSIGHT))
            >>> store.clear_user("user123")
            >>> store.get_user_preference("user123") is None
            True
        """
        with self._lock:
            self._user_prefs.pop(user_id, None)

    def clear_admin(self, org_id: str) -> None:
        """
        Remove an admin preference from the store.

        Silently succeeds if org_id not found (idempotent).

        Args:
            org_id: Organization identifier to clear

        Thread Safety:
            Atomic operation protected by RLock

        Examples:
            >>> store = PreferenceStore()
            >>> from agentic.policy.interaction_modes import InteractionMode
            >>> store.set_admin_preference(AdminPreference("org456", InteractionMode.ANALYTICS_ONLY))
            >>> store.clear_admin("org456")
            >>> store.get_admin_preference("org456") is None
            True
        """
        with self._lock:
            self._admin_prefs.pop(org_id, None)

    def get_user_count(self) -> int:
        """
        Get total number of stored user preferences.

        Returns:
            Count of user preferences

        Thread Safety:
            Atomic operation protected by RLock
        """
        with self._lock:
            return len(self._user_prefs)

    def get_admin_count(self) -> int:
        """
        Get total number of stored admin preferences.

        Returns:
            Count of admin preferences

        Thread Safety:
            Atomic operation protected by RLock
        """
        with self._lock:
            return len(self._admin_prefs)

    def clear_all(self) -> None:
        """
        Clear all preferences (user and admin).

        WARNING: This is a destructive operation.
        Primarily intended for testing and development.

        Thread Safety:
            Atomic operation protected by RLock
        """
        with self._lock:
            self._user_prefs.clear()
            self._admin_prefs.clear()


# ============================================================================
# SINGLETON ACCESSOR
# ============================================================================

_PREFERENCE_STORE: Optional[PreferenceStore] = None
_STORE_LOCK = threading.RLock()


def get_preference_store() -> PreferenceStore:
    """
    Get or create the global PreferenceStore singleton.

    This ensures a single shared instance across all modules
    and threads, providing consistent preference state.

    Returns:
        PreferenceStore: The global preference store instance

    Thread Safety:
        Double-checked locking pattern ensures thread-safe
        singleton initialization

    Examples:
        >>> store1 = get_preference_store()
        >>> store2 = get_preference_store()
        >>> store1 is store2
        True
    """
    global _PREFERENCE_STORE

    # Fast path: if already initialized, return immediately
    if _PREFERENCE_STORE is not None:
        return _PREFERENCE_STORE

    # Slow path: acquire lock and initialize
    with _STORE_LOCK:
        # Double-check after acquiring lock (another thread may have initialized)
        if _PREFERENCE_STORE is None:
            _PREFERENCE_STORE = PreferenceStore()
        return _PREFERENCE_STORE


# Public API
__all__ = [
    'PreferenceStore',
    'get_preference_store',
]
