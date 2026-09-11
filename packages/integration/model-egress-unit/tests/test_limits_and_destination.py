"""LP-3 and LP-5, as code: the pinned snapshot, the one destination, the bound limits,
the non-compensatory budget. No database, no clock, no network."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from ugence_model_egress_unit import (
    COMMISSIONING_LIMITS,
    OPENAI_RESPONSES,
    BudgetExhausted,
    CallBudget,
    DesignatedDestination,
    DestinationRefused,
    EgressRequest,
    MinimizedUnit,
    RefusalReason,
    check_destination,
    check_request,
    is_pinned_snapshot,
    reference_clearance,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
TENANT = uuid.UUID("00000000-0000-4000-8000-000000000001")
PINNED = "gpt-5.4-mini-2026-03-17"


def _request(model=PINNED, tokens=(5,), **params) -> EgressRequest:
    parameters = {"max_output_tokens": 256}
    parameters.update(params)
    return EgressRequest.create(
        request_id=uuid.uuid5(uuid.NAMESPACE_URL, "r"), tenant_id=TENANT,
        correlation_id=uuid.uuid5(uuid.NAMESPACE_URL, "c"), submitted_at=NOW,
        not_valid_after=datetime(2026, 9, 11, 13, 0, tzinfo=timezone.utc),
        authorization=reference_clearance(tenant_id=TENANT, vendor="openai", model=model),
        minimized_context=tuple(MinimizedUnit(f"u{i}", "x", t) for i, t in enumerate(tokens)),
        parameters=parameters)


def test_the_limits_are_the_owners_numbers_and_are_constants():
    L = COMMISSIONING_LIMITS
    assert (L.max_input_tokens, L.max_output_tokens, L.max_genuine_calls, L.budget_usd_cents,
            L.concurrency, L.max_retries) == (8192, 1024, 10, 2500, 1, 1)
    assert L.streaming is False and L.store is False and L.tools is False and L.background is False
    assert L.retry_only_for == ("TRANSIENT_BEFORE_DISPATCH",)
    with pytest.raises(Exception):
        L.max_output_tokens = 4096  # frozen


@pytest.mark.parametrize("model, pinned", [
    (PINNED, True), ("gpt-5.4-mini", False), ("gpt-5.4-mini-latest", False),
    ("gpt-5.4-mini-2026-3-17", False), ("o-2026-03-17", True), ("", False), (None, False),
])
def test_only_a_dated_snapshot_is_pinned(model, pinned):
    assert is_pinned_snapshot(model) is pinned


def test_a_conforming_request_passes_and_each_limit_is_refused_by_name():
    assert check_request(_request()) is None
    cases = [
        (_request(model="gpt-5.4-mini"), RefusalReason.MODEL_NOT_PINNED),
        (_request(max_output_tokens=1025), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(max_output_tokens=0), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(max_output_tokens="256"), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(max_output_tokens=True), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(store=True), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(stream=True), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(background=True), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(tools=[{"type": "web_search"}]), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(tool_choice="auto"), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(previous_response_id="resp_1"), RefusalReason.REQUEST_LIMIT_EXCEEDED),
        (_request(tokens=(8000, 193)), RefusalReason.REQUEST_LIMIT_EXCEEDED),
    ]
    for request, reason in cases:
        violation = check_request(request)
        assert violation is not None and violation.reason is reason, request.parameters
    assert check_request(_request(tokens=(8000, 192), max_output_tokens=1024, store=False, stream=False,
                                  tools=[], tool_choice="none")) is None


def test_the_destination_is_exactly_one_https_url():
    assert OPENAI_RESPONSES.url == "https://api.openai.com/v1/responses"
    assert check_destination("https://api.openai.com/v1/responses") == "https://api.openai.com/v1/responses"
    assert check_destination("https://API.openai.com:443/v1/responses")
    for bad in ("http://api.openai.com/v1/responses", "https://api.openai.com/v1/chat/completions",
                "https://api.openai.com/v1/responses?stream=true", "https://api.openai.com/v1/responses#x",
                "https://evil.example/v1/responses", "https://api.openai.com.evil.example/v1/responses",
                "https://user@api.openai.com/v1/responses", "https://api.openai.com:8443/v1/responses",
                "https://api.openai.com/v1/responses/", "api.openai.com/v1/responses", 7):
        with pytest.raises(DestinationRefused) as excinfo:
            check_destination(bad)
        assert excinfo.value.reason is RefusalReason.DESTINATION_NOT_PERMITTED
    with pytest.raises(ValueError):
        DesignatedDestination(host="api.openai.com", path="/v1/responses", scheme="http")
    with pytest.raises(ValueError):
        DesignatedDestination(host="api.openai.com:443", path="/v1/responses")


def test_the_budget_is_reserved_before_dispatch_and_never_refunded():
    budget = CallBudget()
    budget.reserve(estimated_cents=200, now=NOW, request_id="r1")
    assert budget.as_record()["calls_reserved"] == 1 and budget.in_flight == 1
    with pytest.raises(BudgetExhausted, match="concurrency 1"):
        budget.reserve(estimated_cents=1, now=NOW, request_id="r2")
    budget.release_in_flight()
    budget.release_in_flight()  # idempotent at zero
    assert budget.in_flight == 0 and budget.calls_reserved == 1 and budget.cents_reserved == 200
    with pytest.raises(BudgetExhausted, match="exceed the 2500-cent budget"):
        budget.reserve(estimated_cents=2301, now=NOW, request_id="r3")
    for n in range(9):
        budget.reserve(estimated_cents=100, now=NOW, request_id=f"r{n + 4}")
        budget.release_in_flight()
    assert budget.calls_reserved == 10
    with pytest.raises(BudgetExhausted, match="10 genuine calls already reserved"):
        budget.reserve(estimated_cents=0, now=NOW, request_id="r99")
    with pytest.raises(BudgetExhausted):
        CallBudget().reserve(estimated_cents=-1, now=NOW, request_id="x")
    assert budget.may_retry(attempts_so_far=1, failure_class="TRANSIENT_BEFORE_DISPATCH") is True
    assert budget.may_retry(attempts_so_far=2, failure_class="TRANSIENT_BEFORE_DISPATCH") is False
    assert budget.may_retry(attempts_so_far=1, failure_class="TIMEOUT_AFTER_DISPATCH") is False
    assert all(r.reason for r in [BudgetExhausted("x")]) and BudgetExhausted("x").reason is RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED
