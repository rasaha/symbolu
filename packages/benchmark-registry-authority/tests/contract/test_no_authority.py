"""§09 — the universal no-authority rule survives every route a caller has.

Five permanent derivations on every authority-describing contract, plus the two
envelope derivations and the read-payload derivations. The suite proves they
survive construction, :func:`copy.copy`, :func:`copy.deepcopy`, a
:mod:`pickle` round-trip, ``dataclasses.replace``, subclassing, a forged
same-named object, and the canonical payload itself — and that no
caller-constructed payload can satisfy an API expecting an authority-issued
result, because those result types **do not exist**.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import pickle

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES,
    BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES,
    BenchmarkRegistryCanonicalizationError,
    canonical_bytes,
)
import ugence_benchmark_registry_authority as pkg

CONTRACTS = [(name, builder) for name, builder in fx.PINNED_VECTOR_BUILDERS]
ENVELOPES = [
    ("BenchmarkPublisherSubmissionEnvelope", fx.publisher_envelope),
    ("BenchmarkApprovalEnvelope", fx.approval_envelope),
    ("BenchmarkRevocationEnvelope", fx.revocation_envelope),
]


def test_happy_the_five_properties_are_the_ratified_five():
    assert BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES == (
        "authority_verified",
        "publisher_authenticity_established",
        "approval_authenticity_established",
        "registry_admission_established",
        "trusted_resolution_established",
    )


@pytest.mark.parametrize("name,builder", CONTRACTS)
@pytest.mark.parametrize("prop", BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES)
def test_every_contract_derives_every_property_as_false(name, builder, prop):
    assert getattr(builder(), prop) is False


@pytest.mark.parametrize("name,builder", CONTRACTS)
@pytest.mark.parametrize("prop", BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES)
def test_no_property_is_a_constructor_argument(name, builder, prop):
    assert prop not in {f.name for f in dataclasses.fields(builder())}


@pytest.mark.parametrize("name,builder", CONTRACTS)
@pytest.mark.parametrize("prop", BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES)
def test_no_property_can_be_assigned(name, builder, prop):
    instance = builder()
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        setattr(instance, prop, True)
    assert getattr(instance, prop) is False


@pytest.mark.parametrize("name,builder", CONTRACTS)
@pytest.mark.parametrize("prop", BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES)
def test_object_setattr_cannot_reach_a_class_level_data_descriptor(
    name, builder, prop
):
    """Even ``object.__setattr__`` is refused, and the value is unchanged.

    This is the route that defeats ``@dataclass(frozen=True)`` everywhere else in
    this package's threat model — it writes straight into the instance
    dictionary. It cannot write here: a ``property`` is a **data descriptor**, so
    the attribute lookup never consults instance state, and ``object.__setattr__``
    delegates to the descriptor's setter, which does not exist. The result is a
    refusal rather than a shadowed value.
    """

    instance = builder()
    with pytest.raises(AttributeError):
        object.__setattr__(instance, prop, True)
    assert getattr(instance, prop) is False


@pytest.mark.parametrize("name,builder", CONTRACTS)
@pytest.mark.parametrize("prop", BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES)
def test_the_property_survives_copy_deepcopy_and_pickle(name, builder, prop):
    instance = builder()
    for clone in (
        copy.copy(instance),
        copy.deepcopy(instance),
        pickle.loads(pickle.dumps(instance)),
    ):
        assert getattr(clone, prop) is False


@pytest.mark.parametrize("name,builder", CONTRACTS)
@pytest.mark.parametrize("prop", BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES)
def test_the_property_survives_dataclasses_replace(name, builder, prop):
    instance = builder()
    assert getattr(dataclasses.replace(instance), prop) is False


@pytest.mark.parametrize("name,builder", CONTRACTS)
def test_no_property_appears_in_the_canonical_payload(name, builder):
    """A derived property is not a field, so it is not in the encoded body."""

    body = json.loads(canonical_bytes(builder()).decode("utf-8"))["body"]
    for prop in BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
        assert prop not in body


@pytest.mark.parametrize("name,builder", CONTRACTS)
def test_a_subclass_overriding_a_property_is_never_canonicalizable(name, builder):
    """Subclassing can lie about the property; it can never produce bytes."""

    genuine = builder()
    target = type(genuine)
    liar = dataclasses.dataclass(frozen=True)(
        type(
            f"Liar{target.__name__}",
            (target,),
            {"authority_verified": property(lambda self: True)},
        )
    )
    forged = liar(
        **{f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    )
    assert forged.authority_verified is True  # the lie is expressible...
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(forged)  # ...and worth nothing


@pytest.mark.parametrize("name,builder", ENVELOPES)
def test_every_envelope_derives_signature_and_admission_as_false(name, builder):
    envelope = builder()
    assert envelope.signature_verified is False
    assert envelope.admission_established is False


@pytest.mark.parametrize("name,builder", ENVELOPES)
def test_envelope_derivations_survive_every_clone_route(name, builder):
    envelope = builder()
    for clone in (
        copy.copy(envelope),
        copy.deepcopy(envelope),
        pickle.loads(pickle.dumps(envelope)),
        dataclasses.replace(envelope),
    ):
        assert clone.signature_verified is False
        assert clone.admission_established is False


def test_a_valid_signature_encoding_still_establishes_nothing():
    """128 lowercase hex characters is an encoding, not a signature."""

    envelope = fx.publisher_envelope()
    assert len(envelope.detached_signature) == 128
    assert envelope.signature_verified is False
    assert envelope.publisher_authenticity_established is False


def test_the_reserved_authority_issued_type_names_are_undefined():
    """A payload cannot satisfy a result API because the result type is absent."""

    for reserved in BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES:
        assert not hasattr(pkg, reserved), reserved
        assert reserved not in pkg.__all__


def test_every_caller_constructible_chain_type_is_suffixed_payload():
    """The naming rule that keeps a payload from reading as a result."""

    chain = (
        "BenchmarkSubmissionRecordPayload",
        "BenchmarkAdmissionDecisionPayload",
        "BenchmarkPostAdmissionRejectionEventPayload",
        "BenchmarkRegistrationEventPayload",
        "BenchmarkRevocationEventPayload",
        "BenchmarkConflictRecordPayload",
        "BenchmarkResolutionRecordPayload",
        "BenchmarkHistoricalRecordPayload",
    )
    for name in chain:
        assert name.endswith("Payload")
        assert name in pkg.__all__


def test_a_class_declaring_a_no_authority_property_as_a_field_fails_at_import():
    """The decorator refuses to overwrite, so a settable claim cannot ship."""

    from ugence_benchmark_registry_authority.contracts._authority import (
        permanently_unverified_authority,
    )

    @dataclasses.dataclass(frozen=True)
    class Sneaky:
        authority_verified: bool = True

    with pytest.raises(TypeError):
        permanently_unverified_authority(Sneaky)


def test_the_read_payloads_authorize_nothing():
    for payload in (fx.resolution_record(), fx.historical_record()):
        assert payload.authorizes_execution is False
        assert payload.active_eligibility_established is False


def test_the_scope_expectations_grant_no_authorization():
    for expectation in (fx.platform_expectation(), fx.tenant_expectation()):
        assert expectation.authorization_granted is False
