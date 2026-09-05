"""The declaration record: the identity and vocabulary it borrows, the ceilings it
inherits, the derived id, the window that makes it absent, the tenant rule, and
the supersession rule."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_governance_contracts.api import (
    DataClassificationContractError,
    SystemBindingAuthenticityStatus,
    ValidityStatus,
)
from ugence_governance_contracts.contracts import data_classification as gc_label
from ugence_governance_contracts.contracts import system_identity as gc_identity

from ugence_data_use_admission import (
    AssessedSystemBinding,
    ContractViolation,
    DataClassificationLabel,
    DataUseDeclaration,
    DeclarationSupersessionError,
    declaration_id_for,
    require_admissible_supersession,
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
    TENANT,
    binding,
    declaration,
    window,
)


# --------------------------------------------------------------------------- #
# The identity and the vocabulary are borrowed, never minted
# --------------------------------------------------------------------------- #
def test_the_binding_and_the_label_are_the_governance_contracts_types_themselves():
    assert AssessedSystemBinding is gc_identity.AssessedSystemBinding
    assert DataClassificationLabel is gc_label.DataClassificationLabel
    d = declaration()
    assert d.binding.__class__ is gc_identity.AssessedSystemBinding
    assert d.classification.__class__ is gc_label.DataClassificationLabel


def test_a_look_alike_binding_or_label_is_refused():
    class NotABinding:
        tenant_id = TENANT
        system_id = "x"
        system_version = "1"

        def canonical_digest(self):
            return "0" * 64

    class NotALabel:
        label = "confidential"

        def canonical_digest(self):
            return "0" * 64

    with pytest.raises(ContractViolation, match="mints no system identity"):
        DataUseDeclaration(declaration_id="dud_1", tenant_id=TENANT, binding=NotABinding(),
                           data_ref=DATA, classification=LABEL, purpose_label=PURPOSE,
                           validity=window())
    with pytest.raises(ContractViolation, match="mints no vocabulary"):
        DataUseDeclaration(declaration_id="dud_1", tenant_id=TENANT, binding=binding(),
                           data_ref=DATA, classification=NotALabel(), purpose_label=PURPOSE,
                           validity=window())
    # A bare string is not a label either: the vocabulary type is the contract.
    with pytest.raises(ContractViolation, match="mints no vocabulary"):
        DataUseDeclaration(declaration_id="dud_1", tenant_id=TENANT, binding=binding(),
                           data_ref=DATA, classification="confidential", purpose_label=PURPOSE,
                           validity=window())


def test_the_declaration_inherits_the_bindings_ceiling_and_the_labels_opacity():
    d = declaration()
    assert d.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    assert d.binding_digest == d.binding.canonical_digest()
    assert (d.tenant_id, d.system_id, d.system_version) == (TENANT, "hiring-screener", "1.2.0")
    # The label's text is read through, never copied into a parallel spelling.
    assert d.classification_label == "confidential" and d.classification == LABEL


def test_a_blank_label_is_refused_upstream_and_an_unknown_one_is_recorded():
    with pytest.raises(DataClassificationContractError):
        DataClassificationLabel("   ")
    for text in ("prohibited", "annex-iii/5(a)", "whatever-the-org-calls-it", "PII"):
        assert declaration(label=DataClassificationLabel(text)).classification_label == text
    # Nothing on the record ranks, grades or compares a label.
    surface = {n for n in dir(declaration()) if not n.startswith("_")}
    assert not surface & {"severity", "risk_level", "rank", "tier", "level", "dominates",
                          "is_compatible_with", "is_sensitive", "is_restricted"}


# --------------------------------------------------------------------------- #
# Identity of the record: derived, deterministic, collision-free
# --------------------------------------------------------------------------- #
def test_the_declaration_id_is_derived_and_deterministic():
    b, v = binding(), window()
    first = declaration_id_for(b, DATA, LABEL, PURPOSE, v)
    assert first == declaration_id_for(b, DATA, LABEL, PURPOSE, v)
    assert first.startswith("dud_") and len(first) == 4 + 32
    # Every input participates.
    assert declaration_id_for(binding(configuration="cfg-b"), DATA, LABEL, PURPOSE, v) != first
    assert declaration_id_for(b, OTHER_DATA, LABEL, PURPOSE, v) != first
    assert declaration_id_for(b, DATA, OTHER_LABEL, PURPOSE, v) != first
    assert declaration_id_for(b, DATA, LABEL, OTHER_PURPOSE, v) != first
    assert declaration_id_for(b, DATA, LABEL, PURPOSE, window(days=30)) != first
    # A label's surrounding whitespace is not a difference, because the label
    # contract strips it; a label's case is, because nothing case-folds.
    assert declaration_id_for(b, DATA, DataClassificationLabel(" confidential "), PURPOSE, v) == first
    assert declaration_id_for(b, DATA, DataClassificationLabel("Confidential"), PURPOSE, v) != first


def test_declaration_id_for_refuses_look_alikes_and_blanks():
    b, v = binding(), window()
    with pytest.raises(ContractViolation):
        declaration_id_for("not-a-binding", DATA, LABEL, PURPOSE, v)  # type: ignore[arg-type]
    with pytest.raises(ContractViolation):
        declaration_id_for(b, DATA, "confidential", PURPOSE, v)  # type: ignore[arg-type]
    with pytest.raises(ContractViolation):
        declaration_id_for(b, "  ", LABEL, PURPOSE, v)
    with pytest.raises(ContractViolation):
        declaration_id_for(b, DATA, LABEL, "", v)
    with pytest.raises(ContractViolation):
        declaration_id_for(b, DATA, LABEL, PURPOSE, "not-a-validity")  # type: ignore[arg-type]


def test_the_id_is_derived_and_a_chosen_one_is_refused():
    b, v = binding(), window()
    derived = declaration_id_for(b, DATA, LABEL, PURPOSE, v)
    DataUseDeclaration(declaration_id=derived, tenant_id=TENANT, binding=b, data_ref=DATA,
                       classification=LABEL, purpose_label=PURPOSE, validity=v)
    with pytest.raises(ContractViolation, match="must be the derived id"):
        DataUseDeclaration(declaration_id="dud_chosen", tenant_id=TENANT, binding=b,
                           data_ref=DATA, classification=LABEL, purpose_label=PURPOSE, validity=v)
    # …and the id must match *these* fields, not merely be some derived id.
    with pytest.raises(ContractViolation, match="must be the derived id"):
        DataUseDeclaration(declaration_id=declaration_id_for(b, OTHER_DATA, LABEL, PURPOSE, v),
                           tenant_id=TENANT, binding=b, data_ref=DATA, classification=LABEL,
                           purpose_label=PURPOSE, validity=v)


def test_two_declarations_can_never_share_an_id():
    ids = {d.declaration_id for d in (
        declaration(), declaration(binding(version="1.3.0")), declaration(data_ref=OTHER_DATA),
        declaration(label=OTHER_LABEL), declaration(purpose=OTHER_PURPOSE),
        declaration(binding(tenant="tenant-b")), declaration(validity=window(days=30)))}
    assert len(ids) == 7


def test_the_record_digest_is_deterministic_and_covers_every_field():
    a = declaration(residency="eu", declared_by="admin-1")
    assert a.record_digest() == declaration(residency="eu", declared_by="admin-1").record_digest()
    assert len(a.record_digest()) == 64
    assert a.record_digest() != declaration(residency="us", declared_by="admin-1").record_digest()
    assert a.record_digest() != declaration(residency="eu", declared_by="admin-2").record_digest()
    assert a.to_dict()["classification_label"] == "confidential"
    assert "payload" not in a.to_dict() and "content" not in a.to_dict()


# --------------------------------------------------------------------------- #
# Refusals: required fields, types, and the tenant rule
# --------------------------------------------------------------------------- #
def test_required_fields_are_required():
    b, v = binding(), window()
    for field in ("tenant_id", "data_ref", "purpose_label"):
        kwargs = dict(declaration_id=declaration_id_for(b, DATA, LABEL, PURPOSE, v),
                      tenant_id=TENANT, binding=b, data_ref=DATA, classification=LABEL,
                      purpose_label=PURPOSE, validity=v)
        kwargs[field] = "   "
        with pytest.raises(ContractViolation, match=field):
            DataUseDeclaration(**kwargs)
    with pytest.raises(ContractViolation, match="Validity"):
        DataUseDeclaration(declaration_id=declaration_id_for(b, DATA, LABEL, PURPOSE, v),
                           tenant_id=TENANT, binding=b, data_ref=DATA, classification=LABEL,
                           purpose_label=PURPOSE, validity="not-a-validity")
    with pytest.raises(ContractViolation, match="notes must be a string"):
        declaration_kwargs = dict(declaration_id=declaration_id_for(b, DATA, LABEL, PURPOSE, v),
                                  tenant_id=TENANT, binding=b, data_ref=DATA,
                                  classification=LABEL, purpose_label=PURPOSE, validity=v,
                                  notes=42)
        DataUseDeclaration(**declaration_kwargs)


def test_a_tenant_that_disagrees_with_the_binding_is_refused_not_resolved():
    """Tenant isolation begins at construction: the record never carries two tenants."""

    with pytest.raises(ContractViolation, match="does not match the binding's tenant"):
        declaration(binding(tenant="tenant-a"), tenant="tenant-b")
    with pytest.raises(ContractViolation, match="does not match the binding's tenant"):
        declaration(binding(tenant="tenant-b"), tenant="tenant-a")
    assert declaration(binding(tenant="tenant-b")).tenant_id == "tenant-b"


def test_residency_is_recorded_and_never_evaluated():
    """DE-2: metadata, not a verdict. Any text is accepted and nothing judges it."""

    for text in ("eu", "us-east-1", "on-prem/dc-3", "whatever-the-org-calls-it"):
        assert declaration(residency=text).residency_label == text
    assert declaration().residency_label == ""
    d = declaration(residency="eu")
    for absent in ("is_resident", "residency_allowed", "allowed_region", "region_ok",
                   "residency_required", "check_residency"):
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
    reclassified = declaration(label=OTHER_LABEL, supersedes=first.declaration_id)
    assert supersession_refusals(reclassified, first) == ()
    require_admissible_supersession(reclassified, first)
    # The prior record is untouched — a new snapshot, never an edit.
    assert first.classification_label == "confidential"
    assert reclassified.classification_label == "public"
    # A changed purpose, system or residency is likewise a change.
    for changed in (declaration(purpose=OTHER_PURPOSE, supersedes=first.declaration_id),
                    declaration(binding(version="1.3.0"), supersedes=first.declaration_id),
                    declaration(residency="eu", supersedes=first.declaration_id)):
        assert supersession_refusals(changed, first) == ()


def test_a_supersession_that_changes_nothing_is_refused():
    first = declaration()
    same = declaration(validity=window(days=30), supersedes=first.declaration_id)
    reasons = supersession_refusals(same, first)
    assert reasons and "must change what was declared" in reasons[0]
    with pytest.raises(DeclarationSupersessionError):
        require_admissible_supersession(same, first)


def test_a_supersession_about_different_data_is_refused():
    first = declaration()
    other = declaration(data_ref=OTHER_DATA, supersedes=first.declaration_id)
    assert "must concern the same data" in "; ".join(supersession_refusals(other, first))


def test_a_supersession_may_not_cross_tenants_or_name_a_phantom():
    first = declaration()
    other_tenant = declaration(binding(tenant="tenant-b"), supersedes=first.declaration_id)
    assert "cross tenants" in "; ".join(supersession_refusals(other_tenant, first))
    assert supersession_refusals(declaration(supersedes="dud_nope"), None) == (
        "the superseded declaration does not exist",)
    wrong = declaration(label=OTHER_LABEL, supersedes="dud_nope")
    assert "does not name the presented predecessor" in "; ".join(
        supersession_refusals(wrong, first))


def test_an_ordinary_declaration_supersedes_nothing():
    assert supersession_refusals(declaration(), None) == ()
    require_admissible_supersession(declaration(), None)
