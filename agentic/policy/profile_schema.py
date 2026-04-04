"""
Domain Profile Schema and Registry — Policy Phase P0

Typed, frozen, versionable domain profile schema and registry.

This module replaces the raw hardcoded dicts in domain_profiles.py with
a structured, typed foundation that supports:
- Typed field access (profile.min_coherence)
- Dict-compatible access (profile["min_coherence"], profile.get("key", default))
- Profile versioning metadata (profile_id, profile_version)
- Loading from dicts/JSON for future externalization
- A ProfileRegistry singleton as the single source of truth

Backward Compatibility:
    All existing consumers use profile["key"] or profile.get("key", default).
    DomainProfile supports both, so no consumer changes are needed.

Design Principles:
    - Zero-LLM: Pure deterministic, no inference
    - Frozen: Profiles are immutable after creation
    - Fail-closed: Unknown profiles fall back to generic
    - JSON-serializable: All fields support round-trip serialization
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, asdict
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .interaction_modes import InteractionMode


# =============================================================================
# Profile Schema
# =============================================================================


@dataclass(frozen=True)
class DomainProfile:
    """
    Typed, immutable domain policy profile.

    Supports dict-like access for backward compatibility:
        profile["min_coherence"]    # same as profile.min_coherence
        profile.get("key", default) # safe access with default

    Attributes:
        # Identity / Versioning
        profile_id: Unique identifier for this profile (e.g., "trading")
        profile_version: Version string for change tracking (e.g., "1.0.0")

        # Coherence & Safety Thresholds
        min_coherence: Minimum acceptable coherence score [0.0-1.0]
        max_persona_drift: Maximum allowed persona drift [0.0-1.0]
        max_mapper_volatility: Maximum allowed mapper volatility [0.0-1.0]

        # Mapper Configuration
        prefer_mappers: Ordered list of preferred mapper types
        allow_lam: Whether Long-Arc Mapper is allowed

        # Stylistic Preference
        style: Response style ("precise", "reflective", "exploratory", "neutral")

        # Coherence Feature Flags
        use_coherence_v2: Enable formula-aware coherence (Phase 4)
        use_coherence_v3: Enable megafusion coherence (Phase 10)
        min_v3_quality_for_activation: Quality gate for v3 activation (None = no gate)

        # Formula UI Modulation (Phase 5)
        formula_ui_mode: "none", "light", or "deep"
        min_resonance_for_reflection: Minimum resonance for reflection UI
        max_tension_for_reflection: Maximum tension for reflection UI

        # Trading Guardrails (Phase 7)
        formula_guardrails_enabled: Whether trading guardrails are active
        max_tension_allowed: Maximum tension before risk flag (trading only)
        max_negative_delta_smi: Maximum negative momentum (trading only)
        max_volatility_allowed: Maximum volatility before risk flag (trading only)

        # Interaction Mode (Phase 15)
        interaction_mode_default: Default interaction mode for this domain
    """

    # Identity / Versioning
    profile_id: str
    profile_version: str = "1.0.0"

    # Coherence & Safety Thresholds
    min_coherence: float = 0.40
    max_persona_drift: float = 0.55
    max_mapper_volatility: float = 0.55

    # Mapper Configuration
    prefer_mappers: Tuple[str, ...] = ("HRM",)
    allow_lam: bool = False

    # Stylistic Preference
    style: str = "neutral"

    # Coherence Feature Flags
    use_coherence_v2: bool = False
    use_coherence_v3: bool = False
    min_v3_quality_for_activation: Optional[float] = None

    # Formula UI Modulation (Phase 5)
    formula_ui_mode: str = "none"
    min_resonance_for_reflection: float = 0.55
    max_tension_for_reflection: float = 0.60

    # Trading Guardrails (Phase 7)
    formula_guardrails_enabled: bool = False
    max_tension_allowed: float = 0.70
    max_negative_delta_smi: float = 0.12
    max_volatility_allowed: float = 0.60

    # Interaction Mode (Phase 15)
    interaction_mode_default: InteractionMode = InteractionMode.ANALYTICS_ONLY

    # ========================================================================
    # Dict-compatible access (backward compatibility)
    # ========================================================================

    def __getitem__(self, key: str) -> Any:
        """Dict-style access: profile['min_coherence']."""
        if key == "prefer_mappers":
            # Return as list for backward compat (consumers check 'in' and index)
            return list(self.prefer_mappers)
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-style safe access: profile.get('key', default)."""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        """Support 'key in profile' checks."""
        return hasattr(self, key) and key in self._field_names()

    def keys(self) -> List[str]:
        """Return profile field names (dict-compatible)."""
        return self._field_names()

    def _field_names(self) -> List[str]:
        """Return all field names excluding identity/version metadata."""
        return [f.name for f in fields(self)]

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to a plain dict.

        InteractionMode is serialized as its string value.
        prefer_mappers is serialized as a list.
        """
        d = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, InteractionMode):
                d[f.name] = val.value
            elif isinstance(val, tuple):
                d[f.name] = list(val)
            else:
                d[f.name] = val
        return d

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainProfile":
        """
        Create a DomainProfile from a dict.

        Handles:
        - InteractionMode as string or enum
        - prefer_mappers as list or tuple
        - Missing fields use defaults
        - Unknown fields are ignored

        Args:
            data: Dictionary with profile fields

        Returns:
            DomainProfile instance
        """
        valid_fields = {f.name for f in fields(cls)}
        kwargs = {}

        for key, value in data.items():
            if key not in valid_fields:
                continue

            if key == "interaction_mode_default":
                if isinstance(value, str):
                    # Try to parse string to InteractionMode
                    for mode in InteractionMode:
                        if mode.value == value.lower():
                            value = mode
                            break
                    else:
                        value = InteractionMode.ANALYTICS_ONLY
                kwargs[key] = value
            elif key == "prefer_mappers":
                kwargs[key] = tuple(value) if isinstance(value, (list, tuple)) else (value,)
            else:
                kwargs[key] = value

        return cls(**kwargs)

    @classmethod
    def from_json(cls, json_str: str) -> "DomainProfile":
        """Create a DomainProfile from a JSON string."""
        return cls.from_dict(json.loads(json_str))


# =============================================================================
# Profile Registry
# =============================================================================


class ProfileRegistry:
    """
    Singleton registry of domain profiles.

    Serves as the single source of truth for domain policy profiles.
    Initialized with built-in defaults, but supports runtime loading
    from dicts/JSON for externalization.

    Thread Safety:
        Profile reads are safe from multiple threads. Profile registration
        should happen during initialization, not concurrently at runtime.

    Usage:
        registry = get_profile_registry()
        profile = registry.get("trading")

        # Load custom profiles
        registry.register(DomainProfile(profile_id="custom_trading", ...))

        # Load from dict
        registry.load_from_dict("custom", {...})

        # Reset to defaults
        registry.reset()
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, DomainProfile] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        """Load the built-in default profiles."""
        self._profiles = {
            "trading": DomainProfile(
                profile_id="trading",
                profile_version="1.0.0",
                min_coherence=0.55,
                max_persona_drift=0.40,
                max_mapper_volatility=0.45,
                prefer_mappers=("LCM", "HRM"),
                allow_lam=False,
                style="precise",
                use_coherence_v2=False,
                use_coherence_v3=False,
                min_v3_quality_for_activation=None,
                formula_ui_mode="none",
                min_resonance_for_reflection=0.60,
                max_tension_for_reflection=0.50,
                formula_guardrails_enabled=True,
                max_tension_allowed=0.70,
                max_negative_delta_smi=0.12,
                max_volatility_allowed=0.60,
                interaction_mode_default=InteractionMode.ANALYTICS_ONLY,
            ),
            "therapy": DomainProfile(
                profile_id="therapy",
                profile_version="1.0.0",
                min_coherence=0.45,
                max_persona_drift=0.60,
                max_mapper_volatility=0.60,
                prefer_mappers=("HRM", "LAM"),
                allow_lam=True,
                style="reflective",
                use_coherence_v2=True,
                use_coherence_v3=True,
                min_v3_quality_for_activation=0.40,
                formula_ui_mode="light",
                min_resonance_for_reflection=0.50,
                max_tension_for_reflection=0.75,
                formula_guardrails_enabled=False,
                interaction_mode_default=InteractionMode.SMART_INSIGHT,
            ),
            "identity": DomainProfile(
                profile_id="identity",
                profile_version="1.0.0",
                min_coherence=0.50,
                max_persona_drift=0.50,
                max_mapper_volatility=0.55,
                prefer_mappers=("LAM", "HRM"),
                allow_lam=True,
                style="exploratory",
                use_coherence_v2=True,
                use_coherence_v3=True,
                min_v3_quality_for_activation=0.45,
                formula_ui_mode="light",
                min_resonance_for_reflection=0.50,
                max_tension_for_reflection=0.70,
                formula_guardrails_enabled=False,
                interaction_mode_default=InteractionMode.SMART_INSIGHT,
            ),
            "generic": DomainProfile(
                profile_id="generic",
                profile_version="1.0.0",
                min_coherence=0.40,
                max_persona_drift=0.55,
                max_mapper_volatility=0.55,
                prefer_mappers=("HRM",),
                allow_lam=False,
                style="neutral",
                use_coherence_v2=False,
                use_coherence_v3=False,
                min_v3_quality_for_activation=None,
                formula_ui_mode="none",
                min_resonance_for_reflection=0.55,
                max_tension_for_reflection=0.60,
                formula_guardrails_enabled=False,
                interaction_mode_default=InteractionMode.ANALYTICS_ONLY,
            ),
        }

    def get(self, domain: str) -> DomainProfile:
        """
        Get profile for a domain, with fallback to generic.

        Args:
            domain: Domain identifier (case-insensitive, stripped)

        Returns:
            DomainProfile for the domain, or generic fallback
        """
        normalized = domain.lower().strip() if domain else "generic"
        return self._profiles.get(normalized, self._profiles["generic"])

    def register(self, profile: DomainProfile) -> None:
        """
        Register a profile in the registry.

        Args:
            profile: DomainProfile to register (keyed by profile_id)
        """
        self._profiles[profile.profile_id] = profile

    def load_from_dict(self, profile_id: str, data: Dict[str, Any]) -> DomainProfile:
        """
        Load and register a profile from a raw dict.

        Args:
            profile_id: Domain/profile identifier
            data: Dict with profile fields

        Returns:
            The created DomainProfile
        """
        if "profile_id" not in data:
            data = {**data, "profile_id": profile_id}
        profile = DomainProfile.from_dict(data)
        self._profiles[profile_id] = profile
        return profile

    def load_from_json(self, json_str: str) -> DomainProfile:
        """
        Load and register a profile from a JSON string.

        The JSON must include a 'profile_id' field.

        Args:
            json_str: JSON string with profile fields

        Returns:
            The created DomainProfile
        """
        profile = DomainProfile.from_json(json_str)
        self._profiles[profile.profile_id] = profile
        return profile

    def get_all_domain_names(self) -> List[str]:
        """Get all registered domain names (excluding 'generic')."""
        return [name for name in self._profiles if name != "generic"]

    def is_domain_supported(self, domain: str) -> bool:
        """Check if a domain has an explicit (non-generic) profile."""
        normalized = domain.lower().strip() if domain else ""
        return normalized in self._profiles and normalized != "generic"

    def all_profiles(self) -> Dict[str, DomainProfile]:
        """Return a copy of all registered profiles."""
        return dict(self._profiles)

    def reset(self) -> None:
        """Reset registry to built-in defaults only."""
        self._load_builtins()


# =============================================================================
# Singleton
# =============================================================================

_registry_instance: Optional[ProfileRegistry] = None


def get_profile_registry() -> ProfileRegistry:
    """
    Get the global ProfileRegistry singleton.

    Returns:
        ProfileRegistry instance
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ProfileRegistry()
    return _registry_instance


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "DomainProfile",
    "ProfileRegistry",
    "get_profile_registry",
]
