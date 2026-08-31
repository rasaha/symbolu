"""AuthorityReassessmentSignal — the neutral material-change signal (RA-6 §13).

A signal is the ONLY thing an observer (evidence assurance, policy management,
Runtime Assurance, telemetry, ActionGate observability) may emit toward Risk
Authority. It is deliberately *neutral*: it never carries ``ALLOW``, an
authorization decision, a scope grant, or any machine-authority token. It can
only ever *trigger reassessment*; Risk Authority alone owns the authority
consequence (RA-6 §6, invariant I2/I7).

The type is a frozen, stdlib-only value object owned by the leaf. There is no
field through which a producer could smuggle authority — the absence is
structural, not merely validated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

__all__ = [
    "AUTHORITY_SIGNAL_SCHEMA_VERSION",
    "SUPPORTED_SIGNAL_SCHEMA_VERSIONS",
    "SignalChangeType",
    "SignalTargetType",
    "SignalTarget",
    "AuthorityReassessmentSignal",
]

#: Current signal wire-schema version. A signal declaring an unsupported version
#: is rejected fail-closed (never reassessed, never a state change).
AUTHORITY_SIGNAL_SCHEMA_VERSION = "1"
SUPPORTED_SIGNAL_SCHEMA_VERSIONS = frozenset({AUTHORITY_SIGNAL_SCHEMA_VERSION})


class SignalChangeType(str, Enum):
    """The bounded category of a material change (RA-6 §13).

    These are the only recognized categories. An unknown category is rejected
    fail-closed. ``TENANT_EMERGENCY_STOP`` is privileged (RA-6 §12): it is the
    one category that may map to an immediate tenant-epoch advance, and only
    when presented over the stronger emergency-authorized write path.

    ``EXECUTION_EFFECT_MISMATCH`` is the neutral post-execution effect-mismatch
    category emitted by RA-8 (execution/effect reconciliation, spec §7/D-D): a
    *material* discrepancy between the authorized action and the observed external
    effect. It is additive, non-authority, and — like every ordinary observer
    category — can only *trigger* reassessment; RA-6 alone owns the consequence.
    """

    EVIDENCE_INVALIDATED = "EVIDENCE_INVALIDATED"
    CONTROL_CHANGED = "CONTROL_CHANGED"
    POLICY_SUPERSEDED = "POLICY_SUPERSEDED"
    WORKFLOW_SUPERSEDED = "WORKFLOW_SUPERSEDED"
    MODEL_INVALIDATED = "MODEL_INVALIDATED"
    RUNTIME_RISK_ESCALATED = "RUNTIME_RISK_ESCALATED"
    EXECUTION_EFFECT_MISMATCH = "EXECUTION_EFFECT_MISMATCH"
    TENANT_EMERGENCY_STOP = "TENANT_EMERGENCY_STOP"


class SignalTargetType(str, Enum):
    """What a signal asks Risk Authority to reassess (RA-6 §13 ``target``)."""

    ENVELOPE = "ENVELOPE"
    SUBJECT = "SUBJECT"
    MODEL = "MODEL"
    WORKFLOW = "WORKFLOW"
    POLICY = "POLICY"
    TENANT = "TENANT"


@dataclass(frozen=True)
class SignalTarget:
    """The subject of a reassessment signal.

    ``target_id`` is the envelope/subject/model/workflow/policy identifier; for
    a ``TENANT`` target it is unused (the tenant is carried on the signal).
    """

    target_type: SignalTargetType
    target_id: str = ""


@dataclass(frozen=True)
class AuthorityReassessmentSignal:
    """A neutral material-change signal (RA-6 §13).

    Contains only what is necessary to *cause* reassessment. Every field has a
    stated trust purpose (see the spec table); no field carries authority.
    """

    schema_version: str
    event_id: str
    tenant_id: str
    target: SignalTarget
    change_type: SignalChangeType
    source: str
    source_version: str
    observed_at: datetime
    reason: str
    correlation_id: str
    evidence_refs: tuple[str, ...] = ()
    control_refs: tuple[str, ...] = ()
    prior_state_ref: Optional[str] = None

    def validation_errors(self) -> tuple[str, ...]:
        """Return fail-closed reasons this signal is malformed/untrusted.

        Empty tuple == structurally acceptable *for intake* (dedupe +
        reassessment still decide the consequence). A non-empty result means the
        signal must be ignored (``IGNORE_EVENT``) and can never cause a state
        change (RA-6 §14).
        """

        reasons: list[str] = []
        if self.schema_version not in SUPPORTED_SIGNAL_SCHEMA_VERSIONS:
            reasons.append(f"unsupported signal schema_version {self.schema_version!r}")
        if not self.event_id:
            reasons.append("missing event_id")
        if not self.tenant_id:
            reasons.append("missing tenant_id")
        if not isinstance(self.change_type, SignalChangeType):
            reasons.append("unknown change_type")
        if not isinstance(self.target, SignalTarget):
            reasons.append("missing target")
        elif not isinstance(self.target.target_type, SignalTargetType):
            reasons.append("unknown target_type")
        elif (
            self.target.target_type is not SignalTargetType.TENANT
            and not self.target.target_id
        ):
            reasons.append(
                f"missing target_id for target_type {self.target.target_type.value}"
            )
        if not self.source:
            reasons.append("missing source")
        if not self.correlation_id:
            reasons.append("missing correlation_id")
        return tuple(reasons)
