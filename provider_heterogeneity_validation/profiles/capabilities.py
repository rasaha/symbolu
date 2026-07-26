"""Capability + compatibility profiles (Task 5).

A canonical capability vocabulary and an honest per-provider capability declaration.
Baseline providers declare their capabilities directly in their descriptors; the
frozen TAP/ActionGate providers use their own feature vocabulary, so this module
maps them to the canonical capabilities from their documented, real behaviour —
without modifying any frozen provider. Capability is asserted only where the
provider genuinely supports it (never because an unknown field can be stored).
"""
from __future__ import annotations

# --- canonical capability vocabulary ----------------------------------------

ASSERTION_CAPABILITIES = (
    "exact_evidence_matching", "contradiction_detection", "missing_evidence_detection",
    "qualifier_detection", "scope_analysis", "component_decomposition",
    "provenance_analysis", "confidence_constraints", "human_review_obligation")

ACTION_CAPABILITIES = (
    "allow_deny", "amount_limits", "resource_scope_limits", "region_limits",
    "required_approval", "notifications", "expiry", "single_use",
    "parameter_restrictions", "rate_limits")

# --- honest per-provider capability declarations ----------------------------

_TAP_CAPS = frozenset({
    "exact_evidence_matching", "contradiction_detection", "missing_evidence_detection",
    "qualifier_detection", "scope_analysis", "component_decomposition",
    "provenance_analysis", "confidence_constraints", "human_review_obligation"})
_BASELINE_ASSERTION_CAPS = frozenset({
    "exact_evidence_matching", "contradiction_detection", "missing_evidence_detection"})
_ACTIONGATE_CAPS = frozenset({
    "allow_deny", "amount_limits", "resource_scope_limits", "region_limits",
    "required_approval", "notifications", "expiry", "single_use", "parameter_restrictions"})
_BASELINE_ACTION_CAPS = frozenset({"allow_deny", "amount_limits", "notifications"})

CAPABILITY_PROFILE: dict = {
    "tap-primary": _TAP_CAPS,
    "baseline-assertion": _BASELINE_ASSERTION_CAPS,
    "actiongate-primary": _ACTIONGATE_CAPS,
    "baseline-action": _BASELINE_ACTION_CAPS,
}


def capabilities_of(provider_id: str) -> frozenset:
    return CAPABILITY_PROFILE.get(provider_id, frozenset())


def satisfies(provider_id: str, required) -> bool:
    return set(required) <= capabilities_of(provider_id)
