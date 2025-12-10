"""
Interaction Mode Layer v1.0 (Phase 15A)

Provides system-wide interaction modes that govern how much influence
advanced formulas have on Symbol-U's behavior.

Interaction Modes:
    - ANALYTICS_ONLY: Standard Phase 1-12 behavior, no formula influence on policy
    - SMART_INSIGHT: Soft UI-layer refinement from Phase 5, v3 scoring if domain allows
    - DEEP_ADAPTIVE: Full adaptive mode with VMF/ATH emotional/arc-based hints

Design Principles:
    - Zero-LLM: Pure deterministic rule-based logic
    - Non-invasive: Does not modify routing, mappers, DHA, or Fusion
    - Additive: Only influences presentation layer (hints/badges)
    - Deterministic: Same input always produces same output
    - Backward compatible: ANALYTICS_ONLY preserves all prior behavior

Usage:
    from symbolu.policy.interaction_modes import (
        InteractionMode,
        resolve_interaction_mode,
    )

    # Resolve the active interaction mode
    mode = resolve_interaction_mode(
        domain_profile=profile,
        user_override=None,
        admin_override=None
    )

    # Use in policy engine
    if mode == InteractionMode.DEEP_ADAPTIVE:
        # Enable VMF/ATH hints
        pass
"""

from enum import Enum
from typing import Any, Dict, Optional


class InteractionMode(Enum):
    """
    System-wide interaction modes for Symbol-U.

    Controls how strongly the system adapts to users based on advanced formulas
    (Enhanced SMI, VMF, ATH, coherence v3, guna/kosha resonance, etc.)

    Modes:
        ANALYTICS_ONLY: Standard Phase 1-12 behavior only
            - NO formula influence on policy
            - Safe default for trading/generic domains
            - Complete backward compatibility

        SMART_INSIGHT: Soft UI-layer refinement (Phase 5)
            - Enable Phase 5 UI refinement from formula signals
            - Enable v3 scoring if domain allows (Phase 11)
            - DO NOT modify routing/mappers
            - Suitable for therapy/identity domains

        DEEP_ADAPTIVE: Full adaptive mode
            - Enable Phase 5 UI refinement
            - Enable v3 scoring priority
            - Leverage VMF/ATH for emotional/arc-based hints
            - Still no routing or mapper activation changes
            - Influence ONLY presentation layer (hints/badges), NEVER behavior
            - Requires explicit admin/user opt-in
    """
    ANALYTICS_ONLY = "analytics_only"
    SMART_INSIGHT = "smart_insight"
    DEEP_ADAPTIVE = "deep_adaptive"


def resolve_interaction_mode(
    domain_profile: Dict[str, Any],
    user_override: Optional[str] = None,
    admin_override: Optional[str] = None,
) -> InteractionMode:
    """
    Resolve the active interaction mode based on priority cascade.

    Resolution Priority (highest to lowest):
        1. admin_override - Administrator-level override (highest priority)
        2. user_override - User-level preference
        3. domain default - Fallback from domain profile

    Args:
        domain_profile: Domain profile dictionary (from get_domain_profile)
        user_override: Optional user-specified mode override (string or None)
        admin_override: Optional admin-specified mode override (string or None)

    Returns:
        InteractionMode: The resolved interaction mode

    Raises:
        None - Invalid inputs gracefully fallback to ANALYTICS_ONLY

    Examples:
        >>> profile = {"interaction_mode_default": InteractionMode.SMART_INSIGHT}
        >>> resolve_interaction_mode(profile)
        InteractionMode.SMART_INSIGHT

        >>> resolve_interaction_mode(profile, admin_override="deep_adaptive")
        InteractionMode.DEEP_ADAPTIVE

        >>> resolve_interaction_mode(profile, user_override="analytics_only")
        InteractionMode.ANALYTICS_ONLY

        >>> resolve_interaction_mode(profile, user_override="analytics_only", admin_override="deep_adaptive")
        InteractionMode.DEEP_ADAPTIVE  # Admin takes priority

    Note:
        This function is pure and deterministic. Same inputs always
        produce the same output.
    """
    # Priority 1: Admin override (highest)
    if admin_override is not None:
        resolved = _parse_interaction_mode(admin_override)
        if resolved is not None:
            return resolved

    # Priority 2: User override
    if user_override is not None:
        resolved = _parse_interaction_mode(user_override)
        if resolved is not None:
            return resolved

    # Priority 3: Domain default (from profile)
    domain_default = domain_profile.get("interaction_mode_default")

    if domain_default is not None:
        # Handle both InteractionMode enum and string values
        if isinstance(domain_default, InteractionMode):
            return domain_default
        resolved = _parse_interaction_mode(domain_default)
        if resolved is not None:
            return resolved

    # Fallback: ANALYTICS_ONLY (safest default)
    return InteractionMode.ANALYTICS_ONLY


def _parse_interaction_mode(value: Any) -> Optional[InteractionMode]:
    """
    Parse a string or enum value to InteractionMode.

    Handles:
        - InteractionMode enum values
        - String values (case-insensitive)
        - None values

    Args:
        value: The value to parse (string, InteractionMode, or other)

    Returns:
        InteractionMode if valid, None otherwise

    Examples:
        >>> _parse_interaction_mode("analytics_only")
        InteractionMode.ANALYTICS_ONLY

        >>> _parse_interaction_mode("SMART_INSIGHT")
        InteractionMode.SMART_INSIGHT

        >>> _parse_interaction_mode(InteractionMode.DEEP_ADAPTIVE)
        InteractionMode.DEEP_ADAPTIVE

        >>> _parse_interaction_mode("invalid")
        None

        >>> _parse_interaction_mode(None)
        None
    """
    # Handle None
    if value is None:
        return None

    # Handle InteractionMode enum directly
    if isinstance(value, InteractionMode):
        return value

    # Handle string values
    if isinstance(value, str):
        normalized = value.lower().strip()

        # Try to match enum values
        for mode in InteractionMode:
            if mode.value == normalized:
                return mode

        # Try to match enum names (case-insensitive)
        try:
            return InteractionMode[value.upper().strip()]
        except KeyError:
            pass

    # Invalid value
    return None


def get_mode_name(mode: InteractionMode) -> str:
    """
    Get human-readable name for an interaction mode.

    Args:
        mode: InteractionMode enum value

    Returns:
        Human-readable mode name

    Examples:
        >>> get_mode_name(InteractionMode.ANALYTICS_ONLY)
        'Analytics Only'

        >>> get_mode_name(InteractionMode.SMART_INSIGHT)
        'Smart Insight'

        >>> get_mode_name(InteractionMode.DEEP_ADAPTIVE)
        'Deep Adaptive'
    """
    names = {
        InteractionMode.ANALYTICS_ONLY: "Analytics Only",
        InteractionMode.SMART_INSIGHT: "Smart Insight",
        InteractionMode.DEEP_ADAPTIVE: "Deep Adaptive",
    }
    return names.get(mode, "Unknown")


def is_mode_valid(value: Any) -> bool:
    """
    Check if a value is a valid interaction mode.

    Args:
        value: Value to check (string or InteractionMode)

    Returns:
        True if value represents a valid mode, False otherwise

    Examples:
        >>> is_mode_valid("analytics_only")
        True

        >>> is_mode_valid(InteractionMode.SMART_INSIGHT)
        True

        >>> is_mode_valid("invalid_mode")
        False
    """
    return _parse_interaction_mode(value) is not None


# Public API
__all__ = [
    'InteractionMode',
    'resolve_interaction_mode',
    'get_mode_name',
    'is_mode_valid',
]
