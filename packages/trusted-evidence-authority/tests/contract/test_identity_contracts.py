"""Constructor invariants for every trusted-evidence contract shape.

Every invariant is exercised through the real public constructor, and every
rejection is asserted to be a refusal — never a silent normalization of an
invalid semantic value into an accepted one.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from _builders import (
    BINDING_DIGEST,
    CONTENT_DIGEST,
    CONTEXT_DIGEST,
    OBSERVED_FROM,
    OBSERVED_TO,
    VALID_FROM,
    VALID_TO,
    identity,
    observation,
    provenance,
    scope,
    schema,
)
from ugence_trusted_evidence_authority.api import (
    ApplicabilityCoordinate,
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    EvidenceLifecycleState,
    EvidenceObservation,
    EvidenceProvenanceChain,
    EvidenceSchemaRef,
    EvidenceScopeBinding,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
    TrustedEvidenceContractError,
)

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# Field order and immutability
# --------------------------------------------------------------------------- #

def test_declared_field_order_is_pinned():
    assert [f.name for f in dataclasses.fields(EvidenceSchemaRef)] == [
        "schema_id",
        "schema_version",
    ]
    assert [f.name for f in dataclasses.fields(EvidenceObservation)] == [
        "producer_id",
        "collected_at",
        "observed_from",
        "observed_to",
        "issuer_id",
    ]
    assert [f.name for f in dataclasses.fields(EvidenceScopeBinding)] == [
        "tenant_id",
        "assessment_context_ref",
        "assessment_context_digest",
        "subject_ref",
        "assessment_purpose_ref",
        "usage_scope_ref",
        "assessed_system_applicability",
        "assessed_system_binding_ref",
        "assessed_system_binding_digest",
    ]
    assert [f.name for f in dataclasses.fields(EvidenceProvenanceChain)] == [
        "chain_ref",
        "custody_refs",
    ]
    assert [f.name for f in dataclasses.fields(ApplicabilityCoordinate)] == [
        "declaration",
        "value",
    ]
    assert [f.name for f in dataclasses.fields(CanonicalEvidenceIdentity)] == [
        "evidence_id",
        "evidence_type",
        "schema",
        "content_digest",
        "observation",
        "scope",
        "claim",
        "provenance",
        "lifecycle_state",
        "geography",
        "domain",
        "intended_outcome",
        "valid_from",
        "valid_to",
    ]


@pytest.mark.parametrize(
    "instance",
    [schema(), observation(), scope(), provenance(), identity(),
     ApplicabilityCoordinate.not_applicable()],
)
def test_every_contract_is_frozen(instance):
    assert dataclasses.fields(instance)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, dataclasses.fields(instance)[0].name, "mutated")


def test_a_frozen_contract_digest_cannot_be_changed_after_construction():
    ident = identity()
    before = ident.canonical_digest()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ident.evidence_id = "ev-2"
    assert ident.canonical_digest() == before


# --------------------------------------------------------------------------- #
# Identifier validation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("blank", ["", " ", "\t", "\n", "   \t  "])
def test_blank_and_whitespace_only_identifiers_are_refused(blank):
    with pytest.raises(TrustedEvidenceContractError):
        identity(evidence_id=blank)
    with pytest.raises(TrustedEvidenceContractError):
        schema(schema_id=blank)
    with pytest.raises(TrustedEvidenceContractError):
        scope(tenant_id=blank)


@pytest.mark.parametrize("padded", [" ev-1", "ev-1 ", "\tev-1", "ev-1\n"])
def test_padded_identifiers_are_refused_not_trimmed(padded):
    """Padding is a refusal; the contract never silently repairs it."""

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        identity(evidence_id=padded)
    assert "whitespace" in str(excinfo.value)
    # And the refusal is not a stealth acceptance of the trimmed form.
    assert identity().evidence_id == "ev-1"


@pytest.mark.parametrize("bad", [None, 1, True, False, b"ev-1", ["ev-1"], object()])
def test_non_string_identifiers_are_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        identity(evidence_id=bad)


def test_a_bool_is_refused_where_a_string_is_expected():
    """``True``/``False`` are not identifiers, however truthy."""

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        scope(tenant_id=True)
    assert "string" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Digest validation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-a-digest",
        "A" * 64,                       # uppercase
        CONTENT_DIGEST.upper(),         # uppercase hex
        CONTENT_DIGEST[:63],            # too short
        CONTENT_DIGEST + "0",           # too long
        "sha256:" + CONTENT_DIGEST,     # prefixed
        " " + CONTENT_DIGEST,           # padded
    ],
)
def test_malformed_content_digests_are_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        identity(content_digest=bad)


def test_the_assessment_context_digest_is_mandatory_and_validated():
    with pytest.raises(TrustedEvidenceContractError):
        scope(assessment_context_digest="")
    with pytest.raises(TrustedEvidenceContractError):
        scope(assessment_context_digest="nope")


# --------------------------------------------------------------------------- #
# Exact contract identity — no duck-typed lookalikes
# --------------------------------------------------------------------------- #

def test_a_duck_typed_lookalike_schema_is_refused():
    @dataclasses.dataclass(frozen=True)
    class LookalikeSchema:
        schema_id: str = "ugence.evidence.control-test"
        schema_version: str = "1"

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        identity(schema=LookalikeSchema())
    assert "exactly" in str(excinfo.value)


def test_a_subclass_of_a_nested_contract_is_refused():
    class SubSchema(EvidenceSchemaRef):
        pass

    with pytest.raises(TrustedEvidenceContractError):
        identity(schema=SubSchema(schema_id="s", schema_version="1"))


def test_a_string_valued_lookalike_of_an_enum_is_refused():
    """``EvidenceLifecycleState`` is a ``str`` enum, but a bare ``str`` is not it."""

    with pytest.raises(TrustedEvidenceContractError):
        identity(lifecycle_state="SUBMITTED")


def test_a_datetime_subclass_is_refused():
    class SneakyDatetime(datetime):
        def utcoffset(self, *_):  # would change which instant is recorded
            return timedelta(hours=12)

    with pytest.raises(TrustedEvidenceContractError):
        identity(
            observation=observation(
                observed_from=SneakyDatetime(2026, 3, 1, 10, tzinfo=UTC)
            )
        )


# --------------------------------------------------------------------------- #
# ApplicabilityCoordinate — §15's "never omitted" rule made structural
# --------------------------------------------------------------------------- #

def test_applicable_requires_a_value():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        ApplicabilityCoordinate(
            declaration=ApplicabilityDeclaration.APPLICABLE, value=""
        )
    assert "non-empty value" in str(excinfo.value)


def test_not_applicable_forbids_a_value():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        ApplicabilityCoordinate(
            declaration=ApplicabilityDeclaration.NOT_APPLICABLE, value="US"
        )
    assert "empty value" in str(excinfo.value)


def test_not_applicable_and_applicable_are_distinguishable_in_the_digest():
    a = identity(geography=ApplicabilityCoordinate.not_applicable())
    b = identity(geography=ApplicabilityCoordinate.applicable("US"))
    assert a.canonical_digest() != b.canonical_digest()


def test_the_applicability_coordinate_cannot_be_omitted():
    """There is no default — the caller must record a decision."""

    with pytest.raises(TypeError):
        CanonicalEvidenceIdentity(
            evidence_id="ev-1",
            evidence_type="T",
            schema=schema(),
            content_digest=CONTENT_DIGEST,
            observation=observation(),
            scope=scope(),
            provenance=provenance(),
            lifecycle_state=EvidenceLifecycleState.SUBMITTED,
            geography=ApplicabilityCoordinate.not_applicable(),
            domain=ApplicabilityCoordinate.not_applicable(),
            # intended_outcome deliberately omitted
        )


# --------------------------------------------------------------------------- #
# EvidenceObservation
# --------------------------------------------------------------------------- #

def test_naive_datetimes_are_refused_at_construction():
    for field in ("collected_at", "observed_from", "observed_to"):
        with pytest.raises(TrustedEvidenceContractError) as excinfo:
            observation(**{field: datetime(2026, 3, 1, 10)})
        assert "timezone-aware" in str(excinfo.value)


def test_observed_to_none_means_an_instant_not_a_missing_bound():
    inst = observation(observed_to=None)
    assert inst.observed_to is None
    assert inst.is_observation_window is False
    assert observation().is_observation_window is True


def test_a_reversed_observation_window_is_refused():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        observation(observed_from=OBSERVED_TO, observed_to=OBSERVED_FROM)
    assert "strictly precede" in str(excinfo.value)


def test_a_zero_length_observation_window_is_refused_half_open():
    with pytest.raises(TrustedEvidenceContractError):
        observation(observed_from=OBSERVED_FROM, observed_to=OBSERVED_FROM)


def test_collection_before_observation_is_refused():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        observation(collected_at=OBSERVED_FROM - timedelta(seconds=1))
    assert "before the observation" in str(excinfo.value)


def test_an_issuer_equal_to_the_producer_is_refused_as_not_distinct():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        observation(producer_id="prod-a", issuer_id="prod-a")
    assert "not distinct" in str(excinfo.value)


def test_an_empty_issuer_means_not_distinct_and_is_accepted():
    assert observation(issuer_id="").issuer_id == ""


# --------------------------------------------------------------------------- #
# EvidenceScopeBinding
# --------------------------------------------------------------------------- #

def test_the_assessed_system_applicability_has_no_default():
    with pytest.raises(TypeError):
        EvidenceScopeBinding(
            tenant_id="t",
            assessment_context_ref="c",
            assessment_context_digest=CONTEXT_DIGEST,
            subject_ref="s",
            assessment_purpose_ref="p",
            usage_scope_ref="u",
        )


def test_applicable_system_binding_requires_both_ref_and_digest():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        scope(assessed_system_binding_digest="")
    assert "both required" in str(excinfo.value)
    with pytest.raises(TrustedEvidenceContractError):
        scope(assessed_system_binding_ref="")


def test_not_applicable_system_binding_forbids_both_ref_and_digest():
    ok = scope(
        assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE,
        assessed_system_binding_ref="",
        assessed_system_binding_digest="",
    )
    assert ok.assessed_system_binding_ref == ""
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        scope(
            assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE,
            assessed_system_binding_digest="",
        )
    assert "must both be empty" in str(excinfo.value)


def test_scope_identity_exposes_every_replay_relevant_coordinate():
    assert scope().scope_identity == (
        "tenant-1",
        "ctx-1",
        CONTEXT_DIGEST,
        "subject-1",
        "purpose-readiness",
        "scope-general",
        "bind-1",
        BINDING_DIGEST,
    )


# --------------------------------------------------------------------------- #
# EvidenceProvenanceChain
# --------------------------------------------------------------------------- #

def test_custody_refs_are_normalized_to_an_immutable_tuple():
    chain = provenance(custody_refs=["a", "b", "c"])
    assert chain.custody_refs == ("a", "b", "c")
    assert isinstance(chain.custody_refs, tuple)


def test_a_caller_list_cannot_mutate_a_constructed_chain_or_its_digest():
    caller_list = ["a", "b"]
    ident = identity(provenance=provenance(custody_refs=caller_list))
    before = ident.canonical_digest()
    caller_list.append("c")
    assert ident.provenance.custody_refs == ("a", "b")
    assert ident.canonical_digest() == before


def test_custody_order_is_semantic_and_changes_the_digest():
    a = identity(provenance=provenance(custody_refs=("a", "b")))
    b = identity(provenance=provenance(custody_refs=("b", "a")))
    assert a.canonical_digest() != b.canonical_digest()


def test_duplicate_custody_links_are_refused():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        provenance(custody_refs=("a", "a"))
    assert "duplicate" in str(excinfo.value)


@pytest.mark.parametrize("bad", ["abc", b"abc", {"a": 1}, 42, None])
def test_scalar_and_mapping_substitutes_for_custody_refs_are_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        provenance(custody_refs=bad)


def test_a_generator_is_refused_rather_than_silently_consumed():
    with pytest.raises(TrustedEvidenceContractError):
        provenance(custody_refs=(x for x in ("a", "b")))


@pytest.mark.parametrize("bad", ["", " ", None, 7, True])
def test_blank_and_non_string_custody_entries_are_refused_not_dropped(bad):
    with pytest.raises(TrustedEvidenceContractError):
        provenance(custody_refs=("a", bad))


def test_an_empty_custody_chain_is_permitted_and_distinct_from_a_populated_one():
    empty = identity(provenance=provenance(custody_refs=()))
    assert empty.provenance.custody_refs == ()
    assert empty.canonical_digest() != identity().canonical_digest()


# --------------------------------------------------------------------------- #
# CanonicalEvidenceIdentity — validity interval
# --------------------------------------------------------------------------- #

def test_the_validity_interval_is_half_open_and_rejects_reversal():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        identity(valid_from=VALID_TO, valid_to=VALID_FROM)
    assert "half-open" in str(excinfo.value)


def test_a_zero_length_validity_interval_is_refused():
    with pytest.raises(TrustedEvidenceContractError):
        identity(valid_from=VALID_FROM, valid_to=VALID_FROM)


def test_an_open_ended_validity_interval_is_permitted_on_either_side():
    assert identity(valid_from=None).valid_from is None
    assert identity(valid_to=None).valid_to is None
    assert identity(valid_from=None, valid_to=None).is_valid_at(VALID_FROM)


def test_naive_validity_bounds_are_refused():
    with pytest.raises(TrustedEvidenceContractError):
        identity(valid_from=datetime(2026, 3, 1))


# --------------------------------------------------------------------------- #
# Honest status
# --------------------------------------------------------------------------- #

def test_structural_status_is_the_only_status_and_is_permanently_unverified():
    ident = identity()
    assert ident.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    assert ident.authenticity_verified is False
    assert list(EvidenceStructuralStatus) == [
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    ]


def test_the_object_reports_which_trust_stages_remain_unestablished():
    ident = identity()
    assert ident.established_trust_stages == (
        EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
    )
    assert ident.unestablished_trust_stages == (
        EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        EvidenceTrustStage.PROVENANCE_VERIFIED,
        EvidenceTrustStage.CONTEXT_SYSTEM_BOUND,
        EvidenceTrustStage.CURRENTLY_VALID,
        EvidenceTrustStage.POLICY_SUFFICIENT,
    )
    # Never empty — no constructible object clears every stage.
    assert ident.unestablished_trust_stages
