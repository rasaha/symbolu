"""LP-5: the commissioning limits, bound into every request and enforced without
compensation, before dispatch, by the unit and never by the model adapter.

The numbers are the owner's (``ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md``, LP-5,
2026-09-11) and are constants here on purpose: a limit an adapter could raise is not a
limit. ``CallBudget`` is the in-memory, non-compensatory guard for the commissioning
scope; its durable twin in the exchange (a reservation row the database refuses to
exceed) is recorded as unbuilt in the specification and is not this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from .records import EgressRequest, RefusalReason

__all__ = [
    "CommissioningLimits",
    "COMMISSIONING_LIMITS",
    "FORBIDDEN_REQUEST_FEATURES",
    "LimitViolation",
    "is_pinned_snapshot",
    "check_request",
    "CallBudget",
    "BudgetExhausted",
]


@dataclass(frozen=True)
class CommissioningLimits:
    max_input_tokens: int = 8_192
    max_output_tokens: int = 1_024
    max_genuine_calls: int = 10
    budget_usd_cents: int = 2_500
    concurrency: int = 1
    max_retries: int = 1
    #: The only failure class a retry is permitted for: one where dispatch is *known*
    #: not to have happened. After a possible dispatch the outcome is unknown and the
    #: specification (§3.5) forbids a second billed call.
    retry_only_for: Tuple[str, ...] = ("TRANSIENT_BEFORE_DISPATCH",)
    streaming: bool = False
    store: bool = False
    tools: bool = False
    background: bool = False


COMMISSIONING_LIMITS = CommissioningLimits()

#: Request parameters that, if present and truthy or non-empty, are refused outright
#: (LP-3: no provider-hosted tools, web search, file retrieval, MCP, code execution or
#: background execution; LP-5: no streaming).
FORBIDDEN_REQUEST_FEATURES = ("stream", "background", "tools", "tool_choice", "web_search",
                              "file_search", "mcp_servers", "code_interpreter", "previous_response_id")


class LimitViolation(ValueError):
    """A request outside the commissioning limits. Terminal for that request."""

    def __init__(self, reason: RefusalReason, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason


def is_pinned_snapshot(model: str) -> bool:
    """LP-3: a model identifier is pinned when it ends in a full ``-YYYY-MM-DD`` date.
    A floating alias (``gpt-5.4-mini``) never does."""

    if not isinstance(model, str) or len(model) < 12:
        return False
    tail = model[-11:]
    if tail[0] != "-":
        return False
    date = tail[1:]
    return (len(date) == 10 and date[4] == "-" and date[7] == "-"
            and date[:4].isdigit() and date[5:7].isdigit() and date[8:].isdigit())


def _int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def check_request(request: EgressRequest,
                  limits: CommissioningLimits = COMMISSIONING_LIMITS) -> Optional[LimitViolation]:
    """The first limit this request breaks, or ``None``. Pure; reads no clock."""

    params: Mapping[str, Any] = request.parameters
    if not is_pinned_snapshot(request.authorization.authorized_model):
        return LimitViolation(RefusalReason.MODEL_NOT_PINNED,
                              "the authorized model is not a dated snapshot (LP-3)")
    out = _int(params.get("max_output_tokens"))
    if out is None or out < 1 or out > limits.max_output_tokens:
        return LimitViolation(RefusalReason.REQUEST_LIMIT_EXCEEDED,
                              f"max_output_tokens must be an integer in 1..{limits.max_output_tokens}")
    if params.get("store", False) is not False:
        return LimitViolation(RefusalReason.REQUEST_LIMIT_EXCEEDED, "store must be false (LP-3)")
    for feature in FORBIDDEN_REQUEST_FEATURES:
        value = params.get(feature)
        if value not in (None, False, [], {}, "", "none"):
            return LimitViolation(RefusalReason.REQUEST_LIMIT_EXCEEDED,
                                  f"{feature} is not permitted in the commissioning scope")
    tokens = sum(u.token_count for u in (request.minimized_context or ()))
    if tokens > limits.max_input_tokens:
        return LimitViolation(RefusalReason.REQUEST_LIMIT_EXCEEDED,
                              f"{tokens} input tokens exceed {limits.max_input_tokens}")
    return None


class BudgetExhausted(RuntimeError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"{RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED.value}: {detail}")
        self.reason = RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED


@dataclass
class CallBudget:
    """Non-compensatory: a call counted is never uncounted, cost reserved is never
    refunded, and a reservation is taken *before* dispatch. Concurrency is the one
    thing released, when the in-flight call ends, whatever its outcome."""

    limits: CommissioningLimits = COMMISSIONING_LIMITS
    calls_reserved: int = 0
    cents_reserved: int = 0
    in_flight: int = 0
    history: list = field(default_factory=list)

    def reserve(self, *, estimated_cents: int, now: datetime, request_id: str) -> None:
        if not isinstance(estimated_cents, int) or estimated_cents < 0:
            raise BudgetExhausted("an estimate must be a non-negative integer of cents")
        if self.in_flight >= self.limits.concurrency:
            raise BudgetExhausted(f"concurrency {self.limits.concurrency} already in use")
        if self.calls_reserved >= self.limits.max_genuine_calls:
            raise BudgetExhausted(f"{self.limits.max_genuine_calls} genuine calls already reserved")
        if self.cents_reserved + estimated_cents > self.limits.budget_usd_cents:
            raise BudgetExhausted(
                f"reserving {estimated_cents} cents would exceed the {self.limits.budget_usd_cents}-cent budget")
        self.calls_reserved += 1
        self.cents_reserved += estimated_cents
        self.in_flight += 1
        self.history.append({"request_id": request_id, "at": now.isoformat(),
                             "estimated_cents": estimated_cents, "call_number": self.calls_reserved})

    def release_in_flight(self) -> None:
        """The call ended, in any outcome. Nothing else is given back."""

        if self.in_flight > 0:
            self.in_flight -= 1

    def may_retry(self, *, attempts_so_far: int, failure_class: str) -> bool:
        """LP-5: at most one retry, and only for a failure known to precede dispatch."""

        return (attempts_so_far <= self.limits.max_retries
                and failure_class in self.limits.retry_only_for)

    def as_record(self) -> dict:
        return {
            "calls_reserved": self.calls_reserved, "cents_reserved": self.cents_reserved,
            "in_flight": self.in_flight, "max_genuine_calls": self.limits.max_genuine_calls,
            "budget_usd_cents": self.limits.budget_usd_cents,
        }
