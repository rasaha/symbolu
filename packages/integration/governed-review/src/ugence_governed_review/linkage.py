"""The receipt linkage (GAS-7, step HR-E): one audit reference joining a governed
proposal's fingerprint, the approval that released it, the consumption that used the
approval exactly once, the resume that re-armed the instance, and the evaluation that
ran after it.

    CONTRACT ONLY. THIS MODULE READS THREE STORES AND WRITES NONE.

Today the story of one parked, approved and resumed instance lives in three stores
joined only by convention:

* the approval ledger (``ugence_approval_workflow``): the approval, its ``CONSUMED``
  event and the consumption id;
* the durable engine's event log (``ugence_art.runtime_events``): ``WORKFLOW_PAUSED``,
  the ``EXTERNAL_SIGNAL:review_decision`` row a recorded decision delivers, and
  ``WORKFLOW_RESUMED``;
* the durable engine's checkpoint (``ugence_art.runtime_state``): the execution-state
  journal, every ``CanonicalExecutionState`` the runtime sealed, carrying the proposal
  fingerprint, the governance disposition and the evaluation reference per quantum.
  Each ``GOVERNANCE_DISPOSITION_RECEIVED`` event names the snapshot it was recorded
  against by ``execution_state_digest``, and that key is how the park and the resumed
  evaluation are found: never by guessing over the journal.

:func:`reconstruct` joins them by the identities HR-3 ratified — the fingerprint is the
subject, ``<instance_id>:<task_id>`` is the consumer reference, the consumption id is
deterministic — and refuses, with a typed reason, any join that does not hold: a
different fingerprint after resume, a consumption held by another instance, a resume
recorded before the decision, an ambiguous journal. What it returns is a frozen
:class:`ReviewLinkage` with a canonical digest, and two projections onto the G4
contracts the sequencing record's D-4 ratified as the only cross-store correlation:
an :class:`EvidenceReference` for the linkage itself and one :class:`AuditReference`
per joined entry.

It appends nothing anywhere. Whether the linkage is written into the control-plane
audit ledger (``ugence_control_plane_root``, D-4's ledger service) is an owner decision
recorded in the human-review ADR; a composition root that decides yes hands
``ReviewLinkage.to_dict()`` to that ledger as a ``LedgerEntry`` payload. No existing
store gains a column, and clearance receipts are untouched.

The module reads no clock: every instant is copied from the store that recorded it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from ugence_approval_workflow import ApprovalState, ApprovalWorkflowPort
from ugence_governance_contracts.api import AuditReference, EvidenceReference

from .binding import SUBJECT_KIND, ProposalIdentity, consumer_ref_for, expected_consumption_id
from .errors import GovernedReviewError

__all__ = [
    "Reconstruction",
    "LINKAGE_VERSION",
    "EVIDENCE_KIND",
    "STORE_APPROVAL_LEDGER",
    "STORE_RUNTIME_EVENTS",
    "STORE_EXECUTION_JOURNAL",
    "SIGNAL_EVENT_TYPE",
    "LinkageError",
    "ReviewLinkage",
    "reconstruct",
]

#: Frozen identity of this linkage's shape. A field added or renamed is a new version.
LINKAGE_VERSION = "governed_review.linkage.v1"

#: The ``evidence_kind`` the linkage projects to (G4 ``EvidenceReference``).
EVIDENCE_KIND = "governed_review.linkage"

#: The ``store_ref`` spellings the linkage's audit references use. Named, never
#: hidden (G4): each is one of the platform's separate audit stores.
STORE_APPROVAL_LEDGER = "approval-workflow/ledger_events"
STORE_RUNTIME_EVENTS = "durable-execution/runtime_events"
STORE_EXECUTION_JOURNAL = "durable-execution/runtime_state.execution_state_journal"

#: The event type the review service's delivered decision is recorded under.
SIGNAL_EVENT_TYPE = "EXTERNAL_SIGNAL:review_decision"

_DOMAIN = "ugence.governed_review.linkage"
_PAUSED = "WORKFLOW_PAUSED"
_RESUMED = "WORKFLOW_RESUMED"
_DISPOSITION = "GOVERNANCE_DISPOSITION_RECEIVED"


class LinkageError(GovernedReviewError):
    """A join the stores do not support. The reason names which one."""


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=True).encode("utf-8")


def _digest(domain: str, payload: Any) -> str:
    return hashlib.sha256(f"{_DOMAIN}\x1f{domain}\x1fv1\x1f".encode("utf-8")
                          + _canonical(payload)).hexdigest()


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ReviewLinkage:
    """One parked-approved-resumed round trip, joined by id across three stores.

    Every field is a flat scalar copied from a store; nothing is derived here except
    :meth:`digest`. ``signal_event_seq`` is ``None`` when the decision was recorded
    without the review service (the ledger's own transitions deliver no signal).
    """

    linkage_version: str
    tenant_id: str
    instance_id: str
    task_id: str
    consumer_ref: str
    correlation_id: str
    proposal_fingerprint: str
    # -- the approval ledger --
    approval_id: str
    approval_state: str
    decided_by: str
    decided_role: str
    decided_at: Optional[datetime]
    consumption_id: str
    consumed_at: Optional[datetime]
    consumed_event_sequence: int
    # -- the durable event log --
    parked_disposition_event_seq: int
    paused_event_seq: int
    signal_event_seq: Optional[int]
    resumed_event_seq: int
    resumed_disposition_event_seq: int
    # -- the execution-state journal --
    parked_evaluation_reference: str
    parked_state_digest: str
    parked_disposition: str
    resumed_evaluation_reference: str
    resumed_state_digest: str
    resumed_disposition: str

    def to_dict(self) -> dict:
        out = {}
        for f in fields(self):
            value = getattr(self, f.name)
            out[f.name] = _iso(value) if isinstance(value, datetime) else value
        return out

    def digest(self) -> str:
        """Domain-separated sha-256 over the canonical payload. Deterministic."""

        return _digest("linkage", self.to_dict())

    # -- G4 projections --------------------------------------------------------
    def to_evidence_reference(self) -> EvidenceReference:
        """The linkage as one piece of evidence about ``<instance_id>:<task_id>``."""

        return EvidenceReference(
            evidence_id=f"grl_{self.digest()[:32]}",
            tenant_id=self.tenant_id,
            subject_id=self.consumer_ref,
            evidence_kind=EVIDENCE_KIND,
            content_digest=self.digest(),
            provenance_ref=f"{LINKAGE_VERSION}:{self.approval_id}",
            created_at=self.consumed_at,
        )

    def audit_references(self, *, entry_digests: Mapping[str, str]) -> tuple[AuditReference, ...]:
        """One :class:`AuditReference` per joined entry, in the order they happened.

        ``entry_digests`` maps each ``"<store_ref>:<entry_ref>"`` to the content digest
        :func:`reconstruct` computed when it read the entry, so a reference cannot
        silently follow an entry that changed. Journal entries are their own digest.
        """

        refs = []
        for store, entry in self._entries():
            key = f"{store}:{entry}"
            digest = entry_digests.get(key) if store != STORE_EXECUTION_JOURNAL else entry
            if not digest:
                raise LinkageError(f"no entry digest recorded for {key}")
            refs.append(AuditReference(tenant_id=self.tenant_id, store_ref=store,
                                       entry_ref=entry, entry_digest=digest,
                                       correlation_id=self.correlation_id))
        return tuple(refs)

    def _entries(self) -> tuple[tuple[str, str], ...]:
        entries = [
            (STORE_RUNTIME_EVENTS, f"{self.instance_id}:{self.parked_disposition_event_seq}"),
            (STORE_EXECUTION_JOURNAL, self.parked_state_digest),
            (STORE_RUNTIME_EVENTS, f"{self.instance_id}:{self.paused_event_seq}"),
            (STORE_APPROVAL_LEDGER, f"{self.approval_id}:{self.consumed_event_sequence}"),
        ]
        if self.signal_event_seq is not None:
            entries.append((STORE_RUNTIME_EVENTS, f"{self.instance_id}:{self.signal_event_seq}"))
        entries.append((STORE_RUNTIME_EVENTS, f"{self.instance_id}:{self.resumed_event_seq}"))
        entries.append((STORE_RUNTIME_EVENTS, f"{self.instance_id}:{self.resumed_disposition_event_seq}"))
        entries.append((STORE_EXECUTION_JOURNAL, self.resumed_state_digest))
        return tuple(entries)


@dataclass(frozen=True)
class Reconstruction:
    """What :func:`reconstruct` returns: the linkage and the digests of what it read."""

    linkage: ReviewLinkage
    entry_digests: Mapping[str, str]

    def audit_references(self) -> tuple[AuditReference, ...]:
        return self.linkage.audit_references(entry_digests=self.entry_digests)


def _event_type(event: Mapping[str, Any]) -> str:
    body = event.get("body") if isinstance(event.get("body"), Mapping) else {}
    return str(event.get("event_type") or body.get("type") or "")


def _event_body(event: Mapping[str, Any]) -> Mapping[str, Any]:
    body = event.get("body")
    return body if isinstance(body, Mapping) else {}


def reconstruct(
    ledger: ApprovalWorkflowPort,
    *,
    tenant_id: str,
    instance_id: str,
    task_id: str,
    approval_id: str,
    events: Sequence[Mapping[str, Any]],
    journal: Mapping[str, Mapping[str, Any]],
    correlation_id: str = "",
) -> Reconstruction:
    """Join the three stores by id for one instance and task, or refuse.

    ``events`` is the instance's runtime event log oldest first, each
    ``{"seq", "event_type", "body"}`` as the durable tables hold it; ``journal`` is the
    checkpoint's ``execution_state_journal`` keyed by ``state_digest``. Both are read
    by the caller from the durable engine; this function opens no connection.
    """

    identity = ProposalIdentity(fingerprint="placeholder", instance_id=instance_id,
                                task_id=task_id)
    consumer_ref = consumer_ref_for(identity)
    digests: dict[str, str] = {}

    # -- the approval ledger --------------------------------------------------------
    record = ledger.get_approval(approval_id)
    if record is None:
        raise LinkageError(f"approval {approval_id} is unknown to the ledger")
    if record.tenant_id != tenant_id:
        raise LinkageError("the approval belongs to another tenant")
    if record.subject_kind != SUBJECT_KIND:
        raise LinkageError(f"approval {approval_id} is not bound to a governed proposal")
    if record.subject_ref != consumer_ref:
        raise LinkageError(f"approval {approval_id} binds {record.subject_ref!r}, not {consumer_ref!r}")
    if record.state is not ApprovalState.CONSUMED:
        raise LinkageError(f"approval {approval_id} is {record.state.value}; no consumption to link")
    if record.consumer_ref != consumer_ref:
        raise LinkageError(f"approval {approval_id} was consumed by {record.consumer_ref!r}, "
                           f"not by {consumer_ref!r}")
    fingerprint = record.subject_digest
    identity = ProposalIdentity(fingerprint=fingerprint, instance_id=instance_id, task_id=task_id)
    expected = expected_consumption_id(identity, tenant_id=tenant_id, approval_id=approval_id)

    consumed = [e for e in ledger.approval_events(approval_id)
                if e.event_type is ApprovalState.CONSUMED]
    if len(consumed) != 1:
        raise LinkageError(f"approval {approval_id} has {len(consumed)} CONSUMED events; expected one")
    consumed_event = consumed[0]
    try:
        detail = json.loads(consumed_event.detail) if consumed_event.detail else {}
    except ValueError:
        detail = {}
    consumption_id = str(detail.get("consumption_id") or "")
    if consumption_id != expected:
        raise LinkageError("the recorded consumption id is not this instance and task's "
                           f"({consumption_id!r} != {expected!r})")
    digests[f"{STORE_APPROVAL_LEDGER}:{approval_id}:{consumed_event.sequence}"] = \
        _digest("ledger_event", consumed_event.to_dict())

    # -- the durable event log -------------------------------------------------------
    paused = [e for e in events if _event_type(e) == _PAUSED]
    if not paused:
        raise LinkageError("no WORKFLOW_PAUSED event: the instance never parked")
    paused_seq = int(paused[0]["seq"])

    signal_seq: Optional[int] = None
    for e in events:
        if _event_type(e) == SIGNAL_EVENT_TYPE and int(e["seq"]) > paused_seq:
            payload = _event_body(e).get("payload")
            if isinstance(payload, Mapping) and payload.get("approval_id") == approval_id:
                signal_seq = int(e["seq"])
                break

    after = signal_seq if signal_seq is not None else paused_seq
    resumed = [e for e in events if _event_type(e) == _RESUMED and int(e["seq"]) > after]
    if not resumed:
        raise LinkageError("no WORKFLOW_RESUMED event after the park"
                           + (" and the decision signal" if signal_seq is not None else ""))
    resumed_seq = int(resumed[0]["seq"])
    if record.consumed_at is not None and record.decided_at is not None \
            and record.consumed_at < record.decided_at:
        raise LinkageError("the approval was consumed before it was decided")
    for e in events:
        seq = int(e["seq"])
        if seq in (paused_seq, signal_seq, resumed_seq):
            digests[f"{STORE_RUNTIME_EVENTS}:{instance_id}:{seq}"] = \
                _digest("runtime_event", {"seq": seq, "event_type": _event_type(e),
                                          "body": dict(_event_body(e))})

    # -- the execution-state journal, joined through the disposition events --------
    # Every GOVERNANCE_DISPOSITION_RECEIVED event names the sealed snapshot it was
    # recorded against (``execution_state_digest``), so the park and the resumed
    # evaluation are found by that key, never by guessing over the journal.
    def _disposition_events(lo: int, hi: Optional[int]):
        out = []
        for e in events:
            seq = int(e["seq"])
            if _event_type(e) != _DISPOSITION or seq <= lo or (hi is not None and seq >= hi):
                continue
            detail = _event_body(e).get("detail")
            if isinstance(detail, Mapping) and detail.get("task_id") == task_id:
                out.append((seq, detail))
        return out

    before_park = _disposition_events(0, paused_seq)
    if not before_park:
        raise LinkageError("no governance disposition was recorded for this task before the park")
    parked_seq, parked_detail = before_park[-1]
    if parked_detail.get("disposition") != "ESCALATE":
        raise LinkageError(f"the instance parked on {parked_detail.get('disposition')!r}, not on "
                           "ESCALATE; a HOLD is never released by an approval (HR-5)")
    after_resume = _disposition_events(resumed_seq, None)
    if not after_resume:
        raise LinkageError("no governance disposition was recorded after the resume; the "
                           "resumed evaluation has not happened")
    resumed_disp_seq, resumed_detail = after_resume[0]
    if resumed_detail.get("disposition") != "CLEAR":
        raise LinkageError(f"the resumed evaluation was {resumed_detail.get('disposition')!r}; "
                           "the approval did not release the proposal")

    def _snapshot(detail: Mapping[str, Any], what: str) -> tuple[str, Mapping[str, Any]]:
        digest = str(detail.get("execution_state_digest") or "")
        state = journal.get(digest)
        if not digest or state is None:
            raise LinkageError(f"the {what} disposition event names snapshot {digest[:16]!r}, "
                               "which the journal does not hold")
        if state.get("state_digest") != digest:
            raise LinkageError(f"journal entry {digest[:16]} does not carry its own state digest")
        if state.get("task_id") != task_id:
            raise LinkageError(f"the {what} snapshot belongs to task {state.get('task_id')!r}")
        if state.get("proposal_fingerprint") != fingerprint:
            raise LinkageError(f"the {what} snapshot's fingerprint differs from the approved "
                               "proposal's; the human decided about a different action (HR-3)")
        if state.get("governance_disposition") != detail.get("disposition"):
            raise LinkageError(f"the {what} snapshot's disposition disagrees with its event")
        return digest, state

    parked_digest, parked_state = _snapshot(parked_detail, "parked")
    resumed_digest, resumed_state = _snapshot(resumed_detail, "resumed")
    for e in events:
        seq = int(e["seq"])
        if seq in (parked_seq, resumed_disp_seq):
            digests[f"{STORE_RUNTIME_EVENTS}:{instance_id}:{seq}"] = \
                _digest("runtime_event", {"seq": seq, "event_type": _event_type(e),
                                          "body": dict(_event_body(e))})

    linkage = ReviewLinkage(
        linkage_version=LINKAGE_VERSION,
        tenant_id=tenant_id, instance_id=instance_id, task_id=task_id,
        consumer_ref=consumer_ref,
        correlation_id=correlation_id or str(parked_state.get("correlation_id") or ""),
        proposal_fingerprint=fingerprint,
        approval_id=approval_id, approval_state=record.state.value,
        decided_by=record.decided_by, decided_role=record.decided_role,
        decided_at=record.decided_at,
        consumption_id=consumption_id, consumed_at=record.consumed_at,
        consumed_event_sequence=int(consumed_event.sequence),
        parked_disposition_event_seq=parked_seq, paused_event_seq=paused_seq,
        signal_event_seq=signal_seq, resumed_event_seq=resumed_seq,
        resumed_disposition_event_seq=resumed_disp_seq,
        parked_evaluation_reference=str(parked_state.get("evaluation_reference") or ""),
        parked_state_digest=parked_digest,
        parked_disposition=str(parked_state.get("governance_disposition")),
        resumed_evaluation_reference=str(resumed_state.get("evaluation_reference") or ""),
        resumed_state_digest=resumed_digest,
        resumed_disposition=str(resumed_state.get("governance_disposition")),
    )
    return Reconstruction(linkage=linkage, entry_digests=dict(digests))
