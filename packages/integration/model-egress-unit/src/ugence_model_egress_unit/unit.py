"""The unit's work loop: claim one request, call the provider, record the result.

One request per call, by design. A loop that drained the queue inside one call
would hold a lease on work it had not started while the caller had no way to
stop it. ``run_once`` returns what it did, and the deployment decides whether to
call it again — which also makes the loop trivially testable without a scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from .records import EgressResult, RequestState, ResultOutcome

if TYPE_CHECKING:  # the annotation only; importing it would drag in psycopg
    from .postgres.exchange import Exchange

__all__ = ["UnitPass", "EgressUnit"]


@dataclass(frozen=True)
class UnitPass:
    """What one pass of the unit did. ``request_id`` is ``None`` when idle."""

    request_id: Optional[UUID]
    outcome: Optional[ResultOutcome]
    response_digest: Optional[str]

    @property
    def did_work(self) -> bool:
        return self.request_id is not None


class EgressUnit:
    """Drives one tenant's queue through a provider.

    ``production`` is threaded to the provider rather than consulted here, so the
    refusal is the provider's own — the unit does not decide on a provider's
    behalf whether it is fit to serve.
    """

    def __init__(
        self,
        exchange: "Exchange",
        provider,
        *,
        holder: str,
        lease: timedelta = timedelta(minutes=5),
        production: bool = False,
    ) -> None:
        self._exchange = exchange
        self._provider = provider
        self._holder = holder
        self._lease = lease
        self._production = production

    def _provider_will_dispatch(self, request, now: datetime) -> bool:
        """Whether the adapter would actually reach a provider for this request.

        An adapter that refuses on its pre-flight never dispatches, so marking it
        would strand a refusable request in ``OUTCOME_UNKNOWN`` on the next lease
        expiry. Adapters that expose no pre-flight are assumed to dispatch: the
        conservative answer is the safe one.
        """

        refusal = getattr(self._provider, "_refusal", None)
        if refusal is None:
            return True
        return refusal(request, now) is None

    def run_once(self, tenant_id: UUID, *, now: datetime) -> UnitPass:
        """Claim at most one request, serve it, and record the outcome."""

        claimed = self._exchange.claim(
            tenant_id, holder=self._holder, now=now, lease=self._lease)
        if claimed is None:
            return UnitPass(request_id=None, outcome=None, response_digest=None)

        # Dispatch is marked BEFORE the adapter is called, never after. A crash
        # between the marker and the call leaves the row looking dispatched, which
        # is the conservative reading; a marker written afterwards would be missing
        # in exactly the case it exists for. Only refusals decided before dispatch
        # skip it — and those are decided by the adapter, which is why the marker
        # is written by the adapter's own pre-flight rather than here.
        if self._provider_will_dispatch(claimed.request, now):
            self._exchange.mark_dispatched(
                tenant_id, claimed.request.request_id, at=now)

        result = self._provider.execute(
            claimed.request, now=now, production=self._production)
        digest = self._exchange.record_result(
            result, expect_states=(RequestState.LEASED,))
        return UnitPass(
            request_id=claimed.request.request_id,
            outcome=result.outcome,
            response_digest=digest,
        )
