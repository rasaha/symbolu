"""SE-4: TEA's trust anchors are reused as the identical objects; no second store.

This module binds ``ugence_trusted_evidence_authority`` as a module object,
which TEA's consumer grant permits only in the named boundary-policing test
modules — this is one of them.
"""

from __future__ import annotations

import ast
import pathlib

import ugence_trusted_evidence_authority

import ugence_risk_authority_effect_attestation as ea

SRC = pathlib.Path(ea.__file__).resolve().parent


def test_happy_every_re_exported_trust_symbol_is_the_identical_tea_object():
    for name in (
        "TrustAnchorCoordinate", "TrustAnchorRecord", "TrustAnchorCapability",
        "TrustAnchorResolution", "TrustAnchorResolverPort", "KeyRevocation",
        "StaticTrustAnchorDirectory", "DenyAllTrustAnchorDirectory",
    ):
        assert getattr(ea, name) is getattr(ugence_trusted_evidence_authority, name), name


def test_the_package_defines_no_anchor_record_resolver_or_directory_of_its_own():
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                lowered = node.name.lower()
                for banned in ("anchor", "directory", "resolver", "store", "keyring", "trustset"):
                    assert banned not in lowered, (path.name, node.name)
                methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                assert "resolve" not in methods, (path.name, node.name)


def test_the_two_effect_capabilities_are_tea_members_lent_not_minted_here():
    caps = ugence_trusted_evidence_authority.TrustAnchorCapability
    assert ea.capability_for_role(ea.EffectAttesterRole.EXECUTING_PROVIDER) is (
        caps.EFFECT_ATTESTATION_EXECUTING_PROVIDER)
    assert ea.capability_for_role(ea.EffectAttesterRole.INDEPENDENT_OBSERVER) is (
        caps.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER)
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                bases = {getattr(b, "id", getattr(b, "attr", "")) for b in node.bases}
                assert "TrustAnchorCapability" not in bases, (path.name, node.name)
                if "Enum" in bases:
                    assert node.name in ("EffectAttesterRole", "EffectAttestationVerificationOutcome",
                                         "EffectAttestationRefusalReason"), node.name


def test_the_anchor_revision_is_teas_digest_relabelled_never_recomputed():
    from _fixtures import anchor_of, provider_signer

    anchor = anchor_of(provider_signer())
    assert ea.anchor_record_digest(anchor) == "sha256:" + anchor.canonical_digest()


def test_reference_grade_resolvers_are_exactly_teas_static_directory():
    assert ea.REFERENCE_GRADE_RESOLVERS == (ugence_trusted_evidence_authority.StaticTrustAnchorDirectory,)
