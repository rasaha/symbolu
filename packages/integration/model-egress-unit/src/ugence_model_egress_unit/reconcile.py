"""Worker-side reconciliation: expired leases become ``OUTCOME_UNKNOWN``.

The rule, and why it is not a retry
-----------------------------------
A lease expires when a unit claimed a request and did not record a result before
the deadline. The unit may have crashed before dispatching, after dispatching, or
after the vendor answered but before the write landed. **From the exchange's
side these are indistinguishable**, and the difference between them is the
difference between "nothing happened" and "it happened and you don't know what
it said".

Returning the request to ``PENDING`` would pick the first reading and act on it.
When the second is true, that is a second dispatch of an exchange that already
happened — a duplicated side effect, and a second charge, for a request the
requester asked to make once. So the reconciler does the opposite: it moves the
request to a **terminal** ``OUTCOME_UNKNOWN`` and records a result saying so.

This is a deliberate trade. Some requests that never reached a vendor will be
recorded as unknown and will need a human to re-submit them. That is recoverable.
A duplicated exchange is not.

The scheduler is a pure function of the clock it is handed. There is no
``datetime.now()`` in this module: a caller passes ``now``, so a test can expire
a lease without waiting for one and the sweep is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

from .postgres.exchange import Exchange, RequestNotClaimable
from .records import EgressResult, RequestState

__all__ = ["ReconciliationPass", "ReconciliationScheduler"]


@dataclass(frozen=True)
class ReconciliationPass:
    """What one sweep did."""

    expired: Sequence[UUID]
    reconciled: Sequence[UUID]
    skipped: Sequence[UUID]

    @property
    def count(self) -> int:
        return len(self.reconciled)


class ReconciliationScheduler:
    """Sweeps expired leases into terminal ``OUTCOME_UNKNOWN`` results."""

    def __init__(self, exchange: Exchange, *, reconciler_id: str = "meu-reconciler") -> None:
        self._exchange = exchange
        self._reconciler_id = reconciler_id

    def sweep(self, tenant_id: UUID, *, now: datetime) -> ReconciliationPass:
        """Expire every lease that has run out, once.

        A request whose result landed between the read and the write is skipped
        rather than overwritten: ``record_result`` is told to expect ``LEASED``,
        so a request that has since become terminal raises and is counted as
        skipped. Overwriting there would replace a known outcome with an unknown
        one — losing information to a race, which is the one thing this sweep
        must never do.
        """

        expired = self._exchange.expired_leases(tenant_id, now=now)
        reconciled: list = []
        skipped: list = []

        for request_id, _holder in expired:
            result = EgressResult.outcome_unknown(
                request_id=request_id,
                tenant_id=tenant_id,
                recorded_at=now,
                provider_id=self._reconciler_id,
            )
            try:
                self._exchange.record_result(
                    result, expect_states=(RequestState.LEASED,))
            except RequestNotClaimable:
                skipped.append(request_id)
            else:
                reconciled.append(request_id)

        return ReconciliationPass(
            expired=[r for r, _ in expired],
            reconciled=reconciled,
            skipped=skipped,
        )
