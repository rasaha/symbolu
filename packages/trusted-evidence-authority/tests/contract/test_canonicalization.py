"""Deterministic canonicalization and the single digest path (ADR §22, task §8).

Behavioral tests over the public ``canonical_bytes`` / ``canonical_digest``
functions: pinned bytes, an independently reconstructed digest, offset
equivalence, microsecond preservation, explicit ``None``, and fail-closed
rejection of every type the encoder does not admit.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from _builders import identity, observation, receipt, request, schema
from ugence_trusted_evidence_authority.api import (
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    ApplicabilityCoordinate,
    TrustedEvidenceCanonicalizationError,
    canonical_bytes,
    canonical_digest,
)

# --------------------------------------------------------------------------- #
# Pinned vectors
# --------------------------------------------------------------------------- #

#: Hand-written literal bytes for the smallest contract in the package. Written
#: out by hand from the rules in ``contracts/canonical.py`` — sorted keys, tight
#: separators, the frame's four keys, the declared version and domain strings —
#: NOT copied from a program run. If the encoder changes, this fails.
PINNED_SCHEMA_BYTES = (
    b'{"body":{"schema_id":"ugence.evidence.control-test","schema_version":"1"},'
    b'"canonicalization":"ugence.trusted-evidence-authority/canonicalization/v1",'
    b'"domain":"ugence.trusted-evidence-authority/evidence-identity/v1",'
    b'"type":"EvidenceSchemaRef"}'
)

#: The digest of a representative full evidence identity, pinned so an
#: unintended encoder or field-order change is caught.
#:
#: Changed by the A-02 correction, which added the mandatory ADR §9 row 11-12
#: ``claim`` coordinate to the identity body. The previous pin was
#: ``5fec72b52d13264c31519013a74704fee03cea66f5ebfa22258a3d51f562cf40``; the sole
#: cause of the change is the new ``"claim"`` key in the canonical body. There is
#: no legacy-digest acceptance path — this pin replaces the old one outright, as
#: PR #1444 has never merged.
PINNED_IDENTITY_DIGEST = (
    "26ee959e4c87cc0660895a269c2805af1065ba4f634c9c73070848de7bf51029"
)

#: The digest of a representative receipt payload, under its own domain tag.
PINNED_RECEIPT_DIGEST = (
    "d381c723123c583711b0ce08b0e3fe534e3a065182442a3772b8523c7f18b90a"
)


def test_pinned_canonical_bytes_for_the_minimal_contract():
    assert canonical_bytes(schema()) == PINNED_SCHEMA_BYTES


def test_pinned_digest_is_reconstructible_from_literal_bytes_and_hashlib_alone():
    """Independent reconstruction: no package function is used for the expected value.

    The expected digest is computed here from the hand-written literal byte
    string above using ``hashlib`` only. If the package's digest path ever
    stopped being "sha-256 over exactly ``canonical_bytes``", this diverges.
    """

    expected = hashlib.sha256(PINNED_SCHEMA_BYTES).hexdigest()
    assert canonical_digest(schema()) == expected
    # And the same digest is what a third party recomputes from the emitted
    # bytes, with no package internals involved.
    assert (
        hashlib.sha256(canonical_bytes(schema())).hexdigest()
        == canonical_digest(schema())
    )


def test_pinned_digest_for_a_full_evidence_identity():
    assert identity().canonical_digest() == PINNED_IDENTITY_DIGEST


def test_the_identity_digest_change_is_caused_only_by_the_new_claim_key():
    """The A-02 pin change is explained, not merely accepted.

    The previous pin covered a body without ADR §9 rows 11-12. Removing the one
    new key from the current canonical body must reproduce the old byte sequence
    exactly — proving the digest moved because a coordinate was *added*, not
    because the encoder changed.
    """

    body = json.loads(canonical_bytes(identity()).decode("utf-8"))["body"]
    assert "claim" in body
    del body["claim"]
    reconstructed = json.dumps(
        {
            "body": body,
            "canonicalization": TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
            "domain": EVIDENCE_IDENTITY_DIGEST_DOMAIN,
            "type": "CanonicalEvidenceIdentity",
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert (
        hashlib.sha256(reconstructed).hexdigest()
        == "5fec72b52d13264c31519013a74704fee03cea66f5ebfa22258a3d51f562cf40"
    )


def test_pinned_digest_for_a_receipt_payload():
    assert receipt().canonical_digest() == PINNED_RECEIPT_DIGEST
    assert (
        hashlib.sha256(receipt().canonical_bytes()).hexdigest()
        == PINNED_RECEIPT_DIGEST
    )


def test_contract_types_untouched_by_the_correction_keep_their_bytes():
    """Only the identity gained a key; its siblings are byte-identical.

    ``EvidenceSchemaRef``'s pinned bytes above are unchanged, which also shows
    the A-03 NFC correction moved no digest: it rejects values that were never
    canonicalizable, and leaves every valid NFC value exactly as it was.
    """

    assert canonical_bytes(schema()) == PINNED_SCHEMA_BYTES
    assert (
        canonical_digest(schema())
        == "54b9bd615aa13dd133f88580128b4c4094363c75f96b6bcf1d3b2f582683fa62"
    )


def test_digest_is_computed_solely_from_canonical_bytes():
    ident = identity()
    assert (
        hashlib.sha256(ident.canonical_bytes()).hexdigest() == ident.canonical_digest()
    )


# --------------------------------------------------------------------------- #
# Framing: version, domain and type separation
# --------------------------------------------------------------------------- #

def test_frame_binds_the_canonicalization_version_and_the_domain_tag():
    framed = json.loads(canonical_bytes(identity()).decode("utf-8"))
    assert framed["canonicalization"] == TRUSTED_EVIDENCE_CANONICALIZATION_VERSION
    assert framed["domain"] == EVIDENCE_IDENTITY_DIGEST_DOMAIN
    assert framed["type"] == "CanonicalEvidenceIdentity"
    assert set(framed) == {"body", "canonicalization", "domain", "type"}


def test_the_type_name_separates_two_contracts_with_identical_bodies():
    """Two different contract types can never collide on one byte sequence."""

    ident = identity()
    req = request()
    assert canonical_bytes(ident) != canonical_bytes(req)
    assert json.loads(canonical_bytes(ident))["type"] != json.loads(
        canonical_bytes(req)
    )["type"]


def test_the_pinned_constants_are_the_declared_strings():
    assert (
        TRUSTED_EVIDENCE_CANONICALIZATION_VERSION
        == "ugence.trusted-evidence-authority/canonicalization/v1"
    )
    assert (
        EVIDENCE_IDENTITY_DIGEST_DOMAIN
        == "ugence.trusted-evidence-authority/evidence-identity/v1"
    )
    assert (
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
        == "ugence.trusted-evidence-authority/"
        "evidence-verification-receipt-payload/v1"
    )


def test_the_receipt_domain_is_distinct_from_the_evidence_identity_domain():
    """ADR §26.6 — a digest valid in one domain must not be reusable in another."""

    assert (
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
        != EVIDENCE_IDENTITY_DIGEST_DOMAIN
    )
    assert json.loads(canonical_bytes(receipt()))["domain"] == (
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
    )
    assert json.loads(canonical_bytes(identity()))["domain"] == (
        EVIDENCE_IDENTITY_DIGEST_DOMAIN
    )


def test_receipt_bytes_cannot_collide_with_any_evidence_family_contract():
    """Every evidence-family encoding differs from the receipt's, twice over.

    The domain tag separates the artifact classes, and the type name separates
    every contract within a class — so a collision needs both to coincide.
    """

    from _builders import claim, observation, provenance, scope

    payload = receipt()
    payload_bytes = canonical_bytes(payload)
    payload_frame = json.loads(payload_bytes)

    family = [
        identity(),
        schema(),
        scope(),
        observation(),
        provenance(),
        claim(),
        ApplicabilityCoordinate.applicable("US"),
        request(),
    ]
    for other in family:
        other_bytes = canonical_bytes(other)
        assert other_bytes != payload_bytes, type(other).__name__
        assert canonical_digest(other) != canonical_digest(payload)
        frame = json.loads(other_bytes)
        assert frame["domain"] != payload_frame["domain"], type(other).__name__
        assert frame["type"] != payload_frame["type"], type(other).__name__

    # ... and every pair within the family is distinct too.
    digests = [canonical_digest(o) for o in family] + [canonical_digest(payload)]
    assert len(set(digests)) == len(digests)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #

def test_equal_contracts_always_produce_equal_bytes_and_digests():
    a, b = identity(), identity()
    assert a == b
    assert a.canonical_bytes() == b.canonical_bytes()
    assert a.canonical_digest() == b.canonical_digest()


def test_repeated_calls_are_stable():
    ident = identity()
    assert len({ident.canonical_digest() for _ in range(25)}) == 1


def test_utc_offset_equivalence_produces_byte_identical_output():
    """Three spellings of one instant canonicalize identically (ADR §22.3)."""

    utc = datetime(2026, 3, 1, 10, 0, 0, 250000, tzinfo=timezone.utc)
    india = utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    newyork = utc.astimezone(timezone(timedelta(hours=-4)))
    assert utc == india == newyork
    assert india.utcoffset() != utc.utcoffset()

    built = [identity(observation=observation(observed_from=t)) for t in (utc, india, newyork)]
    assert built[0] == built[1] == built[2]
    assert len({b.canonical_bytes() for b in built}) == 1
    assert len({b.canonical_digest() for b in built}) == 1


def test_microseconds_are_preserved_and_load_bearing():
    base = datetime(2026, 3, 1, 10, 0, 0, 250000, tzinfo=timezone.utc)
    shifted = base.replace(microsecond=250001)
    a = identity(observation=observation(observed_from=base))
    b = identity(observation=observation(observed_from=shifted))
    assert b'10:00:00.250000Z' in a.canonical_bytes()
    assert b'10:00:00.250001Z' in b.canonical_bytes()
    assert a.canonical_digest() != b.canonical_digest()


def test_a_datetime_renders_with_a_trailing_z_and_no_offset_suffix():
    body = json.loads(canonical_bytes(identity()))["body"]
    assert body["valid_from"] == "2026-03-01T00:00:00.000000Z"


def test_none_is_represented_explicitly_and_differs_from_an_empty_string():
    with_window = identity(observation=observation())
    without_window = identity(observation=observation(observed_to=None))
    assert json.loads(canonical_bytes(without_window))["body"]["observation"][
        "observed_to"
    ] is None
    assert with_window.canonical_digest() != without_window.canonical_digest()

    # None (absent bound) and "" (an empty string) are different values and are
    # not interchangeable — an interval bound cannot be spelled "".
    no_valid_to = identity(valid_to=None)
    assert json.loads(canonical_bytes(no_valid_to))["body"]["valid_to"] is None
    assert no_valid_to.canonical_digest() != identity().canonical_digest()


def test_field_inclusion_is_total_no_field_is_dropped_when_empty():
    body = json.loads(canonical_bytes(identity(valid_from=None, valid_to=None)))["body"]
    # Both absent bounds are still present as explicit nulls.
    assert "valid_from" in body and "valid_to" in body
    # An empty-valued applicability coordinate still serializes both members.
    assert body["domain"] == {"declaration": "NOT_APPLICABLE", "value": ""}


def test_json_uses_sorted_keys_and_tight_separators():
    raw = canonical_bytes(schema()).decode("utf-8")
    assert ", " not in raw and ": " not in raw
    body_keys = list(json.loads(raw)["body"])
    assert body_keys == sorted(body_keys)


# --------------------------------------------------------------------------- #
# Fail-closed encoder — no permissive fallback
# --------------------------------------------------------------------------- #

def test_an_unknown_type_is_refused_never_rendered():
    class Opaque:
        pass

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Holder:
        payload: object

    with pytest.raises(TrustedEvidenceCanonicalizationError) as excinfo:
        canonical_bytes(Holder(payload=Opaque()))
    assert "not canonicalizable" in str(excinfo.value)
    # The rejection must not have leaked a repr (which would embed an id()).
    assert "0x" not in str(excinfo.value)


@pytest.mark.parametrize("bad", [1.0, 0.1, float("nan"), float("inf"), float("-inf")])
def test_every_float_is_refused_including_non_finite(bad):
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Holder:
        payload: object

    with pytest.raises(TrustedEvidenceCanonicalizationError) as excinfo:
        canonical_bytes(Holder(payload=bad))
    assert "float" in str(excinfo.value)


@pytest.mark.parametrize("bad", [{"k": "v"}, b"bytes", bytearray(b"x"), {1, 2}])
def test_mappings_bytes_and_sets_are_refused(bad):
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Holder:
        payload: object

    with pytest.raises(TrustedEvidenceCanonicalizationError):
        canonical_bytes(Holder(payload=bad))


def test_a_naive_datetime_is_refused_at_canonicalization_not_assumed_utc():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Holder:
        payload: object

    with pytest.raises(TrustedEvidenceCanonicalizationError) as excinfo:
        canonical_bytes(Holder(payload=datetime(2026, 3, 1)))
    assert "naive" in str(excinfo.value)


def test_a_non_nfc_string_is_refused_not_silently_normalized():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Holder:
        payload: object

    nfd = "é"  # 'e' + combining acute; NFC would fold it to 'é'
    assert nfd != "é"
    with pytest.raises(TrustedEvidenceCanonicalizationError) as excinfo:
        canonical_bytes(Holder(payload=nfd))
    assert "NFC" in str(excinfo.value)


def test_a_bool_serializes_as_a_boolean_never_as_an_integer():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Holder:
        payload: object

    assert json.loads(canonical_bytes(Holder(payload=True)))["body"]["payload"] is True
    assert canonical_bytes(Holder(payload=True)) != canonical_bytes(Holder(payload=1))


def test_canonical_bytes_refuses_a_non_dataclass():
    for bad in ("a string", 42, None, ApplicabilityCoordinate):
        with pytest.raises(TrustedEvidenceCanonicalizationError):
            canonical_bytes(bad)


def test_there_is_exactly_one_public_serialization_and_one_digest_function():
    """No alternate/legacy digest path and no dual-acceptance fallback.

    TEV-2 added functions whose names contain "bytes", but none of them is a
    second serializer:

    * ``signed_evidence_input_bytes`` and ``signed_receipt_input_bytes`` build
      **signing inputs**, not canonical encodings — and each is built *from*
      ``canonical_bytes``, so there is still exactly one path from a contract to
      its canonical form;
    * ``framed_signed_input`` frames byte strings that are already bytes and
      never touches a contract.

    The test therefore asserts the stronger property directly: exactly one
    public function turns a contract into canonical bytes, exactly one turns a
    contract into a digest, and every signing-input builder provably routes
    through the first of those rather than re-encoding anything itself.
    """

    import ast
    import inspect

    from ugence_trusted_evidence_authority import api
    from ugence_trusted_evidence_authority.authority import envelope as envelope_mod

    digesters = [n for n in api.__all__ if "digest" in n.lower() and not n.isupper()]
    assert digesters == ["canonical_digest"]

    signing_input_builders = {
        "signed_evidence_input_bytes",
        "signed_receipt_input_bytes",
        "framed_signed_input",
    }
    serializers = [n for n in api.__all__ if "bytes" in n or "dumps" in n]
    assert set(serializers) - signing_input_builders == {"canonical_bytes"}

    # No signing-input builder re-implements encoding: each either calls
    # canonical_bytes or only frames bytes it was handed.
    source = inspect.getsource(envelope_mod)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name not in ("signed_evidence_input_bytes", "signed_receipt_input_bytes"):
            continue
        called = {
            n.func.id
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "canonical_bytes" in called, node.name
        assert "dumps" not in inspect.getsource(envelope_mod), "no second serializer"
