"""
Preference Models for Phase 15B — User/Admin Preference Store v1.0

Defines data structures for user and admin-level interaction mode preferences.
These models support persisted overrides that integrate with the Phase 15A
interaction mode layer and policy engine.

Design Principles:
    - Zero-LLM: Pure data structures, no AI logic
    - Deterministic: Same inputs → same state
    - Thread-safe: Compatible with concurrent access
    - Extensible: Designed for future preference additions
"""

from dataclasses import dataclass
from typing import Optional

from symbolu.policy.interaction_modes import InteractionMode


@dataclass
class UserPreference:
    """
    User-level interaction mode preference.

    Attributes:
        user_id: Unique user identifier
        preferred_interaction_mode: User's preferred interaction mode (optional)

    Future Extensions:
        - preferred_style: Response style preference
        - language: Preferred language
        - notification_level: Alert verbosity preference
        - custom_thresholds: User-specific policy threshold overrides
    """
    user_id: str
    preferred_interaction_mode: Optional[InteractionMode] = None

    def __post_init__(self):
        """Validate user_id is non-empty."""
        if not self.user_id or not isinstance(self.user_id, str):
            raise ValueError("user_id must be a non-empty string")


@dataclass
class AdminPreference:
    """
    Admin-level (organization) interaction mode preference.

    Admin preferences have highest priority and can enforce
    organization-wide interaction mode constraints.

    Attributes:
        org_id: Unique organization identifier
        forced_interaction_mode: Admin-forced interaction mode (optional)

    Future Extensions:
        - max_mode_allowed: Maximum interaction mode users can select
        - domain_constraints: Per-domain mode restrictions
        - require_user_consent: Whether to require user opt-in for DEEP_ADAPTIVE
        - audit_log_level: Compliance/audit logging level
    """
    org_id: str
    forced_interaction_mode: Optional[InteractionMode] = None

    def __post_init__(self):
        """Validate org_id is non-empty."""
        if not self.org_id or not isinstance(self.org_id, str):
            raise ValueError("org_id must be a non-empty string")


# Public API
__all__ = [
    'UserPreference',
    'AdminPreference',
]
