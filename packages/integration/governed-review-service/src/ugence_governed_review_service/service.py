"""The review service: queue, run detail, and the recording of a human decision.

    THIS SERVICE RECORDS A DECISION A HUMAN ALREADY MADE, THEN RE-ARMS THE INSTANCE.
    IT NEVER APPROVES, AUTHENTICATES, MINTS AUTHORITY, CLEARS OR EXECUTES.

What "re-arms" means, precisely, because it is the one place this package touches the
engine. After a decision is recorded in the approval ledger, the service delivers the
adapter's ``signal`` (data: ``EXTERNAL_SIGNAL:review_decision``, granting nothing) and,
for a GRANT, the adapter's bounded ``resume`` for that instance only. Since HR-B the
adapter's resume runs nothing: it re-arms the parked instance and stops. Whether the
instance then proceeds is decided inside its next quantum, where the approval-bound
input source consumes the GRANTED approval exactly once against the proposal
fingerprint (HR-3), and composition, projection, ``validate_clearance`` and the RA-6
last-mile recheck run unchanged. A decision the ledger refused delivers nothing. A
REJECT delivers the signal and leaves the instance parked.

The approver on every decision is a PRESENTED reference (``IDENTITY_PROOF``). The
ledger's eligibility port, answered by the authority directory, decides whether that
reference may decide. Since 0.3.0 (AI-A) a composition root may also supply an
``ApproverIdentityPort``: then every submission must carry a proof, the port answers
who it proves, and the service binds the presented approver to that proven,
issuer-qualified subject before the ledger is touched (ID-2), derives the tenant from
the proof under an explicit tenant mode (ID-4), and records the asserted assurance
without enforcing any level (ID-5). The service still mints no identity: it relays a
proof to the port and fails closed when the port cannot answer. With only the static
fixture adapter available, every decision stays ``PRESENTED_UNPROVEN``; that is the
honest ceiling of this release and the reason it is labelled shadow-only.

Row 1 of the failure matrix — a duplicate decision — is handled here rather than in
the ledger: an identical resubmission (same approval, same approver, same outcome) is
answered as ``REPLAYED`` with the standing record and nothing re-decided, because a
relay that retries after a lost response must not turn one decision into an error.
Any other second decision is refused and the first stands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence

from ugence_approval_workflow import (
    ApprovalRecord,
    ApprovalState,
    ApprovalWorkflowPort,
    ApproverEligibilityPort,
    ApproverRef,
    EligibilityRefused,
    IllegalTransitionError,
    ReviewDecision,
)
from ugence_governed_review import SUBJECT_KIND

from .errors import ClockDisciplineError, ContractViolation
from .identity import (
    ActorKind,
    ApproverIdentity,
    ApproverIdentityPort,
    RecordedAssurance,
    TenantMode,
    authentication_reference,
)
from .linkage import LinkageAppender, LinkageOutcome, LinkageState, linkage_view
from .reader import RunReader
from .version import IDENTITY_PROOF

__all__ = [
    "SIGNAL_NAME",
    "TENANT_SOURCE_CONFIGURED",
    "TENANT_SOURCE_PROOF",
    "DecisionResult",
    "DecisionOutcome",
    "QueueEntry",
    "ReviewService",
    "instance_of",
]

#: The adapter signal name a recorded decision is delivered under.
SIGNAL_NAME = "review_decision"

#: The workflow states a bounded resume may be delivered to. Anything else is already
#: armed or finished, and a second resume is recorded as skipped, never forced.
_RESUMABLE = frozenset({"WAITING", "PAUSED"})

#: ID-4: where the tenant a decision was recorded under came from.
TENANT_SOURCE_PROOF = "PROOF"
TENANT_SOURCE_CONFIGURED = "CONFIGURED_SINGLE_TENANT"

#: The decisions this service records. ``REQUEST_CHANGES`` is a ledger state with no
#: runtime meaning on this path and is refused here rather than mapped to anything.
_ACCEPTED_DECISIONS = (ReviewDecision.GRANT, ReviewDecision.REJECT)


class DecisionResult(str, Enum):
    RECORDED = "RECORDED"
    REPLAYED = "REPLAYED"
    REFUSED_UNKNOWN_APPROVAL = "REFUSED_UNKNOWN_APPROVAL"
    REFUSED_NOT_REVIEWABLE = "REFUSED_NOT_REVIEWABLE"
    REFUSED_NOT_OPEN = "REFUSED_NOT_OPEN"
    REFUSED_ALREADY_DECIDED = "REFUSED_ALREADY_DECIDED"
    REFUSED_INELIGIBLE = "REFUSED_INELIGIBLE"
    REFUSED_INVALID_DECISION = "REFUSED_INVALID_DECISION"
    # AI-A: identity refusals. Each is answered before any record changes.
    REFUSED_UNAUTHENTICATED = "REFUSED_UNAUTHENTICATED"
    REFUSED_IDENTITY_MISMATCH = "REFUSED_IDENTITY_MISMATCH"
    REFUSED_NOT_HUMAN = "REFUSED_NOT_HUMAN"
    REFUSED_IDENTITY_UNAVAILABLE = "REFUSED_IDENTITY_UNAVAILABLE"
    REFUSED_TENANT_UNPROVEN = "REFUSED_TENANT_UNPROVEN"

    @property
    def recorded(self) -> bool:
        return self in (DecisionResult.RECORDED, DecisionResult.REPLAYED)


@dataclass(frozen=True)
class DecisionOutcome:
    """The typed answer to one submission. ``approval`` is the standing record."""

    result: DecisionResult
    approval_id: str
    approval: Optional[ApprovalRecord] = None
    instance_id: str = ""
    task_id: str = ""
    signal_delivered: bool = False
    resume_delivered: bool = False
    resume_skipped_reason: str = ""
    reason: str = ""
    identity_proof: str = IDENTITY_PROOF
    #: HE-1: what linking did after a GRANT, or why it could not yet. Never withholds
    #: the decision above it.
    linkage: Optional[LinkageOutcome] = None
    #: ID-2: the digest-bound reference to the verified claims; empty without a proof.
    authentication_reference: str = ""
    #: ID-4: ``PROOF`` or ``CONFIGURED_SINGLE_TENANT``; empty when nothing was recorded.
    tenant_source: str = ""
    #: ID-5: the assurance the issuer asserted, recorded and never enforced here.
    assurance: Optional[RecordedAssurance] = None

    @property
    def recorded(self) -> bool:
        return self.result.recorded


@dataclass(frozen=True)
class QueueEntry:
    """One parked ESCALATE instance awaiting a decision, joined to its approval."""

    approval_id: str
    approval_state: ApprovalState
    instance_id: str
    task_id: str
    fingerprint: str
    required_role: str
    requested_by: str
    requested_at: datetime
    expires_at: datetime
    justification: str = ""
    workflow_id: str = ""
    workflow_status: str = ""
    task_status: str = ""
    provider_id: str = ""
    operation: str = ""
    governance_disposition: str = ""
    eligible_approvers: tuple[ApproverRef, ...] = ()
    instance_known: bool = False


def instance_of(record: ApprovalRecord) -> tuple[str, str]:
    """The instance and task an approval binds to, from its ``subject_ref`` (HR-3).

    The binding forbids ':' in an instance id, so the first ':' is the separator.
    """

    ref = record.subject_ref or ""
    instance_id, sep, task_id = ref.partition(":")
    if not sep or not instance_id or not task_id:
        raise ContractViolation(
            f"approval {record.approval_id} has no '<instance_id>:<task_id>' subject_ref"
        )
    return instance_id, task_id


class ReviewService:
    """Queue, run detail and decision recording over the ledger and the adapter."""

    maturity = "REFERENCE_GRADE_SHADOW_ONLY"

    def __init__(
        self,
        *,
        ledger: ApprovalWorkflowPort,
        adapter: Any,
        reader: RunReader,
        tenant_id: str,
        clock: Callable[[], datetime],
        eligibility: Optional[ApproverEligibilityPort] = None,
        fault_injector: Optional[Callable[[str], None]] = None,
        linkage_appender: Optional[LinkageAppender] = None,
        identity_port: Optional[ApproverIdentityPort] = None,
        tenant_mode: Optional[TenantMode] = None,
        production: bool = False,
    ) -> None:
        if not isinstance(ledger, ApprovalWorkflowPort):
            raise ContractViolation("ledger must satisfy ApprovalWorkflowPort")
        for attr in ("signal", "resume", "status"):
            if not callable(getattr(adapter, attr, None)):
                raise ContractViolation(f"adapter must provide {attr}()")
        if not isinstance(reader, RunReader):
            raise ContractViolation("reader must satisfy RunReader")
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ContractViolation("tenant_id must be a non-empty string")
        if not callable(clock):
            raise ContractViolation("clock must be callable and return a tz-aware datetime")
        if eligibility is not None and not isinstance(eligibility, ApproverEligibilityPort):
            raise ContractViolation("eligibility must satisfy ApproverEligibilityPort")
        if identity_port is not None:
            if not isinstance(identity_port, ApproverIdentityPort):
                raise ContractViolation("identity_port must satisfy ApproverIdentityPort")
            if production and getattr(identity_port, "NON_PRODUCTION", False):
                raise ContractViolation("a non-production identity adapter is refused in "
                                        "production mode")
            if tenant_mode is None:
                raise ContractViolation("tenant_mode must be explicit when an identity port "
                                        "is configured (ID-4)")
        if tenant_mode is not None and not isinstance(tenant_mode, TenantMode):
            raise ContractViolation("tenant_mode must be a TenantMode")
        self._ledger = ledger
        self._adapter = adapter
        self._reader = reader
        self._tenant = tenant_id.strip()
        self._clock = clock
        self._eligibility = eligibility
        # A seam for the crash rows only: called with a named point, it may kill the
        # process. It can never change what is recorded, only where the record stops.
        self._fault = fault_injector or (lambda _point: None)
        # HE-1: absent, every linkage outcome is LEDGER_UNCONFIGURED and nothing is written.
        self._linker = linkage_appender
        # AI-A: absent, the approver stays a presented reference and no proof is required.
        # With no port there is no proof to take a tenant from, so the configured tenant
        # is the only source and the service is labelled SINGLE_TENANT.
        self._identity = identity_port
        self._tenant_mode = tenant_mode or TenantMode.SINGLE_TENANT

    @property
    def tenant_mode(self) -> TenantMode:
        return self._tenant_mode

    @property
    def identity_port_configured(self) -> bool:
        return self._identity is not None

    # -- reads ---------------------------------------------------------------------
    def list_queue(self, *, required_role: str = "") -> tuple[QueueEntry, ...]:
        """Every open approval bound to a parked ESCALATE instance (HR-5).

        The ledger holds the queue; the durable checkpoint says what the instance is
        doing. An approval whose subject is not a proposal is not this queue's, and a
        parked HOLD is never listed, even if something raised a request for it.
        """

        as_of = self._now()
        entries = []
        for record in self._ledger.list_open(tenant_id=self._tenant,
                                             required_role=required_role, as_of=as_of):
            if record.subject_kind != SUBJECT_KIND:
                continue
            try:
                instance_id, task_id = instance_of(record)
            except ContractViolation:
                continue
            ckpt = self._reader.checkpoint(instance_id)
            state = _task_state(ckpt, task_id)
            disposition = str(state.get("governance_disposition") or "")
            if disposition and disposition != "ESCALATE":
                continue
            entries.append(QueueEntry(
                approval_id=record.approval_id,
                approval_state=record.state_at(as_of),
                instance_id=instance_id, task_id=task_id,
                fingerprint=record.subject_digest,
                required_role=record.required_role, requested_by=record.requested_by,
                requested_at=record.validity.issued_at, expires_at=record.validity.expires_at,
                justification=record.justification,
                workflow_id=str((ckpt or {}).get("workflow_id") or ""),
                workflow_status=str((ckpt or {}).get("status") or ""),
                task_status=str(state.get("task_status") or _task_status(ckpt, task_id)),
                provider_id=str(state.get("provider_id") or ""),
                operation=str(state.get("operation") or ""),
                governance_disposition=disposition,
                eligible_approvers=self._eligible(record, as_of),
                instance_known=ckpt is not None,
            ))
        return tuple(entries)

    def read_run(self, instance_id: str) -> Optional[Mapping[str, Any]]:
        """One instance: its checkpoint view, engine status and every bound approval."""

        ckpt = self._reader.checkpoint(instance_id)
        if ckpt is None:
            return None
        as_of = self._now()
        approvals = [
            _approval_view(r, as_of) for r in self._ledger.list_open(tenant_id=self._tenant, as_of=as_of)
            if r.subject_kind == SUBJECT_KIND and r.subject_ref.startswith(f"{instance_id}:")
        ]
        return {
            "instance": dict(ckpt),
            "engine": dict(self._adapter.status(instance_id=instance_id)),
            "open_approvals": approvals,
            "linkages": [linkage_view(o) for o in self._link_instance(instance_id, as_of)],
            "identity_proof": IDENTITY_PROOF,
            "tenant_mode": self._tenant_mode.value,
        }

    def _link_instance(self, instance_id: str, as_of: datetime) -> list:
        """HE-5: every decided approval this instance's log names, linked if it can be.

        The approvals are found from the ``EXTERNAL_SIGNAL:review_decision`` rows the
        service itself delivered, so a decision recorded elsewhere is not guessed at.
        """

        seen: list = []
        for e in self._reader.events(instance_id):
            body = e.get("body") if isinstance(e.get("body"), Mapping) else {}
            if str(e.get("event_type") or "") != f"EXTERNAL_SIGNAL:{SIGNAL_NAME}":
                continue
            payload = body.get("payload") if isinstance(body.get("payload"), Mapping) else {}
            approval_id = str(payload.get("approval_id") or "")
            task_id = str(payload.get("task_id") or "")
            if approval_id and task_id and (approval_id, task_id) not in seen:
                seen.append((approval_id, task_id))
        return [self._link(instance_id, task_id, approval_id, as_of) for approval_id, task_id in seen]

    def _link(self, instance_id: str, task_id: str, approval_id: str,
              as_of: datetime) -> LinkageOutcome:
        if self._linker is None:
            return LinkageOutcome(LinkageState.LEDGER_UNCONFIGURED, approval_id, instance_id,
                                  task_id, reason="no control-plane audit ledger is configured")
        return self._linker.link(instance_id=instance_id, task_id=task_id,
                                 approval_id=approval_id, recorded_at=as_of)

    def read_run_events(self, instance_id: str) -> Optional[Sequence[Mapping[str, Any]]]:
        if self._reader.checkpoint(instance_id) is None:
            return None
        return tuple(dict(e) for e in self._reader.events(instance_id))

    def read_approval(self, approval_id: str) -> Optional[Mapping[str, Any]]:
        record = self._ledger.get_approval(approval_id)
        if record is None:
            return None
        as_of = self._now()
        view = _approval_view(record, as_of)
        view["events"] = [e.to_dict() for e in self._ledger.approval_events(approval_id)]
        return view

    # -- the decision -------------------------------------------------------------
    def submit_decision(
        self,
        *,
        approval_id: str,
        decision: ReviewDecision,
        presented_approver: ApproverRef,
        justification: str = "",
        presented_proof: str = "",
    ) -> DecisionOutcome:
        """Record a human's decision verbatim, then re-arm the instance it binds to.

        Order, and what each step can leave behind:

        0. with an identity port configured, the proof is resolved and bound to the
           presented approver (rows 1, 2, 5, 6, 7), then the tenant is derived from it
           (rows 4, 11, 12); every refusal here changes nothing and reads no record;
        1. refusals that change nothing (unknown, not a proposal, not open, decided);
        2. the ledger's own ``decide`` — one SQLite transaction; refused by the
           eligibility port before any record changes (row 5);
        3. the adapter signal, then for a GRANT the bounded resume, each its own
           durable step on the instance named by the approval and no other.

        A crash before step 2 commits leaves the record PENDING and no event (row 7).
        A crash after it leaves a decided approval that the next identical submission
        replays, delivering steps 3 then (row 8).
        """

        if not isinstance(decision, ReviewDecision) or decision not in _ACCEPTED_DECISIONS:
            return DecisionOutcome(DecisionResult.REFUSED_INVALID_DECISION, approval_id,
                                   reason="only GRANT and REJECT are recorded on this path")
        if not isinstance(presented_approver, ApproverRef):
            raise ContractViolation("presented_approver must be an ApproverRef")
        if not isinstance(presented_proof, str):
            raise ContractViolation("presented_proof must be a string")
        as_of = self._now()
        proven = self._resolve_identity(approval_id, presented_approver, presented_proof, as_of)
        if isinstance(proven, DecisionOutcome):
            return proven
        # ID-2 (AI-D): the digest-bound reference to the verified claims, recorded on
        # the approval and in its hash-linked decision event; empty without a proof.
        reference = authentication_reference(proven.claims) \
            if proven is not None and proven.claims is not None else ""
        record = self._ledger.get_approval(approval_id)
        if record is None:
            return DecisionOutcome(DecisionResult.REFUSED_UNKNOWN_APPROVAL, approval_id,
                                   reason="no such approval")
        if record.subject_kind != SUBJECT_KIND:
            return DecisionOutcome(DecisionResult.REFUSED_NOT_REVIEWABLE, approval_id, record,
                                   reason="the approval is not bound to a governed proposal")
        tenant = self._tenant_for(approval_id, record, proven)
        if isinstance(tenant, DecisionOutcome):
            return tenant
        instance_id, task_id = instance_of(record)
        state = self._ledger.state_at(approval_id, as_of=as_of)

        if state in (ApprovalState.REQUESTED, ApprovalState.PENDING):
            self._fault("before_persist")
            try:
                if state is ApprovalState.REQUESTED:
                    self._ledger.present_for_decision(approval_id, as_of=as_of)
                record = self._ledger.decide(
                    approval_id, approver=presented_approver, decision=decision,
                    as_of=as_of, justification=justification,
                    authentication_reference=reference,
                )
            except EligibilityRefused as exc:
                return DecisionOutcome(DecisionResult.REFUSED_INELIGIBLE, approval_id,
                                       self._ledger.get_approval(approval_id),
                                       instance_id, task_id, reason=str(exc))
            except IllegalTransitionError as exc:
                return DecisionOutcome(DecisionResult.REFUSED_NOT_OPEN, approval_id,
                                       self._ledger.get_approval(approval_id),
                                       instance_id, task_id, reason=str(exc))
            result = DecisionResult.RECORDED
        elif _is_same_decision(record, state, presented_approver, decision):
            result = DecisionResult.REPLAYED
        elif state in (ApprovalState.GRANTED, ApprovalState.REJECTED, ApprovalState.CONSUMED,
                       ApprovalState.CHANGES_REQUIRED):
            return DecisionOutcome(DecisionResult.REFUSED_ALREADY_DECIDED, approval_id, record,
                                   instance_id, task_id,
                                   reason=f"already {state.value} by {record.decided_by!r}; "
                                          "the first decision stands")
        else:
            return DecisionOutcome(DecisionResult.REFUSED_NOT_OPEN, approval_id, record,
                                   instance_id, task_id, reason=f"approval is {state.value}")

        self._fault("after_persist")
        return self._deliver(result, record, instance_id, task_id, decision, proven, tenant)

    # -- internals ------------------------------------------------------------------
    def _resolve_identity(self, approval_id: str, presented: ApproverRef, proof: str,
                          as_of: datetime) -> Optional[ApproverIdentity] | DecisionOutcome:
        """Step 0. ``None`` when no port is configured; the proven identity when the
        proof binds to the presented approver; otherwise the refusal.

        Order: a port configured but no proof (row 1); the port unable to answer (row
        7, fail closed on any exception); unauthenticated (row 1); not a human (row 5);
        expired at the write, whatever an earlier read proved (row 6); presented
        approver other than the proven subject (row 2).
        """

        if self._identity is None:
            return None
        if not proof:
            return DecisionOutcome(DecisionResult.REFUSED_UNAUTHENTICATED, approval_id,
                                   reason="an identity port is configured and no proof "
                                          "was presented")
        try:
            identity = self._identity.authenticate(proof)
        except Exception as exc:  # noqa: BLE001 - row 7: any failure to answer fails closed
            return DecisionOutcome(DecisionResult.REFUSED_IDENTITY_UNAVAILABLE, approval_id,
                                   reason=f"the identity port could not answer: "
                                          f"{type(exc).__name__}")
        if not isinstance(identity, ApproverIdentity):
            return DecisionOutcome(DecisionResult.REFUSED_IDENTITY_UNAVAILABLE, approval_id,
                                   reason="the identity port answered with the wrong shape")
        if not identity.authenticated or identity.claims is None:
            return DecisionOutcome(DecisionResult.REFUSED_UNAUTHENTICATED, approval_id,
                                   reason="the proof does not authenticate anyone")
        if identity.actor_type is not ActorKind.HUMAN:
            return DecisionOutcome(DecisionResult.REFUSED_NOT_HUMAN, approval_id,
                                   reason=f"a {identity.actor_type.value} actor never decides; "
                                          "a role grant does not make a human")
        if identity.claims.expires_at <= as_of:
            return DecisionOutcome(DecisionResult.REFUSED_UNAUTHENTICATED, approval_id,
                                   reason="the proof had expired when the decision was written")
        if presented.approver_id != identity.actor_id:
            return DecisionOutcome(DecisionResult.REFUSED_IDENTITY_MISMATCH, approval_id,
                                   reason="the presented approver is not the proven, "
                                          "issuer-qualified subject")
        return identity

    def _tenant_for(self, approval_id: str, record: ApprovalRecord,
                    proven: Optional[ApproverIdentity]) -> tuple[str, str] | DecisionOutcome:
        """ID-4: the tenant this decision is recorded under and where it came from.

        The approval's tenant must equal the tenant of record: the configured one
        without a proof or, with a proof, the verified claim. ``SINGLE_TENANT`` lets a
        missing claim fall back to the configured tenant and says so; ``MULTI_TENANT``
        refuses a missing claim; both refuse an ambiguous one.
        """

        claims = () if proven is None or proven.claims is None else proven.claims.tenant_claims
        if len(claims) > 1:
            return DecisionOutcome(DecisionResult.REFUSED_TENANT_UNPROVEN, approval_id, record,
                                   reason="the proof carries more than one tenant claim")
        if len(claims) == 1:
            tenant, source = claims[0], TENANT_SOURCE_PROOF
        elif proven is not None and self._tenant_mode is TenantMode.MULTI_TENANT:
            return DecisionOutcome(DecisionResult.REFUSED_TENANT_UNPROVEN, approval_id, record,
                                   reason="the proof carries no tenant claim and this service "
                                          "is MULTI_TENANT; configuration never fills the gap")
        else:
            tenant, source = self._tenant, TENANT_SOURCE_CONFIGURED
        if record.tenant_id != tenant:
            return DecisionOutcome(DecisionResult.REFUSED_NOT_REVIEWABLE, approval_id, record,
                                   reason=f"the approval is not reviewable in tenant "
                                          f"{tenant!r} (source {source})")
        return tenant, source

    def _deliver(self, result: DecisionResult, record: ApprovalRecord, instance_id: str,
                 task_id: str, decision: ReviewDecision, proven: Optional[ApproverIdentity],
                 tenant: tuple[str, str]) -> DecisionOutcome:
        proof_label, assurance = IDENTITY_PROOF, None
        if proven is not None and proven.claims is not None:
            proof_label = proven.proof
            assurance = RecordedAssurance(acr=proven.claims.acr, amr=proven.claims.amr)
        # What the ledger recorded is what is reported: on a replay under a fresh
        # proof, the standing record's reference stands, not the resubmission's.
        reference = record.authentication_reference or (
            authentication_reference(proven.claims)
            if proven is not None and proven.claims is not None else "")
        self._adapter.signal(
            instance_id=instance_id, signal_name=SIGNAL_NAME,
            payload={
                "approval_id": record.approval_id, "decision": decision.value,
                "decided_by": record.decided_by, "decided_role": record.decided_role,
                "subject_digest": record.subject_digest, "task_id": task_id,
                "identity_proof": proof_label,
                "authentication_reference": reference,
                "tenant_id": tenant[0], "tenant_source": tenant[1],
                "assurance": None if assurance is None else assurance.to_dict(),
            },
        )
        self._fault("after_signal")
        resumed, skipped = False, ""
        if decision is not ReviewDecision.GRANT:
            skipped = "a REJECT leaves the instance parked"
        else:
            ckpt = self._reader.checkpoint(instance_id)
            status = str((ckpt or {}).get("status") or "")
            if ckpt is None:
                skipped = "the instance has no durable state"
            elif status not in _RESUMABLE:
                skipped = f"the instance is {status}; already armed or finished"
            else:
                self._adapter.resume(instance_id=instance_id)
                resumed = True
        linkage = None
        if decision is ReviewDecision.GRANT:
            # HE-1: link when the round trip is complete; a NOT_YET is the honest answer
            # until the instance's next quantum has consumed the approval.
            linkage = self._link(instance_id, task_id, record.approval_id, self._now())
        return DecisionOutcome(result, record.approval_id, record, instance_id, task_id,
                               signal_delivered=True, resume_delivered=resumed,
                               resume_skipped_reason=skipped, identity_proof=proof_label,
                               linkage=linkage, authentication_reference=reference,
                               tenant_source=tenant[1], assurance=assurance)

    def _eligible(self, record: ApprovalRecord, as_of: datetime) -> tuple[ApproverRef, ...]:
        if self._eligibility is None:
            return ()
        return tuple(self._eligibility.eligible_approvers(
            tenant_id=record.tenant_id, subject_kind=record.subject_kind,
            subject_digest=record.subject_digest, required_role=record.required_role,
            as_of=as_of,
        ))

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ClockDisciplineError("the injected clock must return a timezone-aware datetime")
        return value


def _is_same_decision(record: ApprovalRecord, state: ApprovalState, approver: ApproverRef,
                      decision: ReviewDecision) -> bool:
    """Row 1: the same actor resubmitting the same outcome is a replay, not a decision."""

    wanted = {ReviewDecision.GRANT: (ApprovalState.GRANTED, ApprovalState.CONSUMED),
              ReviewDecision.REJECT: (ApprovalState.REJECTED,)}[decision]
    return state in wanted and record.decided_by == approver.approver_id \
        and record.decided_role == approver.role


def _task_state(ckpt: Optional[Mapping[str, Any]], task_id: str) -> Mapping[str, Any]:
    if not ckpt:
        return {}
    return dict((ckpt.get("execution_states") or {}).get(task_id) or {})


def _task_status(ckpt: Optional[Mapping[str, Any]], task_id: str) -> str:
    if not ckpt:
        return ""
    return str(((ckpt.get("tasks") or {}).get(task_id) or {}).get("status") or "")


def _approval_view(record: ApprovalRecord, as_of: datetime) -> dict:
    view = record.to_dict()
    view["state_at"] = record.state_at(as_of).value
    try:
        view["instance_id"], view["task_id"] = instance_of(record)
    except ContractViolation:
        view["instance_id"], view["task_id"] = "", ""
    return view
