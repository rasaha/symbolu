"""TAP wiring for the assertion-only strategy (imports tap_provider ONLY).

Builds a TAP provider from a scenario's TAP policy and resolves it through the
framework registry. Imports actiongate_provider **never**.
"""
from __future__ import annotations

from governance_providers.api import (
    ProviderKind, ProviderRegistry, ResolutionRequest, resolve)
from tap_provider.configuration import TapSettings, build_tap_provider
from tap_provider.core import TapConstraint, TapEngine, TapObligation, TapOutcome, TapRule


def build_tap_engine(assertion: str, policy) -> TapEngine:
    if policy.fail is not None:
        return TapEngine(fail=policy.fail)
    if policy.emit_unknown:
        return TapEngine(emit_unknown=True)
    if policy.derive_from_evidence:
        return TapEngine()
    rule = TapRule(
        outcome=TapOutcome(policy.outcome), evidence_coverage=policy.evidence_coverage,
        supported_components=tuple(policy.supported_components),
        unsupported_components=tuple(policy.unsupported_components),
        omitted_qualifiers=tuple(policy.omitted_qualifiers),
        constraints=tuple(TapConstraint(t, v) for t, v in policy.constraints),
        obligations=tuple(TapObligation(t, v) for t, v in policy.obligations),
        reason_codes=tuple(policy.reason_codes))
    return TapEngine(rules={assertion: rule})


def resolve_tap(assertion: str, policy):
    """Register + resolve a TAP provider deterministically through the registry."""
    provider = build_tap_provider(
        build_tap_engine(assertion, policy),
        settings=TapSettings(provider_id="tap-primary", mode="in_process"))
    registry = ProviderRegistry()
    registry.register(provider.descriptor())
    resolved, record = resolve(registry, ResolutionRequest(ProviderKind.ASSERTION_GOVERNANCE))
    return resolved, record
