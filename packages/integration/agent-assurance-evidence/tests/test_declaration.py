"""The declaration record: the identity, reference and vocabulary it borrows, the
ceilings it inherits, the derived id, the window that makes it absent, the three
agreement rules, and the supersession rule."""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_governance_contracts.api import (
    AssuranceFindingContractError,
    DataClassificationLabel,
    SystemBindingAuthenticityStatus,
    ValidityStatus,
    VendorRiskLabel,
    VerificationStatus,
)
from ugence_governance_contracts.contracts import assurance_finding as gc_label
from ugence_governance_contracts.contracts import evidence as gc_evidence
from ugence_governance_contracts.contracts import system_identity as gc_identity

from ugence_agent_assurance_evidence import (
    AssessedSystemBinding,
    AssuranceFindingDeclaration,
    AssuranceFindingLabel,
    ContractViolation,
    DeclarationSupersessionError,
    EvidenceReference,
    declaration_id_for,
    require_admissible_supersession,
    supersession_refusals,
)

from _fixtures import (
    AFTER_WINDOW,
    BEFORE_WINDOW,
    EXERCISE,
    FINDING,
    OTHER_EXERCISE,
    OTHER_FINDING,
    SUBJECT,
    T1,
    TENANT,
    binding,
    declaration,
    evidence,
    window,
)


def _kwargs(b=None, e=None, **over):
    b = b or binding()
    e = e or evidence()
    base = dict(declaration_id="afd_1", tenant_id=TENANT, binding=b, evidence=e,
                finding=FINDING, exercise_ref=EXERCISE, validity=window())
    base.update(over)
    return base


# --------------------------------------------------------------------------- #
# Borrowed, never minted
# --------------------------------------------------------------------------- #
def test_the_binding_reference_and_label_are_the_governance_contracts_types_themselves():
    assert AssessedSystemBinding is gc_identity.AssessedSystemBinding
    assert EvidenceReference is gc_evidence.EvidenceReference
    assert AssuranceFindingLabel is gc_label.AssuranceFindingLabel
    d = declaration()
    assert d.binding.__class__ is gc_identity.AssessedSystemBinding
    assert d.evidence.__class__ is gc_evidence.EvidenceReference
    assert d.finding.__class__ is gc_label.AssuranceFindingLabel


def test_look_alike_contracts_are_refused():
    class NotABinding:
        tenant_id = TENANT
        subject_id = SUBJECT
        system_id = "x"
        system_version = "1"

        def canonical_digest(self):
            return "0" * 64

    class NotAReference:
        evidence_id = "ev-1"
        tenant_id = TENANT
        subject_id = SUBJECT
        evidence_kind = "k"
        content_digest = "0" * 64

    class NotALabel:
        label = "no-finding"

        def canonical_digest(self):
            return "0" * 64

    with pytest.raises(ContractViolation, match="mints no system identity"):
        AssuranceFindingDeclaration(**_kwargs(binding=NotABinding()))
    with pytest.raises(ContractViolation, match="mints no evidence identity"):
        AssuranceFindingDeclaration(**_kwargs(evidence=NotAReference()))
    with pytest.raises(ContractViolation, match="mints no vocabulary"):
        AssuranceFindingDeclaration(**_kwargs(finding=NotALabel()))
    with pytest.raises(ContractViolation, match="mints no vocabulary"):
        AssuranceFindingDeclaration(**_kwargs(finding="no-finding"))
    # A dict shaped like a reference is not a reference either (AE-2).
    with pytest.raises(ContractViolation, match="mints no evidence identity"):
        AssuranceFindingDeclaration(**_kwargs(evidence={"evidence_id": "ev-1"}))


def test_a_verification_status_or_another_label_is_not_a_finding():
    """AE-3: the label never represents whether a claim was checked, and the two
    other labels are different dimensions."""

    for wrong in (VerificationStatus.VERIFIED, VerificationStatus.VERIFICATION_FAILED,
                  DataClassificationLabel("no-finding"), VendorRiskLabel("no-finding")):
        with pytest.raises(ContractViolation, match="mints no vocabulary"):
            AssuranceFindingDeclaration(**_kwargs(finding=wrong))
        with pytest.raises(ContractViolation):
            declaration_id_for(binding(), evidence(), wrong, EXERCISE, window())
    with pytest.raises(AssuranceFindingContractError):
        AssuranceFindingLabel(VerificationStatus.VERIFIED)


def test_the_declaration_inherits_the_bindings_ceiling_and_reads_the_reference_through():
    d = declaration()
    assert d.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    assert d.binding_digest == d.binding.canonical_digest()
    assert (d.tenant_id, d.subject_id, d.system_id, d.system_version) == (
        TENANT, SUBJECT, "hiring-screener", "1.2.0")
    # The evidence identity is the reference's own, read through, never copied.
    assert d.evidence_id == d.evidence.evidence_id == "ev-run7-001"
    assert d.evidence_digest == d.evidence.content_digest
    assert d.evidence_kind == d.evidence.evidence_kind == "assurance-exercise-report"
    assert d.finding_label == "prompt-injection-succeeded" and d.finding == FINDING


def test_a_blank_finding_is_refused_upstream_and_an_unknown_one_is_recorded():
    with pytest.raises(AssuranceFindingContractError):
        AssuranceFindingLabel("   ")
    for text in ("no-finding", "data-exfiltration/partial", "whatever-the-team-calls-it", "T1"):
        assert declaration(finding=AssuranceFindingLabel(text)).finding_label == text
    surface = {n for n in dir(declaration()) if not n.startswith("_")}
    assert not surface & {"severity", "score", "cvss", "rank", "tier", "level", "is_verified",
                          "verification_status", "is_true", "is_exploitable", "is_critical"}


def test_findings_cannot_be_ordered_through_the_declaration_either():
    a = declaration(finding=AssuranceFindingLabel("critical"))
    b = declaration(finding=AssuranceFindingLabel("low"))
    with pytest.raises(TypeError):
        sorted([a.finding, b.finding])


# --------------------------------------------------------------------------- #
# Identity of the record: derived, deterministic, collision-free
# --------------------------------------------------------------------------- #
def test_the_declaration_id_is_derived_and_deterministic():
    b, e, v = binding(), evidence(), window()
    first = declaration_id_for(b, e, FINDING, EXERCISE, v)
    assert first == declaration_id_for(b, e, FINDING, EXERCISE, v)
    assert first.startswith("afd_") and len(first) == 4 + 32
    assert declaration_id_for(binding(configuration="cfg-b"), e, FINDING, EXERCISE, v) != first
    assert declaration_id_for(b, evidence("ev-other"), FINDING, EXERCISE, v) != first
    assert declaration_id_for(b, evidence(content="report-8"), FINDING, EXERCISE, v) != first
    assert declaration_id_for(b, e, OTHER_FINDING, EXERCISE, v) != first
    assert declaration_id_for(b, e, FINDING, OTHER_EXERCISE, v) != first
    assert declaration_id_for(b, e, FINDING, EXERCISE, window(days=30)) != first
    assert declaration_id_for(b, e, AssuranceFindingLabel(" prompt-injection-succeeded "),
                              EXERCISE, v) == first


def test_declaration_id_for_refuses_look_alikes_and_blanks():
    b, e, v = binding(), evidence(), window()
    with pytest.raises(ContractViolation):
        declaration_id_for("not-a-binding", e, FINDING, EXERCISE, v)  # type: ignore[arg-type]
    with pytest.raises(ContractViolation):
        declaration_id_for(b, "ev-1", FINDING, EXERCISE, v)  # type: ignore[arg-type]
    with pytest.raises(ContractViolation):
        declaration_id_for(b, e, "no-finding", EXERCISE, v)  # type: ignore[arg-type]
    with pytest.raises(ContractViolation):
        declaration_id_for(b, e, FINDING, "  ", v)
    with pytest.raises(ContractViolation):
        declaration_id_for(b, e, FINDING, EXERCISE, "not-a-validity")  # type: ignore[arg-type]


def test_the_id_is_derived_and_a_chosen_one_is_refused():
    b, e, v = binding(), evidence(), window()
    derived = declaration_id_for(b, e, FINDING, EXERCISE, v)
    AssuranceFindingDeclaration(**_kwargs(b, e, declaration_id=derived, validity=v))
    with pytest.raises(ContractViolation, match="must be the derived id"):
        AssuranceFindingDeclaration(**_kwargs(b, e, declaration_id="afd_chosen", validity=v))
    with pytest.raises(ContractViolation, match="must be the derived id"):
        AssuranceFindingDeclaration(**_kwargs(
            b, e, declaration_id=declaration_id_for(b, evidence("ev-other"), FINDING, EXERCISE, v),
            validity=v))


def test_two_declarations_can_never_share_an_id():
    ids = {d.declaration_id for d in (
        declaration(), declaration(binding(version="1.3.0")), declaration(ev=evidence("ev-other")),
        declaration(finding=OTHER_FINDING), declaration(exercise=OTHER_EXERCISE),
        declaration(binding(tenant="tenant-b")), declaration(validity=window(days=30)))}
    assert len(ids) == 7


def test_the_record_digest_is_deterministic_and_covers_every_field():
    a = declaration(declared_by="admin-1")
    assert a.record_digest() == declaration(declared_by="admin-1").record_digest()
    assert len(a.record_digest()) == 64
    assert a.record_digest() != declaration(declared_by="admin-2").record_digest()
    assert a.record_digest() != declaration(exercise=OTHER_EXERCISE, declared_by="admin-1").record_digest()
    d = a.to_dict()
    assert d["evidence_id"] == "ev-run7-001" and d["finding_label"] == "prompt-injection-succeeded"
    assert "provenance_ref" not in d and "score" not in d and "severity" not in d


# --------------------------------------------------------------------------- #
# Refusals: required fields, types, and the three agreement rules
# --------------------------------------------------------------------------- #
def test_required_fields_are_required():
    b, e, v = binding(), evidence(), window()
    good_id = declaration_id_for(b, e, FINDING, EXERCISE, v)
    for field in ("tenant_id", "exercise_ref"):
        with pytest.raises(ContractViolation, match=field):
            AssuranceFindingDeclaration(**_kwargs(b, e, declaration_id=good_id, validity=v,
                                                  **{field: "   "}))
    with pytest.raises(ContractViolation, match="Validity"):
        AssuranceFindingDeclaration(**_kwargs(b, e, declaration_id=good_id, validity="nope"))
    with pytest.raises(ContractViolation, match="notes must be a string"):
        AssuranceFindingDeclaration(**_kwargs(b, e, declaration_id=good_id, validity=v, notes=42))


def test_a_cross_tenant_record_fails_closed():
    with pytest.raises(ContractViolation, match="does not match the binding's tenant"):
        declaration(binding(tenant="tenant-a"), tenant="tenant-b")
    with pytest.raises(ContractViolation, match="does not match the binding's tenant"):
        declaration(binding(tenant="tenant-b"), tenant="tenant-a")
    # The evidence reference's tenant must agree too.
    with pytest.raises(ContractViolation, match="not the declaring tenant"):
        declaration(binding(tenant="tenant-a"), ev=evidence(tenant="tenant-b"))
    assert declaration(binding(tenant="tenant-b")).tenant_id == "tenant-b"


def test_an_evidence_reference_about_another_subject_is_refused():
    """A finding about one subject is never bound to another system's identity."""

    with pytest.raises(ContractViolation, match="never bound to another's system identity"):
        declaration(binding(subject="subject-1"), ev=evidence(subject="subject-2"))
    with pytest.raises(ContractViolation, match="never bound to another's system identity"):
        declaration(binding(subject="subject-2"), ev=evidence(subject="subject-1"))
    # …and the refusal is by exact text, not by resemblance.
    with pytest.raises(ContractViolation):
        declaration(binding(subject="subject-1"), ev=evidence(subject="Subject-1"))
    assert declaration(binding(subject="subject-9"), ev=evidence(subject="subject-9")).subject_id == "subject-9"


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
def test_a_rerun_with_new_evidence_supersedes_the_prior_finding():
    first = declaration()
    rerun = declaration(ev=evidence("ev-run8-001", content="report-8"), finding=OTHER_FINDING,
                        exercise="exercise://red-team/2026-q3-run-8",
                        supersedes=first.declaration_id)
    assert supersession_refusals(rerun, first) == ()
    require_admissible_supersession(rerun, first)
    assert first.finding_label == "prompt-injection-succeeded"
    assert rerun.finding_label == "no-finding"
    for changed in (declaration(finding=OTHER_FINDING, supersedes=first.declaration_id),
                    declaration(exercise=OTHER_EXERCISE, supersedes=first.declaration_id),
                    declaration(ev=evidence(content="report-8"), supersedes=first.declaration_id)):
        assert supersession_refusals(changed, first) == ()


def test_a_supersession_that_changes_nothing_is_refused():
    first = declaration()
    same = declaration(validity=window(days=30), supersedes=first.declaration_id)
    reasons = supersession_refusals(same, first)
    assert reasons and "must change what was declared" in reasons[0]
    with pytest.raises(DeclarationSupersessionError):
        require_admissible_supersession(same, first)


def test_a_supersession_about_a_different_system_is_refused():
    first = declaration()
    other = declaration(binding("credit-scorer"), supersedes=first.declaration_id)
    assert "must concern the same system identity" in "; ".join(supersession_refusals(other, first))


def test_a_supersession_may_not_cross_tenants_or_name_a_phantom():
    first = declaration()
    other_tenant = declaration(binding(tenant="tenant-b"), supersedes=first.declaration_id)
    assert "cross tenants" in "; ".join(supersession_refusals(other_tenant, first))
    assert supersession_refusals(declaration(supersedes="afd_nope"), None) == (
        "the superseded declaration does not exist",)
    wrong = declaration(finding=OTHER_FINDING, supersedes="afd_nope")
    assert "does not name the presented predecessor" in "; ".join(
        supersession_refusals(wrong, first))


def test_an_ordinary_declaration_supersedes_nothing():
    assert supersession_refusals(declaration(), None) == ()
    require_admissible_supersession(declaration(), None)
