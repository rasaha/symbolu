"""Ugence Incident Response — incident records, containment requests, remediation proposals.

    THIS PACKAGE RECORDS AND PROPOSES.
    IT NEVER REVOKES, EXECUTES, ROLLS BACK, OR LIFTS ITS OWN CONTAINMENT.

Deliberately **not** an orchestrator. That word names optional workflow composition
that acquires no authority (`ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md:61`),
this package composes no workflow, and the one package that took the name reached
infrastructure mutation and needed a containment ADR to pull it back.

Every actor that could stop or fix something already exists and already owns that
power: RA-6 revokes authority, Decision Authority governs the remedial action, and a
human decides whether anything resumes. The gap this fills is the record and the
proposal — not a new authority.

Scoped and ratified by ``docs/architecture/ADR_UGENCE_INCIDENT_RESPONSE_SCOPING.md``.
A recorded incident is an input to somebody else's decision, not a decision.
"""

from __future__ import annotations

from ugence_governance_contracts.api import AuditReference

from ._canon import iso as canonical_instant
from .errors import (
    ContainmentLiftRefused,
    ContractViolation,
    IllegalTransitionError,
    IncidentResponseError,
)
from .journal import (
    IncidentJournalPort,
    contained_incidents,
    incidents_for_subject,
    lift_refusals,
    open_incidents,
    require_admissible_lift,
)
from .records import (
    INCIDENT_ID_PREFIX,
    ContainmentLift,
    ContainmentRequest,
    IncidentRecord,
    RemediationProposal,
    incident_id_for,
)
from .signal import (
    SIGNAL_SCHEMA_VERSION,
    ReassessmentSignalPayload,
    SignalChangeType,
    SignalTargetType,
    signal_for_containment,
)
from .states import (
    LEGAL_TRANSITIONS,
    OPEN_STATES,
    STATE_RANK,
    TERMINAL_STATES,
    ContainmentState,
    IncidentState,
    is_legal_transition,
    require_transition,
)
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    # the audit reference an incident cites, re-exported and never redefined
    "AuditReference",
    # records
    "IncidentRecord", "ContainmentRequest", "ContainmentLift", "RemediationProposal",
    "incident_id_for", "INCIDENT_ID_PREFIX",
    # lifecycle
    "IncidentState", "ContainmentState", "LEGAL_TRANSITIONS", "STATE_RANK",
    "TERMINAL_STATES", "OPEN_STATES", "is_legal_transition", "require_transition",
    # the RA-6 payload: built here, delivered by a composition root
    "ReassessmentSignalPayload", "SignalTargetType", "SignalChangeType",
    "signal_for_containment", "SIGNAL_SCHEMA_VERSION",
    # the read seam and its pure rules
    "IncidentJournalPort", "open_incidents", "incidents_for_subject",
    "contained_incidents", "lift_refusals", "require_admissible_lift",
    # helpers
    "canonical_instant",
    # errors
    "IncidentResponseError", "ContractViolation", "IllegalTransitionError",
    "ContainmentLiftRefused",
]
