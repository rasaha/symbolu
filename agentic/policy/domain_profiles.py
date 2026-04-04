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
- Profiles are now typed DomainProfile instances (Policy Phase P0)
- Dict-compatible access (profile["key"]) preserved for backward compat
- Backed by ProfileRegistry singleton for future externalization
- Deterministic profile selection
- Fallback to 'generic' for unknown domains
- Zero-LLM, JSON-serializable

Usage:
    from agentic.policy.domain_profiles import get_domain_profile

    profile = get_domain_profile("trading")
    min_coherence = profile["min_coherence"]   # dict-style (backward compat)
    min_coherence = profile.min_coherence      # attribute-style (new)
"""

from typing import Any, Dict, List

from .interaction_modes import InteractionMode
from .profile_schema import DomainProfile, ProfileRegistry, get_profile_registry


# ============================================================================
# Legacy DOMAIN_PROFILES dict — backward compatibility shim
# ============================================================================
#
# Some test code directly accesses and mutates DOMAIN_PROFILES (e.g.,
# test_policy_engine.py line 457). This dict is kept as a thin view
# over the registry's built-in profiles so that existing imports work.
#
# New code should use get_profile_registry() or get_domain_profile().

def _build_legacy_dict() -> Dict[str, Dict[str, Any]]:
    """Build the legacy DOMAIN_PROFILES dict from the registry."""
    registry = get_profile_registry()
    result = {}
    for name, profile in registry.all_profiles().items():
        d = {}
        for key in profile.keys():
            if key in ("profile_id", "profile_version"):
                continue  # not in legacy dict
            d[key] = profile[key]
        result[name] = d
    return result


DOMAIN_PROFILES: Dict[str, Dict[str, Any]] = _build_legacy_dict()


# ============================================================================
# Public API
# ============================================================================


def get_domain_profile(domain: str) -> DomainProfile:
    """
    Get domain-specific profile configuration.

    Retrieves the policy profile for a given domain with fallback
    to 'generic' profile for unknown domains.

    Returns a DomainProfile instance that supports both attribute access
    (profile.min_coherence) and dict-style access (profile["min_coherence"]).

    Args:
        domain: Domain identifier (e.g., "trading", "therapy", "identity")

    Returns:
        DomainProfile with domain profile configuration

    Examples:
        >>> profile = get_domain_profile("trading")
        >>> profile["min_coherence"]
        0.55
        >>> profile.min_coherence
        0.55

        >>> profile = get_domain_profile("unknown_domain")
        >>> profile["style"]
        'neutral'
    """
    return get_profile_registry().get(domain)


def get_all_domain_names() -> List[str]:
    """
    Get list of all supported domain names.

    Returns:
        List of domain identifiers (excluding 'generic')

    Examples:
        >>> domains = get_all_domain_names()
        >>> "trading" in domains
        True
    """
    return get_profile_registry().get_all_domain_names()


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
    return get_profile_registry().is_domain_supported(domain)


# Public API
__all__ = [
    'get_domain_profile',
    'get_all_domain_names',
    'is_domain_supported',
    'DOMAIN_PROFILES',
]
