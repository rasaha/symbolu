"""The verifier reports, it does not bless.

A verifier that returned ``True`` would be the whole failure CE-4 exists to
prevent: a consumer reading integrity as authenticity. So the tests here check
both halves — that tampering is caught, and that a clean verification still says
out loud what it did not establish.
"""

from __future__ import annotations

import dataclasses

import pytest

from ugence_clearance_export import (
    UNCHECKABLE,
    ExportIntegrityError,
    artifact_to_dict,
    verify_export,
)

from _fixtures import artifact


def test_a_clean_artifact_verifies():
    report = verify_export(artifact())
    assert report.integrity_verified is True
    assert report.artifact_id.startswith("cxp_")
    assert report.receipt_id.startswith("acr_")


def test_verification_names_what_it_could_not_check():
    report = verify_export(artifact())
    assert len(report.uncheckable) == 4
    joined = " ".join(report.uncheckable)
    assert "AUTHENTICITY_NOT_ESTABLISHED" in joined
    assert "DECLARER_IDENTITY_NOT_VERIFIED" in joined
    assert "POLICY_IN_FORCE_NOT_CHECKABLE" in joined
    assert "APPROVAL_NOT_PROVEN" in joined
    assert report.uncheckable == UNCHECKABLE


def test_verification_confers_nothing_and_says_so():
    report = verify_export(artifact())
    assert report.confers.startswith("NOTHING")
    assert "grants no permission" in report.confers


def test_verification_carries_the_three_labels_forward():
    """A consumer that only ever looks at the verification result still sees all
    three ceilings."""
    report = verify_export(artifact())
    assert report.identity_assurance == "PRESENTED_UNPROVEN"
    assert report.authenticity == "UNSIGNED"
    assert report.data_classification == "SYNTHETIC_DEMONSTRATION_ONLY"


def test_a_tampered_wrapper_is_caught():
    tampered = dataclasses.replace(artifact(), exported_for_tenant="tenant-beta")
    with pytest.raises(ExportIntegrityError):
        verify_export(tampered)


def test_a_swapped_clearance_is_caught():
    """The artifact wrapper and the clearance inside it are verified separately: an
    artifact whose wrapper is intact and whose decision was swapped is not intact."""
    from ugence_action_clearance import ClearanceReceiptBody

    original = artifact()
    swapped_body = ClearanceReceiptBody(
        **{**original.body.__dict__, "obligations": ("do-nothing",)})
    swapped = dataclasses.replace(original, body=swapped_body)
    with pytest.raises(ExportIntegrityError):
        verify_export(swapped)


def test_a_forged_fingerprint_is_caught():
    forged = dataclasses.replace(artifact(), artifact_fingerprint="0" * 64)
    with pytest.raises(ExportIntegrityError):
        verify_export(forged)


def test_verification_is_pure_and_repeatable():
    built = artifact()
    first = verify_export(built)
    second = verify_export(built)
    assert first == second


def test_two_exports_of_the_same_clearance_are_byte_identical():
    """No clock, no nonce, no ordering by dict insertion: the export is a function
    of its inputs, so an external runtime can compare two copies directly."""
    assert artifact_to_dict(artifact()) == artifact_to_dict(artifact())
    assert artifact().artifact_fingerprint == artifact().artifact_fingerprint
