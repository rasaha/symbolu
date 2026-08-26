"""ActionGate wiring for the action-only strategy (imports actiongate_provider ONLY).

Builds an ActionGate provider + control-plane adapter from a scenario's action
policy and resolves it through the framework registry. Imports tap_provider
**never**.
"""
from __future__ import annotations

from actiongate_provider.configuration import ActionGateSettings, build_actiongate_provider
from actiongate_provider.core import (
    ActionGateConstraint, ActionGateEngine, ActionGateObligation, ConstrainedRule)
from governance_providers.api import (
    ActionGovernanceControlPlaneAdapter, ProviderKind, ProviderRegistry, ResolutionRequest,
    resolve)

from ..runners.determinism import make_clock


def build_actiongate_engine(action_type: str, policy) -> ActionGateEngine:
    if policy.fail is not None:
        return ActionGateEngine(fail=policy.fail)
    kwargs: dict = {"available": policy.available}
    if policy.mode == "deny":
        kwargs["denied"] = frozenset({action_type})
    elif policy.mode == "unknown":
        kwargs["unknown"] = frozenset({action_type})
    elif policy.mode == "constrained":
        kwargs["constrained"] = {action_type: ConstrainedRule(
            constraints=tuple(ActionGateConstraint(t, v) for t, v in policy.constraints),
            obligations=tuple(ActionGateObligation(t, v) for t, v in policy.obligations),
            expiry_seconds=policy.expiry_seconds)}
    return ActionGateEngine(**kwargs)


def resolve_actiongate(action_type: str, policy, *, seed: str, register: bool = True):
    """Register + resolve an ActionGate provider through the registry.

    ``register=False`` simulates a registry-resolution failure (empty registry).
    ``seed`` must be the seed the DGM services for this run are built from: the
    adapter is given that run's scenario clock, so CER expiry and authorization
    validity are computed in one time domain rather than against the wall clock.
    Returns (control_plane_adapter, resolution_record).
    """
    registry = ProviderRegistry()
    if register:
        provider = build_actiongate_provider(
            build_actiongate_engine(action_type, policy),
            settings=ActionGateSettings(provider_id="actiongate-primary", mode="in_process"))
        registry.register(provider.descriptor())
    resolved, record = resolve(registry, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE))
    return ActionGovernanceControlPlaneAdapter(resolved, clock=make_clock(seed)), record
