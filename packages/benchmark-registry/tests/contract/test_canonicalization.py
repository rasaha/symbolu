"""One deterministic canonicalization path, one digest path (ADR §22, DD-9).

Includes the pinned byte vectors: a minimal identity and a representative full
identity, each reconstructed here from hand-written literal bytes and
``hashlib`` alone, so the pin is independent of the package's own encoder rather
than a restatement of it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from ugence_benchmark_registry.api import (
    BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN,
    BENCHMARK_REGISTRY_CANONICALIZATION_VERSION,
    BenchmarkCanonicalizationError,
    BenchmarkContractError,
    BenchmarkEffectivePeriod,
    BenchmarkScope,
    canonical_bytes,
    canonical_digest,
)

import _builders as b


# --------------------------------------------------------------------------- #
# Pinned vectors — reconstructed independently
# --------------------------------------------------------------------------- #
#: The exact canonical bytes of ``_builders.minimal_identity()``.
MINIMAL_CANONICAL_BYTES = (
    b'{"body":{"approval":{"approval_authority_ref":"auth","approval_ref":"ap",'
    b'"approved_content_digest":"'
    + b"a" * 64
    + b'"},"content_digest":"'
    + b"a" * 64
    + b'","coordinate":{"benchmark_family":"family-min","benchmark_id":"bmk-min",'
    b'"benchmark_version":"0.1.0","domain":{"declaration":"NOT_APPLICABLE",'
    b'"value":""},"geography":{"declaration":"NOT_APPLICABLE","value":""},'
    b'"scope":{"kind":"PLATFORM_WIDE","tenant_id":""}},"effective_period":'
    b'{"effective_from":"2026-01-01T00:00:00.000000Z","effective_to":null,'
    b'"end_declaration":"OPEN_ENDED"},"lifecycle_state":"AUTHORED","measurement":'
    b'{"aggregation_semantics_ref":"a","intended_outcome_ref":"o","measurement_'
    b'protocol_ref":"p","metric_ref":"m","observation_window_ref":"w",'
    b'"population_ref":"c","unit":"u"},"publisher_id":"pub","source_requirements":'
    b'{"provenance_requirement_refs":["r"],"source_ref":"s"},"supersession":'
    b'{"status":"UNDETERMINED"}},"canonicalization":'
    b'"ugence.benchmark-registry/canonicalization/v1","domain":'
    b'"ugence.benchmark-registry/benchmark-definition-identity/v1","type":'
    b'"CanonicalBenchmarkDefinitionIdentity"}'
)

#: sha-256 of :data:`MINIMAL_CANONICAL_BYTES`, computed here with ``hashlib``
#: over the literal above — never read back from the package.
MINIMAL_IDENTITY_DIGEST = (
    "9162ba434cff5b64678bf58f2dd8d9019ea8fafecc30817bf5953a62e7264a69"
)

#: sha-256 of the representative full identity's canonical bytes.
FULL_IDENTITY_DIGEST = (
    "f27044eafb0519399d71cac460d8820d5c0748aa8de9083346b394f434d93fd9"
)

#: sha-256 of the representative exact coordinate's canonical bytes. Pinned so a
#: change to the coordinate's field order or framing is caught on its own.
COORDINATE_DIGEST = (
    "4c4395db71a09426bb52097f6029b808388ccba22df66ca79f77726b388d26ce"
)


def test_the_minimal_canonical_bytes_are_exactly_the_pinned_literal():
    assert canonical_bytes(b.minimal_identity()) == MINIMAL_CANONICAL_BYTES


def test_the_pinned_minimal_digest_reconstructs_from_the_literal_bytes():
    """Recomputed with ``hashlib`` from the literal, not from the package."""

    assert (
        hashlib.sha256(MINIMAL_CANONICAL_BYTES).hexdigest()
        == MINIMAL_IDENTITY_DIGEST
    )
    assert b.minimal_identity().canonical_digest() == MINIMAL_IDENTITY_DIGEST


def test_the_pinned_full_identity_digest_is_stable():
    identity = b.identity()
    assert identity.canonical_digest() == FULL_IDENTITY_DIGEST
    assert (
        hashlib.sha256(identity.canonical_bytes()).hexdigest()
        == FULL_IDENTITY_DIGEST
    )


def test_the_pinned_coordinate_digest_is_stable_and_distinct():
    coordinate = b.coordinate()
    assert coordinate.canonical_digest() == COORDINATE_DIGEST
    assert COORDINATE_DIGEST != FULL_IDENTITY_DIGEST


# --------------------------------------------------------------------------- #
# Framing
# --------------------------------------------------------------------------- #
def test_the_frame_binds_version_domain_and_type():
    framed = json.loads(canonical_bytes(b.identity()).decode("utf-8"))
    assert set(framed) == {"canonicalization", "domain", "type", "body"}
    assert framed["canonicalization"] == BENCHMARK_REGISTRY_CANONICALIZATION_VERSION
    assert framed["domain"] == BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN
    assert framed["type"] == "CanonicalBenchmarkDefinitionIdentity"


def test_the_canonicalization_version_and_domain_are_the_pinned_strings():
    assert BENCHMARK_REGISTRY_CANONICALIZATION_VERSION == (
        "ugence.benchmark-registry/canonicalization/v1"
    )
    assert BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN == (
        "ugence.benchmark-registry/benchmark-definition-identity/v1"
    )


def test_the_domain_is_not_a_trusted_evidence_domain():
    """Two capabilities, two byte spaces (ADR §22.1, §26.6)."""

    assert "trusted-evidence" not in BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN
    assert BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN.startswith(
        "ugence.benchmark-registry/"
    )
    assert BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN.endswith("/v1")


def test_two_contract_types_never_share_canonical_bytes():
    """The ``type`` element separates types inside the one domain."""

    seen = {}
    identity = b.identity()
    for contract in (
        identity,
        identity.coordinate,
        identity.coordinate.scope,
        identity.coordinate.geography,
        identity.measurement,
        identity.effective_period,
        identity.source_requirements,
        identity.approval,
        identity.supersession,
    ):
        digest = canonical_digest(contract)
        assert digest not in seen, (type(contract).__name__, seen.get(digest))
        seen[digest] = type(contract).__name__


def test_a_subclass_gets_its_own_bytes_and_cannot_borrow_a_registered_type():
    class Impostor(BenchmarkScope):
        pass

    impostor = Impostor(kind=BenchmarkScope.platform_wide().kind, tenant_id="")
    real = BenchmarkScope.platform_wide()
    assert canonical_bytes(impostor) != canonical_bytes(real)
    assert b'"type":"Impostor"' in canonical_bytes(impostor)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_the_encoder_is_deterministic_across_repeated_calls():
    identity = b.identity()
    assert canonical_bytes(identity) == canonical_bytes(identity)
    assert canonical_digest(identity) == canonical_digest(identity)


def test_equal_contracts_produce_byte_identical_output():
    assert canonical_bytes(b.identity()) == canonical_bytes(b.identity())


def test_two_spellings_of_one_instant_produce_one_byte_sequence():
    """ADR §22.3 — aware datetimes are re-expressed in UTC before serialization."""

    utc = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    plus_two = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    assert utc == plus_two
    a = BenchmarkEffectivePeriod.open_ended(utc)
    c = BenchmarkEffectivePeriod.open_ended(plus_two)
    assert canonical_bytes(a) == canonical_bytes(c)


def test_microseconds_are_preserved():
    with_micros = datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)
    without = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    a = BenchmarkEffectivePeriod.open_ended(with_micros)
    c = BenchmarkEffectivePeriod.open_ended(without)
    assert canonical_bytes(a) != canonical_bytes(c)
    assert b"00:00:00.123456Z" in canonical_bytes(a)


def test_object_keys_are_sorted_and_whitespace_is_absent():
    raw = canonical_bytes(b.identity()).decode("utf-8")
    assert ", " not in raw and ": " not in raw
    # Top-level keys are sorted: body, canonicalization, domain, type. Checked on
    # the frame's own boundaries rather than by searching the whole string —
    # ``domain`` is also a §15 coordinate name inside the body.
    assert raw.startswith('{"body":')
    assert raw.endswith('"type":"CanonicalBenchmarkDefinitionIdentity"}')
    tail = raw[raw.rindex('"canonicalization"'):]
    assert tail.index('"canonicalization"') < tail.index('"domain"') < tail.index('"type"')


# --------------------------------------------------------------------------- #
# Rejections — the encoder has no permissive fallback (ADR §22.8)
# --------------------------------------------------------------------------- #
def test_a_naive_datetime_is_refused_at_construction_and_at_canonicalization():
    naive = datetime(2026, 1, 1, 0, 0, 0)
    with pytest.raises(BenchmarkContractError):
        BenchmarkEffectivePeriod.open_ended(naive)

    # And again in the encoder, for a value that arrived by any other route.
    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    object.__setattr__(period, "effective_from", naive)
    with pytest.raises(BenchmarkCanonicalizationError):
        canonical_bytes(period)


@pytest.mark.parametrize(
    "value",
    [1.0, 0.1, float("nan"), float("inf"), float("-inf"), -0.0],
)
def test_every_float_is_refused(value):
    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    object.__setattr__(period, "effective_from", value)
    with pytest.raises(BenchmarkCanonicalizationError):
        canonical_bytes(period)


def test_the_float_refusal_says_why_a_non_finite_number_can_never_be_encoded():
    """The dedicated ``float`` branch exists to make the refusal actionable.

    Falling through to the generic unknown-type refusal would raise the same
    exception type, so this branch is a **diagnostic** refinement rather than an
    additional gate — and ADR §16.3's "stable typed refusal reason" is worth
    little if the caller cannot tell a non-finite number from an unsupported
    class. The message is therefore pinned.
    """

    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    object.__setattr__(period, "effective_from", float("nan"))
    with pytest.raises(BenchmarkCanonicalizationError) as excinfo:
        canonical_bytes(period)
    message = str(excinfo.value)
    assert "float is not canonicalizable" in message
    assert "nan/inf/-inf" in message


def test_a_mapping_is_refused_by_the_encoder():
    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    object.__setattr__(period, "effective_from", {"a": 1})
    with pytest.raises(BenchmarkCanonicalizationError):
        canonical_bytes(period)


def test_bytes_are_refused_by_the_encoder():
    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    object.__setattr__(period, "effective_from", b"\x00\x01")
    with pytest.raises(BenchmarkCanonicalizationError):
        canonical_bytes(period)


def test_an_unknown_object_is_refused_rather_than_rendered():
    class Opaque:
        def __repr__(self):  # pragma: no cover - must never be called
            raise AssertionError("repr must never be used by the encoder")

    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    object.__setattr__(period, "effective_from", Opaque())
    with pytest.raises(BenchmarkCanonicalizationError):
        canonical_bytes(period)


def test_a_non_nfc_string_is_refused_at_both_boundaries():
    nfd = "Café"  # NFD spelling of "Café"
    with pytest.raises(BenchmarkContractError):
        b.coordinate(benchmark_id=nfd)

    scope = BenchmarkScope.platform_wide()
    object.__setattr__(scope, "tenant_id", nfd)
    with pytest.raises(BenchmarkCanonicalizationError):
        canonical_bytes(scope)


def test_canonical_bytes_refuses_a_non_dataclass():
    for value in ("a string", 42, None, [1, 2], {"a": 1}, BenchmarkScope):
        with pytest.raises(BenchmarkCanonicalizationError):
            canonical_bytes(value)


def test_a_bool_serializes_as_a_boolean_never_as_an_integer():
    period = BenchmarkEffectivePeriod.open_ended(b.EFFECTIVE_FROM)
    object.__setattr__(period, "effective_from", True)
    assert b'"effective_from":true' in canonical_bytes(period)


def test_none_and_empty_string_are_distinct():
    scope = BenchmarkScope.platform_wide()
    with_empty = canonical_bytes(scope)
    object.__setattr__(scope, "tenant_id", None)
    assert canonical_bytes(scope) != with_empty


# --------------------------------------------------------------------------- #
# Collection ordering
# --------------------------------------------------------------------------- #
def test_an_order_irrelevant_collection_is_normalized_to_one_digest():
    forward = b.source_requirements(
        provenance_requirement_refs=("r-alpha", "r-beta", "r-gamma")
    )
    reversed_ = b.source_requirements(
        provenance_requirement_refs=("r-gamma", "r-alpha", "r-beta")
    )
    assert forward == reversed_
    assert canonical_bytes(forward) == canonical_bytes(reversed_)


def test_the_encoder_itself_preserves_sequence_order():
    """Normalization happens in the contract; the encoder never reorders.

    The normalized tuple is sorted, so its *sorted* order must be exactly what
    appears in the bytes. If the encoder sorted or reordered independently, a
    future collection whose order is meaningful would silently lose it.
    """

    requirements = b.source_requirements(
        provenance_requirement_refs=("r-gamma", "r-alpha", "r-beta")
    )
    assert requirements.provenance_requirement_refs == ("r-alpha", "r-beta", "r-gamma")
    raw = canonical_bytes(requirements).decode("utf-8")
    assert '["r-alpha","r-beta","r-gamma"]' in raw

    # And a hand-placed out-of-order tuple is rendered in the order given.
    object.__setattr__(
        requirements, "provenance_requirement_refs", ("r-gamma", "r-alpha")
    )
    assert '["r-gamma","r-alpha"]' in canonical_bytes(requirements).decode("utf-8")


# --------------------------------------------------------------------------- #
# The digest is not the content digest
# --------------------------------------------------------------------------- #
def test_the_identity_digest_is_not_the_declared_content_digest():
    identity = b.identity()
    assert identity.canonical_digest() != identity.content_digest


def test_changing_the_declared_content_digest_moves_the_identity_digest():
    before = b.identity().canonical_digest()
    after = b.identity(
        content_digest=b.OTHER_CONTENT_DIGEST,
        approval=b.approval(approved_content_digest=b.OTHER_CONTENT_DIGEST),
    ).canonical_digest()
    assert before != after


def test_computing_a_digest_reads_no_clock_and_no_environment(monkeypatch):
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    first = b.identity().canonical_digest()
    monkeypatch.setenv("TZ", "Etc/GMT+12")
    assert b.identity().canonical_digest() == first
