"""Chain integrity — one graph, one source of truth, no shortened representation."""

from __future__ import annotations

import dataclasses

import pytest

import _builders as fx
from _graph import dataclass_edges
from ugence_benchmark_registry_authority.api import (
    BenchmarkAdmissionDecisionPayload,
    BenchmarkAdmissionOutcome,
    BenchmarkRegistryContractError,
    BenchmarkRegistryLifecycleError,
    BenchmarkRevocationEventPayload,
    canonical_bytes,
    canonical_digest,
)

CHAIN = (
    ("BenchmarkSubmissionRecordPayload", fx.submission_record),
    ("BenchmarkAdmissionDecisionPayload", fx.admission_decision),
    ("BenchmarkPostAdmissionRejectionEventPayload", fx.post_admission_rejection),
    ("BenchmarkRegistrationEventPayload", fx.registration_event),
    ("BenchmarkRevocationEventPayload", fx.revocation_event),
    ("BenchmarkConflictRecordPayload", fx.conflict_record),
)

ALL_CONTRACTS = fx.PINNED_VECTOR_BUILDERS

#: The three BR-2C verified-result types (D-24, D-26). Named as a set so the
#: exemption below cannot be widened by editing a predicate.
VERIFIED_RESULT_CLASSES = frozenset(
    {
        "BenchmarkPublisherVerifiedResult",
        "BenchmarkApprovalVerifiedResult",
        "BenchmarkRevocationVerifiedResult",
    }
)

#: The two digest **fields** D-24 ratifies on every verified result, exempt from
#: the derived-property rule and from nothing else.
#:
#: **Why the rule does not reach here.** The derived-property rule exists
#: because a chain payload *chains*: a caller-supplied ``prev_event_digest``
#: would be an independent spelling of a link, and an artifact could then attest
#: to a predecessor nobody could reproduce. A verified result chains nothing. It
#: is a record of one evaluation, it is permanently ``authority_verified is
#: False`` like every other caller-constructible type here, and a caller who
#: wanted to fabricate one could already write ``outcome=VERIFIED`` into it — so
#: a fabricated digest field adds no forgery the type did not already admit,
#: and the type proves nothing either way.
#:
#: **Why nesting was not chosen instead.** D-24 rules that the result binds "the
#: envelope or artifact digest" and "the anchor-record digest" — digests, named
#: as such, among exactly nine bound facts. Nesting the envelope would add a
#: tenth bound thing D-24 did not rule. It would also make the **refusal** cases
#: unrepresentable: ``TRUST_ANCHOR_NOT_FOUND`` and
#: ``TRUST_DIRECTORY_UNAVAILABLE`` are precisely the conditions in which no
#: anchor record exists to nest, and D-27 requires those refusals to stay
#: distinguishable.
VERIFIED_RESULT_RATIFIED_DIGEST_FIELDS = frozenset(
    {"verified_digest", "anchor_record_digest"}
)


def test_happy_the_chain_links_by_recomputed_digest_at_every_hop():
    event = fx.revocation_event()
    registration = event.registration_event
    decision = registration.admission_decision
    record = decision.submission_record
    assert record.prev_event_digest is None
    assert decision.prev_event_digest == canonical_digest(record)
    assert registration.prev_event_digest == canonical_digest(decision)
    assert event.prev_event_digest == canonical_digest(registration)


# --------------------------------------------------------------------------- #
# No caller-supplied upstream digest exists anywhere
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", ALL_CONTRACTS)
def test_no_contract_declares_an_upstream_digest_field(name, builder):
    """Digest **fields** may only name artifacts outside this package's graph.

    The BR-1 identity digest, the benchmark content digest and the immutable
    admitted digest are digests of things this package does not hold, so they
    cannot be recomputed here and are legitimately declared. Every digest of a
    thing this package *does* hold is a derived property instead.
    """

    allowed = {
        "benchmark_identity_digest",
        "benchmark_content_digest",
        "admitted_digest",
        "declared_admitted_digest",
    }
    if name in VERIFIED_RESULT_CLASSES:
        allowed = allowed | VERIFIED_RESULT_RATIFIED_DIGEST_FIELDS
    for f in dataclasses.fields(builder()):
        if f.name.endswith("_digest"):
            assert f.name in allowed, f"{name}.{f.name} is a caller-supplied digest"


@pytest.mark.parametrize("name,builder", ALL_CONTRACTS)
def test_every_upstream_digest_is_a_derived_read_only_property(name, builder):
    contract = builder()
    for attr in dir(type(contract)):
        if not attr.endswith("_digest"):
            continue
        descriptor = getattr(type(contract), attr, None)
        if isinstance(descriptor, property):
            assert descriptor.fset is None, f"{name}.{attr} has a setter"


def test_a_derived_digest_property_recomputes_rather_than_caching():
    """Reading it twice after a valid substitution gives the new value."""

    decision = fx.admission_decision()
    before = decision.submission_record_digest
    replacement = fx.submission_record(declared_recorded_at=fx.VALIDITY_FROM)
    object.__setattr__(decision, "submission_record", replacement)
    assert decision.submission_record_digest != before
    assert decision.submission_record_digest == canonical_digest(replacement)


# --------------------------------------------------------------------------- #
# No shortened chain
# --------------------------------------------------------------------------- #
def test_no_alternative_shortened_chain_is_constructible():
    """A revocation cannot skip the registration event it must follow."""

    for wrong in (
        fx.admission_decision(),
        fx.submission_record(),
        fx.post_admission_rejection(),
        fx.conflict_record(),
    ):
        with pytest.raises(BenchmarkRegistryContractError):
            BenchmarkRevocationEventPayload(
                registration_event=wrong,
                revocation_envelope=fx.revocation_envelope(),
                declared_recorded_at=fx.RECORDED_AT,
            )


def test_no_second_representation_of_any_transition_exists():
    """Each nested predecessor field has exactly one admissible exact type."""

    seen = {}
    for name, builder in CHAIN:
        contract = builder()
        for f in dataclasses.fields(contract):
            value = getattr(contract, f.name)
            if dataclasses.is_dataclass(value):
                seen.setdefault((name, f.name), set()).add(type(value).__name__)
    for key, types_ in seen.items():
        assert len(types_) == 1, key


# --------------------------------------------------------------------------- #
# Admission's two nested paths must reach one envelope
# --------------------------------------------------------------------------- #
def test_admission_refuses_mismatched_publisher_submissions_across_its_two_paths():
    other_envelope = fx.publisher_envelope(publisher_key_id="publisher-key-2")
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        BenchmarkAdmissionDecisionPayload(
            submission_record=fx.submission_record(),
            approval_envelope=fx.approval_envelope(
                publisher_submission_envelope=other_envelope
            ),
            declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
            declared_recorded_at=fx.RECORDED_AT,
        )
    assert "byte-identical" in str(excinfo.value)


def test_the_mismatch_is_caught_even_for_a_one_character_difference():
    other = fx.publisher_envelope(publisher_identity="publisher-alphb")
    with pytest.raises(BenchmarkRegistryLifecycleError):
        BenchmarkAdmissionDecisionPayload(
            submission_record=fx.submission_record(
                publisher_submission_envelope=other
            ),
            approval_envelope=fx.approval_envelope(),
            declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
            declared_recorded_at=fx.RECORDED_AT,
        )


def test_the_mismatch_is_caught_after_construction_by_revalidation():
    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryCanonicalizationError,
    )

    decision = fx.admission_decision()
    object.__setattr__(
        decision.approval_envelope,
        "publisher_submission_envelope",
        fx.publisher_envelope(publisher_key_id="publisher-key-9"),
    )
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(decision)


# --------------------------------------------------------------------------- #
# One source of truth per identity
# --------------------------------------------------------------------------- #
def test_registry_authority_identity_is_declared_exactly_once_in_the_chain():
    declarations = []
    for name, builder in CHAIN:
        for f in dataclasses.fields(builder()):
            if f.name == "declared_registry_authority_identity":
                declarations.append(name)
    assert declarations == ["BenchmarkSubmissionRecordPayload"]


def test_publisher_identity_is_declared_exactly_once_in_the_whole_package():
    declarations = []
    for name, builder in ALL_CONTRACTS:
        for f in dataclasses.fields(builder()):
            if f.name == "publisher_identity":
                declarations.append(name)
    assert declarations == ["BenchmarkPublisherSubmissionEnvelope"]


def test_revoker_identity_is_declared_exactly_once_in_the_whole_package():
    declarations = []
    for name, builder in ALL_CONTRACTS:
        for f in dataclasses.fields(builder()):
            if f.name == "revoker_identity":
                declarations.append(name)
    assert declarations == ["BenchmarkRevocationEnvelope"]


def test_no_downstream_payload_accepts_a_second_registry_authority_spelling():
    for name, builder in CHAIN:
        if name == "BenchmarkSubmissionRecordPayload":
            continue
        contract = builder()
        assert isinstance(
            type(contract).registry_authority_identity, property
        ), name
        assert contract.registry_authority_identity == (
            fx.REGISTRY_AUTHORITY_IDENTITY
        )


def test_every_derived_identity_reaches_the_one_declaring_object():
    event = fx.revocation_event()
    assert event.publisher_identity == fx.PUBLISHER_IDENTITY
    assert event.registry_authority_identity == fx.REGISTRY_AUTHORITY_IDENTITY
    assert event.revoker_identity == fx.REVOKER_IDENTITY


def test_changing_the_one_declaration_moves_every_derived_reading():
    record = fx.submission_record(
        declared_registry_authority_identity="registry-authority-omega"
    )
    decision = fx.admission_decision(submission_record=record)
    event = fx.registration_event(admission_decision=decision)
    assert event.registry_authority_identity == "registry-authority-omega"


# --------------------------------------------------------------------------- #
# Actor separation
# --------------------------------------------------------------------------- #
def test_the_registry_cannot_be_its_own_publisher():
    with pytest.raises(BenchmarkRegistryContractError):
        fx.submission_record(
            declared_registry_authority_identity=fx.PUBLISHER_IDENTITY
        )


def test_the_approver_cannot_be_the_publisher():
    with pytest.raises(BenchmarkRegistryContractError):
        fx.approval_envelope(approval_authority_identity=fx.PUBLISHER_IDENTITY)


def test_the_registry_cannot_be_the_approver():
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkAdmissionDecisionPayload(
            submission_record=fx.submission_record(),
            approval_envelope=fx.approval_envelope(
                approval_authority_identity=fx.REGISTRY_AUTHORITY_IDENTITY
            ),
            declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
            declared_recorded_at=fx.RECORDED_AT,
        )


def test_the_revoker_cannot_impersonate_the_registry_authority():
    with pytest.raises(BenchmarkRegistryContractError) as excinfo:
        fx.revocation_event(
            revocation_envelope=fx.revocation_envelope(
                revoker_identity=fx.REGISTRY_AUTHORITY_IDENTITY
            )
        )
    assert "four-party separation" in str(excinfo.value)


def test_a_revocation_envelope_for_a_different_locator_is_refused():
    other = fx.revocation_envelope(
        coordinate=fx.coordinate(benchmark_id="other-benchmark")
    )
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        fx.revocation_event(revocation_envelope=other)
    assert "coordinate" in str(excinfo.value)


def test_a_revocation_envelope_naming_a_different_admitted_digest_is_refused():
    other = fx.revocation_envelope(admitted_digest=fx.OTHER_DIGEST)
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        fx.revocation_event(revocation_envelope=other)
    assert "admitted_digest" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# The graph really is a graph
# --------------------------------------------------------------------------- #
def test_the_deepest_root_reaches_every_contract_kind_it_should():
    reached = {
        type(child).__name__
        for _p, _n, child, _path, _d in dataclass_edges(fx.revocation_event())
    }
    assert {
        "BenchmarkRegistrationEventPayload",
        "BenchmarkAdmissionDecisionPayload",
        "BenchmarkSubmissionRecordPayload",
        "BenchmarkPublisherSubmissionEnvelope",
        "BenchmarkApprovalEnvelope",
        "BenchmarkRevocationEnvelope",
        "BenchmarkCoordinate",
        "BenchmarkScope",
        "BenchmarkApplicabilityCoordinate",
    } <= reached
