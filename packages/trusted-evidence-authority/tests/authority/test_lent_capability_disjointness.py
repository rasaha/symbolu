"""The lent Cloud Scaling capability is a vocabulary, not an authority.

``TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION`` was added so the
Cloud Scaling producer-attestation consumer stops overloading
:attr:`~TrustAnchorCapability.EVIDENCE_PRODUCTION` — a key entitled to sign Trusted
Evidence must not thereby be entitled to attest a capacity recommendation.

This module asserts the two properties that make lending it safe:

* it grants **nothing here** — no evidence path and no receipt path admits it; and
* it takes **nothing** from the two capabilities that existed before it — their
  spellings, order and behaviour are unchanged.

This package defines the coordinate and verifies nothing under it. Verification of a
Cloud Scaling recommendation attestation belongs to
``ugence-cloud-scaling-producer-attestation``, and the corresponding refusals are
asserted there.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_trusted_evidence_authority
from ugence_trusted_evidence_authority import (
    EvidenceAdmissionOutcome,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustedEvidenceRefusalReason as R,
)

from _authority_builders import (
    VERIFIED_AT,
    VERIFIER_KEY_ID,
    authority,
    authority_anchor,
    directory,
    producer_anchor,
    request,
    reverifier,
    submission,
)

CS = TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION
PKG_ROOT = pathlib.Path(ugence_trusted_evidence_authority.__file__).resolve().parent


# --------------------------------------------------------------------------------- #
# 1. Nothing that existed before moved.
# --------------------------------------------------------------------------------- #


def test_the_pre_existing_members_keep_their_spelling_and_declaration_order():
    """An additive enum change may not rename, respell or reorder what came before."""

    members = list(TrustAnchorCapability)
    assert [m.name for m in members[:2]] == ["EVIDENCE_PRODUCTION", "RECEIPT_ISSUANCE"]
    assert [m.value for m in members[:2]] == ["EVIDENCE_PRODUCTION", "RECEIPT_ISSUANCE"]
    assert members[2] is CS
    assert CS.value == "CLOUD_SCALING_RECOMMENDATION_ATTESTATION"
    assert len(members) == 3


def test_the_new_member_is_distinct_from_both_existing_ones():
    """No aliasing and no shared value: three members, three distinct spellings."""

    assert CS is not TrustAnchorCapability.EVIDENCE_PRODUCTION
    assert CS is not TrustAnchorCapability.RECEIPT_ISSUANCE
    assert CS != TrustAnchorCapability.EVIDENCE_PRODUCTION
    assert CS != TrustAnchorCapability.RECEIPT_ISSUANCE
    assert len({m.value for m in TrustAnchorCapability}) == 3


# --------------------------------------------------------------------------------- #
# 2. The lent member grants no authority in this package.
# --------------------------------------------------------------------------------- #


def test_an_evidence_submission_is_refused_when_the_producer_holds_only_the_lent_capability():
    """A key granted only the lent capability cannot produce Trusted Evidence.

    The evidence protocol pins ``EVIDENCE_PRODUCTION`` into the coordinate it resolves,
    so an anchor filed under the lent capability is simply not at that coordinate. This
    is the mirror image of the Cloud Scaling refusal asserted downstream.
    """

    anchors = directory(producer_anchor(capability=CS), authority_anchor())
    determination = authority(trust_anchors=anchors).verify(
        submission(),
        request(),
        verified_at=VERIFIED_AT,
        verifier_key_id=VERIFIER_KEY_ID,
    )
    assert determination.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING in determination.refusal_reasons


def test_the_evidence_protocol_resolves_only_the_evidence_production_capability():
    """Structural: the lent member never appears in an evidence-path coordinate."""

    source = (PKG_ROOT / "authority" / "verification.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    capabilities = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "TrustAnchorCapability"
    }
    assert capabilities == {"EVIDENCE_PRODUCTION"}, capabilities


def test_the_receipt_paths_resolve_only_the_receipt_issuance_capability():
    """Structural: the lent member never appears in a receipt-path coordinate."""

    for module in ("signing.py", "reverification.py"):
        tree = ast.parse((PKG_ROOT / "authority" / module).read_text(encoding="utf-8"))
        capabilities = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "TrustAnchorCapability"
        }
        assert capabilities <= {"RECEIPT_ISSUANCE"}, (module, capabilities)


def test_a_receipt_cannot_be_verified_under_an_anchor_holding_the_lent_capability():
    """A key granted only the lent capability cannot stand in for a receipt issuer."""

    from _authority_builders import envelope

    signed = envelope()
    anchors = directory(producer_anchor(), authority_anchor(capability=CS))
    result = reverifier(trust_anchors=anchors).verify_signature(
        signed, evaluated_at=VERIFIED_AT
    )
    assert result.outcome.name == "REFUSED"
    assert result.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING


def test_the_lent_capability_is_never_substitutable_for_either_existing_one():
    """Changing only the capability changes the coordinate, so nothing is fungible."""

    base = dict(authority_id="a", key_id="k")
    coordinates = {
        capability: TrustAnchorCoordinate(**base, capability=capability)
        for capability in TrustAnchorCapability
    }
    assert len(set(coordinates.values())) == 3
    assert len({c.canonical_digest() for c in coordinates.values()}) == 3


# --------------------------------------------------------------------------------- #
# 3. This package verifies nothing under the lent member.
# --------------------------------------------------------------------------------- #


def test_this_package_defines_the_lent_capability_and_verifies_nothing_under_it():
    """The member is declared exactly once, in the trust contract, and used nowhere else.

    If this package ever grew a verification path keyed on the lent capability, it would
    be asserting authority over a Cloud Scaling payload it does not define, does not
    canonicalize and cannot reconcile. That is the failure this test exists to catch.
    """

    referencing = []
    for path in sorted(PKG_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "CLOUD_SCALING_RECOMMENDATION_ATTESTATION" in text:
            referencing.append(path.relative_to(PKG_ROOT).as_posix())
    assert referencing == ["authority/trust.py"], referencing


def test_no_cloud_scaling_contract_is_imported_or_named_by_this_package():
    """Lending a vocabulary is not importing a domain. The arrow stays one-way."""

    offenders = []
    for path in sorted(PKG_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if "cloud_scaling" in module or "cloud-scaling" in module:
                    offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders
