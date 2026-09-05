"""The registration record: the identity it borrows, the ceiling it inherits, the
window that makes it absent, and the supersession rule."""

from __future__ import annotations

import pytest

from ugence_governance_contracts.api import (
    SystemBindingAuthenticityStatus,
    Validity,
    ValidityStatus,
)
from ugence_governance_contracts.contracts import system_identity as gc_system_identity

from ugence_ai_system_registry import (
    AssessedSystemBinding,
    ContractViolation,
    RegistrationSupersessionError,
    SystemRegistration,
    registration_id_for,
    require_admissible_supersession,
    supersession_refusals,
)

from _fixtures import (
    AFTER_WINDOW,
    BEFORE_WINDOW,
    LABEL,
    OWNER,
    T0,
    T1,
    TENANT,
    binding,
    registration,
    window,
)


# --------------------------------------------------------------------------- #
# The identity is borrowed, never minted
# --------------------------------------------------------------------------- #
def test_the_binding_is_the_governance_contracts_type_itself():
    """Not a structural look-alike: the very same class object."""

    assert AssessedSystemBinding is gc_system_identity.AssessedSystemBinding
    assert registration().binding.__class__ is gc_system_identity.AssessedSystemBinding


def test_a_look_alike_binding_is_refused():
    class NotABinding:
        tenant_id = TENANT
        system_id = "x"
        system_version = "1"

        def canonical_digest(self):
            return "0" * 64

    with pytest.raises(ContractViolation, match="mints no system identity"):
        SystemRegistration(registration_id="reg_1", binding=NotABinding(), owner_ref=OWNER,
                           classification_label=LABEL, validity=window())  # binding checked first


def test_the_registration_inherits_the_bindings_ceiling():
    """A binding attests nothing, so neither does a registration."""

    reg = registration()
    assert reg.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    assert reg.binding_digest == reg.binding.canonical_digest()
    # Identity fields are read through, never copied into a parallel spelling.
    assert (reg.tenant_id, reg.system_id, reg.system_version) == (
        TENANT, "hiring-screener", "1.2.0")


# --------------------------------------------------------------------------- #
# Identity of the record
# --------------------------------------------------------------------------- #
def test_the_registration_id_is_derived_from_the_binding_digest():
    b, v = binding(), window()
    assert registration_id_for(b, OWNER, v) == registration_id_for(b, OWNER, v)
    assert registration_id_for(b, OWNER, v).startswith("reg_")
    # A different configuration is a different system identity, so a different id.
    assert registration_id_for(binding(configuration="cfg-b"), OWNER, v) != \
        registration_id_for(b, OWNER, v)
    assert registration_id_for(binding(version="1.3.0"), OWNER, v) != \
        registration_id_for(b, OWNER, v)
    assert registration_id_for(b, "directory://people/other", v) != \
        registration_id_for(b, OWNER, v)
    with pytest.raises(ContractViolation):
        registration_id_for("not-a-binding", OWNER, v)  # type: ignore[arg-type]


def test_the_id_is_derived_and_a_chosen_one_is_refused():
    """Regression (independent review): a hand-picked id let two registrations collide,
    so a collection keyed by id silently lost one. The id is now checked, not just
    non-empty, which makes the collision-freedom the README claims actually true."""

    b, v = binding(), window()
    derived = registration_id_for(b, OWNER, v)
    SystemRegistration(registration_id=derived, binding=b, owner_ref=OWNER,
                       classification_label=LABEL, validity=v)
    with pytest.raises(ContractViolation, match="must be the derived id"):
        SystemRegistration(registration_id="reg_dup", binding=b, owner_ref=OWNER,
                           classification_label=LABEL, validity=v)
    # …and the id must match *these* fields, not merely be some derived id.
    with pytest.raises(ContractViolation, match="must be the derived id"):
        SystemRegistration(registration_id=registration_id_for(binding(version="9.9.9"), OWNER, v),
                           binding=b, owner_ref=OWNER, classification_label=LABEL, validity=v)


def test_two_registrations_can_never_share_an_id():
    """The property the derived id exists to provide, stated as a test."""

    ids = {registration(b).registration_id
           for b in (binding(), binding(version="1.3.0"), binding(configuration="cfg-b"),
                     binding("other-system"), binding(tenant="tenant-b"))}
    assert len(ids) == 5


def test_required_fields_are_required():
    b, v = binding(), window()
    for field in ("owner_ref", "classification_label"):
        kwargs = dict(registration_id=registration_id_for(b, OWNER, v), binding=b,
                      owner_ref=OWNER, classification_label=LABEL, validity=v)
        kwargs[field] = "   "
        with pytest.raises(ContractViolation):
            SystemRegistration(**kwargs)
    with pytest.raises(ContractViolation):
        SystemRegistration(registration_id=registration_id_for(b, OWNER, v), binding=b,
                           owner_ref=OWNER, classification_label=LABEL,
                           validity="not-a-validity")


def test_the_classification_label_is_recorded_and_never_interpreted():
    """D-2: no taxonomy, so any non-blank label is admissible and none is ranked."""

    for label in ("high-risk", "prohibited", "annex-iii/5(a)", "whatever-the-org-calls-it"):
        assert registration(label=label).classification_label == label
    # There is no severity, ordering or recognized set anywhere on the record.
    surface = {n for n in dir(registration()) if not n.startswith("_")}
    assert not surface & {"severity", "risk_level", "rank", "is_high_risk", "tier"}


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #
def test_a_registration_outside_its_window_is_absent_not_flagged():
    reg = registration()
    assert reg.is_registered_at(T1)
    assert not reg.is_registered_at(AFTER_WINDOW)
    assert not reg.is_registered_at(BEFORE_WINDOW)
    assert reg.status_at(AFTER_WINDOW) is ValidityStatus.EXPIRED
    assert reg.status_at(BEFORE_WINDOW) is ValidityStatus.NOT_YET_VALID


def test_the_window_boundary_is_half_open():
    reg = registration()
    assert reg.is_registered_at(reg.validity.issued_at)
    assert not reg.is_registered_at(reg.validity.expires_at)


def test_a_naive_instant_is_refused_rather_than_assumed_utc():
    import datetime as dt

    with pytest.raises(ContractViolation):
        registration().is_registered_at(dt.datetime(2026, 3, 1, 9, 0))


# --------------------------------------------------------------------------- #
# Supersession (D-3)
# --------------------------------------------------------------------------- #
def test_a_new_version_is_registered_afresh_and_supersedes_the_prior_record():
    first = registration()
    second = registration(binding(version="1.3.0"), supersedes=first.registration_id)
    assert supersession_refusals(second, first) == ()
    require_admissible_supersession(second, first)
    # The prior record is untouched — a new snapshot, never an edit.
    assert first.system_version == "1.2.0" and second.system_version == "1.3.0"


def test_a_supersession_that_rebinds_the_same_identity_is_refused():
    first = registration()
    same = registration(supersedes=first.registration_id)
    reasons = supersession_refusals(same, first)
    assert reasons and "different system identity" in reasons[0]
    with pytest.raises(RegistrationSupersessionError):
        require_admissible_supersession(same, first)


def test_a_supersession_may_not_cross_tenants_or_name_a_phantom():
    first = registration()
    other_tenant = registration(binding(tenant="tenant-b"), supersedes=first.registration_id)
    assert "cross tenants" in "; ".join(supersession_refusals(other_tenant, first))
    assert supersession_refusals(registration(supersedes="reg_nope"), None) == (
        "the superseded registration does not exist",)


def test_an_ordinary_registration_supersedes_nothing():
    assert supersession_refusals(registration(), None) == ()
    require_admissible_supersession(registration(), None)
