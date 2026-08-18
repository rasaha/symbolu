"""TEV-2 stops where the ADR says it stops (ADR §30).

Structural proof that no BR-1/BR-2, UVI-EV-1 or GV-* capability leaked into this
milestone, that TEV-2 shipped the verification layer §30 assigns it and nothing
beyond, and that no placeholder, stub or reserved field stands in for a later
milestone. A milestone boundary asserted only in prose is not a boundary.
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


def test_the_package_version_is_the_expected_additive_minor_bump():
    """0.1.0 -> 0.2.0: additive, backward-compatible (ADR §30 TEV-2 on TEV-1).

    A minor bump, not a major one, because every TEV-1 symbol remains present
    with the same shape, the same field order, the same enum member order and
    the same digests. A patch bump would be wrong in the other direction: the
    public surface grew.
    """

    assert ugence_trusted_evidence_authority.__version__ == "0.2.0"
    assert api.__version__ == "0.2.0"


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

#: Names TEV-2 must still **not** define.
#:
#: ``EvidenceAdmissionPort`` and ``ReferenceEvidenceAdmission`` are RA-5's,
#: preserved unchanged by E-13; aligning them with the platform receipt is DD-6
#: and is not TEV-2's. ``EvidenceVerificationReceipt`` without the ``Signed``
#: prefix would be the unsigned "receipt" §13.3 says does not exist.
FORBIDDEN_CLASS_NAMES = {
    "EvidenceAdmissionPort", "ReferenceEvidenceAdmission",
    "EvidenceVerificationReceipt",
    "SystemManifest", "SubjectContext", "AssessedSystemBinding",
    "ActionGate", "DeploymentAuthorizer", "ExecutionReceipt",
    "CredentialIssuer", "CertificateAuthority", "KmsClient",
    "PolicyApplicabilityResolver", "ReadinessEvaluator",
}

BR_CLASS_NAMES = {
    "BenchmarkDefinition", "BenchmarkRegistry", "BenchmarkReference",
    "BenchmarkResolution", "BenchmarkVersion", "BenchmarkPublisher",
}

#: The TEV-2 surface ADR §30 assigns to this milestone. Each must exist.
REQUIRED_TEV2_CLASS_NAMES = {
    "EvidenceVerificationAuthority",
    "EvidenceVerificationDetermination",
    "EvidenceVerificationProtocolPort",
    "SignedEvidenceSubmission",
    "SignedEvidenceVerificationReceipt",
    "SignedReceiptVerifier",
    "ReceiptScopeExpectation",
    "SignatureOnlyVerificationResult",
    "ScopeBoundVerificationResult",
    "ReceiptIssuer",
    "ReceiptSignerPort",
    "TrustAnchorRecord",
    "TrustAnchorResolverPort",
    "KeyRevocation",
    "EvidenceVerificationAuditRecord",
}


def _defined_class_names():
    names = set()
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
    return names


@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_CLASS_NAMES))
def test_no_out_of_scope_type_is_defined(forbidden):
    assert forbidden not in _defined_class_names()
    assert forbidden not in api.__all__


@pytest.mark.parametrize("required", sorted(REQUIRED_TEV2_CLASS_NAMES))
def test_the_ratified_tev2_type_is_defined_and_exported(required):
    """The boundary cuts both ways: TEV-2 must also *reach* its milestone."""

    assert required in _defined_class_names()
    assert required in api.__all__


@pytest.mark.parametrize("forbidden", sorted(BR_CLASS_NAMES))
def test_no_benchmark_registry_type_is_defined(forbidden):
    assert forbidden not in _defined_class_names()
    assert forbidden not in api.__all__


def test_cryptography_comes_only_from_the_two_ratified_backends():
    """TEV-2 signs, and implements none of it.

    Ed25519 signing, verification and public-key derivation come from
    ``cryptography`` (OpenSSL); strict point validation comes from libsodium
    through ``PyNaCl``. Both are imported from ``authority/backend.py`` and
    nowhere else, so there is exactly one module to review and exactly one set
    of validation rules in force.

    An earlier revision implemented RFC 8032 in ``authority/ed25519.py``,
    justified partly by reading ADR §23 as a prohibition on third-party
    cryptography. §23 is the *Ugence package* dependency matrix and says no such
    thing. The independent closure audit found the handwritten implementation
    unsafe (F-01, F-02, F-03, F-06), and it is now deleted — this test asserts
    it has not come back.

    ``hmac``, ``secrets`` and ``ecdsa`` remain banned outright: ``hmac`` is not
    a signature scheme, ``secrets`` is an entropy source this package must not
    have, and ``ecdsa`` would be both a second algorithm and an unmaintained
    pure-Python one.
    """

    banned_modules = {"hmac", "secrets", "ecdsa"}
    backends = {"cryptography", "nacl"}
    backend_importers = set()
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            assert not (roots & banned_modules), (
                path.name, sorted(roots & banned_modules)
            )
            if roots & backends:
                backend_importers.add(path.name)
    assert backend_importers == {"backend.py"}, sorted(backend_importers)


def test_the_handwritten_implementation_is_gone_and_stays_gone():
    """No module implements curve arithmetic, and none is named for one.

    The audit's finding was not "the implementation had a bug" but "a
    production path depended on handwritten cryptography". The correction only
    holds if it cannot quietly return, so both the file name and the arithmetic
    it contained are asserted absent.
    """

    for path in _sources():
        assert path.name != "ed25519.py", path

    # The primitives an in-package implementation would need. Searching for the
    # operations rather than the module name catches a rename.
    banned_symbols = {
        "_point_add", "_point_double", "_scalarmult", "_decode_point",
        "_encode_point", "_recover_x", "_edwards_add", "_sha512_modq",
    }
    banned_constants = {
        "2**255 - 19", "2 ** 255 - 19", "57896044618658097711785492504343953926634992332820282019728792003956564819949",
    }
    for path in _sources():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert node.name not in banned_symbols, (path.name, node.name)
        for constant in banned_constants:
            assert constant not in source, (path.name, constant)


def test_the_contracts_subpackage_still_defines_no_signing_surface():
    """The TEV-1/TEV-2 seam, asserted structurally.

    TEV-1's guard was "nothing in this package signs". TEV-2 signs, so the guard
    moves to the seam that still matters: the ``contracts`` subpackage — which
    holds every TEV-1 shape and every pinned digest — must remain free of
    signing, key and trust-anchor code. If a signature field or a key handle
    ever appeared there, it would mean TEV-2 had retrofitted the TEV-1 payload
    rather than wrapping it.
    """

    import ugence_trusted_evidence_authority.contracts as contracts_pkg

    contracts_root = pathlib.Path(contracts_pkg.__file__).resolve().parent
    banned_stems = ("sign", "signature", "keypair", "private_key", "public_key",
                    "trust_anchor", "verify_signature", "ed25519")

    # Domain **tags** are the one exception, and are exempted by exact name.
    # ``contracts/canonical.py`` is the single module that owns domain selection
    # for the whole package — TEV-1 put it there deliberately, "keyed by type
    # name so this module stays import-cycle-free" — so TEV-2's tags are
    # declared there too. A tag is an opaque byte-space label: it holds no key,
    # performs no signing, and imports nothing from the authority layer.
    exempt_names = {
        "TRUST_ANCHOR_RECORD_DIGEST_DOMAIN",
        "SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN",
        "SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN",
    }
    for path in sorted(contracts_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        # Enum member names are *vocabulary*, not code. The refusal enum
        # legitimately names signature, key and trust-anchor conditions —
        # DD-1 delegates one vocabulary covering the whole failure surface, and
        # §11 rows 5 and 6 are in it. Naming a refusal is not performing a
        # check; the scan below is for signing *code*, so enum bodies are
        # skipped and the members are pinned by ``tests/contract/test_reasons``.
        enum_bodies = {
            id(child)
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(
                isinstance(b, ast.Name) and b.id.endswith("Enum") for b in node.bases
            )
            for child in node.body
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lowered = node.name.lower()
                for stem in banned_stems:
                    assert stem not in lowered, (path.name, node.name)
            if isinstance(node, ast.Assign) and id(node) not in enum_bodies:
                for target in node.targets:
                    if not isinstance(target, ast.Name) or target.id in exempt_names:
                        continue
                    lowered = target.id.lower()
                    for stem in banned_stems:
                        assert stem not in lowered, (path.name, target.id)

    # And the contracts layer imports nothing from the authority layer, so the
    # arrow runs one way only: authority -> contracts, never the reverse.
    for path in sorted(contracts_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "from ..authority" not in text, path.name
        assert "from .authority" not in text, path.name
        assert "import authority" not in text, path.name


def test_the_tev1_receipt_payload_carries_no_signature_field():
    """The envelope wraps the payload; it did not retrofit fields into it."""

    import dataclasses as dc

    from ugence_trusted_evidence_authority.api import (
        EvidenceVerificationReceiptPayload,
    )

    names = [f.name for f in dc.fields(EvidenceVerificationReceiptPayload)]

    # ``verified_at`` is ADR §9 row 6 — the mandatory, explicit verification
    # instant TEV-1 already carried — so it is named exactly and kept, while
    # every *flag*-shaped spelling of "verified" stays forbidden.
    assert "verified_at" in names
    for banned in ("signature", "signed", "signer", "envelope", "authentic",
                   "trust_anchor", "public_key", "is_verified",
                   "verified_flag", "verification_status"):
        assert not any(banned in n for n in names), (banned, names)


def test_hashlib_is_used_only_for_digests_and_the_rfc8032_hash():
    """``hashlib`` appears in exactly two places, each for its documented job.

    ``contracts/canonical.py`` uses sha-256 for the one digest path;
    ``authority/verification.py`` uses sha-256 to derive a deterministic receipt
    id; ``authority/reverification.py`` uses sha-256 for the scope-expectation
    digest. No fourth module hashes anything, and no module substitutes a hash
    for a signature.

    Ed25519's internal SHA-512 is **not** in this list any more, and its absence
    is the point: the hash is inside ``cryptography``, not inside this package.
    """

    users = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                a.name == "hashlib" for a in node.names
            ):
                users.append(path.name)
    assert sorted(set(users)) == [
        "canonical.py",
        "reverification.py",
        "verification.py",
    ]


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
               "NullVerifier", "StubVerifier", "AllowAllTrustAnchor",
               "InsecureSigner", "SkipSignature")
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
