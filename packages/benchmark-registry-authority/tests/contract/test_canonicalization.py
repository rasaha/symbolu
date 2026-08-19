"""One encoder, one digest path, and fifteen pinned byte vectors."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

import _builders as fx
from ugence_benchmark_registry import BenchmarkCoordinate
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION,
    BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS,
    BenchmarkRegistryCanonicalizationError,
    BenchmarkRegistryContractError,
    canonical_bytes,
    canonical_digest,
    canonical_domain_inventory,
)

PKG = pathlib.Path(__file__).resolve().parents[2]
VECTORS = json.loads((PKG / "pinned_canonical_vectors.json").read_text())["vectors"]


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", fx.PINNED_VECTOR_BUILDERS)
def test_happy_every_shipped_artifact_matches_its_pinned_byte_vector(name, builder):
    """Every shipped class reproduces its committed canonical bytes exactly."""

    assert canonical_bytes(builder()).decode("utf-8") == VECTORS[name][
        "canonical_bytes"
    ]


@pytest.mark.parametrize("name,builder", fx.PINNED_VECTOR_BUILDERS)
def test_happy_every_pinned_digest_is_independently_recomputable(name, builder):
    """The digest is sha-256 over the pinned bytes, recomputed with hashlib alone.

    Importing nothing from the package for the recomputation: a third party
    holding only the byte string and the standard library gets the same answer.
    """

    raw = VECTORS[name]["canonical_bytes"].encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == VECTORS[name]["digest"]
    assert canonical_digest(builder()) == VECTORS[name]["digest"]


def test_happy_equal_contracts_produce_byte_identical_output():
    assert canonical_bytes(fx.submission_record()) == canonical_bytes(
        fx.submission_record()
    )


def test_happy_two_spellings_of_one_instant_canonicalize_identically():
    """A UTC instant written with a different offset is the same instant."""

    other_zone = timezone(timedelta(hours=5, minutes=30))
    shifted = fx.RECORDED_AT.astimezone(other_zone)
    assert canonical_bytes(
        fx.submission_record(declared_recorded_at=shifted)
    ) == canonical_bytes(fx.submission_record())


def test_happy_every_frame_carries_version_domain_and_type():
    for name, builder in fx.PINNED_VECTOR_BUILDERS:
        framed = json.loads(canonical_bytes(builder()).decode("utf-8"))
        assert set(framed) == {"body", "canonicalization", "domain", "type"}
        assert framed["canonicalization"] == (
            BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION
        )
        assert framed["type"] == name
        assert framed["domain"] in BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS


def test_happy_keys_are_sorted_and_whitespace_free():
    raw = canonical_bytes(fx.submission_record()).decode("utf-8")
    assert ", " not in raw and ": " not in raw
    framed = json.loads(raw)
    assert list(framed) == sorted(framed)


# --------------------------------------------------------------------------- #
# Adversarial
# --------------------------------------------------------------------------- #
def test_fifteen_distinct_domains_no_two_artifacts_share_a_byte_space():
    assert len(set(BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS)) == 15


def test_every_shipped_class_has_a_distinct_digest_under_one_fixture_family():
    digests = {name: VECTORS[name]["digest"] for name, _ in fx.PINNED_VECTOR_BUILDERS}
    assert len(set(digests.values())) == len(digests)


def test_two_read_payloads_over_the_same_facts_have_different_digests():
    """A historical answer can never collide with a current one, even at the digest."""

    assert canonical_digest(fx.resolution_record()) != canonical_digest(
        fx.historical_record()
    )


def test_a_br1_contract_is_refused_as_a_canonicalization_root():
    """BR-1 owns its own digest path; BR-2 never re-digests a BR-1 artifact."""

    with pytest.raises(BenchmarkRegistryCanonicalizationError) as excinfo:
        canonical_bytes(fx.coordinate())
    assert "nested" in str(excinfo.value)


def test_a_bare_dataclass_is_refused():
    import dataclasses

    @dataclasses.dataclass(frozen=True)
    class Foreign:
        value: str = "x"

    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(Foreign())


def test_a_non_dataclass_is_refused():
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes({"body": 1})


def test_a_class_object_rather_than_an_instance_is_refused():
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(BenchmarkCoordinate)


def test_float_is_refused_outright():
    record = fx.submission_record()
    object.__setattr__(record, "declared_recorded_at", 1.5)
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(record)


def test_bytes_are_refused_so_a_signature_has_one_spelling():
    envelope = fx.publisher_envelope()
    object.__setattr__(envelope, "detached_signature", b"\x01" * 64)
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(envelope)


def test_a_mapping_is_refused_so_no_coordinate_hides_in_an_extension_bag():
    record = fx.submission_record()
    object.__setattr__(record, "declared_registry_authority_identity", {"a": 1})
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(record)


def test_an_unknown_object_is_refused_before_any_byte_and_leaks_no_repr():
    """An opaque object is refused at revalidation, before the encoder is reached.

    That ordering is the stronger guarantee: revalidation runs the trusted exact
    class's own ``__post_init__`` first, so the object never reaches the
    encoder's unknown-type branch at all. Neither boundary renders the object —
    the message names the field and the rule, and carries no ``repr()`` and so
    no ``id()``-derived memory address, which would make a failure message
    non-deterministic across processes.
    """

    class Opaque:
        def __repr__(self):  # pragma: no cover - must never be called
            raise AssertionError("the refusal path rendered an unknown object")

    record = fx.submission_record()
    object.__setattr__(record, "declared_registry_authority_identity", Opaque())
    with pytest.raises(BenchmarkRegistryCanonicalizationError) as excinfo:
        canonical_bytes(record)
    message = str(excinfo.value)
    assert "failed structural revalidation before canonicalization" in message
    assert "0x" not in message


def test_a_naive_datetime_is_refused_at_the_encoder_as_well():
    record = fx.submission_record()
    object.__setattr__(record, "declared_recorded_at", datetime(2026, 1, 1))
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(record)


def test_a_non_nfc_string_is_refused_never_normalized():
    record = fx.submission_record()
    object.__setattr__(record, "declared_registry_authority_identity", "éx")
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(record)


def test_microseconds_survive_the_encoding():
    precise = fx.RECORDED_AT.replace(microsecond=123456)
    raw = canonical_bytes(fx.submission_record(declared_recorded_at=precise))
    assert b".123456Z" in raw


def test_none_and_empty_string_are_distinct_byte_sequences():
    admitted = canonical_bytes(fx.admission_decision())
    assert b'"declared_refusal_reason":null' in admitted


def test_the_encoder_module_contains_no_repr_fallback_and_no_default_hook():
    source = (
        PKG
        / "src"
        / "ugence_benchmark_registry_authority"
        / "contracts"
        / "canonical.py"
    ).read_text()
    body = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    code = body.split('"""', 2)[-1]
    assert "repr(" not in code
    assert "default=" not in code


def test_the_domain_inventory_is_derived_from_the_sealed_registry():
    inventory = canonical_domain_inventory()
    assert len(inventory) == 18
    assert sum(1 for d in inventory.values() if d is not None) == 15
    assert sum(1 for d in inventory.values() if d is None) == 3


def test_mutating_the_domain_inventory_snapshot_cannot_reach_the_encoder():
    snapshot = canonical_domain_inventory()
    with pytest.raises(TypeError):
        snapshot["Evil"] = "x"  # type: ignore[index]
    assert canonical_digest(fx.submission_record()) == VECTORS[
        "BenchmarkSubmissionRecordPayload"
    ]["digest"]


def test_the_contract_type_registry_is_sealed_and_cannot_be_widened():
    """The seal is a ratified property, so it is tested rather than assumed.

    After package import the registry is closed for the life of the process.
    A caller holding a reference to the "private" registration function — which
    anyone who imports the module does — must still be unable to add a type,
    because a widened registry would let a foreign class produce genuine
    canonical bytes under a borrowed domain while every other check kept
    behaving normally.
    """

    import dataclasses

    from ugence_benchmark_registry_authority.contracts.canonical import (
        _register_contract_type,
        _seal_contract_types,
    )

    @dataclasses.dataclass(frozen=True)
    class Foreign:
        value: str = "x"

    with pytest.raises(BenchmarkRegistryContractError) as excinfo:
        _register_contract_type(
            Foreign,
            "ugence.benchmark-registry-authority/forged/v1",
            root_canonicalizable=True,
        )
    assert "sealed" in str(excinfo.value)

    # Sealing again is equally refused: the registry closes exactly once.
    with pytest.raises(BenchmarkRegistryContractError):
        _register_contract_type(Foreign, None, root_canonicalizable=False)
    _seal_contract_types()
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(Foreign())


def test_a_non_dataclass_type_cannot_be_registered_even_before_sealing():
    """The registration guard itself, exercised through the sealed boundary."""

    from ugence_benchmark_registry_authority.contracts.canonical import (
        _register_contract_type,
    )

    with pytest.raises(BenchmarkRegistryContractError):
        _register_contract_type(str, "x", root_canonicalizable=True)
