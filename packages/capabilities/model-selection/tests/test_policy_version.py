"""Policy-version identity, and backward replay of stored decisions.

A policy version identifies **decision semantics**, not record shape. Adding the
non-compensatory `quality_within_floor` branch means this code can reach a different
outcome from 0.1.0 on identical inputs when a floor is configured, so it may not keep
answering to `exec_gate_v1` — two implementations that can disagree must not both claim
the same policy version, because ruling that out is what replay and audit use the field
for.

The bump does not reach backwards. Stored v1 records are neither rewritten nor
invalidated: they keep their own stamp and stay readable and verifiable here forever.
Writing is confined to the current version; reading spans every supported one.

The five properties below are the regression the owner ruling named.
"""

from __future__ import annotations

import json

import pytest

from ugence_model_selection.api import (
    Candidate,
    EligibilityDecision,
    EligibilityState,
    Evidence,
    EvidenceSource,
    ExecutionGate,
    GateConfig,
    ModelRecord,
    PolicyWeights,
    POLICY_VERSION,
    POLICY_VERSION_V1,
    POLICY_VERSION_V2,
    ReasonCode,
    Request,
    Signal,
    SUPPORTED_POLICY_VERSIONS,
    UnsupportedPolicyVersionError,
    fingerprint,
    select,
)

NOW = 1_700_000_000.0

#: A decision record exactly as 0.1.0 wrote it: stamped ``exec_gate_v1``, fifteen
#: conditions, and no ``quality_within_floor`` — because that condition did not exist.
#: Held here as a literal rather than regenerated, so it cannot silently follow the code
#: it is supposed to outlive. Trimmed to four conditions for legibility; the version
#: admission and the reconstruction do not depend on how many there are.
STORED_V1_RECORD = {
    "provider": "anthropic",
    "model_id": "anthropic-model",
    "state": "ELIGIBLE",
    "reasons": ["OK"],
    "policy_version": "exec_gate_v1",
    "evaluated_at": 1_600_000_000.0,
    "ttl_seconds": 3600.0,
    "conditions": [
        {"condition": "provider_reachable", "verdict": "PASS", "reason": "OK",
         "criticality": "CRITICAL_OP",
         "evidence": {"source": "live_probe", "timestamp": 1_600_000_000.0,
                      "confidence": 1.0, "ttl_seconds": 3600.0, "raw_signal": None},
         "detail": ""},
        {"condition": "enterprise_policy_allowed", "verdict": "PASS", "reason": "OK",
         "criticality": "CRITICAL_GOV",
         "evidence": {"source": "config", "timestamp": 1_600_000_000.0,
                      "confidence": 1.0, "ttl_seconds": 1e12, "raw_signal": None},
         "detail": ""},
        {"condition": "latency_within_limit", "verdict": "PASS", "reason": "OK",
         "criticality": "OPERATIONAL",
         "evidence": {"source": "telemetry", "timestamp": 1_600_000_000.0,
                      "confidence": 1.0, "ttl_seconds": 900.0, "raw_signal": None},
         "detail": "500.0ms<= 60000.0"},
        {"condition": "reliability_within_limit", "verdict": "PASS", "reason": "OK",
         "criticality": "OPERATIONAL",
         "evidence": {"source": "telemetry", "timestamp": 1_600_000_000.0,
                      "confidence": 0.9, "ttl_seconds": 900.0,
                      "raw_signal": "provider reported 0.99"},
         "detail": "0.99>= 0.9"},
    ],
}


def _ev(ttl=900.0):
    return Evidence(EvidenceSource.TELEMETRY, NOW, 1.0, ttl_seconds=ttl)


def _candidate(quality=None) -> Candidate:
    signals = {
        "reachable": Signal(True, _ev()),
        "network_allowed": Signal(True, _ev()),
        "authenticated": Signal(True, _ev()),
        "credential_expiry_ts": Signal(NOW + 10_000, _ev()),
        "billing_active": Signal(True, _ev()),
        "quota_state": Signal("ok", _ev()),
        "model_available": Signal(True, _ev()),
        "observed_latency_ms": Signal(500.0, _ev()),
        "reliability": Signal(0.99, _ev()),
    }
    if quality is not None:
        signals["quality"] = Signal(quality, _ev())
    return Candidate(
        provider="anthropic", model_id="anthropic-model", family="claude", region="us",
        context_limit=200_000, structured_output=True, tool_use=True,
        price_in_per_mtok=3.0, price_out_per_mtok=15.0, signals=signals)


def _request(**kw) -> Request:
    defaults = {"context_tokens": 1_000, "est_output_tokens": 200}
    defaults.update(kw)
    return Request(request_id="r-1", **defaults)


# --- 1. historical v1 records remain readable and verifiable ------------------------

def test_a_stored_v1_record_is_readable():
    decision = EligibilityDecision.from_dict(STORED_V1_RECORD)

    assert decision.policy_version == POLICY_VERSION_V1
    assert decision.state is EligibilityState.ELIGIBLE
    assert decision.provider == "anthropic"
    assert [c.condition for c in decision.conditions] == [
        "provider_reachable", "enterprise_policy_allowed",
        "latency_within_limit", "reliability_within_limit"]


def test_a_stored_v1_record_round_trips_byte_identically():
    """Verifiable means the record that comes back out is the record that went in —
    including its own stamp. Reading a v1 decision must never re-stamp it as v2."""
    restored = EligibilityDecision.from_dict(STORED_V1_RECORD)

    assert restored.to_dict() == STORED_V1_RECORD
    assert json.dumps(restored.to_dict(), sort_keys=True) == \
        json.dumps(STORED_V1_RECORD, sort_keys=True)


def test_a_stored_v1_records_fingerprint_is_unchanged_by_the_bump():
    """The audit identity of a historical decision survives the version bump intact."""
    before = fingerprint(STORED_V1_RECORD)
    after = fingerprint(EligibilityDecision.from_dict(STORED_V1_RECORD).to_dict())

    assert before == after


def test_v1_evidence_detail_survives_replay():
    """Down to the raw provider string kept for audit and the per-condition detail."""
    restored = EligibilityDecision.from_dict(STORED_V1_RECORD)
    reliability = restored.conditions[3]

    assert reliability.evidence.raw_signal == "provider reported 0.99"
    assert reliability.evidence.confidence == 0.9
    assert reliability.detail == "0.99>= 0.9"


def test_a_v1_record_keeps_fifteen_style_shape_without_the_floor_condition():
    """A v1 record has no ``quality_within_floor``. That is not damage to repair — it is
    what a v1 decision was — and nothing here invents one."""
    restored = EligibilityDecision.from_dict(STORED_V1_RECORD)

    assert not any(c.condition == "quality_within_floor" for c in restored.conditions)


# --- 2. new evaluations identify themselves as v2 -----------------------------------

def test_a_new_decision_is_stamped_v2():
    decision = ExecutionGate(GateConfig()).evaluate(_candidate(), _request(), NOW)

    assert decision.policy_version == POLICY_VERSION_V2 == "exec_gate_v2"
    assert POLICY_VERSION == POLICY_VERSION_V2


def test_a_new_decision_is_stamped_v2_with_a_floor_configured_too():
    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(
        _candidate(quality=0.9), _request(), NOW)

    assert decision.policy_version == POLICY_VERSION_V2


def test_this_implementation_may_not_write_an_older_version():
    """The lie the bump exists to prevent: v2 code stamping a v1 record.

    Reading v1 is supported; *writing* it is not, because this code cannot reproduce v1
    semantics and so may not claim to be them.
    """
    with pytest.raises(ValueError, match="may not write"):
        GateConfig(policy_version=POLICY_VERSION_V1)


def test_the_supported_set_is_ordered_oldest_first_and_contains_both():
    assert SUPPORTED_POLICY_VERSIONS == (POLICY_VERSION_V1, POLICY_VERSION_V2)
    assert POLICY_VERSION in SUPPORTED_POLICY_VERSIONS


# --- 3. the configured quality floor is non-compensatory under v2 -------------------

def test_under_v2_a_configured_floor_disqualifies_and_cannot_be_outbid():
    weak = ModelRecord(internal_id="weak", candidate=_candidate(quality=0.2),
                       observed_latency_ms=1.0)
    gate = ExecutionGate(GateConfig(quality_floor=0.8))
    request = _request()

    decision = gate.evaluate(weak.candidate, request, NOW)
    assert decision.policy_version == POLICY_VERSION_V2
    assert decision.state is EligibilityState.INELIGIBLE
    assert ReasonCode.QUALITY_BELOW_FLOOR in decision.reasons

    # and no weight reaches it
    selection = select([(weak, decision)], request, lambda r: 1.0,
                       PolicyWeights(quality=10_000.0))
    assert selection.selected is None and selection.abstained


def test_under_v2_a_perfect_score_still_approves_no_provider():
    """The floor narrows only, at v2 exactly as it did when it was introduced."""
    candidate = _candidate(quality=1.0)
    candidate.provider = "unapproved-vendor"
    request = _request(approved_providers={"anthropic"})

    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(candidate, request, NOW)

    assert decision.state is EligibilityState.INELIGIBLE
    assert ReasonCode.PROVIDER_NOT_APPROVED in decision.reasons


# --- 4. an unconfigured floor adds no gate condition --------------------------------

def test_v2_without_a_floor_adds_no_condition():
    """v2 is an identity claim about the code, not about every record it writes.

    With no floor configured the condition list is what v1 produced. The record is still
    honestly stamped v2, because the *implementation* is v2 — it is the code that could
    have applied a floor, and a reader is entitled to know which code answered.
    """
    decision = ExecutionGate(GateConfig()).evaluate(_candidate(quality=0.01), _request(), NOW)

    assert not any(c.condition == "quality_within_floor" for c in decision.conditions)
    assert decision.state is EligibilityState.ELIGIBLE
    assert decision.policy_version == POLICY_VERSION_V2


def test_the_unfloored_v2_condition_list_matches_the_v1_algorithm():
    """Fifteen conditions, in the order v1 emitted them."""
    decision = ExecutionGate(GateConfig()).evaluate(_candidate(), _request(), NOW)

    assert [c.condition for c in decision.conditions] == [
        "provider_reachable", "network_policy_allowed", "authenticated",
        "credential_expiry_valid", "billing_active", "quota_available",
        "model_available", "region_allowed", "enterprise_policy_allowed",
        "data_residency_allowed", "required_features_supported",
        "context_length_sufficient", "projected_cost_within_limit",
        "latency_within_limit", "reliability_within_limit",
    ]
    assert len(decision.conditions) == 15


# --- 5. unsupported future versions fail closed -------------------------------------

@pytest.mark.parametrize("version", [
    "exec_gate_v3",          # a future release this build cannot know
    "exec_gate_v99",
    "exec_gate_v0",          # before the first version
    "EXEC_GATE_V1",          # case is not normalized away
    "exec_gate_v1 ",         # nor is whitespace
    "",
    None,
    123,
])
def test_replaying_an_unsupported_version_is_refused(version):
    record = dict(STORED_V1_RECORD, policy_version=version)

    with pytest.raises(UnsupportedPolicyVersionError) as raised:
        EligibilityDecision.from_dict(record)

    assert raised.value.policy_version == version


def test_a_missing_policy_version_is_refused_rather_than_defaulted():
    """Absence is not v1. Defaulting would silently attribute unknown semantics."""
    record = {k: v for k, v in STORED_V1_RECORD.items() if k != "policy_version"}

    with pytest.raises(UnsupportedPolicyVersionError):
        EligibilityDecision.from_dict(record)


def test_the_refusal_names_what_this_build_can_read():
    with pytest.raises(UnsupportedPolicyVersionError, match="exec_gate_v1.*exec_gate_v2"):
        EligibilityDecision.from_dict(dict(STORED_V1_RECORD, policy_version="exec_gate_v3"))


def test_a_v2_record_round_trips_as_well():
    """Replay is not a v1-only courtesy; the current version reads back too."""
    written = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(
        _candidate(quality=0.9), _request(), NOW).to_dict()

    assert EligibilityDecision.from_dict(written).to_dict() == written
