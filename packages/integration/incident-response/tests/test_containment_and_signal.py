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

from _fixtures import T0, T1, T2, T3, TENANT, containment, incident, lift


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

    contained = dataclasses.replace(
        incident().advanced_to(IncidentState.CONTAINMENT_REQUESTED),
        containment=ContainmentState.REQUESTED)
    closed = contained.closed(at=T3, by="operator-2")
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


def test_the_enum_values_match_ra6s_by_value():
    """Structural compatibility: both are str enums, so a payload crosses verbatim."""

    assert SignalTargetType.ENVELOPE == "ENVELOPE"
    assert SignalChangeType.RUNTIME_RISK_ESCALATED == "RUNTIME_RISK_ESCALATED"
    assert SignalTargetType.TENANT in frozenset({"TENANT", "SUBJECT"})


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
    import ugence_incident_response as pkg

    for name in pkg.__all__:
        value = getattr(pkg, name)
        surface = {n for n in dir(value) if not n.startswith("_")} if isinstance(value, type) else set()
        for forbidden in ("send", "deliver", "emit", "publish", "post", "submit",
                          "reassess", "revoke", "advance_epoch", "write"):
            assert forbidden not in surface, (name, forbidden)
