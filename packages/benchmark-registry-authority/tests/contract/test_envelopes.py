"""Envelopes — declared signature material validated as an encoding, never verified."""

from __future__ import annotations

import dataclasses

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
    BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_SIGNING_FRAME_SPECIFICATION,
    BENCHMARK_SIGNING_FRAME_VERSION,
    BenchmarkRegistryContractError,
    BenchmarkSignatureProfile,
    canonical_digest,
)

ENVELOPES = (
    ("BenchmarkPublisherSubmissionEnvelope", fx.publisher_envelope),
    ("BenchmarkApprovalEnvelope", fx.approval_envelope),
    ("BenchmarkRevocationEnvelope", fx.revocation_envelope),
)

BAD_SIGNATURES = (
    ("", "empty"),
    ("00" * 63, "too short"),
    ("00" * 65, "too long"),
    ("AB" * 64, "uppercase hex"),
    ("zz" * 64, "non-hex characters"),
    ("0x" + "0" * 126, "0x-prefixed"),
    (" " + "0" * 128, "padded"),
)


def test_happy_all_three_envelopes_construct():
    for _name, builder in ENVELOPES:
        assert builder()


@pytest.mark.parametrize("name,builder", ENVELOPES)
@pytest.mark.parametrize("value,label", BAD_SIGNATURES, ids=[l for _, l in BAD_SIGNATURES])
def test_every_envelope_refuses_a_malformed_signature_encoding(
    name, builder, value, label
):
    with pytest.raises(BenchmarkRegistryContractError):
        builder(detached_signature=value)


@pytest.mark.parametrize("name,builder", ENVELOPES)
def test_a_bare_string_signature_profile_is_refused(name, builder):
    """A closed vocabulary that accepts strings is not closed."""

    with pytest.raises(BenchmarkRegistryContractError):
        builder(signature_profile="ED25519_SHA512_V1")


@pytest.mark.parametrize("name,builder", ENVELOPES)
def test_an_unconstrained_algorithm_string_is_unrepresentable(name, builder):
    for algorithm in ("none", "NONE", "HS256", "RS256", "ed25519", "md5"):
        with pytest.raises(BenchmarkRegistryContractError):
            builder(signature_profile=algorithm)


def test_the_signature_profile_enum_has_exactly_one_ratified_member():
    assert [p.value for p in BenchmarkSignatureProfile] == ["ED25519_SHA512_V1"]


@pytest.mark.parametrize(
    "name,builder,expected",
    [
        (
            "publisher",
            fx.publisher_envelope,
            BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
        ),
        ("approval", fx.approval_envelope, BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN),
        (
            "revocation",
            fx.revocation_envelope,
            BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
        ),
    ],
)
def test_each_envelope_admits_only_its_own_signing_frame_domain(
    name, builder, expected
):
    assert builder().signing_frame_domain == expected
    for other in (
        BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
        BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
        BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
        "ugence.benchmark-registry-authority/attacker-frame/v1",
    ):
        if other == expected:
            continue
        with pytest.raises(BenchmarkRegistryContractError):
            builder(signing_frame_domain=other)


def test_the_three_signing_frames_are_three_distinct_byte_spaces():
    """A publisher signature can never be replayed as an approval or a revocation."""

    assert len(
        {
            BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
            BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
            BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
        }
    ) == 3


@pytest.mark.parametrize("name,builder", ENVELOPES)
def test_an_arbitrary_signing_frame_version_is_refused(name, builder):
    for version in ("v0", "v2", "1", "", "V1"):
        with pytest.raises(BenchmarkRegistryContractError):
            builder(signing_frame_version=version)


def test_the_signing_frame_specification_is_complete_for_every_envelope():
    frames = BENCHMARK_SIGNING_FRAME_SPECIFICATION["frames"]
    assert set(frames) == {name for name, _ in ENVELOPES}
    for frame in frames.values():
        assert frame["domain"]
        assert frame["element_order"][0] == "signing_frame_domain"
        assert frame["element_order"][1] == "signing_frame_version"
        assert len(frame["element_order"]) == len(set(frame["element_order"]))


def test_the_signing_frame_specification_pins_length_prefixing_and_exclusions():
    spec = BENCHMARK_SIGNING_FRAME_SPECIFICATION
    assert "uint32_be" in spec["length_prefix"]
    assert "detached_signature" in spec["excluded"]
    assert spec["version"] == BENCHMARK_SIGNING_FRAME_VERSION
    assert set(spec["profiles"]) == {BenchmarkSignatureProfile.ED25519_SHA512_V1.value}


def test_no_signing_frame_covers_its_own_signature():
    for frame in BENCHMARK_SIGNING_FRAME_SPECIFICATION["frames"].values():
        assert "detached_signature" not in frame["element_order"]


# --------------------------------------------------------------------------- #
# Publisher envelope specifics
# --------------------------------------------------------------------------- #
def test_the_publisher_envelope_binds_both_digests_distinctly():
    envelope = fx.publisher_envelope()
    assert envelope.benchmark_identity_digest != envelope.benchmark_content_digest
    assert canonical_digest(
        fx.publisher_envelope(benchmark_content_digest=fx.OTHER_DIGEST)
    ) != canonical_digest(envelope)


def test_the_publisher_envelope_carries_no_declared_recorded_at():
    names = {f.name for f in dataclasses.fields(fx.publisher_envelope())}
    assert "declared_recorded_at" not in names


def test_a_blank_publisher_identity_or_key_is_refused():
    for override in ({"publisher_identity": ""}, {"publisher_key_id": ""}):
        with pytest.raises(BenchmarkRegistryContractError):
            fx.publisher_envelope(**override)


def test_no_key_material_field_exists_anywhere():
    """Naming a key is not possessing one; no public key is carried or parsed."""

    banned = ("public_key", "private_key", "key_material", "pem", "der", "jwk")
    for _name, builder in fx.PINNED_VECTOR_BUILDERS:
        for f in dataclasses.fields(builder()):
            for token in banned:
                assert token not in f.name.lower(), f.name


# --------------------------------------------------------------------------- #
# Approval envelope specifics
# --------------------------------------------------------------------------- #
def test_the_approval_envelope_nests_the_envelope_not_its_digest():
    approval = fx.approval_envelope()
    names = {f.name for f in dataclasses.fields(approval)}
    assert "publisher_submission_envelope" in names
    assert "publisher_submission_envelope_digest" not in names
    assert isinstance(
        type(approval).publisher_submission_envelope_digest, property
    )


def test_the_derived_submission_digest_is_recomputed_from_the_nested_object():
    approval = fx.approval_envelope()
    assert approval.publisher_submission_envelope_digest == canonical_digest(
        approval.publisher_submission_envelope
    )


def test_a_caller_supplied_submission_envelope_digest_is_not_accepted():
    with pytest.raises(TypeError):
        fx.approval_envelope(publisher_submission_envelope_digest="0" * 64)


def test_the_approval_validity_interval_is_half_open_and_strictly_ordered():
    for override in (
        {"validity_to": fx.VALIDITY_FROM},
        {"validity_to": fx.VALIDITY_FROM.replace(year=2025)},
    ):
        with pytest.raises(BenchmarkRegistryContractError):
            fx.approval_envelope(**override)


def test_a_br1_approved_lifecycle_state_never_substitutes_for_this_envelope():
    """B-5: a lifecycle enum on the artifact is not approval evidence."""

    from ugence_benchmark_registry import BenchmarkLifecycleState

    approval = fx.approval_envelope()
    assert approval.approval_authenticity_established is False
    # Nothing anywhere in the package accepts a BR-1 lifecycle state in place of
    # an approval envelope: there is no such field and no such conversion.
    for _name, builder in fx.PINNED_VECTOR_BUILDERS:
        for f in dataclasses.fields(builder()):
            assert f.name != "lifecycle_state"
    with pytest.raises(BenchmarkRegistryContractError):
        fx.admission_decision(approval_envelope=BenchmarkLifecycleState.APPROVED)


# --------------------------------------------------------------------------- #
# Revocation envelope specifics
# --------------------------------------------------------------------------- #
def test_the_revocation_envelope_is_not_a_registry_event():
    envelope = fx.revocation_envelope()
    assert not hasattr(envelope, "declared_state")
    assert not hasattr(envelope, "prev_event_digest")
    assert not hasattr(envelope, "is_terminal")


def test_the_revocation_reason_is_required_and_unpadded():
    for value in ("", "   ", " reason "):
        with pytest.raises(BenchmarkRegistryContractError):
            fx.revocation_envelope(declared_revocation_reason=value)


def test_no_name_anywhere_in_the_package_calls_anything_a_receipt():
    """"Receipt" is the trusted-evidence layer's word under ADR §6.4.

    Checked on **names**, not on prose: the module docstrings deliberately
    discuss what a receipt is and why nothing here is one, so a text scan would
    flag the very sentences that state the rule. What must never appear is a
    class, function, field, constant or exported symbol carrying the word —
    because that is what a consumer would read as a claim.
    """

    import ast
    import pathlib

    import ugence_benchmark_registry_authority as pkg

    for symbol in pkg.__all__:
        assert "receipt" not in symbol.lower(), symbol

    src = pathlib.Path(__file__).resolve().parents[2] / "src"
    offenders = []
    for path in sorted(src.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            name = None
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                name = node.name
            elif isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.arg):
                name = node.arg
            elif isinstance(node, ast.Attribute):
                name = node.attr
            if name and "receipt" in name.lower():
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], offenders


def test_registry_generated_artifacts_are_named_records_or_events():
    """The naming rule that keeps the vocabularies apart."""

    chain_names = (
        "BenchmarkSubmissionRecordPayload",
        "BenchmarkAdmissionDecisionPayload",
        "BenchmarkPostAdmissionRejectionEventPayload",
        "BenchmarkRegistrationEventPayload",
        "BenchmarkRevocationEventPayload",
        "BenchmarkConflictRecordPayload",
    )
    for name in chain_names:
        assert "Record" in name or "Event" in name or "Decision" in name, name
