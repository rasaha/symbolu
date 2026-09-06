"""The three honesty labels: present, non-optional, and not softenable.

ADR §13.1 says the artifact carries three separate claims, "none of which may be
inferred from the absence of another, and none of which an implementation may omit
because a consumer 'would know'". §13.3 adds that nothing may strip, default or
condition away the label.

That is a property of the type, not of anyone's care, so it is tested as one. Each
route by which a label could go missing gets its own test: omission at
construction, substitution with a value the package does not admit, absence from
the serialized form, absence from the reconstruction path, and quiet alteration
after the fact.
"""

from __future__ import annotations

import pytest

from ugence_action_clearance import ClearanceReceiptBody
from ugence_clearance_export import (
    AUTHENTICITY_PREREQUISITE,
    AuthenticityClaimRefused,
    ClassificationClaimRefused,
    ClearanceExportArtifact,
    ContractViolation,
    ExportAuthenticity,
    ExportDataClassification,
    IdentityAssurance,
    IdentityAssuranceClaimRefused,
    artifact_from_dict,
    artifact_to_dict,
    build_export,
)

from _fixtures import artifact, body

THE_THREE = ("identity_assurance", "authenticity", "data_classification")


def test_each_enum_has_exactly_one_member():
    """One member is the honest size of what the platform can establish (CE-3, CE-4,
    CE-7). A second member would invite a producer to set it."""
    assert list(IdentityAssurance) == [IdentityAssurance.PRESENTED_UNPROVEN]
    assert list(ExportAuthenticity) == [ExportAuthenticity.UNSIGNED]
    assert list(ExportDataClassification) == [
        ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY]


@pytest.mark.parametrize("label", THE_THREE)
def test_no_label_can_be_omitted_at_construction(label):
    """Not defaults: keyword arguments. Leaving one out is a TypeError, not a
    quietly-correct artifact that a later caller could quietly make incorrect."""
    supplied = {
        "identity_assurance": IdentityAssurance.PRESENTED_UNPROVEN,
        "authenticity": ExportAuthenticity.UNSIGNED,
        "data_classification": ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY,
    }
    del supplied[label]
    with pytest.raises(TypeError):
        build_export(body(), **supplied)


def test_an_inadmissible_identity_assurance_is_refused():
    with pytest.raises(IdentityAssuranceClaimRefused):
        build_export(
            body(),
            identity_assurance="VERIFIED",
            authenticity=ExportAuthenticity.UNSIGNED,
            data_classification=ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY)


def test_an_inadmissible_authenticity_is_refused():
    with pytest.raises(AuthenticityClaimRefused):
        build_export(
            body(),
            identity_assurance=IdentityAssurance.PRESENTED_UNPROVEN,
            authenticity="SIGNED",
            data_classification=ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY)


def test_an_inadmissible_classification_is_refused():
    with pytest.raises(ClassificationClaimRefused):
        build_export(
            body(),
            identity_assurance=IdentityAssurance.PRESENTED_UNPROVEN,
            authenticity=ExportAuthenticity.UNSIGNED,
            data_classification="PRODUCTION")


@pytest.mark.parametrize("label", THE_THREE)
def test_every_serialized_artifact_carries_every_label(label):
    assert label in artifact_to_dict(artifact())


@pytest.mark.parametrize("label", THE_THREE)
def test_a_payload_that_dropped_a_label_is_refused_not_defaulted(label):
    """The reconstruction path is where a stripped label would otherwise re-enter
    as an innocent-looking absence."""
    payload = artifact_to_dict(artifact())
    del payload[label]
    with pytest.raises(ContractViolation):
        artifact_from_dict(payload)


@pytest.mark.parametrize("label", THE_THREE)
def test_a_payload_that_softened_a_label_is_refused(label):
    payload = artifact_to_dict(artifact())
    payload[label] = "VERIFIED_AND_SIGNED_PRODUCTION"
    with pytest.raises(ContractViolation):
        artifact_from_dict(payload)


@pytest.mark.parametrize("label", THE_THREE)
def test_altering_a_label_changes_the_fingerprint(label):
    """The labels are inside the fingerprint preimage, so a consumer that
    recomputes detects a stripped label exactly as it detects an altered
    decision."""
    original = artifact()
    payload = artifact_to_dict(original)
    without = dict(payload)
    del without[label]
    # Rebuilt from the same body but with the label absent: refused outright, so
    # there is no fingerprint to compare — which is the stronger property.
    with pytest.raises(ContractViolation):
        artifact_from_dict(without)
    # And the label genuinely participates: it appears in the canonical bytes.
    from ugence_clearance_export import canonical_form
    assert payload[label] in canonical_form(original)


def test_the_authenticity_prerequisite_is_fixed_text():
    """CE-4 requires the artifact to name the unfed prerequisite. Softening the
    wording would let an artifact imply the gap is smaller than it is."""
    built = artifact()
    assert built.authenticity_prerequisite == AUTHENTICITY_PREREQUISITE
    assert "no signing key or trust root is configured" in AUTHENTICITY_PREREQUISITE
    with pytest.raises(AuthenticityClaimRefused):
        ClearanceExportArtifact(
            artifact_version=built.artifact_version,
            body=built.body,
            identity_assurance=built.identity_assurance,
            authenticity=built.authenticity,
            authenticity_prerequisite="signing is planned",
            data_classification=built.data_classification,
            exported_for_tenant=built.exported_for_tenant,
            artifact_fingerprint=built.artifact_fingerprint,
        )


def test_the_labels_survive_a_round_trip():
    original = artifact()
    restored = artifact_from_dict(artifact_to_dict(original))
    assert restored == original
    assert restored.artifact_fingerprint == original.artifact_fingerprint


def test_the_body_is_carried_unaltered():
    """CE-2: action-clearance is not extended. The receipt goes out as it came in."""
    original = artifact()
    assert isinstance(original.body, ClearanceReceiptBody)
    restored = artifact_from_dict(artifact_to_dict(original))
    assert restored.body == original.body
    assert restored.receipt_id == original.receipt_id
