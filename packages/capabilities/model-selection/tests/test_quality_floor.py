"""The hard, non-compensatory capability floor, and the boundary it may not cross.

The capability prior was a soft term only: ``PolicyWeights.quality`` multiplies it and
adds it to a utility, where a cheap, fast, weak model can out-score a strong one. That is
correct for a preference and wrong for a floor. These tests pin the floor's three
properties: it is off unless configured, it cannot be outbid, and it narrows only.

The last is the one worth stating twice. A quality floor that could *qualify* a candidate
would be this capability approving a provider, which it may not do.
"""

from __future__ import annotations

import math

import pytest

from ugence_model_selection.api import (
    Candidate,
    EligibilityState,
    Evidence,
    EvidenceSource,
    ExecutionGate,
    GateConfig,
    ModelRecord,
    PolicyWeights,
    ReasonCode,
    Request,
    Signal,
    select,
)

NOW = 1_000_000.0


def _evidence(now: float = NOW, ttl: float = 900.0, source=EvidenceSource.PROVIDER_DECLARED):
    return Evidence(source, now, 1.0, ttl_seconds=ttl)


def _healthy_signals(quality=None, quality_evidence=None) -> dict:
    """Every operational signal passing, so only the condition under test can fail."""
    signals = {
        "reachable": Signal(True, _evidence()),
        "network_allowed": Signal(True, _evidence()),
        "authenticated": Signal(True, _evidence()),
        "credential_expiry_ts": Signal(NOW + 10_000, _evidence()),
        "billing_active": Signal(True, _evidence()),
        "quota_state": Signal("ok", _evidence()),
        "model_available": Signal(True, _evidence()),
        "observed_latency_ms": Signal(100.0, _evidence()),
        "reliability": Signal(0.99, _evidence()),
    }
    if quality is not None:
        signals["quality"] = Signal(quality, quality_evidence or _evidence())
    return signals


def _candidate(provider="anthropic", model_id="m-1", quality=None, quality_evidence=None,
               **kw) -> Candidate:
    return Candidate(
        provider=provider, model_id=model_id, family="f", region="us",
        context_limit=100_000, structured_output=True, tool_use=True,
        price_in_per_mtok=1.0, price_out_per_mtok=1.0,
        signals=_healthy_signals(quality, quality_evidence), **kw)


def _request(**kw) -> Request:
    defaults = {"context_tokens": 100, "est_output_tokens": 10}
    defaults.update(kw)
    return Request(request_id="r-1", **defaults)


def _condition(decision, name):
    return next((c for c in decision.conditions if c.condition == name), None)


# --- off unless configured ---------------------------------------------------------

def test_no_floor_configured_evaluates_no_quality_condition_at_all():
    """Not 'evaluated and passed' — not evaluated.

    A condition that always passes would still append a ConditionResult and change every
    serialized decision, breaking replay of records written before the floor existed.
    """
    decision = ExecutionGate(GateConfig()).evaluate(_candidate(quality=0.01), _request(), NOW)

    assert _condition(decision, "quality_within_floor") is None
    assert decision.state is EligibilityState.ELIGIBLE


def test_a_configured_floor_is_the_only_thing_that_adds_the_condition():
    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(
        _candidate(quality=0.9), _request(), NOW)

    condition = _condition(decision, "quality_within_floor")
    assert condition is not None and condition.reason is ReasonCode.OK
    assert decision.state is EligibilityState.ELIGIBLE


@pytest.mark.parametrize("floor", [-0.01, 1.01, float("nan")])
def test_a_floor_outside_the_unit_interval_is_refused(floor):
    with pytest.raises(ValueError):
        GateConfig(quality_floor=floor)


@pytest.mark.parametrize("floor", [True, False, "0.5", object()])
def test_a_floor_that_is_not_a_real_number_is_refused(floor):
    """``True`` would otherwise configure a floor of 1.0 that nobody wrote."""
    with pytest.raises(TypeError):
        GateConfig(quality_floor=floor)


# --- the floor disqualifies, and cannot be outbid ----------------------------------

def test_quality_below_the_floor_is_ineligible():
    decision = ExecutionGate(GateConfig(quality_floor=0.7)).evaluate(
        _candidate(quality=0.69), _request(), NOW)

    assert decision.state is EligibilityState.INELIGIBLE
    assert ReasonCode.QUALITY_BELOW_FLOOR in decision.reasons


def test_quality_exactly_at_the_floor_passes():
    """The floor is a minimum, not a strict inequality."""
    decision = ExecutionGate(GateConfig(quality_floor=0.7)).evaluate(
        _candidate(quality=0.7), _request(), NOW)

    assert decision.state is EligibilityState.ELIGIBLE


@pytest.mark.parametrize("quality, detail", [
    (None, "missing"),
    (float("nan"), "NaN"),
    ("high", "non-numeric"),
    (True, "bool"),
    (1.5, "outside [0, 1]"),
])
def test_unusable_quality_evidence_against_a_configured_floor_fails_closed(quality, detail):
    """A floor whose input is unknown must disqualify, or it is not a floor.

    Note what is *not* done: an unusable prior is never read as 0.0. That would be an
    inference the caller never made. It is UNKNOWN, and UNKNOWN against a configured
    floor is fail-closed.
    """
    candidate = _candidate(quality=quality) if quality is not None else _candidate()
    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(candidate, _request(), NOW)

    assert decision.state is EligibilityState.INELIGIBLE, detail


def test_stale_quality_evidence_fails_closed_and_says_so():
    stale = Evidence(EvidenceSource.TELEMETRY, NOW - 5_000, 1.0, ttl_seconds=60.0)
    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(
        _candidate(quality=0.99, quality_evidence=stale), _request(), NOW)

    assert decision.state is EligibilityState.INELIGIBLE
    assert ReasonCode.TELEMETRY_STALE in decision.reasons


def test_a_cheap_fast_low_quality_model_cannot_outbid_the_floor():
    """The property the floor exists for, exercised through ranking rather than asserted.

    The weak candidate is free and instant, so under ``PolicyWeights`` alone it wins on
    utility. With the floor configured it is not merely out-ranked — it never reaches
    ranking at all.
    """
    # The gap is deliberately modest (0.30 vs 0.55). With the default weights the price
    # and latency terms can subtract up to 0.85, so a free, instant, mediocre model beats
    # a costly, slow, better one — which is the realistic version of this failure, not a
    # contrived one. A wider quality gap would let the soft term win on its own and prove
    # nothing about the floor.
    weak = ModelRecord(internal_id="weak",
                       candidate=_candidate(model_id="weak", quality=0.30),
                       observed_latency_ms=1.0)
    weak.candidate.price_in_per_mtok = 0.0
    weak.candidate.price_out_per_mtok = 0.0
    strong = ModelRecord(internal_id="strong",
                         candidate=_candidate(model_id="strong", quality=0.55),
                         observed_latency_ms=5_000.0)
    strong.candidate.price_in_per_mtok = 50.0
    strong.candidate.price_out_per_mtok = 50.0

    request = _request()
    quality_of = {"weak": 0.30, "strong": 0.55}

    unfloored = ExecutionGate(GateConfig())
    pairs = [(r, unfloored.evaluate(r.candidate, request, NOW)) for r in (weak, strong)]
    # Without a floor the weak model wins on price and latency: that is the soft term
    # behaving exactly as designed, and exactly why a floor cannot be built from it.
    assert select(pairs, request, lambda r: quality_of[r.internal_id],
                  PolicyWeights()).selected.internal_id == "weak"

    floored = ExecutionGate(GateConfig(quality_floor=0.5))
    pairs = [(r, floored.evaluate(r.candidate, request, NOW)) for r in (weak, strong)]
    selection = select(pairs, request, lambda r: quality_of[r.internal_id], PolicyWeights())

    assert selection.selected.internal_id == "strong"
    assert [record.internal_id for record, _ in selection.ranked] == ["strong"], \
        "the disqualified candidate must not even appear in the ranking"


def test_an_enormous_quality_weight_still_cannot_rescue_a_floored_candidate():
    """Non-compensatory means non-compensatory: the weight is not a second chance."""
    weak = ModelRecord(internal_id="weak", candidate=_candidate(model_id="weak", quality=0.1))
    gate = ExecutionGate(GateConfig(quality_floor=0.9))
    request = _request()

    selection = select([(weak, gate.evaluate(weak.candidate, request, NOW))],
                       request, lambda r: 1.0, PolicyWeights(quality=10_000.0))

    assert selection.selected is None and selection.abstained


def test_downgrading_the_floor_to_indeterminate_still_never_selects():
    """Even a caller who moves the condition into ``indeterminate_on_unknown``.

    INDETERMINATE is not selectable either, so the escape hatch that exists for billing
    and credential expiry does not become one for the floor.
    """
    config = GateConfig(quality_floor=0.5,
                        indeterminate_on_unknown={"quality_within_floor"})
    decision = ExecutionGate(config).evaluate(_candidate(), _request(), NOW)

    assert decision.state is EligibilityState.INDETERMINATE
    assert not decision.selectable


# --- the boundary: narrowing only --------------------------------------------------

def test_a_perfect_quality_score_cannot_approve_an_unapproved_provider():
    """The floor may not override enterprise policy. CRITICAL_GOV outranks everything."""
    candidate = _candidate(provider="unapproved-vendor", quality=1.0)
    request = _request(approved_providers={"anthropic"})

    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(candidate, request, NOW)

    assert decision.state is EligibilityState.INELIGIBLE
    assert ReasonCode.PROVIDER_NOT_APPROVED in decision.reasons


@pytest.mark.parametrize("request_kwargs, expected", [
    ({"residency_required": "eu"}, ReasonCode.DATA_RESIDENCY_VIOLATION),
    ({"region_allowed": {"eu"}}, ReasonCode.REGION_UNAVAILABLE),
    ({"context_tokens": 10 ** 9}, ReasonCode.CONTEXT_TOO_SMALL),
    ({"cost_cap_usd": 0.0}, ReasonCode.COST_LIMIT_EXCEEDED),
])
def test_a_perfect_quality_score_rescues_no_other_failing_condition(request_kwargs, expected):
    candidate = _candidate(quality=1.0)
    request = _request(**request_kwargs)

    decision = ExecutionGate(GateConfig(quality_floor=0.5)).evaluate(candidate, request, NOW)

    assert decision.state is EligibilityState.INELIGIBLE
    assert expected in decision.reasons


def test_the_floor_only_ever_removes_candidates_from_the_eligible_set():
    """Stated as the general property rather than a case: across a spread of priors, the
    floored eligible set is always a subset of the unfloored one."""
    request = _request()
    candidates = [_candidate(model_id=f"m-{i}", quality=i / 10.0) for i in range(11)]

    unfloored = ExecutionGate(GateConfig())
    floored = ExecutionGate(GateConfig(quality_floor=0.6))

    before = {c.model_id for c in candidates
              if unfloored.evaluate(c, request, NOW).selectable}
    after = {c.model_id for c in candidates
             if floored.evaluate(c, request, NOW).selectable}

    assert after < before, "the floor must remove candidates, and add none"
    assert after == {f"m-{i}" for i in range(6, 11)}


def test_the_floor_adds_no_new_selection_behaviour_for_survivors():
    """Among candidates the floor admits, ranking is byte-identical to the unfloored run."""
    request = _request()
    records = [ModelRecord(internal_id=f"m-{i}",
                           candidate=_candidate(model_id=f"m-{i}", quality=0.7 + i / 100.0),
                           observed_latency_ms=100.0 * (i + 1))
               for i in range(5)]
    quality_of = lambda r: 0.7 + int(r.internal_id.split("-")[1]) / 100.0  # noqa: E731

    unfloored = ExecutionGate(GateConfig())
    floored = ExecutionGate(GateConfig(quality_floor=0.5))   # admits all five

    a = select([(r, unfloored.evaluate(r.candidate, request, NOW)) for r in records],
               request, quality_of)
    b = select([(r, floored.evaluate(r.candidate, request, NOW)) for r in records],
               request, quality_of)

    assert [(r.internal_id, s) for r, s in a.ranked] == [(r.internal_id, s) for r, s in b.ranked]
    assert a.selected.internal_id == b.selected.internal_id
