"""The read seam and its pure selectors: in-force filtering, tenant isolation, exact
finding, evidence and exercise matching, the supersession chain, and the fact
that the Protocol can only read."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_agent_assurance_evidence import (
    AssuranceFindingLabel,
    AssuranceFindingPort,
    ContractViolation,
    declaration_id_for,
    declared_at,
    select_by_exercise,
    select_by_finding,
    select_for_evidence,
    select_for_system,
    select_for_tenant,
    supersession_chain,
    supersession_refusals,
)

from _fixtures import (
    AFTER_WINDOW,
    BEFORE_WINDOW,
    EXERCISE,
    FINDING,
    OTHER_EXERCISE,
    OTHER_FINDING,
    T1,
    T2,
    TENANT,
    binding,
    declaration,
    evidence,
    window,
)


def _order(d):
    return (d.tenant_id, d.system_id, d.system_version, d.evidence_id, d.declaration_id)


def _world():
    """Two findings in one tenant, one in another, one already lapsed."""

    current = declaration()
    other_system = declaration(binding("credit-scorer", version="2.0.0"),
                               ev=evidence("ev-cs-001", content="cs-report"),
                               finding=OTHER_FINDING, exercise=OTHER_EXERCISE)
    other_tenant = declaration(binding(tenant="tenant-b"))
    lapsed = declaration(binding("retired-bot"), ev=evidence("ev-old"),
                         validity=window(BEFORE_WINDOW, days=1))
    return current, other_system, other_tenant, lapsed


# --------------------------------------------------------------------------- #
# In-force filtering
# --------------------------------------------------------------------------- #
def test_every_selector_returns_only_declarations_in_force():
    current, other_system, other_tenant, lapsed = _world()
    everything = (current, other_system, other_tenant, lapsed)
    assert declared_at(everything, T1) == tuple(sorted(
        (current, other_system, other_tenant), key=_order))
    assert lapsed not in declared_at(everything, T1)
    assert declared_at(everything, AFTER_WINDOW) == ()
    assert select_for_tenant(everything, tenant_id=TENANT, as_of=AFTER_WINDOW) == ()


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #
def test_no_selector_ever_returns_another_tenants_declaration():
    current, other_system, other_tenant, lapsed = _world()
    everything = (current, other_system, other_tenant, lapsed)

    assert select_for_tenant(everything, tenant_id=TENANT, as_of=T1) == tuple(sorted(
        (current, other_system), key=_order))
    assert select_for_tenant(everything, tenant_id="tenant-b", as_of=T1) == (other_tenant,)
    assert select_for_tenant(everything, tenant_id="tenant-c", as_of=T1) == ()
    # The same evidence id, system, finding and exercise exist in both tenants; every
    # narrowing selector still answers within one tenant only.
    assert select_for_evidence(everything, tenant_id="tenant-b", evidence_id="ev-run7-001",
                               as_of=T1) == (other_tenant,)
    assert select_for_system(everything, tenant_id="tenant-b", system_id="hiring-screener",
                             as_of=T1) == (other_tenant,)
    assert select_by_finding(everything, tenant_id="tenant-b", finding_label=FINDING.label,
                             as_of=T1) == (other_tenant,)
    assert select_by_exercise(everything, tenant_id="tenant-b", exercise_ref=EXERCISE,
                              as_of=T1) == (other_tenant,)
    for answer in (
        select_for_evidence(everything, tenant_id=TENANT, evidence_id="ev-run7-001", as_of=T1),
        select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener", as_of=T1),
        select_by_finding(everything, tenant_id=TENANT, finding_label=FINDING.label, as_of=T1),
        select_by_exercise(everything, tenant_id=TENANT, exercise_ref=EXERCISE, as_of=T1),
    ):
        assert answer == (current,)
        assert all(d.tenant_id == TENANT for d in answer)


# --------------------------------------------------------------------------- #
# Narrowing selectors
# --------------------------------------------------------------------------- #
def test_evidence_and_system_are_selected_exactly():
    current, other_system, _, _ = _world()
    everything = (current, other_system)
    assert select_for_evidence(everything, tenant_id=TENANT, evidence_id="ev-run7-001",
                               as_of=T1) == (current,)
    assert select_for_evidence(everything, tenant_id=TENANT, evidence_id="ev-cs-001",
                               as_of=T1) == (other_system,)
    assert select_for_evidence(everything, tenant_id=TENANT, evidence_id="ev-nope", as_of=T1) == ()
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="1.2.0", as_of=T1) == (current,)
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="9.9.9", as_of=T1) == ()


def test_a_finding_and_an_exercise_are_matched_exactly_and_never_interpreted():
    current, other_system, _, _ = _world()
    everything = (current, other_system)
    assert select_by_finding(everything, tenant_id=TENANT, finding_label=FINDING.label,
                             as_of=T1) == (current,)
    assert select_by_finding(everything, tenant_id=TENANT, finding_label=OTHER_FINDING.label,
                             as_of=T1) == (other_system,)
    assert select_by_exercise(everything, tenant_id=TENANT, exercise_ref=OTHER_EXERCISE,
                              as_of=T1) == (other_system,)
    # No taxonomy: "prompt-injection-succeeded" does not include "prompt-injection",
    # and case or substring never widens the answer.
    for near_miss in ("Prompt-Injection-Succeeded", "prompt-injection", "injection", "critical"):
        assert select_by_finding(everything, tenant_id=TENANT, finding_label=near_miss,
                                 as_of=T1) == ()
    for near_miss in ("exercise://red-team/2026-q3-run-8", "exercise://red-team", "run-7"):
        assert select_by_exercise(everything, tenant_id=TENANT, exercise_ref=near_miss,
                                  as_of=T1) == ()


def test_selectors_refuse_blank_arguments_and_naive_instants():
    everything = (declaration(),)
    with pytest.raises(ContractViolation):
        select_for_tenant(everything, tenant_id="  ", as_of=T1)
    with pytest.raises(ContractViolation):
        select_for_evidence(everything, tenant_id=TENANT, evidence_id="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_for_system(everything, tenant_id=TENANT, system_id="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_by_finding(everything, tenant_id=TENANT, finding_label="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_by_exercise(everything, tenant_id=TENANT, exercise_ref=" ", as_of=T1)
    with pytest.raises(ContractViolation):
        declared_at(everything, dt.datetime(2026, 3, 1))


# --------------------------------------------------------------------------- #
# The supersession chain
# --------------------------------------------------------------------------- #
def test_the_chain_reconstructs_history_and_is_not_filtered_by_instant():
    first = declaration(validity=window(BEFORE_WINDOW, days=1))
    second = declaration(finding=OTHER_FINDING, supersedes=first.declaration_id)
    third = declaration(finding=OTHER_FINDING, exercise=OTHER_EXERCISE,
                        supersedes=second.declaration_id)
    world = (first, second, third)
    assert supersession_chain(world, third.declaration_id) == (third, second, first)
    assert supersession_chain(world, first.declaration_id) == (first,)
    assert supersession_chain(world, "afd_nope") == ()
    assert first not in select_for_tenant(world, tenant_id=TENANT, as_of=T2)


def test_a_cycle_terminates_rather_than_looping():
    b_id = declaration_id_for(binding(), evidence(), OTHER_FINDING, EXERCISE, window())
    a = declaration(finding=FINDING, supersedes=b_id)
    b_decl = declaration(finding=OTHER_FINDING, supersedes=a.declaration_id)
    assert b_decl.declaration_id == b_id
    chain = supersession_chain((a, b_decl), a.declaration_id)
    assert [d.declaration_id for d in chain] == [a.declaration_id, b_id]


def test_the_chain_stops_at_a_link_the_packages_own_rule_rejects():
    predecessor = declaration(binding("sysA", tenant="tenant-a"))
    cross_tenant = declaration(binding("sysB", tenant="tenant-z"),
                               supersedes=predecessor.declaration_id)
    assert supersession_refusals(cross_tenant, predecessor)
    assert supersession_chain((predecessor, cross_tenant),
                              cross_tenant.declaration_id) == (cross_tenant,)
    first = declaration(validity=window(BEFORE_WINDOW, days=1))
    unchanged = declaration(supersedes=first.declaration_id)
    assert supersession_chain((first, unchanged), unchanged.declaration_id) == (unchanged,)
    other_system = declaration(binding("credit-scorer"), supersedes=first.declaration_id)
    assert supersession_chain((first, other_system), other_system.declaration_id) == (other_system,)


def test_the_chain_stops_at_a_predecessor_that_is_absent_from_the_collection():
    orphan = declaration(finding=AssuranceFindingLabel("no-finding"), supersedes="afd_missing")
    assert supersession_chain((orphan,), orphan.declaration_id) == (orphan,)


# --------------------------------------------------------------------------- #
# The port reads and cannot write
# --------------------------------------------------------------------------- #
def test_the_port_declares_only_read_methods():
    surface = {n for n in dir(AssuranceFindingPort) if not n.startswith("_")}
    assert surface == {"get_declaration", "declarations_for_tenant", "declarations_for_system",
                       "declarations_for_evidence", "declarations_by_finding"}
    for forbidden in ("declare", "put", "add", "upsert", "delete", "revoke", "admit", "evaluate",
                      "score", "cite", "submit", "run", "probe", "sync"):
        assert forbidden not in surface


def test_no_implementation_of_the_port_ships():
    import ugence_agent_assurance_evidence as pkg

    implementations = [
        name for name in pkg.__all__
        if isinstance(getattr(pkg, name), type)
        and not getattr(getattr(pkg, name), "_is_protocol", False)
        and hasattr(getattr(pkg, name), "declarations_for_tenant")
    ]
    assert implementations == []
    assert isinstance(AssuranceFindingPort, type) and AssuranceFindingPort._is_protocol
