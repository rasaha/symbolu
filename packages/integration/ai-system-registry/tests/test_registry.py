"""The read seam and its pure selectors: in-force filtering, exact label matching,
the supersession chain, and the fact that the Protocol can only read."""

from __future__ import annotations

import pytest

from ugence_ai_system_registry import (
    ContractViolation,
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
    a = registration(binding(version="1.0.0"), supersedes="reg_b")
    b_reg = registration(binding(version="1.1.0"), supersedes=a.registration_id)
    forged = type(a)(registration_id="reg_b", binding=b_reg.binding, owner_ref=b_reg.owner_ref,
                     classification_label=b_reg.classification_label, validity=b_reg.validity,
                     supersedes=a.registration_id)
    chain = supersession_chain((a, forged), a.registration_id)
    assert [r.registration_id for r in chain] == [a.registration_id, "reg_b"]


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
