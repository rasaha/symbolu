"""Neutral test doubles for the token-accounting contract.

Self-contained fakes — none imports a model SDK, tokenizer, or product. They exercise
the neutral RequestTokenCounter contract exactly as a real provider adapter would.
"""

from __future__ import annotations

from ugence_context_minimization.api import (
    MinimizationMode,
    RequestComponents,
    RequestTokenEstimate,
    TokenCountBasis,
    minimize_context,
)

from support import KeywordOracle, context, unit


def sample_minimization_result(target=0.6):
    """A real MinimizationResult (oracle mode) carrying a genuine run_fingerprint."""
    ctx = context(
        [
            unit("crit", "deploy anchor credential", source_type="state_fact"),
            unit("f1", "filler one two three four", source_type="log_event"),
            unit("f2", "filler five six seven eight", source_type="log_event"),
            unit("f3", "filler nine ten eleven twelve", source_type="log_event"),
        ]
    )
    return minimize_context(ctx, oracle=KeywordOracle(), target_reduction=target, evaluation_time=1.0)


class ExactRequestCounter:
    """A counter that claims an EXACT, fully-covering count (as a real BPE adapter would)."""

    counter_id = "exact-bpe"
    counter_version = "9"

    def __init__(self, value: int, basis: TokenCountBasis = TokenCountBasis.INJECTED_COUNTER):
        self._value = value
        self._basis = basis

    def estimate_request(self, components: RequestComponents, *, model_id=None, provider_id=None):
        return RequestTokenEstimate(
            estimated_input_tokens=self._value,
            counter_id=self.counter_id,
            counter_version=self.counter_version,
            basis=self._basis,
            model_id=model_id,
            provider_id=provider_id,
            covers_tools=True,
            covers_schemas=True,
            covers_images=True,
            covers_non_text=True,
        )
