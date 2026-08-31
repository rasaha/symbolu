"""Two read payloads, two exact types, and no substitution in either direction."""

from __future__ import annotations

import dataclasses
import json

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BenchmarkHistoricalRecordPayload,
    BenchmarkRegistryContractError,
    BenchmarkResolutionRecordPayload,
    canonical_bytes,
    canonical_digest,
    require_exact_historical_record_payload,
    require_exact_resolution_record_payload,
)


def test_happy_both_read_payloads_construct():
    assert fx.resolution_record().declared_registration_state.value == "REGISTERED"
    assert fx.historical_record().as_of == fx.AS_OF


def test_they_are_different_exact_types():
    assert type(fx.resolution_record()) is not type(fx.historical_record())


def test_a_historical_payload_cannot_satisfy_a_resolution_api():
    with pytest.raises(BenchmarkRegistryContractError):
        require_exact_resolution_record_payload(fx.historical_record())


def test_a_resolution_payload_cannot_satisfy_a_historical_api():
    with pytest.raises(BenchmarkRegistryContractError):
        require_exact_historical_record_payload(fx.resolution_record())


def test_the_happy_direction_of_each_guard_works():
    assert require_exact_resolution_record_payload(fx.resolution_record())
    assert require_exact_historical_record_payload(fx.historical_record())


@pytest.mark.parametrize(
    "guard,builder",
    [
        (require_exact_resolution_record_payload, fx.resolution_record),
        (require_exact_historical_record_payload, fx.historical_record),
    ],
)
def test_neither_guard_admits_a_subclass(guard, builder):
    genuine = builder()
    subclass = dataclasses.dataclass(frozen=True)(
        type(f"Sub{type(genuine).__name__}", (type(genuine),), {})
    )
    forged = subclass(
        **{f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    )
    with pytest.raises(BenchmarkRegistryContractError):
        guard(forged)


@pytest.mark.parametrize(
    "guard", [require_exact_resolution_record_payload,
              require_exact_historical_record_payload]
)
def test_neither_guard_admits_an_arbitrary_object(guard):
    for wrong in (None, "REGISTERED", {}, fx.registration_event()):
        with pytest.raises(BenchmarkRegistryContractError):
            guard(wrong)


def test_the_resolution_payload_carries_no_as_of():
    payload = fx.resolution_record()
    assert "as_of" not in {f.name for f in dataclasses.fields(payload)}
    assert not hasattr(payload, "as_of")


def test_the_historical_payload_discloses_as_of_and_its_historical_nature():
    payload = fx.historical_record()
    assert payload.as_of == fx.AS_OF
    assert payload.is_historical_disclosure is True


def test_the_resolution_payload_reports_it_is_not_a_historical_disclosure():
    assert fx.resolution_record().is_historical_disclosure is False


def test_neither_authorizes_execution_or_establishes_active_eligibility():
    for payload in (fx.resolution_record(), fx.historical_record()):
        assert payload.authorizes_execution is False
        assert payload.active_eligibility_established is False
        assert payload.trusted_resolution_established is False


def test_a_revoked_declaration_still_establishes_nothing():
    """DENY_ALWAYS is a resolver rule; a payload declaring REVOKED resolves nothing."""

    from ugence_benchmark_registry_authority.api import BenchmarkRegistrationState

    payload = fx.resolution_record(
        declared_registration_state=BenchmarkRegistrationState.REVOKED
    )
    assert payload.trusted_resolution_established is False
    assert payload.authorizes_execution is False


def test_they_occupy_different_canonical_byte_spaces():
    a = json.loads(canonical_bytes(fx.resolution_record()))
    b = json.loads(canonical_bytes(fx.historical_record()))
    assert a["domain"] != b["domain"]
    assert a["type"] != b["type"]
    assert canonical_digest(fx.resolution_record()) != canonical_digest(
        fx.historical_record()
    )


def test_a_bare_string_registration_state_is_refused():
    with pytest.raises(BenchmarkRegistryContractError):
        fx.resolution_record(declared_registration_state="REGISTERED")


def test_an_uppercase_digest_is_refused_never_lowercased():
    """One digest value has exactly one spelling, so equality cannot be dodged."""

    upper = fx.IDENTITY_DIGEST.upper()
    assert upper != fx.IDENTITY_DIGEST
    with pytest.raises(BenchmarkRegistryContractError):
        fx.resolution_record(declared_admitted_digest=upper)


def test_a_prefixed_or_padded_digest_is_refused_never_trimmed():
    for spelling in (
        "0x" + fx.IDENTITY_DIGEST[2:],
        " " + fx.IDENTITY_DIGEST,
        fx.IDENTITY_DIGEST + " ",
        fx.IDENTITY_DIGEST[:-1],
        fx.IDENTITY_DIGEST + "a",
    ):
        with pytest.raises(BenchmarkRegistryContractError):
            fx.resolution_record(declared_admitted_digest=spelling)


def test_the_authoritative_result_type_does_not_exist():
    import ugence_benchmark_registry_authority as pkg

    assert not hasattr(pkg, "BenchmarkResolution")
    assert BenchmarkResolutionRecordPayload.__name__.endswith("Payload")
    assert BenchmarkHistoricalRecordPayload.__name__.endswith("Payload")
