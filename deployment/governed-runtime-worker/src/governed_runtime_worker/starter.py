"""The shadow-run starter (front-door seam 6, rulings FD-10.1 to FD-10.3).

    THE STUDIO SUPPLIES NOTHING BUT A CORRELATION ID. THE WORKER HOLDS THE DEFINITION.

The review service's sixth route asks this object to start the deployment's own shadow
workflow. It mints the instance id (from the correlation id, so a retried request lands
on the same instance), passes the deployment's own ``definition_digest`` to the adapter
and nothing else, and runs the first bounded quantum so the governed hook evaluates the
proposal and the run parks where the review queue can see it. Nothing here reads a
workflow, a task, a provider, a mode or a digest from the caller: the parameters do not
exist (FD-10.3).

Every refusal is the adapter's own, mapped to a typed outcome: a digest this deployment
is not running (``DefinitionVersionMismatch``) is ``REFUSED_DEFINITION``, an instance
that already exists under different identifying fields (``InstanceIdentityError``) is
``REFUSED_CONFLICT``, and an instance that already exists under the same ones is
``REPLAYED`` with nothing re-run. The starter grants, authorizes, clears and executes
nothing: every provider the run can reach is the workload's ``FIXTURE_ONLY`` recorder,
and a consequential task parks on ESCALATE until a recorded human decision.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Optional

from ugence_durable_execution.errors import DefinitionVersionMismatch, InstanceIdentityError
from ugence_governed_review_service import StartOutcome, StartResult

__all__ = ["ShadowRunStarter", "instance_id_for"]

#: Instance ids minted here carry this prefix so a relayed run is recognisable as one.
INSTANCE_PREFIX = "shadow-"


def instance_id_for(workflow_id: str, correlation_id: str) -> str:
    """Deterministic: the same correlation id always names the same instance, which is
    what lets the adapter's idempotency rule answer a retried start with ``REPLAYED``."""

    digest = hashlib.sha256(f"{workflow_id}|{correlation_id}".encode("utf-8")).hexdigest()
    return INSTANCE_PREFIX + digest[:24]


class ShadowRunStarter:
    """Starts one workflow, the one the composed workload already defines."""

    def __init__(self, *, adapter: Any, workflow_id: str, definition_digest: str,
                 workload_maturity: str) -> None:
        if not isinstance(definition_digest, str) or not definition_digest:
            raise ValueError("definition_digest is required: the starter passes the "
                             "deployment's own digest to the adapter and never another")
        self._adapter = adapter
        self.workflow_id = workflow_id
        self._digest = definition_digest
        self._workload_maturity = workload_maturity

    def start(self, *, correlation_id: Optional[str]) -> StartOutcome:
        if correlation_id is None:
            # The ruling says the worker mints (FD-10.2): with no correlation id there is
            # nothing to be idempotent on, so a fresh instance is minted each time.
            correlation_id = INSTANCE_PREFIX + uuid.uuid4().hex[:16]
        instance_id = instance_id_for(self.workflow_id, correlation_id)
        known = bool(self._adapter.status(instance_id=instance_id).get("known"))
        common = dict(instance_id=instance_id, workflow_id=self.workflow_id,
                      correlation_id=correlation_id, definition_digest=self._digest,
                      workload_maturity=self._workload_maturity)
        try:
            self._adapter.start(workflow_id=self.workflow_id, definition_digest=self._digest,
                                instance_id=instance_id, correlation_id=correlation_id, inputs={})
        except DefinitionVersionMismatch as exc:
            return StartOutcome(StartResult.REFUSED_DEFINITION, reason=str(exc), **common)
        except InstanceIdentityError as exc:
            return StartOutcome(StartResult.REFUSED_CONFLICT, reason=str(exc), **common)
        except KeyError as exc:
            return StartOutcome(StartResult.REFUSED_DEFINITION, **common,
                                reason=f"the composed workload defines no {self.workflow_id!r}: {exc}")
        if known:
            # The adapter returned the existing handle and touched nothing; neither do we.
            return StartOutcome(StartResult.REPLAYED, **common,
                                reason="the instance already exists under this deployment's own "
                                       "definition; nothing was re-run (adapter idempotency)")
        outcome = self._adapter.advance(instance_id=instance_id,
                                        attempt_token=f"{instance_id}:start")
        return StartOutcome(StartResult.STARTED, **common, advanced=True,
                            awaiting_external=bool(outcome.awaiting_external),
                            stop_reason=str(outcome.stop_reason or ""))
