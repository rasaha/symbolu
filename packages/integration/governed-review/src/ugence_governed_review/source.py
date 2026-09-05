"""The production ``GovernanceInputSource`` that reads the approval ledger.

    THIS SOURCE BINDS AND CONSUMES AN APPROVAL. IT DECIDES NOTHING.

Where it sits: in front of a deployment's real input source, inside the governance
hook, inside the durable step. The upstream source resolves Risk Authority, Decision
Authority and ActionGate results as it always has. This wrapper looks at one thing —
whether the Decision Authority result is a HOLD carrying ``required_approvals`` —
because that, and only that, is what the hook projects to ESCALATE and what a human
may review (owner ruling HR-5). Every other result passes through untouched.

For an ESCALATE-bound proposal it does, in order:

1. derive the approval identity from the proposal fingerprint (HR-3);
2. if no approval exists, raise the request in the ledger and present it for
   decision, then return the inputs unchanged: the instance parks, and the queue now
   shows why;
3. if an approval exists and is GRANTED (or EXCEPTION_GRANTED), consume it under the
   per-instance, per-task consumption key; a first consumption, or an
   ``ALREADY_CONSUMED`` whose holder is this same instance and task, satisfies the
   obligation; anything else does not;
4. when satisfied, return the upstream inputs with the Decision Authority result
   changed to ``NO_VETO`` and its ``required_approvals`` emptied, with a reason code
   naming the consumed approval. Composition, projection, ``validate_clearance`` and
   the RA-6 last-mile recheck then run exactly as they would for any other proposal.

Consumption happens in the SQLite ledger before the engine's Postgres transaction
commits (HR-3). A crash between the two leaves a CONSUMED approval whose holder names
this instance; the re-drive resolves ``ALREADY_CONSUMED`` with that holder and is
satisfied, so the approval is used exactly once and the action runs exactly once.

The package reads no clock. Every instant comes from the injected ``clock``, which a
composition root supplies from the same time base the runtime uses.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from ugence_agent_runtime_governance import CompositionInputs
from ugence_approval_workflow import (
    ApprovalRecord,
    ApprovalState,
    ApprovalWorkflowPort,
    ConsumptionResult,
    EligibilityRefused,
    IllegalTransitionError,
)
from ugence_governance_contracts.api import Validity
from ugence_risk_authority_runtime.contracts import GovernanceVetoResult, VetoDisposition

from .binding import (
    ProposalIdentity,
    approval_id_for_identity,
    consumer_ref_for,
    expected_consumption_id,
    identity_of,
    subject_for,
)
from .errors import ClockDisciplineError, ContractViolation

__all__ = [
    "REASON_APPROVAL_CONSUMED",
    "BindingState",
    "BindingOutcome",
    "ApprovalBoundInputSource",
]

#: Reason code added to the Decision Authority result when a consumed approval
#: satisfied its HOLD. Composition carries it into the evaluation's reason codes.
REASON_APPROVAL_CONSUMED = "GR_APPROVAL_CONSUMED"

#: Default validity of a request this source raises. A parked instance that nobody
#: decides within the window expires in the ledger and must be re-requested, which is
#: a new ordinal — deliberately not automatic.
DEFAULT_REQUEST_VALIDITY = timedelta(days=7)


class BindingState(str, Enum):
    """What the binding found. Only ``SATISFIED`` changes the composition inputs."""

    NOT_APPROVAL_BOUND = "NOT_APPROVAL_BOUND"
    UPSTREAM_ABSENT = "UPSTREAM_ABSENT"
    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    AWAITING_DECISION = "AWAITING_DECISION"
    SATISFIED = "SATISFIED"
    CONSUMED_BY_OTHER = "CONSUMED_BY_OTHER"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class BindingOutcome:
    """A typed account of one binding, for tests and for the review surface."""

    state: BindingState
    approval_id: str = ""
    approval_state: Optional[ApprovalState] = None
    consumption: Optional[ConsumptionResult] = None
    holder: str = ""
    reason: str = ""

    @property
    def satisfied(self) -> bool:
        return self.state is BindingState.SATISFIED


def _is_escalate_bound(inputs: CompositionInputs) -> bool:
    """True when the hook would project this composition to ESCALATE (HR-5).

    Mirrors the projection rule: a Decision Authority HOLD whose restrictions carry at
    least one required approval. A HOLD with none is released only by an upstream
    authority change and is never offered to a human here.
    """

    da = inputs.decision_authority
    if getattr(da, "disposition", None) is not VetoDisposition.HOLD:
        return False
    restrictions = getattr(da, "restrictions", None)
    labels = getattr(restrictions, "required_approvals", None)
    try:
        return bool(labels)
    except Exception:  # noqa: BLE001 - an unreadable label set is not an obligation
        return False


def _released(da: GovernanceVetoResult, approval_id: str) -> GovernanceVetoResult:
    """The same Decision Authority result with its HOLD satisfied.

    Only the disposition and the ``required_approvals`` label set change. Every other
    restriction the authority contributed stays exactly as tightening as it was.
    """

    restrictions = replace(da.restrictions, required_approvals=frozenset())
    return replace(
        da,
        disposition=VetoDisposition.NO_VETO,
        reason_codes=tuple(da.reason_codes) + (f"{REASON_APPROVAL_CONSUMED}:{approval_id}",),
        restrictions=restrictions,
    )


class ApprovalBoundInputSource:
    """Wrap a deployment's input source with approval binding and consumption."""

    maturity = "REFERENCE_GRADE_SHADOW_ONLY"

    def __init__(
        self,
        *,
        upstream: Any,
        ledger: ApprovalWorkflowPort,
        tenant_id: str,
        required_role: str,
        clock: Callable[[], datetime],
        requester_ref: str = "governed-review",
        request_validity: timedelta = DEFAULT_REQUEST_VALIDITY,
    ) -> None:
        if not hasattr(upstream, "inputs_for"):
            raise ContractViolation("upstream must be a GovernanceInputSource (inputs_for)")
        if not isinstance(ledger, ApprovalWorkflowPort):
            raise ContractViolation("ledger must satisfy ApprovalWorkflowPort")
        for name, value in (("tenant_id", tenant_id), ("required_role", required_role),
                            ("requester_ref", requester_ref)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{name} must be a non-empty string")
        if not callable(clock):
            raise ContractViolation("clock must be callable and return a tz-aware datetime")
        if not isinstance(request_validity, timedelta) or request_validity <= timedelta(0):
            raise ContractViolation("request_validity must be a positive timedelta")
        self._upstream = upstream
        self._ledger = ledger
        self._tenant = tenant_id.strip()
        self._role = required_role.strip()
        self._clock = clock
        self._requester = requester_ref.strip()
        self._request_validity = request_validity

    # -- GovernanceInputSource ------------------------------------------------
    def inputs_for(self, proposal: Any) -> Optional[CompositionInputs]:
        upstream = self._upstream.inputs_for(proposal)
        if upstream is None:
            return None
        if not _is_escalate_bound(upstream):
            return upstream
        outcome = self.bind(identity_of(proposal))
        if not outcome.satisfied:
            return upstream
        return replace(upstream,
                       decision_authority=_released(upstream.decision_authority,
                                                    outcome.approval_id))

    # -- the binding, callable on its own ---------------------------------------
    def bind(self, identity: ProposalIdentity) -> BindingOutcome:
        """Request, or consume, the approval bound to this proposal identity.

        Idempotent per (identity, ledger state): repeated calls converge on the same
        outcome, and only the first consumption writes a consumption row.
        """

        as_of = self._now()
        approval_id = approval_id_for_identity(identity, tenant_id=self._tenant,
                                               requester_ref=self._requester)
        record = self._ledger.get_approval(approval_id)
        if record is None:
            return self._request(identity, approval_id, as_of)

        state = self._ledger.state_at(approval_id, as_of=as_of)
        if state is ApprovalState.REQUESTED:
            return self._present(record, approval_id, as_of)
        if state in (ApprovalState.PENDING, ApprovalState.EXCEPTION_REQUESTED):
            return BindingOutcome(BindingState.AWAITING_DECISION, approval_id, state)
        if state in (ApprovalState.GRANTED, ApprovalState.EXCEPTION_GRANTED,
                     ApprovalState.CONSUMED):
            return self._consume(identity, approval_id, state, as_of)
        return BindingOutcome(BindingState.REFUSED, approval_id, state,
                              reason=f"approval is {state.value}; not consumable")

    def outcome_for(self, proposal: Any) -> BindingOutcome:
        """Observe the binding for a proposal without consuming anything."""

        identity = identity_of(proposal)
        as_of = self._now()
        approval_id = approval_id_for_identity(identity, tenant_id=self._tenant,
                                               requester_ref=self._requester)
        record = self._ledger.get_approval(approval_id)
        if record is None:
            return BindingOutcome(BindingState.NOT_APPROVAL_BOUND, approval_id,
                                  reason="no approval has been requested for this proposal")
        state = self._ledger.state_at(approval_id, as_of=as_of)
        if state is ApprovalState.CONSUMED:
            holder = record.consumer_ref
            mine = holder == consumer_ref_for(identity)
            return BindingOutcome(BindingState.SATISFIED if mine else BindingState.CONSUMED_BY_OTHER,
                                  approval_id, state, holder=holder)
        return BindingOutcome(BindingState.AWAITING_DECISION, approval_id, state)

    # -- internals ----------------------------------------------------------------
    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ClockDisciplineError(
                "the injected clock must return a timezone-aware datetime"
            )
        return value

    def _request(self, identity: ProposalIdentity, approval_id: str,
                 as_of: datetime) -> BindingOutcome:
        subject = subject_for(identity, tenant_id=self._tenant)
        record = self._ledger.request_approval(
            subject, requested_by=self._requester, required_role=self._role,
            validity=Validity(issued_at=as_of, expires_at=as_of + self._request_validity),
            as_of=as_of,
            justification=f"governed proposal {identity.fingerprint[:16]} parked awaiting "
                          f"{self._role}",
        )
        if record.approval_id != approval_id:  # pragma: no cover - deterministic by construction
            raise ContractViolation("the ledger minted an approval id the binding did not derive")
        return self._present(record, approval_id, as_of)

    def _present(self, record: ApprovalRecord, approval_id: str,
                 as_of: datetime) -> BindingOutcome:
        try:
            presented = self._ledger.present_for_decision(approval_id, as_of=as_of)
        except EligibilityRefused as exc:
            return BindingOutcome(BindingState.REQUESTED, approval_id, ApprovalState.REQUESTED,
                                  reason=f"no eligible approver: {exc}")
        except IllegalTransitionError as exc:
            return BindingOutcome(BindingState.REFUSED, approval_id, record.state,
                                  reason=str(exc))
        return BindingOutcome(BindingState.PENDING, approval_id, presented.state)

    def _consume(self, identity: ProposalIdentity, approval_id: str,
                 state: ApprovalState, as_of: datetime) -> BindingOutcome:
        outcome = self._ledger.consume(
            approval_id, consumer_ref=consumer_ref_for(identity),
            subject_digest=identity.fingerprint, as_of=as_of,
        )
        result = outcome.result
        if result is ConsumptionResult.CONSUMED_FIRST:
            return BindingOutcome(BindingState.SATISFIED, approval_id, ApprovalState.CONSUMED,
                                  consumption=result, holder=outcome.consumption_id)
        if result is ConsumptionResult.ALREADY_CONSUMED:
            mine = expected_consumption_id(identity, tenant_id=self._tenant,
                                           approval_id=approval_id)
            if outcome.holder == mine:
                return BindingOutcome(BindingState.SATISFIED, approval_id,
                                      ApprovalState.CONSUMED, consumption=result,
                                      holder=outcome.holder,
                                      reason="already consumed by this instance and task")
            return BindingOutcome(BindingState.CONSUMED_BY_OTHER, approval_id,
                                  ApprovalState.CONSUMED, consumption=result,
                                  holder=outcome.holder)
        return BindingOutcome(BindingState.REFUSED, approval_id, state, consumption=result,
                              reason=outcome.reason or result.value)
