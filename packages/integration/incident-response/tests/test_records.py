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


def test_the_invariant_cannot_be_inherited_away():
    """A subclass overriding ``__post_init__`` would inherit the shape without the
    rules — one line, no type-system fight. Subclassing is refused outright."""

    with pytest.raises(TypeError, match="may not be subclassed"):
        class _Evil(IncidentRecord):  # pragma: no cover - the class body never runs
            def __post_init__(self):
                pass


def test_an_inadmissible_state_cannot_be_revived_from_a_pickle():
    """``pickle`` never calls ``__init__``, so ``__setstate__`` re-runs the invariant.

    Without it a record could be serialised, edited in transit, and revived reporting
    ``LIFTED`` with no lift behind it.
    """

    import pickle

    record, request = contained()
    lifted = record.containment_lifted(lift(request))

    # An honest round trip survives unchanged.
    assert pickle.loads(pickle.dumps(lifted)) == lifted
    assert pickle.loads(pickle.dumps(record)) == record

    # A doctored payload — the containment advanced, the lift left absent — does not.
    doctored = dict(record.__dict__, containment=ContainmentState.LIFTED)
    with pytest.raises(ContractViolation, match="LIFTED requires"):
        object.__new__(IncidentRecord).__setstate__(doctored)

    # And that is the exact path pickle takes to rebuild one.
    assert type(record).__setstate__ is IncidentRecord.__setstate__


def test_a_lift_from_a_different_containment_is_refused():
    record, request = contained()
    other_request = containment(incident(subject="envelope:env-2"))
    with pytest.raises(ContainmentLiftRefused, match="request_digest does not match"):
        record.containment_lifted(lift(other_request))
    with pytest.raises(ContainmentLiftRefused, match="only a REQUESTED"):
        incident().containment_lifted(lift(request))


# --------------------------------------------------------------------------- #
# Containment and remediation records
# --------------------------------------------------------------------------- #
def test_a_containment_request_records_who_asked_and_why():
    request = containment()
    assert request.target_ref and request.reason and request.requested_by
    assert request.requested_at == T1
    assert len(request.record_digest()) == 64
    for blank in ("target_ref", "reason", "requested_by"):
        with pytest.raises(ContractViolation):
            dataclasses.replace(request, **{blank: "  "})


def test_a_remediation_proposal_may_cite_a_compensation_requirement():
    plain = proposal()
    assert not plain.cites_compensation and plain.compensation_ref == ""
    citing = proposal(compensation="comp-42")
    assert citing.cites_compensation and citing.compensation_ref == "comp-42"


def test_no_second_compensation_type_or_status_is_minted():
    import ugence_incident_response as pkg

    assert not [n for n in pkg.__all__ if "Compensation" in n]
    assert not [n for n in pkg.__all__ if n.endswith("ApprovalStatus")]


def test_every_instant_must_be_timezone_aware():
    import datetime as dt

    naive = dt.datetime(2026, 3, 1, 9, 0)
    with pytest.raises(ContractViolation, match="timezone-aware"):
        incident(opened=naive)
    with pytest.raises(ContractViolation, match="timezone-aware"):
        containment(at=naive)
    with pytest.raises(ContractViolation, match="timezone-aware"):
        proposal(at=naive)


# --------------------------------------------------------------------------- #
# The refusals themselves. A refusal nobody exercises is a refusal nobody has.
# --------------------------------------------------------------------------- #
def test_containment_may_be_requested_once_and_only_for_this_incident():
    """Every guard on the one mutator that opens containment.

    A third review found all three of these untested: the happy path was the only
    call site in the suite, so the "a second request is a new incident, not a
    re-request" rule the docstring names could have been deleted silently.
    """

    record = incident().advanced_to(IncidentState.CONTAINMENT_REQUESTED)
    request = containment(record)

    with pytest.raises(ContractViolation, match="must be a ContainmentRequest"):
        record.containment_requested(object())

    other = containment(incident(subject="envelope:env-2"))
    with pytest.raises(ContractViolation, match="different incident"):
        record.containment_requested(other)
    cross_tenant = dataclasses.replace(request, tenant_id="tenant-b")
    with pytest.raises(ContractViolation, match="different incident"):
        record.containment_requested(cross_tenant)

    contained_record = record.containment_requested(request)
    with pytest.raises(ContractViolation, match="already REQUESTED"):
        contained_record.containment_requested(request)


def test_the_containment_fields_must_hold_the_records_they_claim_to():
    """Direct construction is checked exactly as the mutators are."""

    record, request = contained()

    with pytest.raises(ContractViolation, match="must be a ContainmentRequest"):
        dataclasses.replace(record, containment_request="not-a-record")
    with pytest.raises(ContractViolation, match="must be a ContainmentLift"):
        dataclasses.replace(record.containment_lifted(lift(request)),
                            containment_lift="not-a-record")
    with pytest.raises(ContractViolation, match="REQUESTED carries no lift"):
        dataclasses.replace(record, containment_lift=lift(request))
    with pytest.raises(ContractViolation, match="different incident"):
        dataclasses.replace(record, containment_request=dataclasses.replace(
            request, tenant_id="tenant-b"))
    with pytest.raises(ContractViolation, match="requires the ContainmentRequest"):
        dataclasses.replace(record, containment_request=None)


def test_the_state_fields_must_be_the_enums_they_declare():
    record = incident()
    with pytest.raises(ContractViolation, match="must be a IncidentState"):
        dataclasses.replace(record, state="OPEN")
    with pytest.raises(ContractViolation, match="must be a ContainmentState"):
        dataclasses.replace(record, containment="NONE")


def test_the_transition_tables_agree_with_the_forward_only_rule():
    """The rank check in ``require_transition`` is redundant with the table *today*.

    That is the point of asserting it: if a later edit adds a backward or sideways
    edge to ``LEGAL_TRANSITIONS``, this names it rather than letting the two
    disagree silently.
    """

    for current, targets in LEGAL_TRANSITIONS.items():
        for target in targets:
            assert STATE_RANK[target] > STATE_RANK[current], (current, target)
    assert set(LEGAL_TRANSITIONS) == set(IncidentState)
    assert all(LEGAL_TRANSITIONS[s] == frozenset() for s in TERMINAL_STATES)


def test_a_non_datetime_instant_is_refused_before_the_timezone_is_read():
    with pytest.raises(ContractViolation, match="must be a datetime"):
        incident(opened="2026-03-01T09:00:00Z")
    with pytest.raises(ContractViolation, match="must be a datetime"):
        containment(at=1772355600)


def test_optional_text_refuses_a_non_string():
    record = incident()
    with pytest.raises(ContractViolation):
        dataclasses.replace(record, summary=object())


# --------------------------------------------------------------------------- #
# Mutation coverage, stated honestly
# --------------------------------------------------------------------------- #
# `scripts/mutation_sweep.py` disables each refusal in src/ in turn and reports the
# ones no test catches. It ships rather than being described, because the claim has
# been wrong four times: the sweep behind it saw only `raise` guards and missed
# `reasons.append`; then it reached only records.py and states.py and missed
# journal.py's filters; then it reported by line, hiding which of two clauses on one
# line had survived — which concealed that nothing asserted contained_incidents()
# actually filters on containment; then it skipped `else`-bearing guards and
# unconditional raises while its docstring claimed all of src/. Run it; the number
# is whatever it is today.
#
# Four sites survive by design. Each is redundant with a twin that runs downstream
# on the same call, so it cannot be killed alone:
#
#   IncidentRecord.containment_requested's cross-incident check -> the same rule
#       re-runs in _require_containment_evidence via replace()
#   IncidentRecord.containment_lifted's lift_refusals re-check    -> likewise
#   require_transition's two checks (states.py) are mutually redundant for every
#       state pair the tables define today
#
# They are kept as defence in depth, since each becomes load-bearing the moment its
# twin's inputs change, and named by function rather than line because a drifted
# citation reads as rigor it no longer has. What is asserted instead is that they
# cannot diverge silently: the transition tables are pinned forward-only, and the
# two records.py guards are pinned against their construction-time twin below.
def test_the_redundant_containment_guards_have_a_twin_that_agrees():
    """The downstream invariant refuses exactly what the method's own guard refuses."""

    record, request = contained()
    foreign = containment(incident(subject="envelope:env-2"))

    # containment_requested's cross-incident guard, and its twin on construction.
    fresh = incident().advanced_to(IncidentState.CONTAINMENT_REQUESTED)
    with pytest.raises(ContractViolation, match="different incident"):
        fresh.containment_requested(foreign)
    with pytest.raises(ContractViolation, match="different incident"):
        dataclasses.replace(fresh, containment=ContainmentState.REQUESTED,
                            containment_request=foreign)

    # containment_lifted's refusal check, and its twin on construction.
    with pytest.raises(ContainmentLiftRefused, match="request_digest does not match"):
        record.containment_lifted(lift(foreign))
    with pytest.raises(ContainmentLiftRefused, match="admissible lift"):
        dataclasses.replace(record, containment=ContainmentState.LIFTED,
                            containment_lift=lift(foreign))
