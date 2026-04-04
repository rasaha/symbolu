"""
Domain Coherence Profiles + Policy Layer v1.0

This module provides domain-specific policy profiles and deterministic
policy flag computation for Symbol-U AGI responses.

Design Principles:
- Zero-LLM: All operations are deterministic and rule-based
- Non-invasive: Does not modify pipeline behavior
- Additive: Optional layer that provides advisory flags
- CI-tested: Comprehensive test coverage

Phase 15: Interaction Mode Layer v1.0
- ANALYTICS_ONLY: Standard behavior, no formula influence
- SMART_INSIGHT: Soft UI-layer refinement
- DEEP_ADAPTIVE: Full adaptive mode with VMF/ATH hints

Usage:
    from agentic.policy import compute_policy_flags, get_domain_profile
    from agentic.policy import InteractionMode, resolve_interaction_mode

    # After pipeline execution:
    policy_flags = compute_policy_flags(unified_output, domain="trading")

    # Phase 15: Check interaction mode
    mode = resolve_interaction_mode(profile, user_override=None)

Public API:
    get_domain_profile(domain: str) -> DomainProfile
    compute_policy_flags(unified: Dict[str, Any], domain: str) -> Dict[str, Any]
    InteractionMode: Enum for interaction modes
    resolve_interaction_mode: Mode resolution function
    DomainProfile: Typed, frozen domain profile (Policy Phase P0)
    ProfileRegistry / get_profile_registry: Profile management
"""

from .domain_profiles import get_domain_profile
from .policy_engine import compute_policy_flags
from .interaction_modes import (
    InteractionMode,
    resolve_interaction_mode,
    get_mode_name,
    is_mode_valid,
)
from .profile_schema import (
    DomainProfile,
    ProfileRegistry,
    get_profile_registry,
)
from .policy_service import (
    PolicyService,
    get_policy_service,
    P1_VERSION,
)
from .session_policy import SessionPolicyFlags
from .trading_guardrail_engine import TradingGuardrailFlags

__all__ = [
    'get_domain_profile',
    'compute_policy_flags',
    'InteractionMode',
    'resolve_interaction_mode',
    'get_mode_name',
    'is_mode_valid',
    'DomainProfile',
    'ProfileRegistry',
    'get_profile_registry',
    # Policy Phase P1
    'PolicyService',
    'get_policy_service',
    'P1_VERSION',
    'SessionPolicyFlags',
    'TradingGuardrailFlags',
]

__version__ = '1.2.0'
