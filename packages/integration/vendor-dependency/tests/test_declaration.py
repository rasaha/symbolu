"""The declaration record: the identity and vocabulary it borrows, the ceilings it
inherits, the derived id, the window that makes it absent, the tenant rule, the
policy reference that is never resolved, and the supersession rule."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_governance_contracts.api import (
    DataClassificationLabel,
    SystemBindingAuthenticityStatus,
    ValidityStatus,
    VendorRiskContractError,
)
from ugence_governance_contracts.contracts import system_identity as gc_identity
from ugence_governance_contracts.contracts import vendor_risk as gc_label

from ugence_vendor_dependency import (
    AssessedSystemBinding,
    ContractViolation,
    DeclarationSupersessionError,
    VendorDependencyDeclaration,
    VendorRiskLabel,
    declaration_id_for,
    require_admissible_supersession,
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
    TENANT,
    VENDOR,
    binding,
    declaration,
    window,
)


# --------------------------------------------------------------------------- #
# The identity and the vocabulary are borrowed, never minted
# --------------------------------------------------------------------------- #
def test_the_binding_and_the_label_are_the_governance_contracts_types_themselves():
    assert AssessedSystemBinding is gc_identity.AssessedSystemBinding
    assert VendorRiskLabel is gc_label.VendorRiskLabel
    d = declaration()
    assert d.binding.__class__ is gc_identity.AssessedSystemBinding
    assert d.risk_posture.__class__ is gc_label.VendorRiskLabel


def test_a_look_alike_binding_or_label_is_refused():
    class NotABinding:
        tenant_id = TENANT
        system_id = "x"
        system_version = "1"

        def canonical_digest(self):
            return "0" * 64

    class NotALabel:
        label = "elevated"

        def canonical_digest(self):
            return "0" * 64

    kwargs = dict(declaration_id="vdd_1", tenant_id=TENANT, vendor_ref=VENDOR,
                  policy_ref=POLICY, validity=window())
    with pytest.raises(ContractViolation, match="mints no system identity"):
        VendorDependencyDeclaration(binding=NotABinding(), risk_posture=POSTURE, **kwargs)
    with pytest.raises(ContractViolation, match="mints no vocabulary"):
        VendorDependencyDeclaration(binding=binding(), risk_posture=NotALabel(), **kwargs)
    # A bare string is not a label either.
    with pytest.raises(ContractViolation, match="mints no vocabulary"):
        VendorDependencyDeclaration(binding=binding(), risk_posture="elevated", **kwargs)


def test_a_registry_registration_is_not_accepted_as_an_identity():
    """VR-2: binding only. Something registration-shaped is refused like any look-alike."""

    class RegistrationShaped:
        registration_id = "reg_abc"
        tenant_id = TENANT
        system_id = "hiring-screener"
        system_version = "1.2.0"
        binding = binding()

        def canonical_digest(self):
            return "0" * 64

    with pytest.raises(ContractViolation, match="accepts no inventory record"):
        VendorDependencyDeclaration(declaration_id="vdd_1", tenant_id=TENANT,
                                    binding=RegistrationShaped(), vendor_ref=VENDOR,
                                    risk_posture=POSTURE, policy_ref=POLICY, validity=window())


def test_a_data_classification_label_is_not_a_risk_posture():
    """VR-3: two dimensions, two types. The same text in the other type is refused."""

    with pytest.raises(ContractViolation, match="mints no vocabulary"):
        VendorDependencyDeclaration(declaration_id="vdd_1", tenant_id=TENANT, binding=binding(),
                                    vendor_ref=VENDOR,
                                    risk_posture=DataClassificationLabel("elevated"),
                                    policy_ref=POLICY, validity=window())
    with pytest.raises(ContractViolation):
        declaration_id_for(binding(), VENDOR, DataClassificationLabel("elevated"), POLICY, window())


def test_the_declaration_inherits_the_bindings_ceiling_and_the_labels_opacity():
    d = declaration()
    assert d.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    assert d.binding_digest == d.binding.canonical_digest()
    assert (d.tenant_id, d.system_id, d.system_version) == (TENANT, "hiring-screener", "1.2.0")
    assert d.risk_posture_label == "elevated" and d.risk_posture == POSTURE


def test_a_blank_posture_is_refused_upstream_and_an_unknown_one_is_recorded():
    with pytest.raises(VendorRiskContractError):
        VendorRiskLabel("   ")
    for text in ("critical", "approved-with-conditions", "whatever-the-org-calls-it", "T1"):
        assert declaration(posture=VendorRiskLabel(text)).risk_posture_label == text
    surface = {n for n in dir(declaration()) if not n.startswith("_")}
    assert not surface & {"severity", "risk_level", "risk_score", "score", "grade", "rank",
                          "tier", "level", "dominates", "is_eligible", "is_approved"}


def test_postures_cannot_be_ordered_through_the_declaration_either():
    high, low = declaration(posture=VendorRiskLabel("high")), declaration(posture=VendorRiskLabel("low"))
    with pytest.raises(TypeError):
        sorted([high.risk_posture, low.risk_posture])
    with pytest.raises(TypeError):
        high.risk_posture > low.risk_posture  # type: ignore[operator]


# --------------------------------------------------------------------------- #
# Identity of the record: derived, deterministic, collision-free
# --------------------------------------------------------------------------- #
def test_the_declaration_id_is_derived_and_deterministic():
    b, v = binding(), window()
    first = declaration_id_for(b, VENDOR, POSTURE, POLICY, v)
    assert first == declaration_id_for(b, VENDOR, POSTURE, POLICY, v)
    assert first.startswith("vdd_") and len(first) == 4 + 32
    assert declaration_id_for(binding(configuration="cfg-b"), VENDOR, POSTURE, POLICY, v) != first
    assert declaration_id_for(b, OTHER_VENDOR, POSTURE, POLICY, v) != first
    assert declaration_id_for(b, VENDOR, OTHER_POSTURE, POLICY, v) != first
    assert declaration_id_for(b, VENDOR, POSTURE, OTHER_POLICY, v) != first
    assert declaration_id_for(b, VENDOR, POSTURE, POLICY, window(days=30)) != first
    assert declaration_id_for(b, VENDOR, VendorRiskLabel(" elevated "), POLICY, v) == first
    assert declaration_id_for(b, VENDOR, VendorRiskLabel("Elevated"), POLICY, v) != first


def test_declaration_id_for_refuses_look_alikes_and_blanks():
    b, v = binding(), window()
    with pytest.raises(ContractViolation):
        declaration_id_for("not-a-binding", VENDOR, POSTURE, POLICY, v)  # type: ignore[arg-type]
    with pytest.raises(ContractViolation):
        declaration_id_for(b, VENDOR, "elevated", POLICY, v)  # type: ignore[arg-type]
    with pytest.raises(ContractViolation):
        declaration_id_for(b, "  ", POSTURE, POLICY, v)
    with pytest.raises(ContractViolation):
        declaration_id_for(b, VENDOR, POSTURE, "", v)
    with pytest.raises(ContractViolation):
        declaration_id_for(b, VENDOR, POSTURE, POLICY, "not-a-validity")  # type: ignore[arg-type]


def test_the_id_is_derived_and_a_chosen_one_is_refused():
    b, v = binding(), window()
    derived = declaration_id_for(b, VENDOR, POSTURE, POLICY, v)
    VendorDependencyDeclaration(declaration_id=derived, tenant_id=TENANT, binding=b,
                                vendor_ref=VENDOR, risk_posture=POSTURE, policy_ref=POLICY,
                                validity=v)
    with pytest.raises(ContractViolation, match="must be the derived id"):
        VendorDependencyDeclaration(declaration_id="vdd_chosen", tenant_id=TENANT, binding=b,
                                    vendor_ref=VENDOR, risk_posture=POSTURE, policy_ref=POLICY,
                                    validity=v)
    with pytest.raises(ContractViolation, match="must be the derived id"):
        VendorDependencyDeclaration(
            declaration_id=declaration_id_for(b, OTHER_VENDOR, POSTURE, POLICY, v),
            tenant_id=TENANT, binding=b, vendor_ref=VENDOR, risk_posture=POSTURE,
            policy_ref=POLICY, validity=v)


def test_two_declarations_can_never_share_an_id():
    ids = {d.declaration_id for d in (
        declaration(), declaration(binding(version="1.3.0")), declaration(vendor=OTHER_VENDOR),
        declaration(posture=OTHER_POSTURE), declaration(policy=OTHER_POLICY),
        declaration(binding(tenant="tenant-b")), declaration(validity=window(days=30)))}
    assert len(ids) == 7


def test_the_record_digest_is_deterministic_and_covers_every_field():
    a = declaration(declared_by="admin-1")
    assert a.record_digest() == declaration(declared_by="admin-1").record_digest()
    assert len(a.record_digest()) == 64
    assert a.record_digest() != declaration(declared_by="admin-2").record_digest()
    assert a.record_digest() != declaration(policy=OTHER_POLICY, declared_by="admin-1").record_digest()
    assert a.to_dict()["risk_posture_label"] == "elevated"
    assert a.to_dict()["policy_ref"] == POLICY


# --------------------------------------------------------------------------- #
# Refusals: required fields, types, the tenant rule
# --------------------------------------------------------------------------- #
def test_required_fields_are_required():
    b, v = binding(), window()
    for field in ("tenant_id", "vendor_ref", "policy_ref"):
        kwargs = dict(declaration_id=declaration_id_for(b, VENDOR, POSTURE, POLICY, v),
                      tenant_id=TENANT, binding=b, vendor_ref=VENDOR, risk_posture=POSTURE,
                      policy_ref=POLICY, validity=v)
        kwargs[field] = "   "
        with pytest.raises(ContractViolation, match=field):
            VendorDependencyDeclaration(**kwargs)
    with pytest.raises(ContractViolation, match="Validity"):
        VendorDependencyDeclaration(declaration_id=declaration_id_for(b, VENDOR, POSTURE, POLICY, v),
                                    tenant_id=TENANT, binding=b, vendor_ref=VENDOR,
                                    risk_posture=POSTURE, policy_ref=POLICY,
                                    validity="not-a-validity")
    with pytest.raises(ContractViolation, match="notes must be a string"):
        VendorDependencyDeclaration(declaration_id=declaration_id_for(b, VENDOR, POSTURE, POLICY, v),
                                    tenant_id=TENANT, binding=b, vendor_ref=VENDOR,
                                    risk_posture=POSTURE, policy_ref=POLICY, validity=v, notes=42)


def test_a_cross_tenant_record_fails_closed():
    """Tenant isolation begins at construction: the record never carries two tenants."""

    with pytest.raises(ContractViolation, match="does not match the binding's tenant"):
        declaration(binding(tenant="tenant-a"), tenant="tenant-b")
    with pytest.raises(ContractViolation, match="does not match the binding's tenant"):
        declaration(binding(tenant="tenant-b"), tenant="tenant-a")
    assert declaration(binding(tenant="tenant-b")).tenant_id == "tenant-b"


def test_the_policy_ref_is_recorded_as_text_and_never_resolved():
    """VR-4: any non-empty string is a reference, and nothing here looks it up."""

    for text in ("policy://vendor-standard/v3", "pol_9f3a", "whatever-the-org-uses"):
        assert declaration(policy=text).policy_ref == text
    d = declaration()
    for absent in ("policy", "resolved_policy", "policy_version", "resolve_policy",
                   "verify_policy", "policy_valid", "is_policy_current"):
        assert not hasattr(d, absent), absent


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #
def test_a_declaration_outside_its_window_is_absent_not_flagged():
    d = declaration()
    assert d.is_declared_at(T1)
    assert not d.is_declared_at(AFTER_WINDOW)
    assert not d.is_declared_at(BEFORE_WINDOW)
    assert d.status_at(AFTER_WINDOW) is ValidityStatus.EXPIRED
    assert d.status_at(BEFORE_WINDOW) is ValidityStatus.NOT_YET_VALID


def test_the_window_boundary_is_half_open():
    d = declaration()
    assert d.is_declared_at(d.validity.issued_at)
    assert not d.is_declared_at(d.validity.expires_at)


def test_a_naive_instant_is_refused_rather_than_assumed_utc():
    with pytest.raises(ContractViolation, match="timezone-aware"):
        declaration().is_declared_at(dt.datetime(2026, 3, 1, 9, 0))
    with pytest.raises(ContractViolation, match="must be a datetime"):
        declaration().status_at("2026-03-01T09:00:00Z")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Supersession
# --------------------------------------------------------------------------- #
def test_a_changed_declaration_is_made_afresh_and_supersedes_the_prior_record():
    first = declaration()
    reposted = declaration(posture=OTHER_POSTURE, supersedes=first.declaration_id)
    assert supersession_refusals(reposted, first) == ()
    require_admissible_supersession(reposted, first)
    assert first.risk_posture_label == "elevated"
    assert reposted.risk_posture_label == "approved-with-conditions"
    for changed in (declaration(policy=OTHER_POLICY, supersedes=first.declaration_id),
                    declaration(binding(version="1.3.0"), supersedes=first.declaration_id)):
        assert supersession_refusals(changed, first) == ()


def test_a_supersession_that_changes_nothing_is_refused():
    first = declaration()
    same = declaration(validity=window(days=30), supersedes=first.declaration_id)
    reasons = supersession_refusals(same, first)
    assert reasons and "must change what was declared" in reasons[0]
    with pytest.raises(DeclarationSupersessionError):
        require_admissible_supersession(same, first)


def test_a_supersession_about_a_different_vendor_is_refused():
    first = declaration()
    other = declaration(vendor=OTHER_VENDOR, supersedes=first.declaration_id)
    assert "must concern the same vendor" in "; ".join(supersession_refusals(other, first))


def test_a_supersession_may_not_cross_tenants_or_name_a_phantom():
    first = declaration()
    other_tenant = declaration(binding(tenant="tenant-b"), supersedes=first.declaration_id)
    assert "cross tenants" in "; ".join(supersession_refusals(other_tenant, first))
    assert supersession_refusals(declaration(supersedes="vdd_nope"), None) == (
        "the superseded declaration does not exist",)
    wrong = declaration(posture=OTHER_POSTURE, supersedes="vdd_nope")
    assert "does not name the presented predecessor" in "; ".join(
        supersession_refusals(wrong, first))


def test_an_ordinary_declaration_supersedes_nothing():
    assert supersession_refusals(declaration(), None) == ()
    require_admissible_supersession(declaration(), None)
