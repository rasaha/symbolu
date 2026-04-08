"""
Policy Simulation & Replay — Policy Phase P2

Allows policy outputs to be evaluated under different profile/config
conditions without invoking the full runtime stack.

Capabilities:
    - Simulate policy posture under a supplied DomainProfile
    - Simulate session policy with threshold overrides
    - Simulate trading guardrails with threshold overrides
    - Compare baseline vs candidate profile results side by side
    - Produce structured, serializable results

Design Principles:
    - Zero-LLM: Pure deterministic replay
    - Delegation-only: Calls existing engines with overridden config
    - No side effects: Does not modify profiles, registries, or audit logs
    - Serializable: All results are plain dicts suitable for JSON

Usage:
    from agentic.policy.policy_simulation import (
        simulate_policy,
        simulate_session_policy,
        simulate_trading_guardrails,
        compare_policy,
    )

    # Simulate with alternate profile
    result = simulate_policy(unified, profile=custom_profile)

    # Compare default vs candidate
    comparison = compare_policy(unified, domain="trading", candidate_profile=custom_profile)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .profile_schema import DomainProfile, get_profile_registry
from .domain_profiles import get_domain_profile
from .interaction_modes import InteractionMode, resolve_interaction_mode
from .policy_engine import compute_policy_flags
from .session_policy import SessionPolicyFlags, compute_session_policy_flags
from .trading_guardrail_engine import TradingGuardrailFlags, compute_trading_guardrails


# =============================================================================
# Constants
# =============================================================================

SIM_VERSION = "1.0.0"


# =============================================================================
# Threshold extraction helper
# =============================================================================


def _extract_thresholds_from_profile(profile: DomainProfile) -> Dict[str, float]:
    """
    Extract all P2 threshold fields from a DomainProfile as a flat dict.

    This dict can be passed as ``thresholds`` to session_policy and
    trading_guardrail engines.
    """
    return {
        # Session policy thresholds
        "session_coherence_stable": profile.session_coherence_stable,
        "session_coherence_recovering": profile.session_coherence_recovering,
        "session_grounding_drift": profile.session_grounding_drift,
        "session_grounding_semantic": profile.session_grounding_semantic,
        "session_reflection_arc": profile.session_reflection_arc,
        "session_reflection_volatility": profile.session_reflection_volatility,
        "session_exploratory_arc": profile.session_exploratory_arc,
        # Trading guardrail thresholds
        "trading_resonance_floor": profile.trading_resonance_floor,
        "trading_coherence_floor": profile.trading_coherence_floor,
        "trading_drift_floor": profile.trading_drift_floor,
    }


# =============================================================================
# Core simulation functions
# =============================================================================


def simulate_policy(
    unified: Dict[str, Any],
    domain: str = "generic",
    profile: Optional[DomainProfile] = None,
    user_mode_override: Optional[str] = None,
    admin_mode_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Simulate policy flag computation under a given profile.

    If ``profile`` is supplied, it is used directly (the ``domain``
    parameter is only used for metadata). Otherwise the registry
    profile for ``domain`` is used.

    Args:
        unified: Unified output dict (same shape as runtime)
        domain: Domain identifier (used for registry lookup if no profile given)
        profile: Optional DomainProfile to evaluate against
        user_mode_override: Optional interaction mode override
        admin_mode_override: Optional admin interaction mode override

    Returns:
        Dict with:
            flags: computed policy flags dict
            profile_id: profile used
            profile_version: version of profile used
            domain: domain identifier
            sim_version: simulation engine version
            timestamp: ISO-8601 timestamp
    """
    effective_profile = profile if profile is not None else get_domain_profile(domain)

    # compute_policy_flags uses get_domain_profile(domain) internally.
    # To use a custom profile, we temporarily register it.
    registry = get_profile_registry()
    sim_domain = f"__sim__{effective_profile.profile_id}"

    try:
        registry.register(effective_profile, domain_id=sim_domain)
        flags = compute_policy_flags(
            unified=unified,
            domain=sim_domain,
            user_mode_override=user_mode_override,
            admin_mode_override=admin_mode_override,
        )
    finally:
        # Clean up temporary registration
        registry.unregister(sim_domain)

    return {
        "flags": flags,
        "profile_id": effective_profile.profile_id,
        "profile_version": effective_profile.profile_version,
        "domain": domain,
        "sim_version": SIM_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def simulate_session_policy(
    session_summary: Any,
    profile: Optional[DomainProfile] = None,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Simulate session policy computation under given thresholds.

    Threshold resolution priority:
        1. Explicit ``thresholds`` dict
        2. Extracted from ``profile`` if supplied
        3. Original hardcoded defaults (no override)

    Args:
        session_summary: SessionSummary (or mock) with multi-turn metrics
        profile: Optional DomainProfile to extract thresholds from
        thresholds: Optional explicit threshold overrides (highest priority)

    Returns:
        Dict with:
            flags: SessionPolicyFlags.to_dict() or None
            thresholds_used: the thresholds that were applied
            sim_version: simulation engine version
            timestamp: ISO-8601 timestamp
    """
    effective_thresholds: Optional[Dict[str, float]] = None
    if thresholds is not None:
        effective_thresholds = thresholds
    elif profile is not None:
        effective_thresholds = _extract_thresholds_from_profile(profile)

    flags_obj = compute_session_policy_flags(
        session_summary,
        thresholds=effective_thresholds,
    )

    return {
        "flags": flags_obj.to_dict() if flags_obj is not None else None,
        "thresholds_used": effective_thresholds,
        "sim_version": SIM_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def simulate_trading_guardrails(
    summary: Any,
    policy: Any = None,
    motivation: Any = None,
    intent_arc: Any = None,
    identity_signature: Any = None,
    profile: Optional[DomainProfile] = None,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Simulate trading guardrail computation under given thresholds.

    Threshold resolution priority:
        1. Explicit ``thresholds`` dict
        2. Extracted from ``profile`` if supplied
        3. Original hardcoded defaults (no override)

    Args:
        summary: SessionSummary with trading metrics
        policy: PolicyFlags (reserved, pass None)
        motivation: MotivationProfile (reserved, pass None)
        intent_arc: IntentArc (reserved, pass None)
        identity_signature: IdentitySignature (reserved, pass None)
        profile: Optional DomainProfile to extract thresholds from
        thresholds: Optional explicit threshold overrides

    Returns:
        Dict with:
            flags: TradingGuardrailFlags.to_dict()
            thresholds_used: the thresholds applied
            sim_version: simulation engine version
            timestamp: ISO-8601 timestamp
    """
    effective_thresholds: Optional[Dict[str, float]] = None
    if thresholds is not None:
        effective_thresholds = thresholds
    elif profile is not None:
        effective_thresholds = _extract_thresholds_from_profile(profile)

    flags_obj = compute_trading_guardrails(
        summary=summary,
        policy=policy,
        motivation=motivation,
        intent_arc=intent_arc,
        identity_signature=identity_signature,
        thresholds=effective_thresholds,
    )

    return {
        "flags": flags_obj.to_dict(),
        "thresholds_used": effective_thresholds,
        "sim_version": SIM_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Comparison
# =============================================================================


def compare_policy(
    unified: Dict[str, Any],
    domain: str,
    candidate_profile: DomainProfile,
    user_mode_override: Optional[str] = None,
    admin_mode_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compare policy outputs between default and candidate profiles.

    Runs ``simulate_policy`` twice — once with the registry default
    for ``domain``, once with ``candidate_profile`` — and produces
    a structured diff.

    Args:
        unified: Unified output dict
        domain: Domain identifier for the baseline profile
        candidate_profile: Alternate profile to compare against
        user_mode_override: Optional mode override (applied to both)
        admin_mode_override: Optional admin mode override (applied to both)

    Returns:
        Dict with:
            baseline: simulate_policy result for default profile
            candidate: simulate_policy result for candidate_profile
            changed_flags: list of flag keys whose values differ
            is_identical: True if all flags match
            sim_version: simulation engine version
            timestamp: ISO-8601 timestamp
    """
    baseline = simulate_policy(
        unified=unified,
        domain=domain,
        profile=None,  # uses registry default
        user_mode_override=user_mode_override,
        admin_mode_override=admin_mode_override,
    )

    candidate = simulate_policy(
        unified=unified,
        domain=domain,
        profile=candidate_profile,
        user_mode_override=user_mode_override,
        admin_mode_override=admin_mode_override,
    )

    # Compute diff
    baseline_flags = baseline["flags"]
    candidate_flags = candidate["flags"]
    changed_flags = [
        key for key in baseline_flags
        if baseline_flags.get(key) != candidate_flags.get(key)
    ]

    return {
        "baseline": baseline,
        "candidate": candidate,
        "changed_flags": changed_flags,
        "is_identical": len(changed_flags) == 0,
        "sim_version": SIM_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compare_session_policy(
    session_summary: Any,
    baseline_thresholds: Optional[Dict[str, float]] = None,
    candidate_thresholds: Optional[Dict[str, float]] = None,
    baseline_profile: Optional[DomainProfile] = None,
    candidate_profile: Optional[DomainProfile] = None,
) -> Dict[str, Any]:
    """
    Compare session policy outputs between two threshold configs.

    Args:
        session_summary: SessionSummary with multi-turn metrics
        baseline_thresholds: Thresholds for baseline (or use baseline_profile)
        candidate_thresholds: Thresholds for candidate (or use candidate_profile)
        baseline_profile: Profile for baseline threshold extraction
        candidate_profile: Profile for candidate threshold extraction

    Returns:
        Dict with baseline, candidate, changed_flags, is_identical
    """
    baseline = simulate_session_policy(
        session_summary,
        profile=baseline_profile,
        thresholds=baseline_thresholds,
    )
    candidate = simulate_session_policy(
        session_summary,
        profile=candidate_profile,
        thresholds=candidate_thresholds,
    )

    b_flags = baseline["flags"] or {}
    c_flags = candidate["flags"] or {}
    changed_flags = [
        key for key in set(list(b_flags.keys()) + list(c_flags.keys()))
        if b_flags.get(key) != c_flags.get(key)
    ]

    return {
        "baseline": baseline,
        "candidate": candidate,
        "changed_flags": changed_flags,
        "is_identical": len(changed_flags) == 0,
        "sim_version": SIM_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "simulate_policy",
    "simulate_session_policy",
    "simulate_trading_guardrails",
    "compare_policy",
    "compare_session_policy",
    "SIM_VERSION",
]
