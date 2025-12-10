"""
Domain Coherence Profiles for Symbol-U Policy Layer

Defines domain-specific tolerances, preferences, and behavioral profiles
for different application contexts (trading, therapy, identity exploration, etc.).

Each profile includes:
- Coherence thresholds
- Persona drift limits
- Mapper volatility bounds
- Preferred mapper configurations
- Stylistic preferences
- Phase 5: Formula UI modulation settings (therapy/identity only)
- Phase 15: Interaction mode defaults (controls formula influence level)

Design:
- Static configuration (no runtime modification)
- Deterministic profile selection
- Fallback to 'generic' for unknown domains
- Zero-LLM, JSON-serializable

Usage:
    from symbolu.policy.domain_profiles import get_domain_profile

    profile = get_domain_profile("trading")
    min_coherence = profile["min_coherence"]
"""

from typing import Dict, Any
from .interaction_modes import InteractionMode


# Domain profile definitions
DOMAIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "trading": {
        "min_coherence": 0.55,
        "max_persona_drift": 0.40,
        "max_mapper_volatility": 0.45,
        "prefer_mappers": ["LCM", "HRM"],
        "allow_lam": False,
        "style": "precise",
        "use_coherence_v2": False,  # Phase 4: Stay ultra-conservative, use v1 only
        "use_coherence_v3": False,  # Phase 10: Experimental megafusion (disabled by default)
        # Phase 12: v3 quality gating (disabled for trading, v3 not used)
        "min_v3_quality_for_activation": None,
        # Phase 5: Formula UI modulation (disabled for trading)
        "formula_ui_mode": "none",
        "min_resonance_for_reflection": 0.60,
        "max_tension_for_reflection": 0.50,
        # Phase 7: Trading Formula Guardrails v1.0
        "formula_guardrails_enabled": True,
        "max_tension_allowed": 0.70,
        "max_negative_delta_smi": 0.12,
        "max_volatility_allowed": 0.60,  # from mapper_volatility_score
        # Phase 15: Interaction Mode Layer v1.0
        "interaction_mode_default": InteractionMode.ANALYTICS_ONLY,
    },
    "therapy": {
        "min_coherence": 0.45,
        "max_persona_drift": 0.60,
        "max_mapper_volatility": 0.60,
        "prefer_mappers": ["HRM", "LAM"],
        "allow_lam": True,
        "style": "reflective",
        "use_coherence_v2": True,  # Phase 4: Enable formula-aware coherence
        "use_coherence_v3": True,  # Phase 11: Enable megafusion v3 for therapy domain
        # Phase 12: v3 quality gating (soft, forgiving threshold for therapy)
        "min_v3_quality_for_activation": 0.40,
        # Phase 5: Formula UI modulation (enabled for therapy)
        "formula_ui_mode": "light",
        "min_resonance_for_reflection": 0.50,
        "max_tension_for_reflection": 0.75,
        # Phase 7: Trading Formula Guardrails v1.0 (disabled for therapy)
        "formula_guardrails_enabled": False,
        # Phase 15: Interaction Mode Layer v1.0
        "interaction_mode_default": InteractionMode.SMART_INSIGHT,
    },
    "identity": {
        "min_coherence": 0.50,
        "max_persona_drift": 0.50,
        "max_mapper_volatility": 0.55,
        "prefer_mappers": ["LAM", "HRM"],
        "allow_lam": True,
        "style": "exploratory",
        "use_coherence_v2": True,  # Phase 4: Enable formula-aware coherence
        "use_coherence_v3": True,  # Phase 11: Enable megafusion v3 for identity domain
        # Phase 12: v3 quality gating (slightly stricter than therapy)
        "min_v3_quality_for_activation": 0.45,
        # Phase 5: Formula UI modulation (enabled for identity)
        "formula_ui_mode": "light",
        "min_resonance_for_reflection": 0.50,
        "max_tension_for_reflection": 0.70,
        # Phase 7: Trading Formula Guardrails v1.0 (disabled for identity)
        "formula_guardrails_enabled": False,
        # Phase 15: Interaction Mode Layer v1.0
        "interaction_mode_default": InteractionMode.SMART_INSIGHT,
    },
    "generic": {
        "min_coherence": 0.40,
        "max_persona_drift": 0.55,
        "max_mapper_volatility": 0.55,
        "prefer_mappers": ["HRM"],
        "allow_lam": False,
        "style": "neutral",
        "use_coherence_v2": False,  # Phase 4: Stay conservative, use v1 by default
        "use_coherence_v3": False,  # Phase 10: Experimental megafusion (disabled by default)
        # Phase 12: v3 quality gating (disabled for generic, v3 not used)
        "min_v3_quality_for_activation": None,
        # Phase 5: Formula UI modulation (disabled for generic)
        "formula_ui_mode": "none",
        "min_resonance_for_reflection": 0.55,
        "max_tension_for_reflection": 0.60,
        # Phase 7: Trading Formula Guardrails v1.0 (disabled for generic)
        "formula_guardrails_enabled": False,
        # Phase 15: Interaction Mode Layer v1.0
        "interaction_mode_default": InteractionMode.ANALYTICS_ONLY,
    },
}


def get_domain_profile(domain: str) -> Dict[str, Any]:
    """
    Get domain-specific profile configuration.

    Retrieves the policy profile for a given domain with fallback
    to 'generic' profile for unknown domains.

    Args:
        domain: Domain identifier (e.g., "trading", "therapy", "identity")

    Returns:
        Dictionary with domain profile configuration including:
        - min_coherence: Minimum acceptable coherence score
        - max_persona_drift: Maximum allowed persona drift
        - max_mapper_volatility: Maximum allowed mapper volatility
        - prefer_mappers: List of preferred mapper types
        - allow_lam: Whether Long-Arc Mapper is allowed
        - style: Recommended stylistic approach

    Examples:
        >>> profile = get_domain_profile("trading")
        >>> profile["min_coherence"]
        0.55

        >>> profile = get_domain_profile("unknown_domain")
        >>> profile["style"]
        'neutral'
    """
    # Normalize domain string (lowercase, strip whitespace)
    normalized_domain = domain.lower().strip() if domain else "generic"

    # Return profile with fallback to generic
    return DOMAIN_PROFILES.get(normalized_domain, DOMAIN_PROFILES["generic"])


def get_all_domain_names() -> list[str]:
    """
    Get list of all supported domain names.

    Returns:
        List of domain identifiers (excluding 'generic')

    Examples:
        >>> domains = get_all_domain_names()
        >>> "trading" in domains
        True
    """
    return [name for name in DOMAIN_PROFILES.keys() if name != "generic"]


def is_domain_supported(domain: str) -> bool:
    """
    Check if a domain has an explicit profile.

    Args:
        domain: Domain identifier to check

    Returns:
        True if domain has explicit profile, False if it will use generic

    Examples:
        >>> is_domain_supported("trading")
        True
        >>> is_domain_supported("unknown")
        False
    """
    normalized_domain = domain.lower().strip() if domain else ""
    return normalized_domain in DOMAIN_PROFILES and normalized_domain != "generic"


# Public API
__all__ = [
    'get_domain_profile',
    'get_all_domain_names',
    'is_domain_supported',
    'DOMAIN_PROFILES',
]
