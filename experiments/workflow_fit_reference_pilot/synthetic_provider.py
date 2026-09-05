"""SYNTHETIC provider factory for the mechanism-validation fixture. No network, no
credentials, no model. Imported only by the boundary process through its single dynamic
import. Its output is a canned structured answer chosen by a substring table over the prompt;
it measures nothing about any reasoning method."""

from __future__ import annotations

import os

from ugence_reasoning_method_governance.api import TokenUsageSnapshot, UsageAvailabilityToken
from ugence_workflow_fit_pilot.api import ProviderResult

from .env import MODE_ENV

# Substring of the workflow-visible query -> canned answer. The expected document holds the
# same answers separately; this table is the synthetic "model", nothing more.
ANSWER_TABLE = (
    ("two plus two", "4"),
    ("capital of france", "paris"),
    ("boiling point of water in celsius", "100"),
)


class SyntheticProvider:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.n = 0

    def complete(self, prompt: str) -> ProviderResult:
        self.n += 1
        low = prompt.lower()
        if self.mode.startswith("raise:") and self.mode.split(":", 1)[1] in low:
            raise RuntimeError("synthetic provider failure")
        answer = next((a for needle, a in ANSWER_TABLE if needle in low), "unknown")
        text = f"Reasoning omitted.\nANSWER: {answer}"
        if self.mode == "no_usage":
            return ProviderResult(text=text, usage=None, usage_availability=UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED, provider_request_id=f"syn-{self.n}", provider_id="provider:synthetic")
        usage = TokenUsageSnapshot(input_tokens=len(prompt), output_tokens=len(text), total_tokens=len(prompt) + len(text))
        return ProviderResult(text=text, usage=usage, usage_availability=UsageAvailabilityToken.AVAILABLE, provider_request_id=f"syn-{self.n}", provider_id="provider:synthetic")


def make_provider() -> SyntheticProvider:
    return SyntheticProvider(os.environ.get(MODE_ENV, "ok"))


__all__ = ["ANSWER_TABLE", "MODE_ENV", "SyntheticProvider", "make_provider"]
