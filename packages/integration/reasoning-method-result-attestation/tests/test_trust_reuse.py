"""SCR-1: TEA's trust anchors are reused as the identical objects; no second store.

This module binds ``ugence_trusted_evidence_authority`` as a module object,
which TEA's consumer grant permits only in the named boundary-policing test
modules — this is one of them.
"""

from __future__ import annotations

import ast
import pathlib

import ugence_trusted_evidence_authority

import ugence_reasoning_method_result_attestation as ra

SRC = pathlib.Path(ra.__file__).resolve().parent


def test_happy_every_re_exported_trust_symbol_is_the_identical_tea_object():
    for name in (
        "TrustAnchorCoordinate", "TrustAnchorRecord", "TrustAnchorCapability",
        "TrustAnchorResolution", "TrustAnchorResolverPort", "KeyRevocation",
        "StaticTrustAnchorDirectory", "DenyAllTrustAnchorDirectory",
    ):
        assert getattr(ra, name) is getattr(ugence_trusted_evidence_authority, name), name


def test_the_package_defines_no_anchor_record_resolver_or_directory_of_its_own():
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                lowered = node.name.lower()
                for banned in ("anchor", "directory", "resolver", "store", "keyring", "trustset"):
                    assert banned not in lowered, (path.name, node.name)
                methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                assert "resolve" not in methods, (path.name, node.name)


def test_the_comparison_result_capability_is_a_tea_member_lent_not_minted_here():
    caps = ugence_trusted_evidence_authority.TrustAnchorCapability
    assert ra.capability_for_role(ra.ComparisonResultAttesterRole.COMPARISON_ENGINE) is (
        caps.COMPARISON_RESULT_ATTESTATION)
    assert list(caps)[-1] is caps.COMPARISON_RESULT_ATTESTATION and len(list(caps)) == 7
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                bases = {getattr(b, "id", getattr(b, "attr", "")) for b in node.bases}
                assert "TrustAnchorCapability" not in bases, (path.name, node.name)
                if "Enum" in bases:
                    assert node.name in ("ComparisonResultAttesterRole", "ComparisonResultVerificationOutcome",
                                         "ComparisonResultRefusalReason"), node.name


def test_the_anchor_revision_is_teas_digest_relabelled_never_recomputed():
    from _fixtures import anchor_of, engine_signer

    anchor = anchor_of(engine_signer())
    assert ra.anchor_record_digest(anchor) == "sha256:" + anchor.canonical_digest()


def test_reference_grade_resolvers_are_exactly_teas_static_directory():
    assert ra.REFERENCE_GRADE_RESOLVERS == (ugence_trusted_evidence_authority.StaticTrustAnchorDirectory,)
