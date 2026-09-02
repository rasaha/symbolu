"""Caller-side provider factory for tests. Imported ONLY by the boundary process through
its single dynamic import; the pilot package never imports it. Deterministic, offline."""

from __future__ import annotations

import os

from ugence_reasoning_method_governance.api import TokenUsageSnapshot, UsageAvailabilityToken
from ugence_workflow_fit_pilot.api import ProviderResult


class StubProvider:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.n = 0

    def complete(self, prompt: str) -> ProviderResult:
        self.n += 1
        second = "call 2]" in prompt  # the FakeExecutor numbers each method's calls across cases; modes act on every method's second call
        if self.mode == "raise" and second:
            raise ValueError("simulated provider failure")
        usage = TokenUsageSnapshot(input_tokens=len(prompt), output_tokens=9, total_tokens=len(prompt) + 9)
        availability = UsageAvailabilityToken.AVAILABLE
        if self.mode == "no_usage_second" and second:
            usage, availability = None, UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED
        if self.mode == "partial_usage_second" and second:
            usage = TokenUsageSnapshot(total_tokens=len(prompt) + 9)
        return ProviderResult(text="ANSWER: deterministic stub response", usage=usage, usage_availability=availability, provider_request_id=f"stub-{self.n}", provider_id="provider:stub")


def make_provider():
    return StubProvider(os.environ.get("WFP_STUB_MODE", "ok"))


def not_a_provider():
    return object()
