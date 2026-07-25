"""Deterministic engine construction from scenario policy (composition layer).

Translates the scenario's *deployed-policy* description into concrete TAP /
ActionGate reference engines and the DGM execution adapter. This is the only
place that reads provider-native engine knobs; scenario handlers never do.

Only policy fields are read here — never the scenario's ``expected`` region.
"""
from __future__ import annotations

from typing import Optional

from actiongate_provider.core import (
    ActionGateConstraint, ActionGateEngine, ActionGateObligation, ConstrainedRule)
from decision_governance.api.contracts import BusinessOutcome
from decision_governance.api.ports import OfflineDeterministicExecutionAdapter
from tap_provider.core import TapConstraint, TapEngine, TapObligation, TapOutcome, TapRule

from ..schemas.scenario import ActionPolicy, ExecutionSpec, TapPolicy


def build_tap_engine(assertion: str, policy: TapPolicy) -> TapEngine:
    if policy.fail is not None:
        return TapEngine(fail=policy.fail)
    if policy.emit_unknown:
        return TapEngine(emit_unknown=True)
    if policy.derive_from_evidence:
        return TapEngine()  # derive outcome purely from supplied evidence stance
    rule = TapRule(
        outcome=TapOutcome(policy.outcome),
        evidence_coverage=policy.evidence_coverage,
        supported_components=tuple(policy.supported_components),
        unsupported_components=tuple(policy.unsupported_components),
        omitted_qualifiers=tuple(policy.omitted_qualifiers),
        constraints=tuple(TapConstraint(t, v) for t, v in policy.constraints),
        obligations=tuple(TapObligation(t, v) for t, v in policy.obligations),
        reason_codes=tuple(policy.reason_codes))
    return TapEngine(rules={assertion: rule})


def build_actiongate_engine(action_type: str, policy: ActionPolicy) -> ActionGateEngine:
    if policy.fail is not None:
        return ActionGateEngine(fail=policy.fail)
    kwargs: dict = {"available": policy.available}
    if policy.mode == "deny":
        kwargs["denied"] = frozenset({action_type})
    elif policy.mode == "unknown":
        kwargs["unknown"] = frozenset({action_type})
    elif policy.mode == "constrained":
        rule = ConstrainedRule(
            constraints=tuple(ActionGateConstraint(t, v) for t, v in policy.constraints),
            obligations=tuple(ActionGateObligation(t, v) for t, v in policy.obligations),
            expiry_seconds=policy.expiry_seconds)
        kwargs["constrained"] = {action_type: rule}
    return ActionGateEngine(**kwargs)


def build_execution_adapter(action_type: str, spec: ExecutionSpec, *,
                            id_factory=None, clock=None
                            ) -> OfflineDeterministicExecutionAdapter:
    transport = frozenset({action_type}) if spec.transport_fail else frozenset()
    timing = frozenset({action_type}) if spec.timeout else frozenset()
    outcomes: Optional[dict] = None
    if spec.business_outcome and spec.business_outcome != "SUCCEEDED":
        outcomes = {action_type: BusinessOutcome[spec.business_outcome]}
    overrides = None
    if spec.observed_overrides:
        overrides = {action_type: dict(spec.observed_overrides)}
    extra = {}
    if id_factory is not None:
        extra["id_factory"] = id_factory
    if clock is not None:
        extra["clock"] = clock
    return OfflineDeterministicExecutionAdapter(
        transport_failing=transport, timing_out=timing, outcomes=outcomes,
        observed_parameter_overrides=overrides, **extra)
