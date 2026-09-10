"""Worker-side reconciliation, and what an expired lease may and may not do.

The rule, and why it is not one rule
------------------------------------
What an expiry permits depends entirely on whether dispatch may have occurred:

* **Before dispatch** the request becomes claimable again. No call was made, so
  nothing is at risk in serving it.
* **After possible dispatch** — nothing. The request becomes ``OUTCOME_UNKNOWN``,
  terminal. It does not return to ``PENDING``, and its authorization and clearance
  are spent.

The second case is the one worth being careful about. The unit may have crashed
before dispatching, after dispatching, or after the vendor answered but before the
write landed, and **from the exchange's side these are indistinguishable**. The
difference between them is the difference between "nothing happened" and "it
happened and you don't know what it said". Returning such a request to the queue
picks the first reading and acts on it — a duplicated billed inference for a
request the requester asked to make once.

So the reconciler is conservative exactly where it cannot know, and only there.
Some requests that did reach the vendor but were never dispatched-marked would be
re-served; that is why the marker is written *before* the call rather than after.

**The reservation is never released.** A request reaching ``OUTCOME_UNKNOWN`` after
possible dispatch is conservatively counted as consumed until an independently
authorized reconciliation proves otherwise. Neither lease expiry nor content
purging releases the vendor allocation — releasing capacity on an ambiguous outcome
would reintroduce at the quota layer precisely the duplicate billed inference this
exists to prevent: the reservation would come back while the vendor's invoice did
not.

**A refusal or an unknown outcome must resume the workflow.** An unknown outcome is
still an outcome: it is written back through the exchange, the driver observes it
like any other, and the workflow advances on it. A request whose provider outcome
is unknown must not become a workflow parked forever — which is the line an
implementation is most likely to drop.

A fresh authorized call after an ``OUTCOME_UNKNOWN`` is a **new request linked to
the uncertain original**, never a retry of it. Calling it a retry would imply the
first one did not happen, which is precisely what nobody knows.

The scheduler is a pure function of the clock it is handed: no ``now()`` anywhere,
so a test can expire a lease without waiting and the sweep is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Sequence
from uuid import UUID

from .errors import RequestNotClaimable
from .records import DispatchAttempt, EgressResult, RequestState

if TYPE_CHECKING:  # the annotation only; importing it would drag in psycopg
    from .postgres.exchange import Exchange

__all__ = ["ReconciliationPass", "ReconciliationScheduler"]


@dataclass(frozen=True)
class ReconciliationPass:
    """What one sweep did, by disposition."""

    expired: Sequence[UUID]
    #: Undispatched, returned to the queue.
    requeued: Sequence[UUID]
    #: Possibly dispatched, closed as terminal ``OUTCOME_UNKNOWN``.
    reconciled: Sequence[UUID]
    #: Already terminal by the time the write ran; left alone.
    skipped: Sequence[UUID]

    @property
    def count(self) -> int:
        return len(self.reconciled) + len(self.requeued)


class ReconciliationScheduler:
    """Sweeps expired leases, by whether dispatch may have occurred."""

    def __init__(self, exchange: "Exchange", *,
                 reconciler_id: str = "meu-reconciler") -> None:
        self._exchange = exchange
        self._reconciler_id = reconciler_id

    def sweep(self, tenant_id: UUID, *, now: datetime) -> ReconciliationPass:
        """Expire every lease that has run out, once.

        A request whose result landed between the read and the write is skipped
        rather than overwritten: ``record_result`` is told to expect ``LEASED``, so
        a request that has since become terminal raises and is counted as skipped.
        Overwriting there would replace a known outcome with an unknown one —
        losing information to a race, which is the one thing this sweep must never
        do.
        """

        expired = self._exchange.expired_leases(tenant_id, now=now)
        requeued: list = []
        reconciled: list = []
        skipped: list = []

        for request_id, _holder, dispatched_at in expired:
            if dispatched_at is None:
                # Undispatched: no call was made, so the request may be served.
                # The exchange re-checks ``dispatched_at IS NULL`` inside its own
                # UPDATE, so a marker landing in between cannot be undone here.
                if self._exchange.release_undispatched_lease(tenant_id, request_id):
                    requeued.append(request_id)
                else:
                    skipped.append(request_id)
                continue

            attempt = DispatchAttempt(
                adapter_id=self._reconciler_id,
                dispatch_observed_at=dispatched_at,
                detected_at=now,
                reason="lease expired after dispatch may have occurred",
            )
            result = EgressResult.outcome_unknown(
                request_id=request_id,
                tenant_id=tenant_id,
                correlation_id=self._correlation_for(tenant_id, request_id),
                recorded_at=now,
                attempt=attempt,
            )
            try:
                self._exchange.record_result(
                    result, expect_states=(RequestState.LEASED,))
            except RequestNotClaimable:
                skipped.append(request_id)
            else:
                reconciled.append(request_id)

        return ReconciliationPass(
            expired=[r for r, _, _ in expired],
            requeued=requeued,
            reconciled=reconciled,
            skipped=skipped,
        )

    def _correlation_for(self, tenant_id: UUID, request_id: UUID) -> UUID:
        """The request's own correlation id, never a fresh one.

        The result's identity derives from the request rather than from whoever
        produced it, so an ``OUTCOME_UNKNOWN`` written by the reconciler ties to
        the same audit trail as the request it closes.
        """

        row = self._exchange.read_request(tenant_id, request_id)
        if row is None:
            raise RequestNotClaimable(
                f"request {request_id} vanished between the sweep's read and its "
                f"write; it cannot be correlated")
        return row["correlation_id"]
