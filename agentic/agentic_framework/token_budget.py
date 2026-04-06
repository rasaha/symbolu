"""
Token / Cost Budget Tracking (R9)

Lightweight token accounting and optional per-run budget enforcement
layered on top of the existing event + tracing backbone.

Accounting modes:
- **exact** — adapter provides real token counts via ``get_last_usage()``.
- **estimated** — fallback heuristic (``len(text) / 4``) when adapter
  does not report usage.
- **none** — no usage data available.

Usage::

    from agentic.agentic_framework.token_budget import BudgetPolicy, UsageStats

    policy = BudgetPolicy(max_total_tokens=4000, max_cost=0.05)
    for event in agent.run_stream("Hello", budget_policy=policy):
        ...

    # Or inspect after the run:
    trace = collector.build_trace()
    print(trace.total_tokens, trace.estimated_cost)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Token estimation fallback
# ---------------------------------------------------------------------------

# Rough chars-per-token ratio.  GPT / Claude / Mistral all hover around
# 3.5-4.5 chars/token for English text.  We use 4 as a simple default.
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count from plain text using a simple heuristic.

    This is explicitly an *estimate* — not a tokenizer-specific count.
    """
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Usage stats model
# ---------------------------------------------------------------------------


@dataclass
class UsageStats:
    """Mutable accumulator for token / cost metadata.

    Fields marked ``_exact`` indicate whether the corresponding value
    came from the adapter (``True``) or from the fallback estimator
    (``False``).
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    model: str = ""
    accounting_mode: str = "none"  # exact | estimated | mixed | none

    # Internal flags — not serialised
    _input_exact: bool = field(default=False, repr=False)
    _output_exact: bool = field(default=False, repr=False)

    # ----- mutation helpers -----

    def record_generation(
        self,
        prompt_text: str,
        output_text: str,
        *,
        exact_input: Optional[int] = None,
        exact_output: Optional[int] = None,
        cost: Optional[float] = None,
        model: Optional[str] = None,
    ) -> None:
        """Record one generation (prompt + completion).

        When ``exact_input`` / ``exact_output`` are supplied they are used
        directly and ``accounting_mode`` reflects ``exact``.  Otherwise
        the values are estimated from text length.
        """
        if exact_input is not None:
            self.input_tokens += exact_input
            self._input_exact = True
        else:
            self.input_tokens += estimate_tokens(prompt_text)

        if exact_output is not None:
            self.output_tokens += exact_output
            self._output_exact = True
        else:
            self.output_tokens += estimate_tokens(output_text)

        self.total_tokens = self.input_tokens + self.output_tokens

        if cost is not None:
            self.estimated_cost += cost

        if model:
            self.model = model

        # Derive accounting mode
        if self._input_exact and self._output_exact:
            self.accounting_mode = "exact"
        elif self._input_exact or self._output_exact:
            self.accounting_mode = "mixed"
        elif self.total_tokens > 0:
            self.accounting_mode = "estimated"
        else:
            self.accounting_mode = "none"

    # ----- serialisation -----

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe dict (excludes internal flags)."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "model": self.model,
            "accounting_mode": self.accounting_mode,
        }


# ---------------------------------------------------------------------------
# Budget policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BudgetPolicy:
    """Optional per-run budget limits.

    Set any limit to ``None`` (the default) to leave it unconstrained.

    Args:
        max_total_tokens: Hard cap on cumulative total tokens.
        max_input_tokens: Hard cap on cumulative input/prompt tokens.
        max_output_tokens: Hard cap on cumulative output tokens.
        max_cost: Hard cap on cumulative estimated cost.
    """

    max_total_tokens: Optional[int] = None
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    max_cost: Optional[float] = None

    def is_exceeded(self, usage: UsageStats) -> Optional[str]:
        """Return a human-readable reason if *usage* exceeds this policy,
        or ``None`` if within budget.
        """
        if self.max_total_tokens is not None and usage.total_tokens > self.max_total_tokens:
            return (
                f"Total tokens {usage.total_tokens} exceed budget "
                f"{self.max_total_tokens}"
            )
        if self.max_input_tokens is not None and usage.input_tokens > self.max_input_tokens:
            return (
                f"Input tokens {usage.input_tokens} exceed budget "
                f"{self.max_input_tokens}"
            )
        if self.max_output_tokens is not None and usage.output_tokens > self.max_output_tokens:
            return (
                f"Output tokens {usage.output_tokens} exceed budget "
                f"{self.max_output_tokens}"
            )
        if self.max_cost is not None and usage.estimated_cost > self.max_cost:
            return (
                f"Estimated cost {usage.estimated_cost:.6f} exceeds budget "
                f"{self.max_cost:.6f}"
            )
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
