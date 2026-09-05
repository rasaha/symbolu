"""The read seam and its pure selectors: in-force filtering, exact label matching,
the supersession chain, and the fact that the Protocol can only read."""

from __future__ import annotations

import pytest

from ugence_ai_system_registry import (
    ContractViolation,
    registration_id_for,
    SystemRegistryPort,
    registered_at,
    select_by_classification,
    select_for_system,
    select_for_tenant,
    supersession_chain,
)

from _fixtures import (
    AFTER_WINDOW,
    BEFORE_WINDOW,
    LABEL,
    OTHER_LABEL,
    OWNER,
    T0,
    T1,
    T2,
    TENANT,
    binding,
    registration,
    window,
)


def _world():
    """Two systems in one tenant, one in another, one already lapsed."""

    current = registration()
    other_system = registration(binding("credit-scorer", version="2.0.0"), label=OTHER_LABEL)
    other_tenant = registration(binding(tenant="tenant-b"))
    lapsed = registration(binding("retired-bot"), validity=window(BEFORE_WINDOW, days=1))
    return current, other_system, other_tenant, lapsed


# --------------------------------------------------------------------------- #
# In-force filtering
# --------------------------------------------------------------------------- #
def test_every_selector_returns_only_registrations_in_force():
    current, other_system, other_tenant, lapsed = _world()
    everything = (current, other_system, other_tenant, lapsed)

    assert registered_at(everything, T1) == tuple(sorted(
        (current, other_system, other_tenant),
        key=lambda r: (r.tenant_id, r.system_id, r.system_version, r.registration_id)))
    assert lapsed not in registered_at(everything, T1)
    assert registered_at(everything, AFTER_WINDOW) == ()

    assert select_for_tenant(everything, tenant_id=TENANT, as_of=T1) == tuple(sorted(
        (current, other_system),
        key=lambda r: (r.tenant_id, r.system_id, r.system_version, r.registration_id)))
    assert select_for_tenant(everything, tenant_id=TENANT, as_of=AFTER_WINDOW) == ()


def test_a_system_is_selected_by_id_and_optionally_by_version():
    current, other_system, _, _ = _world()
    everything = (current, other_system)
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             as_of=T1) == (current,)
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="1.2.0", as_of=T1) == (current,)
    assert select_for_system(everything, tenant_id=TENANT, system_id="hiring-screener",
                             system_version="9.9.9", as_of=T1) == ()
    assert select_for_system(everything, tenant_id="tenant-b", system_id="hiring-screener",
                             as_of=T1) == ()


def test_a_label_is_matched_exactly_and_never_interpreted():
    current, other_system, _, _ = _world()
    everything = (current, other_system)
    assert select_by_classification(everything, tenant_id=TENANT,
                                    classification_label=LABEL, as_of=T1) == (current,)
    assert select_by_classification(everything, tenant_id=TENANT,
                                    classification_label=OTHER_LABEL, as_of=T1) == (other_system,)
    # No taxonomy: a label the organization never used simply matches nothing, and
    # case or substring never widens the answer.
    for near_miss in ("High-Risk", "risk", "high-risk-plus"):
        assert select_by_classification(everything, tenant_id=TENANT,
                                        classification_label=near_miss, as_of=T1) == ()


def test_selectors_refuse_blank_arguments_and_naive_instants():
    import datetime as dt

    everything = (registration(),)
    with pytest.raises(ContractViolation):
        select_for_tenant(everything, tenant_id="  ", as_of=T1)
    with pytest.raises(ContractViolation):
        select_for_system(everything, tenant_id=TENANT, system_id="", as_of=T1)
    with pytest.raises(ContractViolation):
        select_by_classification(everything, tenant_id=TENANT, classification_label="", as_of=T1)
    with pytest.raises(ContractViolation):
        registered_at(everything, dt.datetime(2026, 3, 1))


# --------------------------------------------------------------------------- #
# The supersession chain
# --------------------------------------------------------------------------- #
def test_the_chain_reconstructs_history_and_is_not_filtered_by_instant():
    first = registration(validity=window(BEFORE_WINDOW, days=1))          # already lapsed
    second = registration(binding(version="1.3.0"), supersedes=first.registration_id)
    third = registration(binding(version="1.4.0"), supersedes=second.registration_id)
    world = (first, second, third)

    assert supersession_chain(world, third.registration_id) == (third, second, first)
    assert supersession_chain(world, first.registration_id) == (first,)
    assert supersession_chain(world, "reg_nope") == ()
    # The lapsed predecessor is absent from a current answer but present in history.
    assert first not in select_for_tenant(world, tenant_id=TENANT, as_of=T2)


def test_a_cycle_terminates_rather_than_looping():
    """Ids are derived from the binding, owner and window — not from ``supersedes`` —
    so a genuine two-way cycle is still constructible, and must still terminate."""

    b_binding, a_binding = binding(version="1.1.0"), binding(version="1.0.0")
    b_id = registration_id_for(b_binding, OWNER, window())
    a = registration(a_binding, supersedes=b_id)
    b_reg = registration(b_binding, supersedes=a.registration_id)
    assert b_reg.registration_id == b_id

    chain = supersession_chain((a, b_reg), a.registration_id)
    assert [r.registration_id for r in chain] == [a.registration_id, b_id]


# --------------------------------------------------------------------------- #
# The chain never splices an inadmissible link (regression: independent review)
# --------------------------------------------------------------------------- #
def test_the_chain_stops_at_a_link_the_packages_own_rule_rejects():
    """A ``supersedes`` across tenants is refused by ``supersession_refusals``; the
    chain must not walk it into a history that spans two tenants."""

    from ugence_ai_system_registry import supersession_refusals

    predecessor = registration(binding("sysA", tenant="tenant-a"))
    cross_tenant = registration(binding("sysB", tenant="tenant-z"),
                                supersedes=predecessor.registration_id)
    assert supersession_refusals(cross_tenant, predecessor)  # the rule rejects it
    assert supersession_chain((predecessor, cross_tenant),
                              cross_tenant.registration_id) == (cross_tenant,)


def test_the_chain_stops_at_a_link_that_rebinds_the_same_identity():
    first = registration(validity=window(BEFORE_WINDOW, days=1))
    same_identity = registration(supersedes=first.registration_id)
    # Same binding, so D-3 rejects the supersession and the chain refuses to walk it.
    assert same_identity.binding_digest == first.binding_digest
    assert supersession_chain((first, same_identity),
                              same_identity.registration_id) == (same_identity,)


def test_the_chain_stops_at_a_predecessor_that_is_absent_from_the_collection():
    orphan = registration(binding(version="2.0.0"), supersedes="reg_missing")
    assert supersession_chain((orphan,), orphan.registration_id) == (orphan,)


# --------------------------------------------------------------------------- #
# The port reads and cannot write
# --------------------------------------------------------------------------- #
def test_the_port_declares_only_read_methods():
    surface = {n for n in dir(SystemRegistryPort) if not n.startswith("_")}
    assert surface == {"get_registration", "registrations_for_tenant",
                       "registrations_for_system", "registrations_by_classification"}
    for forbidden in ("register", "admit", "put", "add", "upsert", "delete", "revoke",
                      "promote", "approve", "gate", "resolve", "attest", "sync"):
        assert forbidden not in surface


def test_no_implementation_of_the_port_ships():
    """D-4: a Protocol is a seam, not an adapter."""

    import ugence_ai_system_registry as pkg

    implementations = [
        name for name in pkg.__all__
        if isinstance(getattr(pkg, name), type)
        and not getattr(getattr(pkg, name), "_is_protocol", False)
        and hasattr(getattr(pkg, name), "registrations_for_tenant")
    ]
    assert implementations == []
    assert isinstance(SystemRegistryPort, type) and SystemRegistryPort._is_protocol
