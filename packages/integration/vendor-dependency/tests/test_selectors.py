"""The read seam and its pure selectors: in-force filtering, tenant isolation, exact
posture and policy-reference matching, the supersession chain, and the fact that
the Protocol can only read."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_vendor_dependency import (
    ContractViolation,
    VendorDependencyPort,
    VendorRiskLabel,
    declaration_id_for,
    declared_at,
    select_by_policy_ref,
    select_by_risk_posture,
    select_for_system,
    select_for_tenant,
    select_for_vendor,
    supersession_chain,
    supersession_refusals,
)

from _fixtures import (
    AFTER_WINDOW,
    BEFORE_WINDOW,
    OTHER_POLICY,
    OTHER_POSTURE,
    OTHER_VENDOR,
    POLICY,
    POSTURE,
    T1,
    T2,
    TENANT,
    VENDOR,
    binding,
    declaration,
    window,
)


def _order(d):
    return (d.tenant_id, d.vendor_ref, d.system_id, d.system_version, d.declaration_id)


def _world():
    """Two declarations in one tenant, one in another, one already lapsed."""

    current = declaration()
    other_vendor = declaration(binding("credit-scorer", version="2.0.0"), vendor=OTHER_VENDOR,
                               posture=OTHER_POSTURE, policy=OTHER_POLICY)
    other_tenant = declaration(binding(tenant="tenant-b"))
    lapsed = declaration(binding("retired-bot"), validity=window(BEFORE_WINDOW, days=1))
    return current, other_vendor, other_tenant, lapsed


# --------------------------------------------------------------------------- #
# In-force filtering
# --------------------------------------------------------------------------- #
def test_every_selector_returns_only_declarations_in_force():
    current, other_vendor, other_tenant, lapsed = _world()
    everything = (current, other_vendor, other_tenant, lapsed)
    assert declared_at(everything, T1) == tuple(sorted(
        (current, other_vendor, other_tenant), key=_order))
    assert lapsed not in declared_at(everything, T1)
    assert declared_at(everything, AFTER_WINDOW) == ()
    assert select_for_tenant(everything, tenant_id=TENANT, as_of=AFTER_WINDOW) == ()


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #
def test_no_selector_ever_returns_another_tenants_declaration():
    current, other_vendor, other_tenant, lapsed = _world()
    everything = (current, other_vendor, other_tenant, lapsed)

    assert select_for_tenant(everything, tenant_id=TENANT, as_of=T1) == tuple(sorted(
        (current, other_vendor), key=_order))
    assert select_for_tenant(everything, tenant_id="tenant-b", as_of=T1) == (other_tenant,)
    assert select_for_tenant(everything, tenant_id="tenant-c", as_of=T1) == ()
    # The same vendor, system, posture and policy exist in both tenants; every
    # narrowing selector still answers within one tenant only.
    assert select_for_vendor(everything, tenant_id="tenant-b", vendor_ref=VENDOR, as_of=T1) == (
        other_tenant,)
    assert select_for_system(everything, tenant_id="tenant-b", system_id="hiring-screener",
                             as_of=T1) == (other_tenant,)
    assert select_by_risk_posture(everything, tenant_id="tenant-b",
                                  risk_posture_label="elevated", as_of=T1) == (other_tenant,)
    assert select_by_policy_ref(everything, tenant_id="tenant-b", policy_ref=POLICY,
                                as_of=T1) == (other_tenant,)
    for answer in (
        select_for_vendor(everything, tenant_id=TENANT, vendor_ref=VENDOR, as_of=T1),
        select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener", as_of=T1),
        select_by_risk_posture(everything, tenant_id=TENANT, risk_posture_label="elevated",
                               as_of=T1),
        select_by_policy_ref(everything, tenant_id=TENANT, policy_ref=POLICY, as_of=T1),
    ):
        assert answer == (current,)
        assert all(d.tenant_id == TENANT for d in answer)


# --------------------------------------------------------------------------- #
# Narrowing selectors
# --------------------------------------------------------------------------- #
def test_vendor_and_system_are_selected_exactly():
    current, other_vendor, _, _ = _world()
    everything = (current, other_vendor)
    assert select_for_vendor(everything, tenant_id=TENANT, vendor_ref=VENDOR, as_of=T1) == (current,)
    assert select_for_vendor(everything, tenant_id=TENANT, vendor_ref=OTHER_VENDOR, as_of=T1) == (
        other_vendor,)
    assert select_for_vendor(everything, tenant_id=TENANT, vendor_ref="vendor://nope", as_of=T1) == ()
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="1.2.0", as_of=T1) == (current,)
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="9.9.9", as_of=T1) == ()


def test_a_posture_and_a_policy_ref_are_matched_exactly_and_never_interpreted():
    current, other_vendor, _, _ = _world()
    everything = (current, other_vendor)
    assert select_by_risk_posture(everything, tenant_id=TENANT, risk_posture_label=POSTURE.label,
                                  as_of=T1) == (current,)
    assert select_by_risk_posture(everything, tenant_id=TENANT,
                                  risk_posture_label=OTHER_POSTURE.label, as_of=T1) == (other_vendor,)
    assert select_by_policy_ref(everything, tenant_id=TENANT, policy_ref=OTHER_POLICY,
                                as_of=T1) == (other_vendor,)
    # No grade: "elevated" does not include "critical", and case or substring never
    # widens the answer. A policy reference is text, so a near-miss version matches nothing.
    for near_miss in ("Elevated", "elev", "elevated-plus", "critical", "high"):
        assert select_by_risk_posture(everything, tenant_id=TENANT, risk_posture_label=near_miss,
                                      as_of=T1) == ()
    for near_miss in ("policy://vendor-standard/v2", "policy://vendor-standard", "v3"):
        assert select_by_policy_ref(everything, tenant_id=TENANT, policy_ref=near_miss,
                                    as_of=T1) == ()


def test_selectors_refuse_blank_arguments_and_naive_instants():
    everything = (declaration(),)
    with pytest.raises(ContractViolation):
        select_for_tenant(everything, tenant_id="  ", as_of=T1)
    with pytest.raises(ContractViolation):
        select_for_vendor(everything, tenant_id=TENANT, vendor_ref="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_for_system(everything, tenant_id=TENANT, system_id="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_by_risk_posture(everything, tenant_id=TENANT, risk_posture_label="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_by_policy_ref(everything, tenant_id=TENANT, policy_ref=" ", as_of=T1)
    with pytest.raises(ContractViolation):
        declared_at(everything, dt.datetime(2026, 3, 1))


# --------------------------------------------------------------------------- #
# The supersession chain
# --------------------------------------------------------------------------- #
def test_the_chain_reconstructs_history_and_is_not_filtered_by_instant():
    first = declaration(validity=window(BEFORE_WINDOW, days=1))
    second = declaration(posture=OTHER_POSTURE, supersedes=first.declaration_id)
    third = declaration(posture=OTHER_POSTURE, policy=OTHER_POLICY, supersedes=second.declaration_id)
    world = (first, second, third)
    assert supersession_chain(world, third.declaration_id) == (third, second, first)
    assert supersession_chain(world, first.declaration_id) == (first,)
    assert supersession_chain(world, "vdd_nope") == ()
    assert first not in select_for_tenant(world, tenant_id=TENANT, as_of=T2)


def test_a_cycle_terminates_rather_than_looping():
    b_id = declaration_id_for(binding(), VENDOR, OTHER_POSTURE, POLICY, window())
    a = declaration(posture=POSTURE, supersedes=b_id)
    b_decl = declaration(posture=OTHER_POSTURE, supersedes=a.declaration_id)
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
    other_vendor = declaration(vendor=OTHER_VENDOR, supersedes=first.declaration_id)
    assert supersession_chain((first, other_vendor), other_vendor.declaration_id) == (other_vendor,)


def test_the_chain_stops_at_a_predecessor_that_is_absent_from_the_collection():
    orphan = declaration(posture=VendorRiskLabel("low"), supersedes="vdd_missing")
    assert supersession_chain((orphan,), orphan.declaration_id) == (orphan,)


# --------------------------------------------------------------------------- #
# The port reads and cannot write
# --------------------------------------------------------------------------- #
def test_the_port_declares_only_read_methods():
    surface = {n for n in dir(VendorDependencyPort) if not n.startswith("_")}
    assert surface == {"get_declaration", "declarations_for_tenant", "declarations_for_vendor",
                       "declarations_for_system", "declarations_by_risk_posture"}
    for forbidden in ("declare", "put", "add", "upsert", "delete", "revoke", "resolve",
                      "verify", "score", "grade", "approve", "contact", "sync"):
        assert forbidden not in surface


def test_no_implementation_of_the_port_ships():
    import ugence_vendor_dependency as pkg

    implementations = [
        name for name in pkg.__all__
        if isinstance(getattr(pkg, name), type)
        and not getattr(getattr(pkg, name), "_is_protocol", False)
        and hasattr(getattr(pkg, name), "declarations_for_tenant")
    ]
    assert implementations == []
    assert isinstance(VendorDependencyPort, type) and VendorDependencyPort._is_protocol
