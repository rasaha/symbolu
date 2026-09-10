"""Identical inputs yield the identical decision, and the fingerprint proves it.

The gate's own docstring claims decisions are "replayable, auditable". That claim rests on
two things nothing was checking: that no wall clock is read (``now`` is a parameter), and
that aggregation precedence is fixed rather than dependent on dict or set iteration order.
"""

from __future__ import annotations

import pytest

from ugence_model_selection.api import (
    Candidate,
    EligibilityState,
    Evidence,
    EvidenceSource,
    ExecutableRegistry,
    ExecutionGate,
    GateConfig,
    ModelRecord,
    PolicyWeights,
    Request,
    Signal,
    fingerprint,
    select,
)

NOW = 1_700_000_000.0


def _ev(ttl=900.0):
    return Evidence(EvidenceSource.TELEMETRY, NOW, 1.0, ttl_seconds=ttl)


def _candidate(model_id="m", quality=0.8, region="us", provider="anthropic") -> Candidate:
    return Candidate(
        provider=provider, model_id=model_id, family="f", region=region,
        context_limit=100_000, structured_output=True, tool_use=True,
        price_in_per_mtok=3.0, price_out_per_mtok=15.0,
        signals={
            "reachable": Signal(True, _ev()),
            "network_allowed": Signal(True, _ev()),
            "authenticated": Signal(True, _ev()),
            "credential_expiry_ts": Signal(NOW + 10_000, _ev()),
            "billing_active": Signal(True, _ev()),
            "quota_state": Signal("ok", _ev()),
            "model_available": Signal(True, _ev()),
            "observed_latency_ms": Signal(420.0, _ev()),
            "reliability": Signal(0.995, _ev()),
            "quality": Signal(quality, _ev()),
        })


def _request(**kw) -> Request:
    defaults = {"context_tokens": 4_000, "est_output_tokens": 500}
    defaults.update(kw)
    return Request(request_id="req-determinism", **defaults)


@pytest.mark.parametrize("config", [
    GateConfig(),
    GateConfig(quality_floor=0.5),
    GateConfig(require_billing=True, allow_conditional=False),
])
def test_repeated_evaluation_produces_an_identical_decision_record(config):
    gate = ExecutionGate(config)
    first = gate.evaluate(_candidate(), _request(), NOW)
    second = gate.evaluate(_candidate(), _request(), NOW)

    assert first.to_dict() == second.to_dict()
    assert fingerprint(first.to_dict()) == fingerprint(second.to_dict())


def test_a_fresh_gate_instance_decides_identically():
    """No instance state may leak between evaluations."""
    a = ExecutionGate(GateConfig(quality_floor=0.6)).evaluate(_candidate(), _request(), NOW)
    b = ExecutionGate(GateConfig(quality_floor=0.6)).evaluate(_candidate(), _request(), NOW)

    assert fingerprint(a.to_dict()) == fingerprint(b.to_dict())


def test_condition_order_is_fixed_not_incidental():
    """The serialized record's condition order is part of its identity."""
    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(
        _candidate(), _request(), NOW)

    assert [c.condition for c in decision.conditions] == [
        "provider_reachable", "network_policy_allowed", "authenticated",
        "credential_expiry_valid", "billing_active", "quota_available",
        "model_available", "region_allowed", "enterprise_policy_allowed",
        "data_residency_allowed", "required_features_supported",
        "context_length_sufficient", "projected_cost_within_limit",
        "latency_within_limit", "reliability_within_limit", "quality_within_floor",
    ]


def test_registry_insertion_order_does_not_change_the_ranking():
    """Ranking must break ties on ``internal_id``, not on whichever record arrived first."""
    request = _request()
    records = [ModelRecord(internal_id=f"m-{i}", candidate=_candidate(model_id=f"m-{i}"),
                           observed_latency_ms=400.0) for i in range(5)]

    def ranked(order):
        registry = ExecutableRegistry(ExecutionGate(GateConfig()))
        for record in order:
            registry.upsert(record)
        selectable, _ = registry.evaluate(request, NOW)
        return [(r.internal_id, s) for r, s in
                select(selectable, request, lambda r: 0.8, PolicyWeights()).ranked]

    assert ranked(records) == ranked(list(reversed(records)))


def test_evidence_staleness_is_measured_against_the_supplied_now():
    """Not the system clock: the same inputs at a later ``now`` decide differently, and
    that is the only thing that may change the answer."""
    candidate = _candidate()
    gate = ExecutionGate(GateConfig())

    fresh = gate.evaluate(candidate, _request(), NOW)
    stale = gate.evaluate(candidate, _request(), NOW + 10_000)

    assert fresh.state is EligibilityState.ELIGIBLE
    assert stale.state is not EligibilityState.ELIGIBLE
