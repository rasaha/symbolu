"""The read seam and its pure selectors: in-force filtering, tenant isolation, exact
label and purpose matching, the supersession chain, and the fact that the Protocol
can only read."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_data_use_admission import (
    ContractViolation,
    DataUseDeclarationPort,
    declaration_id_for,
    declared_at,
    select_by_classification,
    select_by_purpose,
    select_for_data,
    select_for_system,
    select_for_tenant,
    supersession_chain,
    supersession_refusals,
)

from _fixtures import (
    AFTER_WINDOW,
    BEFORE_WINDOW,
    DATA,
    LABEL,
    OTHER_DATA,
    OTHER_LABEL,
    OTHER_PURPOSE,
    PURPOSE,
    T1,
    T2,
    TENANT,
    binding,
    declaration,
    window,
)


def _order(d):
    return (d.tenant_id, d.data_ref, d.system_id, d.system_version, d.declaration_id)


def _world():
    """Two declarations in one tenant, one in another, one already lapsed."""

    current = declaration()
    other_data = declaration(binding("credit-scorer", version="2.0.0"), data_ref=OTHER_DATA,
                             label=OTHER_LABEL, purpose=OTHER_PURPOSE)
    other_tenant = declaration(binding(tenant="tenant-b"))
    lapsed = declaration(binding("retired-bot"), validity=window(BEFORE_WINDOW, days=1))
    return current, other_data, other_tenant, lapsed


# --------------------------------------------------------------------------- #
# In-force filtering
# --------------------------------------------------------------------------- #
def test_every_selector_returns_only_declarations_in_force():
    current, other_data, other_tenant, lapsed = _world()
    everything = (current, other_data, other_tenant, lapsed)

    assert declared_at(everything, T1) == tuple(sorted(
        (current, other_data, other_tenant), key=_order))
    assert lapsed not in declared_at(everything, T1)
    assert declared_at(everything, AFTER_WINDOW) == ()
    assert select_for_tenant(everything, tenant_id=TENANT, as_of=AFTER_WINDOW) == ()


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #
def test_no_selector_ever_returns_another_tenants_declaration():
    current, other_data, other_tenant, lapsed = _world()
    everything = (current, other_data, other_tenant, lapsed)

    assert select_for_tenant(everything, tenant_id=TENANT, as_of=T1) == tuple(sorted(
        (current, other_data), key=_order))
    assert select_for_tenant(everything, tenant_id="tenant-b", as_of=T1) == (other_tenant,)
    assert select_for_tenant(everything, tenant_id="tenant-c", as_of=T1) == ()
    # The same data, system, label and purpose exist in both tenants; every
    # narrowing selector still answers within one tenant only.
    assert select_for_data(everything, tenant_id="tenant-b", data_ref=DATA, as_of=T1) == (
        other_tenant,)
    assert select_for_system(everything, tenant_id="tenant-b", system_id="hiring-screener",
                             as_of=T1) == (other_tenant,)
    assert select_by_classification(everything, tenant_id="tenant-b",
                                    classification_label="confidential", as_of=T1) == (
        other_tenant,)
    assert select_by_purpose(everything, tenant_id="tenant-b", purpose_label=PURPOSE,
                             as_of=T1) == (other_tenant,)
    for answer in (
        select_for_data(everything, tenant_id=TENANT, data_ref=DATA, as_of=T1),
        select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener", as_of=T1),
        select_by_classification(everything, tenant_id=TENANT,
                                 classification_label="confidential", as_of=T1),
        select_by_purpose(everything, tenant_id=TENANT, purpose_label=PURPOSE, as_of=T1),
    ):
        assert answer == (current,)
        assert all(d.tenant_id == TENANT for d in answer)


# --------------------------------------------------------------------------- #
# Narrowing selectors
# --------------------------------------------------------------------------- #
def test_data_and_system_are_selected_exactly():
    current, other_data, _, _ = _world()
    everything = (current, other_data)
    assert select_for_data(everything, tenant_id=TENANT, data_ref=DATA, as_of=T1) == (current,)
    assert select_for_data(everything, tenant_id=TENANT, data_ref=OTHER_DATA, as_of=T1) == (
        other_data,)
    assert select_for_data(everything, tenant_id=TENANT, data_ref="dataset://nope", as_of=T1) == ()
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="1.2.0", as_of=T1) == (current,)
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="9.9.9", as_of=T1) == ()


def test_a_label_and_a_purpose_are_matched_exactly_and_never_interpreted():
    current, other_data, _, _ = _world()
    everything = (current, other_data)
    assert select_by_classification(everything, tenant_id=TENANT,
                                    classification_label=LABEL.label, as_of=T1) == (current,)
    assert select_by_classification(everything, tenant_id=TENANT,
                                    classification_label=OTHER_LABEL.label, as_of=T1) == (
        other_data,)
    assert select_by_purpose(everything, tenant_id=TENANT, purpose_label=OTHER_PURPOSE,
                             as_of=T1) == (other_data,)
    # No taxonomy: a label the organization never used simply matches nothing, and
    # case or substring never widens the answer. "public" does not imply
    # "confidential" and nothing here says otherwise.
    for near_miss in ("Confidential", "confid", "confidential-plus", "restricted"):
        assert select_by_classification(everything, tenant_id=TENANT,
                                        classification_label=near_miss, as_of=T1) == ()
    for near_miss in ("Candidate-Screening", "screening", "candidate-screening-v2"):
        assert select_by_purpose(everything, tenant_id=TENANT, purpose_label=near_miss,
                                 as_of=T1) == ()


def test_selectors_refuse_blank_arguments_and_naive_instants():
    everything = (declaration(),)
    with pytest.raises(ContractViolation):
        select_for_tenant(everything, tenant_id="  ", as_of=T1)
    with pytest.raises(ContractViolation):
        select_for_data(everything, tenant_id=TENANT, data_ref="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_for_system(everything, tenant_id=TENANT, system_id="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_by_classification(everything, tenant_id=TENANT, classification_label="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_by_purpose(everything, tenant_id=TENANT, purpose_label=" ", as_of=T1)
    with pytest.raises(ContractViolation):
        declared_at(everything, dt.datetime(2026, 3, 1))


# --------------------------------------------------------------------------- #
# The supersession chain
# --------------------------------------------------------------------------- #
def test_the_chain_reconstructs_history_and_is_not_filtered_by_instant():
    first = declaration(validity=window(BEFORE_WINDOW, days=1))          # already lapsed
    second = declaration(label=OTHER_LABEL, supersedes=first.declaration_id)
    third = declaration(label=OTHER_LABEL, purpose=OTHER_PURPOSE,
                        supersedes=second.declaration_id)
    world = (first, second, third)

    assert supersession_chain(world, third.declaration_id) == (third, second, first)
    assert supersession_chain(world, first.declaration_id) == (first,)
    assert supersession_chain(world, "dud_nope") == ()
    assert first not in select_for_tenant(world, tenant_id=TENANT, as_of=T2)


def test_a_cycle_terminates_rather_than_looping():
    a_label, b_label = LABEL, OTHER_LABEL
    b_id = declaration_id_for(binding(), DATA, b_label, PURPOSE, window())
    a = declaration(label=a_label, supersedes=b_id)
    b_decl = declaration(label=b_label, supersedes=a.declaration_id)
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

    other_data = declaration(data_ref=OTHER_DATA, supersedes=first.declaration_id)
    assert supersession_chain((first, other_data), other_data.declaration_id) == (other_data,)


def test_the_chain_stops_at_a_predecessor_that_is_absent_from_the_collection():
    orphan = declaration(label=OTHER_LABEL, supersedes="dud_missing")
    assert supersession_chain((orphan,), orphan.declaration_id) == (orphan,)


# --------------------------------------------------------------------------- #
# The port reads and cannot write
# --------------------------------------------------------------------------- #
def test_the_port_declares_only_read_methods():
    surface = {n for n in dir(DataUseDeclarationPort) if not n.startswith("_")}
    assert surface == {"get_declaration", "declarations_for_tenant", "declarations_for_data",
                       "declarations_for_system", "declarations_by_classification"}
    for forbidden in ("declare", "admit", "put", "add", "upsert", "delete", "revoke",
                      "authorize", "classify", "redact", "minimize", "enforce", "evaluate",
                      "sync"):
        assert forbidden not in surface


def test_no_implementation_of_the_port_ships():
    import ugence_data_use_admission as pkg

    implementations = [
        name for name in pkg.__all__
        if isinstance(getattr(pkg, name), type)
        and not getattr(getattr(pkg, name), "_is_protocol", False)
        and hasattr(getattr(pkg, name), "declarations_for_tenant")
    ]
    assert implementations == []
    assert isinstance(DataUseDeclarationPort, type) and DataUseDeclarationPort._is_protocol
