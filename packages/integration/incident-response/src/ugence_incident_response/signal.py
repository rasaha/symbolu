"""The RA-6 reassessment signal payload — built here, delivered by somebody else.

RA-6 owns authority lifecycle exclusively: observers **signal**, Risk Authority
**reassesses**, ``AuthorityLifecycleService`` is "the sole mutator" and the only
authenticated writer, and ActionGate enforces read-only
(``packages/integration/risk-authority-status-runtime/README.md:14-27``). This
package is an observer, so it builds the payload and **stops there**.

It holds no writer, no client and no reference to the lifecycle service, so it
cannot mutate authority state even by mistake. Delivery is a composition root's
job — and a composition root that never delivers is a valid deployment: the
incident record stands on its own.

The payload is **field-compatible** with
``risk_authority.domain.authority_signal.AuthorityReassessmentSignal``, not identical
to it, and it is deliberately not the same object — the same seam-without-import
relationship ``authority-directory`` has to the approval workflow's
``ApproverEligibilityPort``. Both sides use ``str`` enums, so member values compare
and hash equal; but this payload keeps ``target_type``/``target_id`` **flat** where
RA-6 nests them in a ``SignalTarget``, so a composition root delivering the signal
must adapt it — see :meth:`ReassessmentSignalPayload.as_signal_fields`.
Nothing here is accepted verbatim, and claiming otherwise would describe an
integration nobody wrote. The cross-package contract is pinned by
``tests/integration/test_ra6_signal_contract.py``, which imports RA-6, performs that
one construction, and asserts ``validation_errors() == ()``.

The kinds are deliberately a subset: this package can only ever report what it
observed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ._canon import domain_digest, iso, optional_text, require_nonempty, require_tzaware
from .errors import ContractViolation
from .records import ContainmentRequest, IncidentRecord

__all__ = [
    "SIGNAL_SCHEMA_VERSION", "SignalTargetType", "SignalChangeType",
    "ReassessmentSignalPayload", "signal_for_containment",
]

#: RA-6's current wire-schema version. A payload declaring anything else is
#: rejected fail-closed by the reassessor, so it is pinned rather than guessed.
SIGNAL_SCHEMA_VERSION = "1"


class SignalTargetType(str, Enum):
    """What the signal asks Risk Authority to reassess. Values match RA-6's."""

    ENVELOPE = "ENVELOPE"
    SUBJECT = "SUBJECT"
    MODEL = "MODEL"
    WORKFLOW = "WORKFLOW"
    POLICY = "POLICY"
    TENANT = "TENANT"


class SignalChangeType(str, Enum):
    """The categories an incident may report.

    A deliberate **subset** of RA-6's: ``TENANT_EMERGENCY_STOP`` is privileged —
    RA-6 §12 admits it only over a stronger emergency-authorized write path — and
    this package holds no write path at all, so it may not name it. Nor does it
    name categories owned by other observers (``EVIDENCE_INVALIDATED``,
    ``POLICY_SUPERSEDED``, and so on): reporting somebody else's category would be
    claiming an observation this package did not make.
    """

    RUNTIME_RISK_ESCALATED = "RUNTIME_RISK_ESCALATED"
    EXECUTION_EFFECT_MISMATCH = "EXECUTION_EFFECT_MISMATCH"


@dataclass(frozen=True)
class ReassessmentSignalPayload:
    """A neutral, authority-free payload. Built, never sent.

    Every field is a platform-neutral scalar or tuple, so the payload can cross to
    RA-6's reassessor without either package importing the other.
    """

    schema_version: str
    event_id: str
    tenant_id: str
    target_type: SignalTargetType
    target_id: str
    change_type: SignalChangeType
    source: str
    source_version: str
    observed_at: datetime
    reason: str
    correlation_id: str
    evidence_refs: tuple[str, ...] = ()
    #: Controls RA-6 should reconsider alongside the evidence. Present because
    #: ``AuthorityReassessmentSignal`` carries it: omitting a field the receiving
    #: type has would silently drop whatever a caller meant to say.
    control_refs: tuple[str, ...] = ()
    prior_state_ref: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("schema_version", "event_id", "tenant_id", "source",
                     "source_version", "reason", "correlation_id"):
            object.__setattr__(self, name, require_nonempty(
                getattr(self, name), f"ReassessmentSignalPayload.{name}"))
        object.__setattr__(self, "target_id",
                           optional_text(self.target_id, "ReassessmentSignalPayload.target_id"))
        for name in ("evidence_refs", "control_refs"):
            values = tuple(getattr(self, name))
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    raise ContractViolation(
                        f"ReassessmentSignalPayload.{name} entries must be non-blank strings")
            object.__setattr__(self, name, values)
        if not isinstance(self.target_type, SignalTargetType):
            raise ContractViolation("target_type must be a SignalTargetType member")
        if not isinstance(self.change_type, SignalChangeType):
            raise ContractViolation("change_type must be a SignalChangeType member")
        if self.schema_version != SIGNAL_SCHEMA_VERSION:
            raise ContractViolation(
                f"schema_version must be {SIGNAL_SCHEMA_VERSION!r}; RA-6 rejects any "
                "other version fail-closed, so building one would be building a payload "
                "that can never be acted on")
        # A non-TENANT target names something specific; a TENANT target does not
        # (RA-6 carries the tenant on the signal itself).
        if self.target_type is not SignalTargetType.TENANT and not self.target_id:
            raise ContractViolation(f"a {self.target_type.value} target requires a target_id")
        require_tzaware(self.observed_at, "ReassessmentSignalPayload.observed_at")

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version, "event_id": self.event_id,
            "tenant_id": self.tenant_id, "target_type": self.target_type.value,
            "target_id": self.target_id, "change_type": self.change_type.value,
            "source": self.source, "source_version": self.source_version,
            "observed_at": iso(self.observed_at, "observed_at"), "reason": self.reason,
            "correlation_id": self.correlation_id,
            "evidence_refs": list(self.evidence_refs),
            "control_refs": list(self.control_refs),
            "prior_state_ref": self.prior_state_ref or "",
        }

    def as_signal_fields(self) -> dict:
        """The fields RA-6's ``AuthorityReassessmentSignal`` takes **as they are**.

        Two are missing, and their absence is the honest part. RA-6 nests
        ``target_type``/``target_id`` in its own ``SignalTarget``, and it
        ``isinstance``-checks its own ``SignalChangeType``; constructing either type
        here would mean importing RA-6. So a composition root supplies ``target=``
        and ``change_type=`` itself, from :attr:`target_type`, :attr:`target_id` and
        :attr:`change_type` — whose *values* are equal to RA-6's, which is why the
        adaptation is two constructor calls and not a translation table.

        ``tests/integration/test_ra6_signal_contract.py`` performs exactly this and
        asserts the result's ``validation_errors()`` is empty.
        """

        return {
            "schema_version": self.schema_version, "event_id": self.event_id,
            "tenant_id": self.tenant_id, "source": self.source,
            "source_version": self.source_version, "observed_at": self.observed_at,
            "reason": self.reason, "correlation_id": self.correlation_id,
            "evidence_refs": self.evidence_refs, "control_refs": self.control_refs,
            "prior_state_ref": self.prior_state_ref,
        }

    def canonical_digest(self) -> str:
        return domain_digest("reassessment_signal", self.to_dict())


def signal_for_containment(
    incident: IncidentRecord, request: ContainmentRequest, *,
    target_type: SignalTargetType, change_type: SignalChangeType,
    source_version: str, correlation_id: str,
) -> ReassessmentSignalPayload:
    """Build the payload a containment request would justify. Nothing is delivered.

    The evidence references travel as digests, so the signal names where to read
    without carrying what was read.
    """

    return ReassessmentSignalPayload(
        schema_version=SIGNAL_SCHEMA_VERSION,
        event_id=request.record_digest()[:32],
        tenant_id=incident.tenant_id,
        target_type=target_type,
        target_id="" if target_type is SignalTargetType.TENANT else request.target_ref,
        change_type=change_type,
        source="ugence_incident_response",
        source_version=require_nonempty(source_version, "source_version"),
        observed_at=request.requested_at,
        reason=request.reason,
        correlation_id=require_nonempty(correlation_id, "correlation_id"),
        evidence_refs=incident.evidence_digests(),
        prior_state_ref=incident.incident_id)
