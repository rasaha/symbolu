"""The runtime bridge: an AttemptObserver that records token-accounting, plus the
H22-D budget-settlement seam.

`RuntimeTokenAccountingBridge` implements the Agent Runtime's `AttemptObserver`
protocol. Registered pre-call measurements (`PreparedApiCall`) are keyed by
`(instance_id, task_id)`; each observed attempt is translated into an
`ApiCallTokenRecord` and pushed to a Context Minimization `TokenAccountingSink`.

Budget settlement is a **separate, explicit** step (`settle_budget_from_usage`) invoked
at the H22-D quantum settlement boundary — NOT per attempt — so a quantum's reservation
is settled exactly once. It uses **measured** token units when authoritative usage is
available and falls back to the existing **conservative full-reservation** settlement
otherwise; a measured overrun raises `BudgetEstimateExceeded` (never clamped/hidden).
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, Optional, Tuple

from ugence_agent_runtime.observability.attempts import ProviderAttempt
from ugence_agent_runtime.orchestration import (
    BudgetCoordinator,
    BudgetEstimateExceeded,
    BudgetSettlement,
)
from ugence_context_minimization.api import (
    ApiCallTokenRecord,
    LogicalRequestTokenSummary,
    PreparedApiCall,
    ProviderTokenUsage,
    TokenAccountingSink,
)

from .translation import UsageNormalizer, translate_attempt

#: The default budget dimension the settlement seam charges measured token usage against.
DEFAULT_TOKEN_DIMENSION = "token_units"


class RuntimeTokenAccountingBridge:
    """An `AttemptObserver` that records one `ApiCallTokenRecord` per observed attempt.

    Injected: the CM `sink`, an optional provider-specific `normalizer`, and an optional
    `logical_request_id_of` selector (defaults to the prepared measurement's id). An
    attempt with no registered pre-call measurement is skipped (no minimization link →
    no record) and counted in `skipped_attempts` so the gap is visible, never silently
    dropped as zero.
    """

    def __init__(
        self,
        sink: TokenAccountingSink,
        *,
        normalizer: Optional[UsageNormalizer] = None,
    ) -> None:
        self._sink = sink
        self._normalizer = normalizer
        self._prepared: Dict[Tuple[str, str], PreparedApiCall] = {}
        # F4: guard mutable diagnostics and the registry so concurrent attempts cannot lose
        # a skip increment or race the registry lookup.
        self._lock = threading.Lock()
        self._skipped_attempts: int = 0

    @property
    def skipped_attempts(self) -> int:
        """Count of observed attempts with no registered pre-call measurement (thread-safe)."""
        with self._lock:
            return self._skipped_attempts

    def register(self, prepared: PreparedApiCall, *, instance_id: str, task_id: str) -> None:
        """Link a pre-call measurement to the runtime identity its attempts will carry."""
        if not isinstance(prepared, PreparedApiCall):
            raise TypeError("prepared must be a PreparedApiCall")
        with self._lock:
            self._prepared[(instance_id, task_id)] = prepared

    def prepared_for(self, instance_id: str, task_id: str) -> Optional[PreparedApiCall]:
        with self._lock:
            return self._prepared.get((instance_id, task_id))

    # -- AttemptObserver ----------------------------------------------------
    def on_attempt(self, attempt: ProviderAttempt) -> Optional[ApiCallTokenRecord]:
        key = (attempt.instance_id or "", attempt.task_id or "")
        with self._lock:
            prepared = self._prepared.get(key)
            if prepared is None:
                self._skipped_attempts += 1  # atomic increment (no lost updates under F4)
                return None
        # Translation + sink write happen OUTSIDE the bridge lock: the sink has its own
        # lock (F4), and holding the bridge lock across a sink write would needlessly widen
        # the critical section. The prepared snapshot above is immutable.
        return translate_attempt(
            prepared, attempt, normalizer=self._normalizer, sink=self._sink
        )


def token_units_from_usage(usage: ProviderTokenUsage) -> Optional[float]:
    """The authoritative billable-token magnitude for budget settlement, or ``None``.

    Prefers the provider-reported ``total_tokens``; else the explicitly *derived*
    ``input + output`` total; else ``None`` (not enough is known to charge a measured
    amount — the caller must fall back to conservative settlement). Cached/reasoning
    details are never added in here (they are subsets/details, not extra billable units).
    """
    if usage.total_tokens is not None:
        return float(usage.total_tokens)
    derived = usage.derived_total()
    return float(derived) if derived is not None else None


def settle_budget_from_usage(
    coordinator: BudgetCoordinator,
    instance_id: str,
    usage: Optional[ProviderTokenUsage],
    *,
    dimension: str = DEFAULT_TOKEN_DIMENSION,
    token_units_of: Callable[[ProviderTokenUsage], Optional[float]] = token_units_from_usage,
) -> BudgetSettlement:
    """Settle one H22-D quantum's reservation using measured usage when authoritative.

    * With authoritative usage that yields a token-unit magnitude, settles the **measured**
      amount against ``dimension`` (``actual_known=True``). A measured value above the
      reservation raises :class:`BudgetEstimateExceeded` from the coordinator — surfaced,
      never clamped or hidden.
    * With no usage, or usage from which no magnitude can be derived, falls back to the
      existing **conservative full-reservation** settlement (``actual=None`` →
      ``actual_known=False``) — never under-charging.

    This is the ONLY place measured token units feed the budget; it must be called once,
    at the quantum settlement boundary, not per attempt.
    """
    if usage is None:
        return coordinator.settle(instance_id)  # conservative
    units = token_units_of(usage)
    if units is None:
        return coordinator.settle(instance_id)  # conservative — nothing measurable
    # Measured settlement (BudgetEstimateExceeded propagates on overrun — do not catch).
    return coordinator.settle(instance_id, {dimension: units})


def settle_budget_from_summary(
    coordinator: BudgetCoordinator,
    instance_id: str,
    summary: LogicalRequestTokenSummary,
    *,
    dimension: str = DEFAULT_TOKEN_DIMENSION,
) -> BudgetSettlement:
    """Settle from an aggregated logical-request summary.

    Charges the documented settlement selection (``summary.settlement_token_units`` —
    provider-reported total per attempt where present, else derived input+output) ONLY when
    the summary is **complete** (no unknown-usage attempts). An incomplete summary — any
    attempt whose usage is unavailable — falls back to conservative full-reservation
    settlement (F1 §6): a partial known sum is never settled as if it were the whole truth.

    Note ``settlement_token_units`` is deliberately used here rather than
    ``provider_reported_total_tokens`` (which, by contract, holds ONLY provider-reported
    values and would understate consumption whenever an attempt reported input/output but
    no explicit total).
    """
    if summary.complete and summary.settlement_token_units > 0:
        return coordinator.settle(instance_id, {dimension: float(summary.settlement_token_units)})
    return coordinator.settle(instance_id)


__all__ = [
    "RuntimeTokenAccountingBridge",
    "settle_budget_from_usage",
    "settle_budget_from_summary",
    "token_units_from_usage",
    "BudgetEstimateExceeded",
    "DEFAULT_TOKEN_DIMENSION",
]
