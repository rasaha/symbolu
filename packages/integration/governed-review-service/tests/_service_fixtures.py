"""Builders for the unit suite: a real SQLite ledger, a static reader and an adapter
double that records what the service delivered. Every instant is explicit."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Mapping

import _fixtures as F  # the governed-review package's fixtures (ledger, clock, approvers)
from ugence_governed_review import ProposalIdentity, subject_for
from ugence_governance_contracts.api import Validity

from ugence_governed_review_service import ReviewService, StaticRunReader

__all__ = ["F", "RecordingAdapter", "parked_checkpoint", "request_for", "service"]


class RecordingAdapter:
    """Looks like the DBOS adapter to the service; remembers every delivery."""

    def __init__(self, known: tuple[str, ...] = ()) -> None:
        self.signals: list[tuple[str, str, Mapping[str, Any]]] = []
        self.resumes: list[str] = []
        self._known = set(known)

    def signal(self, *, instance_id: str, signal_name: str, payload: Mapping[str, Any]) -> None:
        self.signals.append((instance_id, signal_name, dict(payload)))

    def resume(self, *, instance_id: str) -> None:
        self.resumes.append(instance_id)

    def status(self, *, instance_id: str) -> Mapping[str, Any]:
        return {"known": instance_id in self._known, "engine_id": "double"}


def parked_checkpoint(instance_id: str, task_id: str, fingerprint: str, *,
                      disposition: str = "ESCALATE", status: str = "PAUSED") -> dict:
    return {
        "instance_id": instance_id, "workflow_id": "wf", "status": status,
        "correlation_id": f"c-{instance_id}",
        "tasks": {task_id: {"status": "WAITING", "attempts": 1}},
        "execution_states": {task_id: {
            "workflow_status": status, "task_status": "WAITING", "attempt": 1,
            "provider_id": "p", "operation": "op", "idempotency_key": f"{instance_id}:{task_id}",
            "proposal_fingerprint": fingerprint, "governance_disposition": disposition,
            "evaluation_reference": "eval-1", "valid_until": None,
        }},
        "checkpoint_digest": "d",
    }


def request_for(ledger, clock: F.Clock, instance_id: str, task_id: str = "t1",
                fingerprint: str = "f" * 64, *, role: str = F.ROLE):
    """Raise the request the source would raise on park, and present it."""

    identity = ProposalIdentity(fingerprint=fingerprint, instance_id=instance_id, task_id=task_id)
    now = clock.datetime()
    record = ledger.request_approval(
        subject_for(identity, tenant_id=F.TENANT), requested_by=F.REQUESTER, required_role=role,
        validity=Validity(issued_at=now, expires_at=now + timedelta(days=7)), as_of=now,
        justification="parked",
    )
    return ledger.present_for_decision(record.approval_id, as_of=now)


def service(ledger, clock: F.Clock, *, adapter=None, reader=None, eligibility=None,
            fault_injector=None) -> ReviewService:
    return ReviewService(
        ledger=ledger, adapter=adapter or RecordingAdapter(), reader=reader or StaticRunReader(),
        tenant_id=F.TENANT, clock=clock.datetime, eligibility=eligibility,
        fault_injector=fault_injector,
    )
