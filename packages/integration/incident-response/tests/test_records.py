"""The records: derived identity, required evidence, the lifecycle, and the one rule
the whole package exists to protect — closing an incident restores nothing."""

from __future__ import annotations

import dataclasses

import pytest

from ugence_incident_response import (
    ContainmentLiftRefused,
    ContainmentState,
    ContractViolation,
    IllegalTransitionError,
    IncidentRecord,
    IncidentState,
    LEGAL_TRANSITIONS,
    STATE_RANK,
    TERMINAL_STATES,
    incident_id_for,
    is_legal_transition,
)

from _fixtures import (
    SEVERITY,
    SUBJECT,
    T0,
    T1,
    T2,
    T3,
    TENANT,
    audit_ref,
    contained,
    containment,
    incident,
    lift,
    proposal,
)


# --------------------------------------------------------------------------- #
# Evidence: the record points, it does not hold
# --------------------------------------------------------------------------- #
def test_an_incident_must_name_at_least_one_audit_entry():
    with pytest.raises(ContractViolation, match="at least one AuditReference"):
        incident(evidence=())


def test_the_evidence_must_be_the_governance_contracts_reference():
    from ugence_governance_contracts.contracts import audit as gc_audit
    import ugence_incident_response as pkg

    assert pkg.AuditReference is gc_audit.AuditReference

    class NotAReference:
        def canonical_digest(self):
            return "0" * 64

    with pytest.raises(ContractViolation, match="mints no audit reference"):
        incident(evidence=(NotAReference(),))


def test_the_record_carries_digests_not_evidence_bodies():
    record = incident()
    stored = record.to_dict()
    assert stored["evidence"] == list(record.evidence_digests())
    names = {f.name for f in dataclasses.fields(IncidentRecord)}
    for forbidden in ("body", "payload", "entry", "log", "content", "cause", "diagnosis"):
        assert forbidden not in names, forbidden


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def test_the_incident_id_is_derived_and_a_chosen_one_is_refused():
    refs = (audit_ref(),)
    derived = incident_id_for(TENANT, SUBJECT, refs, T0)
    assert derived.startswith("inc_")
    with pytest.raises(ContractViolation, match="must be the derived id"):
        IncidentRecord(incident_id="inc_chosen", tenant_id=TENANT, subject_ref=SUBJECT,
                       severity_label=SEVERITY, evidence=refs, opened_at=T0,
                       opened_by="operator-1")


def test_different_evidence_or_instants_are_different_incidents():
    base = incident().incident_id
    assert incident(evidence=(audit_ref("e:2", content="other"),)).incident_id != base
    assert incident(opened=T1).incident_id != base
    assert incident(subject="envelope:env-2").incident_id != base
    assert incident(tenant="tenant-b").incident_id != base
    # Re-recording the same observation at the same instant is the same incident.
    assert incident().incident_id == base


def test_the_severity_label_is_recorded_and_never_interpreted():
    for label in ("sev-1", "P0", "whatever-the-org-calls-it"):
        assert incident(severity=label).severity_label == label
    surface = {n for n in dir(incident()) if not n.startswith("_")}
    assert not surface & {"severity", "rank", "priority", "escalate", "is_critical"}


# --------------------------------------------------------------------------- #
# The lifecycle
# --------------------------------------------------------------------------- #
def test_every_legal_transition_is_forward_only():
    for current, targets in LEGAL_TRANSITIONS.items():
        for target in targets:
            assert STATE_RANK[target] > STATE_RANK[current], (current, target)
    assert TERMINAL_STATES == frozenset({IncidentState.CLOSED})
    assert not is_legal_transition(IncidentState.CLOSED, IncidentState.OPEN)


def test_an_incident_advances_and_closes():
    record = incident()
    assert record.is_open and record.state is IncidentState.OPEN
    contained = record.advanced_to(IncidentState.CONTAINMENT_REQUESTED)
    proposed = contained.advanced_to(IncidentState.REMEDIATION_PROPOSED)
    closed = proposed.closed(at=T3, by="operator-2")
    assert closed.state is IncidentState.CLOSED and not closed.is_open
    assert closed.closed_at == T3 and closed.closed_by == "operator-2"


def test_a_closed_incident_never_reopens():
    closed = incident().closed(at=T3, by="operator-2")
    for target in IncidentState:
        with pytest.raises(IllegalTransitionError):
            closed.advanced_to(target)
    with pytest.raises(IllegalTransitionError):
        closed.closed(at=T3, by="operator-2")


def test_a_closed_state_and_a_closed_instant_agree():
    record = incident()
    with pytest.raises(ContractViolation, match="closed_at"):
        dataclasses.replace(record, state=IncidentState.CLOSED)
    with pytest.raises(ContractViolation, match="closed_at"):
        dataclasses.replace(record, closed_at=T3)


# --------------------------------------------------------------------------- #
# The rule the package exists for
# --------------------------------------------------------------------------- #
def test_closing_an_incident_does_not_touch_containment():
    """An incident that closed itself and silently restored service is how a
    containment becomes theatre. Closing records only that the incident is over."""

    record, _request = contained()
    assert record.is_contained

    closed = record.closed(at=T3, by="operator-2")
    assert closed.state is IncidentState.CLOSED
    assert closed.containment is ContainmentState.REQUESTED  # untouched
    assert closed.is_contained, "closing must never lift containment"


def test_containment_cannot_be_lifted_by_rewriting_the_record():
    """The bypass a name-scan would miss: ``dataclasses.replace`` onto ``LIFTED``.

    A containment state is admissible only with the record that produced it, so
    fabricating the state without a :class:`ContainmentLift` is refused at
    construction rather than merely undiscoverable.
    """

    record, request = contained()

    with pytest.raises(ContractViolation, match="LIFTED requires"):
        dataclasses.replace(record, containment=ContainmentState.LIFTED)
    with pytest.raises(ContainmentLiftRefused, match="admissible lift"):
        dataclasses.replace(record, containment=ContainmentState.LIFTED,
                            containment_lift=lift(containment(
                                incident(subject="envelope:env-2"))))
    with pytest.raises(ContractViolation, match="NONE carries no"):
        dataclasses.replace(record, containment=ContainmentState.NONE)
    with pytest.raises(ContractViolation, match="REQUESTED requires"):
        dataclasses.replace(incident(), containment=ContainmentState.REQUESTED)

    # And the one legitimate path does work, on the real lift record.
    lifted = record.containment_lifted(lift(request))
    assert lifted.containment is ContainmentState.LIFTED
    assert lifted.containment_lift == lift(request)


def test_closing_is_not_a_route_to_lifting():
    """Closing an incident leaves the only lift path exactly where it was."""

    record, request = contained()
    closed = record.closed(at=T3, by="operator-2")
    assert closed.is_contained

    # Closing did not make the lift admissible-by-default, and it did not make it
    # inadmissible either: the lift is still its own decision, still required.
    with pytest.raises(ContractViolation, match="LIFTED requires"):
        dataclasses.replace(closed, containment=ContainmentState.LIFTED)
    assert closed.containment_lifted(lift(request)).containment is ContainmentState.LIFTED


def test_a_lift_from_a_different_containment_is_refused():
    record, request = contained()
    other_request = containment(incident(subject="envelope:env-2"))
    with pytest.raises(ContainmentLiftRefused, match="request_digest does not match"):
        record.containment_lifted(lift(other_request))
    with pytest.raises(ContainmentLiftRefused, match="only a REQUESTED"):
        incident().containment_lifted(lift(request))
