"""TEV-1 stops where the ADR says it stops (ADR §30).

Structural proof that no TEV-2, BR-1/BR-2, UVI-EV-1 or GV-* capability leaked
into this milestone, and that no placeholder, stub or reserved field stands in
for one. A milestone boundary asserted only in prose is not a boundary.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import pathlib

import pytest
import ugence_trusted_evidence_authority
from ugence_trusted_evidence_authority import api

PKG_ROOT = pathlib.Path(ugence_trusted_evidence_authority.__file__).resolve().parent


def _sources():
    return sorted(PKG_ROOT.rglob("*.py"))


def test_the_package_version_is_the_expected_new_package_version():
    assert ugence_trusted_evidence_authority.__version__ == "0.1.0"
    assert api.__version__ == "0.1.0"


def test_no_separate_contract_version_constant_is_minted():
    """Contract-shape packages in this repo do not carry a ``CONTRACT_VERSION``.

    ``CONTRACT_VERSION`` is the *provider* convention
    (``ugence-tap-provider``, ``ugence-actiongate-provider``, the provider
    framework): it names the version of a provider contract implemented against
    a kernel/framework major. The contract-shape packages —
    ``ugence-governance-contracts``, ``ugence-uvi-policy-contracts``,
    ``ugence-policy-authority`` — carry only ``__version__``. TEV-1 follows the
    contract-shape convention rather than inventing a constant for symmetry.

    Versioning that *is* load-bearing here is carried where it belongs: the
    canonicalization rule-set version is bound into every digest.
    """

    assert not hasattr(ugence_trusted_evidence_authority, "CONTRACT_VERSION")
    assert "CONTRACT_VERSION" not in api.__all__
    assert api.TRUSTED_EVIDENCE_CANONICALIZATION_VERSION.endswith("/v1")


# --------------------------------------------------------------------------- #
# TEV-2 surfaces are absent
# --------------------------------------------------------------------------- #

TEV2_CLASS_NAMES = {
    "EvidenceVerifier", "TrustedEvidenceVerifier", "TapVerifier",
    "EvidenceVerificationReceipt", "VerificationReceipt", "TrustedEvidenceReceipt",
    "EvidenceVerificationResult", "VerificationResult",
    "TrustAnchor", "TrustAnchorSet", "KeyRing", "VerificationKey",
    "EvidenceSigner", "ReceiptSigner", "EvidenceAdmissionPort",
    "ReferenceEvidenceAdmission",
}

BR_CLASS_NAMES = {
    "BenchmarkDefinition", "BenchmarkRegistry", "BenchmarkReference",
    "BenchmarkResolution", "BenchmarkVersion", "BenchmarkPublisher",
}


def _defined_class_names():
    names = set()
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
    return names


@pytest.mark.parametrize("forbidden", sorted(TEV2_CLASS_NAMES))
def test_no_tev2_type_is_defined(forbidden):
    assert forbidden not in _defined_class_names()
    assert forbidden not in api.__all__


@pytest.mark.parametrize("forbidden", sorted(BR_CLASS_NAMES))
def test_no_benchmark_registry_type_is_defined(forbidden):
    assert forbidden not in _defined_class_names()
    assert forbidden not in api.__all__


def test_no_cryptographic_primitive_is_imported_or_implemented():
    banned_modules = {"hmac", "secrets", "cryptography", "nacl", "ecdsa", "ed25519"}
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            assert not (roots & banned_modules), (path.name, sorted(roots & banned_modules))


def test_hashlib_is_used_only_for_the_content_digest_never_for_signing():
    """``hashlib`` is a digest primitive here, not a signature primitive.

    Checked over defined names rather than raw text, so the modules' own prose
    (which discusses signing precisely because it does *not* do it) is not
    mistaken for an implementation.
    """

    import ugence_trusted_evidence_authority.contracts.canonical as canonical

    assert "hashlib.sha256" in pathlib.Path(canonical.__file__).read_text(
        encoding="utf-8"
    )

    banned_stems = ("sign", "signature", "keypair", "private_key", "public_key",
                    "trust_anchor", "verify_signature")
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lowered = node.name.lower()
                for stem in banned_stems:
                    assert stem not in lowered, (path.name, node.name)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        lowered = target.id.lower()
                        for stem in banned_stems:
                            assert stem not in lowered, (path.name, target.id)


# --------------------------------------------------------------------------- #
# No placeholder, stub or reserved field
# --------------------------------------------------------------------------- #

def test_no_public_dataclass_carries_a_field_reserved_for_a_later_milestone():
    reserved_markers = ("reserved", "placeholder", "todo", "future", "_tev2", "unused")
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                lowered = field.name.lower()
                for marker in reserved_markers:
                    assert marker not in lowered, (name, field.name)


def test_no_source_file_contains_a_stub_or_permissive_placeholder_marker():
    markers = ("TODO", "FIXME", "XXX", "NotImplementedError", "pragma: no cover",
               "allow_all", "AllowAll", "PermissiveVerifier", "FakeVerifier",
               "NullVerifier", "StubVerifier")
    for path in _sources():
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            assert marker not in source, (path.name, marker)


def test_every_public_enum_member_is_reachable_and_meaningful():
    """No enum ships a member no TEV-1 code path can justify."""

    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            members = list(obj)
            assert members, name
            values = [m.value for m in members]
            assert len(set(values)) == len(values), name
            assert all(v == v.upper() for v in values), name


# --------------------------------------------------------------------------- #
# Ownership: this package is not the things it must not be
# --------------------------------------------------------------------------- #

def test_the_distribution_and_namespace_are_the_ratified_ones():
    assert ugence_trusted_evidence_authority.__name__ == "ugence_trusted_evidence_authority"
    manifest = PKG_ROOT.parents[1] / "public_api.json"
    if manifest.is_file():
        import json

        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["distribution"] == "ugence-trusted-evidence-authority"
        assert data["namespace"] == "ugence_trusted_evidence_authority"


def test_no_assertion_support_vocabulary_is_reused_from_the_tap_provider():
    """ADR §6.1 — the two trust questions are never merged.

    ``ugence-tap-provider``'s ``TapOutcome`` members and its
    ``evidence_coverage`` ratio are an assertion-support score. Reusing either as
    a verification vocabulary is prohibited by name.
    """

    forbidden = {"SUPPORTED", "UNSUPPORTED", "CONSTRAINED", "UNKNOWN"}
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            assert not ({m.name for m in obj} & forbidden), name
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                assert "coverage" not in field.name.lower(), (name, field.name)
                assert "confidence" not in field.name.lower(), (name, field.name)
                assert "score" not in field.name.lower(), (name, field.name)
                assert "fingerprint" not in field.name.lower(), (name, field.name)
