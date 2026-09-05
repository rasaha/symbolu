"""Lifting containment is a separate, justified decision — and the RA-6 payload is
built here and delivered by somebody else."""

from __future__ import annotations

import dataclasses

import pytest

from ugence_incident_response import (
    SIGNAL_SCHEMA_VERSION,
    ContainmentLiftRefused,
    ContainmentState,
    ContractViolation,
    IncidentState,
    ReassessmentSignalPayload,
    SignalChangeType,
    SignalTargetType,
    contained_incidents,
    lift_refusals,
    open_incidents,
    require_admissible_lift,
    signal_for_containment,
)

from _fixtures import (
    T0,
    T1,
    T2,
    T3,
    TENANT,
    contained,
    containment,
    incident,
    lift,
)


# --------------------------------------------------------------------------- #
# Lifting is separate, and must answer a specific request
# --------------------------------------------------------------------------- #
def test_an_admissible_lift_answers_its_own_request():
    inc = incident()
    request = containment(inc)
    assert lift_refusals(lift(request), request, inc) == ()
    require_admissible_lift(lift(request), request, inc)


def test_a_lift_that_answers_no_request_is_refused():
    with pytest.raises(ContainmentLiftRefused, match="does not exist"):
        require_admissible_lift(lift(containment()), None)


def test_a_lift_may_not_be_retargeted_retenanted_or_reattached():
    inc = incident()
    request = containment(inc)
    for changed, expected in (
        ({"target_ref": "envelope:other"}, "name the target"),
        ({"tenant_id": "tenant-b"}, "cross tenants"),
        ({"incident_id": "inc_other"}, "belong to the incident"),
        ({"request_digest": "0" * 64}, "does not match"),
    ):
        bad = dataclasses.replace(lift(request), **changed)
        reasons = "; ".join(lift_refusals(bad, request, None))
        assert expected in reasons, (changed, reasons)


def test_a_lift_may_not_precede_the_containment_it_lifts():
    request = containment(at=T2)
    reasons = lift_refusals(lift(request, at=T1), request, None)
    assert any("may not precede" in r for r in reasons)


def test_a_lift_is_never_justified_by_the_incident_being_closed():
    """The asymmetry, stated as a test: closing is not a reason to resume."""

    inc = incident()
    request = containment(inc)
    closed = inc.advanced_to(IncidentState.CONTAINMENT_REQUESTED).closed(at=T3, by="operator-2")
    # A lift still needs its own author and justification; closure changes nothing.
    admissible = lift(request)
    assert admissible.justification and admissible.lifted_by
    assert lift_refusals(admissible, request, closed) == ()
    with pytest.raises(ContractViolation):
        dataclasses.replace(admissible, justification="   ")
    with pytest.raises(ContractViolation):
        dataclasses.replace(admissible, lifted_by="")


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def test_a_contained_but_closed_incident_stays_visible():
    """The case a lifecycle-driven view would hide, and the one that matters most."""

    record, _request = contained()
    closed = record.closed(at=T3, by="operator-2")
    world = (closed,)
    assert open_incidents(world, tenant_id=TENANT) == ()          # not open
    assert contained_incidents(world, tenant_id=TENANT) == (closed,)  # still contained


def test_reads_are_tenant_scoped():
    mine, theirs = incident(), incident(tenant="tenant-b")
    assert open_incidents((mine, theirs), tenant_id=TENANT) == (mine,)


# --------------------------------------------------------------------------- #
# The RA-6 payload: built, never sent
# --------------------------------------------------------------------------- #
def _payload():
    inc = incident()
    return inc, signal_for_containment(
        inc, containment(inc), target_type=SignalTargetType.ENVELOPE,
        change_type=SignalChangeType.RUNTIME_RISK_ESCALATED,
        source_version="0.1.0", correlation_id="corr-1")


def test_the_payload_is_neutral_and_names_where_to_read():
    inc, payload = _payload()
    assert isinstance(payload, ReassessmentSignalPayload)
    assert payload.schema_version == SIGNAL_SCHEMA_VERSION == "1"
    assert payload.source == "ugence_incident_response"
    assert payload.tenant_id == inc.tenant_id
    assert payload.evidence_refs == inc.evidence_digests()
    assert payload.prior_state_ref == inc.incident_id
    assert len(payload.canonical_digest()) == 64


def test_the_payload_carries_no_authority_field():
    names = {f.name for f in dataclasses.fields(ReassessmentSignalPayload)}
    for forbidden in ("authority", "envelope", "signature", "epoch", "revoked",
                      "decision", "outcome", "token"):
        assert forbidden not in names, forbidden


def test_the_change_types_are_a_deliberate_subset_of_ra6s():
    """TENANT_EMERGENCY_STOP is privileged and needs a write path this package lacks."""

    assert {m.value for m in SignalChangeType} == {
        "RUNTIME_RISK_ESCALATED", "EXECUTION_EFFECT_MISMATCH"}
    assert "TENANT_EMERGENCY_STOP" not in {m.value for m in SignalChangeType}


def test_the_enum_values_are_exactly_ra6s_by_value():
    """Structural compatibility, checked against RA-6 itself rather than a literal.

    A hand-written copy of RA-6's spellings would keep passing after RA-6 changed
    them, which is the failure this package's whole seam-without-import design
    depends on catching. So the real enums are imported *by the test* — never by
    the package — and compared.
    """

    ra6 = pytest.importorskip("risk_authority.domain.authority_signal",
                              reason="RA-6 is not installed in this environment")

    assert {m.value for m in SignalTargetType} == {m.value for m in ra6.SignalTargetType}

    ours = {m.value for m in SignalChangeType}
    theirs = {m.value for m in ra6.SignalChangeType}
    assert ours < theirs, "our change types must be a strict subset of RA-6's"
    assert "TENANT_EMERGENCY_STOP" not in ours

    # str-enum equality is what lets the value cross without either import.
    assert SignalTargetType.ENVELOPE == ra6.SignalTargetType.ENVELOPE.value
    assert SIGNAL_SCHEMA_VERSION in ra6.SUPPORTED_SIGNAL_SCHEMA_VERSIONS


def test_a_non_tenant_target_must_name_something():
    inc = incident()
    request = dataclasses.replace(containment(inc), target_ref="envelope:env-1")
    with pytest.raises(ContractViolation, match="requires a target_id"):
        ReassessmentSignalPayload(
            schema_version="1", event_id="e", tenant_id=TENANT,
            target_type=SignalTargetType.ENVELOPE, target_id="",
            change_type=SignalChangeType.RUNTIME_RISK_ESCALATED, source="s",
            source_version="v", observed_at=T1, reason="r", correlation_id="c")
    # A TENANT target carries no id: RA-6 reads the tenant from the signal itself.
    tenant_payload = signal_for_containment(
        inc, request, target_type=SignalTargetType.TENANT,
        change_type=SignalChangeType.RUNTIME_RISK_ESCALATED,
        source_version="0.1.0", correlation_id="corr-1")
    assert tenant_payload.target_id == ""


def test_an_unsupported_schema_version_is_refused_at_construction():
    with pytest.raises(ContractViolation, match="schema_version"):
        ReassessmentSignalPayload(
            schema_version="2", event_id="e", tenant_id=TENANT,
            target_type=SignalTargetType.TENANT, target_id="",
            change_type=SignalChangeType.RUNTIME_RISK_ESCALATED, source="s",
            source_version="v", observed_at=T1, reason="r", correlation_id="c")


def test_nothing_in_the_package_can_deliver_the_payload():
    """Not a name scan of the curated types: every callable they reach.

    A name-only check passes for a method called ``dispatch`` and for a constructor
    that quietly accepts a ``client=``. So this walks each exported callable's
    signature too, and refuses transport-shaped parameters — the thing a deliverer
    would actually need to be given.
    """

    import inspect

    import ugence_incident_response as pkg

    forbidden_names = ("send", "deliver", "emit", "publish", "post", "submit",
                       "dispatch", "notify", "reassess", "revoke", "advance_epoch",
                       "write", "execute", "rollback", "apply")
    forbidden_params = ("client", "session", "transport", "connection", "conn",
                        "channel", "producer", "publisher", "sink", "endpoint",
                        "url", "socket", "writer", "bus", "queue")

    def check(owner: str, name: str, value) -> None:
        assert name not in forbidden_names, f"{owner}.{name}"
        try:
            signature = inspect.signature(value)
        except (TypeError, ValueError):
            return
        for parameter in signature.parameters:
            assert parameter.lower().lstrip("_") not in forbidden_params, (
                f"{owner}.{name}({parameter})")

    for exported in pkg.__all__:
        value = getattr(pkg, exported)
        if callable(value):
            check("ugence_incident_response", exported, value)
        if isinstance(value, type):
            for name, member in inspect.getmembers(value, callable):
                if not name.startswith("_"):
                    check(exported, name, member)
