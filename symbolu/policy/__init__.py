"""
Domain Coherence Profiles + Policy Layer v1.0

This module provides domain-specific policy profiles and deterministic
policy flag computation for Symbol-U AGI responses.

Design Principles:
- Zero-LLM: All operations are deterministic and rule-based
- Non-invasive: Does not modify pipeline behavior
- Additive: Optional layer that provides advisory flags
- CI-tested: Comprehensive test coverage

Usage:
    from symbolu.policy import compute_policy_flags, get_domain_profile

    # After pipeline execution:
    policy_flags = compute_policy_flags(unified_output, domain="trading")

Public API:
    get_domain_profile(domain: str) -> Dict[str, Any]
    compute_policy_flags(unified: Dict[str, Any], domain: str) -> Dict[str, Any]
"""

from .domain_profiles import get_domain_profile
from .policy_engine import compute_policy_flags

__all__ = [
    'get_domain_profile',
    'compute_policy_flags',
]

__version__ = '1.0.0'
