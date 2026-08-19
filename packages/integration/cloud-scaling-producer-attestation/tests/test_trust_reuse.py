"""TEV's trust primitives are reused, not rebuilt — and its evidence verifier is not.

Two claims, both structural. First: every trust-anchor contract this package uses is the
*identical object* TEV exports, so there is exactly one anchor store in the repository.
Second: TEV's evidence and receipt **verifiers** are not reused, because a producer
attestation is not an evidence item and a verifier specified against one payload has not
verified another.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from _producer_fixtures import (
    AS_OF,
    ISSUER_ID,
    PRODUCER_KEY_ID,
    build_anchor,
    build_attestation,
    build_directory,
    build_verifier,
)

import ugence_trusted_evidence_authority as tev
import ugence_cloud_scaling_producer_attestation as pkg
from ugence_cloud_scaling_producer_attestation import (
    PRODUCER_ATTESTATION_CAPABILITY,
    REFERENCE_GRADE_RESOLVERS,
    DenyAllTrustAnchorDirectory,
    KeyRevocation,
    ProducerAttestationConfigurationError,
    ProducerAuthenticityOutcome,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustAnchorResolverPort,
    producer_anchor_coordinate,
    require_production_resolver,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

O = ProducerAuthenticityOutcome
PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent


# --------------------------------------------------------------------------------------- #
# 1. The same objects, not copies
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    [
        "TrustAnchorCoordinate",
        "TrustAnchorRecord",
        "TrustAnchorCapability",
        "TrustAnchorResolution",
        "TrustAnchorResolverPort",
        "KeyRevocation",
        "StaticTrustAnchorDirectory",
        "DenyAllTrustAnchorDirectory",
    ],
)

@pytest.mark.invariant
def test_every_trust_contract_is_the_identical_tev_object(name):
    """R-1: re-exported, never re-declared. A second store could drift from the first."""

    assert getattr(pkg, name) is getattr(tev, name), name


def test_no_trust_anchor_type_is_defined_in_this_package():
    """R-2: no class in this distribution declares a trust anchor, key or directory."""

    offenders = []
    for path in sorted(PKG_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                lowered = node.name.lower()
                if any(
                    fragment in lowered
                    for fragment in ("trustanchor", "keyring", "keystore", "directory")
                ):
                    offenders.append(f"{path.name}: {node.name}")
    assert offenders == [], offenders


def test_no_local_key_map_exists_in_the_package():
    """R-3: no dictionary of keys, no key registry, no ambient anchor set."""

    banned = ("KEY_MAP", "KEYS = {", "TRUSTED_KEYS", "PUBLIC_KEYS", "ANCHORS = {")
    for path in sorted(PKG_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for phrase in banned:
            assert phrase not in text, f"{path.name}: {phrase}"


@pytest.mark.invariant
def test_resolution_is_by_exact_coordinate_only():
    """R-4: the coordinate is the whole lookup, and the capability is not a parameter."""

    import inspect

    parameters = set(inspect.signature(producer_anchor_coordinate).parameters)
    assert parameters == {"issuer", "producer_key_id"}
    coordinate = producer_anchor_coordinate(
        issuer=ISSUER_ID, producer_key_id=PRODUCER_KEY_ID
    )
    assert coordinate.capability is PRODUCER_ATTESTATION_CAPABILITY


def test_a_near_miss_coordinate_is_a_miss(candidate):
    """R-5: no prefix match, no case folding, no wildcard, no first-key-wins."""

    for near_miss in (
        build_attestation(candidate, issuer=ISSUER_ID.upper()),
        build_attestation(candidate, issuer=ISSUER_ID + "-2"),
        build_attestation(candidate, producer_key_id=PRODUCER_KEY_ID.upper()),
        build_attestation(candidate, producer_key_id=PRODUCER_KEY_ID[:-1]),
    ):
        result = build_verifier().verify(
            candidate=candidate, attestation=near_miss, as_of=AS_OF
        )
        assert result.refusal.outcome is O.ANCHOR_UNKNOWN


def test_a_duplicate_coordinate_is_refused_by_the_store():
    """R-6: TEV refuses two anchors at one coordinate; this package inherits that."""

    from ugence_trusted_evidence_authority import TrustedEvidenceContractError

    with pytest.raises(TrustedEvidenceContractError):
        StaticTrustAnchorDirectory((build_anchor(), build_anchor()))


# --------------------------------------------------------------------------------------- #
# 2. The evidence verifier is NOT reused
# --------------------------------------------------------------------------------------- #


def test_no_tev_evidence_or_receipt_verifier_is_imported():
    """R-7: a verifier specified against evidence has not verified this payload."""

    banned = {
        "EvidenceVerificationAuthority",
        "SignedReceiptVerifier",
        "ReceiptIssuer",
        "ReceiptSigningInput",
        "ReceiptSignerPort",
        "Ed25519ReceiptSigner",
        "EvidenceVerificationDetermination",
    }
    for path in sorted(PKG_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    assert alias.name not in banned, f"{path.name}: {alias.name}"


def test_no_tev_evidence_framing_or_domain_tag_is_used():
    """R-8: TEV's length-prefixed frame and its evidence/receipt domains stay TEV's."""

    banned = (
        "framed_signed_input",
        "TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN",
        "TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN",
        "SIGNED_INPUT_LENGTH_PREFIX_BYTES",
    )
    for path in sorted(PKG_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for phrase in banned:
            # A prose mention in a module docstring explaining the decision is fine; a
            # reference in code is not. Check the AST rather than the raw text.
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    assert node.id != phrase, f"{path.name}: {phrase}"
                if isinstance(node, ast.alias):
                    assert node.name != phrase, f"{path.name}: {phrase}"


@pytest.mark.invariant
def test_the_signed_bytes_are_canonical_json_not_a_length_prefixed_frame(candidate):
    """R-9: this package signs Risk Authority's canonical bytes, and nothing else."""

    attestation = build_attestation(candidate)
    signed = attestation.signed_bytes()
    assert signed.startswith(b"{"), "signed bytes are not canonical JSON"
    assert signed.endswith(b"}")
    assert b"\x00\x00\x00\x00" not in signed[:16], "a length prefix was introduced"


@pytest.mark.invariant
def test_the_producer_capability_is_never_receipt_issuance():
    """R-10: ADR E-3's producer/verifier separation, inherited and asserted."""

    assert PRODUCER_ATTESTATION_CAPABILITY is TrustAnchorCapability.EVIDENCE_PRODUCTION
    assert PRODUCER_ATTESTATION_CAPABILITY is not TrustAnchorCapability.RECEIPT_ISSUANCE
    assert len(list(TrustAnchorCapability)) == 2


# --------------------------------------------------------------------------------------- #
# 3. Reference grade versus production grade
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_static_directory_is_classified_reference_grade():
    """R-11: by the repository's own words, which the production guard reads."""

    assert StaticTrustAnchorDirectory in REFERENCE_GRADE_RESOLVERS
    docstring = StaticTrustAnchorDirectory.__doc__ or ""
    assert "reference" in docstring.lower()
    assert "for tests" in docstring.lower()


@pytest.mark.invariant
def test_the_deny_all_directory_is_not_classified_reference_grade():
    """R-12: it can only refuse, so admitting it in production widens nothing."""

    assert DenyAllTrustAnchorDirectory not in REFERENCE_GRADE_RESOLVERS
    assert require_production_resolver(DenyAllTrustAnchorDirectory()) is not None


def test_the_reference_directory_is_refused_in_production():
    """R-13: refusing it is the ruling this phase was asked to make and did make."""

    with pytest.raises(ProducerAttestationConfigurationError):
        require_production_resolver(build_directory())


@pytest.mark.happy
def test_a_declared_production_resolver_is_admitted():
    """R-14: a managed key service that opts in explicitly is admitted."""

    class ManagedKeyServiceResolver:
        is_production_authoritative = True

        def resolve(self, coordinate):
            return TrustAnchorResolution.refused(
                coordinate,
                tev.TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING,
            )

    resolver = ManagedKeyServiceResolver()
    assert require_production_resolver(resolver) is resolver
    verifier = build_verifier(directory=resolver, production_mode=True)
    assert verifier.production_mode is True


def test_a_truthy_non_true_production_declaration_is_refused():
    """R-15: ``is True``, not truthiness. A trust posture may not rest on coercion."""

    class SloppyResolver:
        is_production_authoritative = "yes"

        def resolve(self, coordinate):  # pragma: no cover - construction fails first
            raise AssertionError

    with pytest.raises(ProducerAttestationConfigurationError):
        require_production_resolver(SloppyResolver())


def test_a_none_resolver_is_refused_in_production():
    """R-16: there is no ambient anchor store to fall back to."""

    with pytest.raises(ProducerAttestationConfigurationError):
        require_production_resolver(None)


@pytest.mark.happy
def test_the_reference_directory_is_still_usable_outside_production(candidate):
    """R-17: refusing it in production does not make it useless for tests and local use."""

    result = build_verifier(directory=build_directory(), production_mode=False).verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert result.refusal is None
