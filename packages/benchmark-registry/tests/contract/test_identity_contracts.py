"""The twenty ADR §15 coordinates are present, mandatory and cross-checked.

Every rejection here is structural. None of them is the inverse of a trusted
resolution: a contract that constructs has established internal consistency and
nothing else (ADR B-9).
"""

from __future__ import annotations

import copy
import dataclasses
import pickle

import pytest
from ugence_benchmark_registry.api import (
    BENCHMARK_IDENTITY_COORDINATES,
    BenchmarkApplicabilityCoordinate,
    BenchmarkApprovalReference,
    BenchmarkContractError,
    BenchmarkCoordinate,
    BenchmarkEffectivePeriod,
    BenchmarkLifecycleState,
    BenchmarkMeasurementSemantics,
    BenchmarkRefusalReason,
    BenchmarkScope,
    BenchmarkSourceRequirements,
    BenchmarkStructuralStatus,
    BenchmarkSupersessionDeclaration,
    BenchmarkSupersessionStatus,
    CanonicalBenchmarkDefinitionIdentity,
    TemporalBoundDeclaration,
    canonical_bytes,
)

import _builders as b

_R = BenchmarkRefusalReason


# --------------------------------------------------------------------------- #
# The happy path exists and is genuinely happy
# --------------------------------------------------------------------------- #
def test_a_complete_identity_constructs():
    identity = b.identity()
    assert identity.coordinate.benchmark_id == "bmk-support-resolution-time"
    assert identity.content_digest == b.CONTENT_DIGEST
    assert identity.lifecycle_state is BenchmarkLifecycleState.REGISTERED
    assert len(identity.canonical_digest()) == 64


def test_the_minimal_identity_also_constructs_and_differs():
    minimal = b.minimal_identity()
    assert minimal.canonical_digest() != b.identity().canonical_digest()


# --------------------------------------------------------------------------- #
# Mandatory: no coordinate has a default, so none can be omitted
# --------------------------------------------------------------------------- #
def test_no_identity_field_carries_a_default():
    """ADR §15: every coordinate is required, so none may be defaultable.

    A default would let a caller omit a coordinate and still construct — which is
    precisely the "absence disappearing into an implicit default" §15 forbids
    when it rules that "an omitted field is not" a decision on the record.
    """

    for field in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity):
        assert field.default is dataclasses.MISSING, field.name
        assert field.default_factory is dataclasses.MISSING, field.name


@pytest.mark.parametrize(
    "field", [f.name for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)]
)
def test_every_identity_field_is_required_at_construction(field):
    kwargs = {
        f.name: getattr(b.identity(), f.name)
        for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)
    }
    kwargs.pop(field)
    with pytest.raises(TypeError):
        CanonicalBenchmarkDefinitionIdentity(**kwargs)


def test_every_adr_15_coordinate_path_resolves():
    """The declared §15 row map is not prose: every path must exist."""

    assert len(BENCHMARK_IDENTITY_COORDINATES) == 20
    identity = b.identity()
    for path in BENCHMARK_IDENTITY_COORDINATES:
        target = identity
        for part in path.split("."):
            assert hasattr(target, part), path
            target = getattr(target, part)
        assert target is not None, path


def test_no_public_contract_carries_a_mapping_or_extension_bag_field():
    """§15's coordinates cannot disappear into a free-form dictionary.

    Checked on the *type* rather than only on the encoder: a field annotated as a
    mapping would be a place to hide a coordinate even if the encoder refused it
    at digest time.
    """

    contracts = [
        BenchmarkApplicabilityCoordinate,
        BenchmarkScope,
        BenchmarkCoordinate,
        BenchmarkMeasurementSemantics,
        BenchmarkEffectivePeriod,
        BenchmarkSourceRequirements,
        BenchmarkApprovalReference,
        BenchmarkSupersessionDeclaration,
        CanonicalBenchmarkDefinitionIdentity,
    ]
    banned = ("dict", "mapping", "metadata", "extension", "extra", "attributes",
              "properties", "payload", "any")
    for contract in contracts:
        for field in dataclasses.fields(contract):
            annotation = str(field.type).lower()
            name = field.name.lower()
            for marker in banned:
                assert marker not in annotation, (contract.__name__, field.name)
                assert marker not in name, (contract.__name__, field.name)


# --------------------------------------------------------------------------- #
# B-5 — approval binds an exact content digest
# --------------------------------------------------------------------------- #
def test_an_approval_for_different_content_is_refused():
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.identity(approval=b.approval(approved_content_digest=b.OTHER_CONTENT_DIGEST))
    assert excinfo.value.reason is _R.BENCHMARK_APPROVAL_REFERENCE_INVALID


def test_the_approved_digest_must_be_a_bare_lowercase_sha256():
    for bad in ("A" * 64, "0x" + "a" * 62, "a" * 63, "a" * 65, "zz" + "a" * 62):
        with pytest.raises(BenchmarkContractError):
            BenchmarkApprovalReference(
                approval_ref="ap",
                approval_authority_ref="auth",
                approved_content_digest=bad,
            )


def test_the_content_digest_must_be_a_bare_lowercase_sha256():
    with pytest.raises(BenchmarkContractError):
        b.identity(content_digest="A" * 64)


def test_matching_approval_and_content_digests_prove_nothing():
    """The invariant is consistency, not approval verification (§16.2 stage 3)."""

    identity = b.identity()
    assert identity.approval.approved_content_digest == identity.content_digest
    assert identity.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED
    assert identity.trusted_resolution_performed is False


# --------------------------------------------------------------------------- #
# B-3 / B-4 — no component occupies two adjacent roles
# --------------------------------------------------------------------------- #
def test_the_publisher_may_not_be_the_approving_authority():
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.identity(publisher_id="authority-benchmark-governance-board")
    assert excinfo.value.reason is _R.BENCHMARK_ROLE_SEPARATION_VIOLATED


def test_a_distinct_publisher_and_approver_construct():
    identity = b.identity()
    assert identity.publisher_id != identity.approval.approval_authority_ref


# --------------------------------------------------------------------------- #
# Measurement semantics (ADR §15 rows 8-14)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "field",
    [f.name for f in dataclasses.fields(BenchmarkMeasurementSemantics)],
)
def test_every_measurement_coordinate_is_required(field):
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.measurement(**{field: ""})
    assert excinfo.value.reason is _R.BENCHMARK_MEASUREMENT_SEMANTICS_INCOMPLETE


def test_the_measurement_group_reports_every_missing_coordinate_at_once():
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.measurement(unit="", population_ref="")
    message = str(excinfo.value)
    assert "unit" in message and "population_ref" in message


def test_measurement_has_exactly_the_seven_adr_rows():
    names = [f.name for f in dataclasses.fields(BenchmarkMeasurementSemantics)]
    assert names == [
        "intended_outcome_ref",
        "metric_ref",
        "unit",
        "measurement_protocol_ref",
        "population_ref",
        "aggregation_semantics_ref",
        "observation_window_ref",
    ]


# --------------------------------------------------------------------------- #
# Source / provenance requirements (ADR §15 row 16)
# --------------------------------------------------------------------------- #
def test_source_requirements_must_not_be_empty():
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.source_requirements(provenance_requirement_refs=())
    assert excinfo.value.reason is _R.BENCHMARK_SOURCE_REQUIREMENTS_INVALID


def test_a_duplicate_provenance_requirement_is_refused_not_deduplicated():
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.source_requirements(provenance_requirement_refs=("r-a", "r-a"))
    assert excinfo.value.reason is _R.BENCHMARK_SOURCE_REQUIREMENTS_INVALID


def test_a_string_is_not_a_sequence_of_references():
    with pytest.raises(BenchmarkContractError):
        b.source_requirements(provenance_requirement_refs="r-a")


def test_a_mapping_is_not_a_sequence_of_references():
    with pytest.raises(BenchmarkContractError):
        b.source_requirements(provenance_requirement_refs={"r-a": 1})


def test_a_generator_is_refused_rather_than_consumed():
    with pytest.raises(BenchmarkContractError):
        b.source_requirements(provenance_requirement_refs=(x for x in ("r-a",)))


def test_the_caller_list_is_defensively_copied():
    refs = ["r-b", "r-a"]
    requirements = b.source_requirements(provenance_requirement_refs=refs)
    before = canonical_bytes(requirements)
    refs.append("r-c")
    assert canonical_bytes(requirements) == before
    assert requirements.provenance_requirement_refs == ("r-a", "r-b")
    assert isinstance(requirements.provenance_requirement_refs, tuple)


# --------------------------------------------------------------------------- #
# Supersession (ADR §15 row 20, §17.12, DD-4)
# --------------------------------------------------------------------------- #
def test_the_only_ratified_supersession_status_is_undetermined():
    assert [m.value for m in BenchmarkSupersessionStatus] == ["UNDETERMINED"]


def test_the_supersession_declaration_is_mandatory_on_the_identity():
    fields = {f.name for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)}
    assert "supersession" in fields


def test_no_successor_reference_field_exists_anywhere():
    """DD-4 defers the structured successor reference; nothing pre-empts it."""

    contracts = [
        BenchmarkSupersessionDeclaration,
        CanonicalBenchmarkDefinitionIdentity,
        BenchmarkCoordinate,
    ]
    for contract in contracts:
        for field in dataclasses.fields(contract):
            lowered = field.name.lower()
            for banned in ("successor", "supersedes", "superseded_by",
                           "predecessor", "replaces", "replacement"):
                assert banned not in lowered, (contract.__name__, field.name)


def test_the_undetermined_declaration_is_not_a_claim_of_not_superseded():
    """§15 row 20 — "its absence never implies 'not superseded'"."""

    declaration = BenchmarkSupersessionDeclaration.undetermined()
    assert declaration.status is BenchmarkSupersessionStatus.UNDETERMINED
    # There is no member, property or method that would say "not superseded".
    for name in dir(declaration):
        assert "not_superseded" not in name.lower()
        assert "is_current" not in name.lower()


# --------------------------------------------------------------------------- #
# Immutability, subclassing and duck typing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "contract",
    [
        BenchmarkApplicabilityCoordinate,
        BenchmarkScope,
        BenchmarkCoordinate,
        BenchmarkMeasurementSemantics,
        BenchmarkEffectivePeriod,
        BenchmarkSourceRequirements,
        BenchmarkApprovalReference,
        BenchmarkSupersessionDeclaration,
        CanonicalBenchmarkDefinitionIdentity,
    ],
)
def test_every_public_contract_is_a_frozen_dataclass(contract):
    assert dataclasses.is_dataclass(contract)
    assert contract.__dataclass_params__.frozen is True


def test_assignment_to_a_constructed_identity_is_refused():
    identity = b.identity()
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.publisher_id = "someone-else"


def test_a_subclass_is_refused_where_contract_identity_is_load_bearing():
    class SneakyScope(BenchmarkScope):
        pass

    sneaky = SneakyScope(kind=BenchmarkScope.platform_wide().kind, tenant_id="")
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.coordinate(scope=sneaky)
    assert excinfo.value.reason is _R.BENCHMARK_MALFORMED_CONTRACT


def test_a_duck_typed_lookalike_is_refused():
    class LooksLikeAScope:
        kind = BenchmarkScope.platform_wide().kind
        tenant_id = ""

    with pytest.raises(BenchmarkContractError):
        b.coordinate(scope=LooksLikeAScope())


class _SneakyStr(str):
    """A ``str`` subclass that claims to equal everything.

    The concrete reason ``require_canonical_str`` uses ``type(x) is str`` rather
    than ``isinstance``: a subclass can override ``__eq__``, ``__hash__`` or
    ``__str__`` and thereby change what the padding check, the NFC check, a
    role-separation comparison and canonicalization all see.
    """

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


def test_a_str_subclass_is_refused_as_a_coordinate_token():
    """Refused for being the wrong *type*, before any comparison runs."""

    with pytest.raises(BenchmarkContractError) as excinfo:
        b.coordinate(benchmark_id=_SneakyStr("bmk-alpha"))
    assert excinfo.value.reason is _R.BENCHMARK_MALFORMED_CONTRACT


def test_a_str_subclass_is_refused_as_an_identifier():
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.identity(publisher_id=_SneakyStr("publisher-x"))
    # The reason matters: a lying subclass must be refused as *malformed*, not
    # incidentally caught by the role-separation comparison it also corrupts.
    assert excinfo.value.reason is _R.BENCHMARK_MALFORMED_CONTRACT


def test_a_str_subclass_is_refused_everywhere_a_token_is_required():
    for build in (
        lambda v: b.coordinate(benchmark_family=v),
        lambda v: BenchmarkScope.for_tenant(v),
        lambda v: b.measurement(unit=v),
        lambda v: b.source_requirements(source_ref=v),
        lambda v: b.source_requirements(provenance_requirement_refs=(v,)),
    ):
        with pytest.raises(BenchmarkContractError) as excinfo:
            build(_SneakyStr("value"))
        assert excinfo.value.reason in {
            _R.BENCHMARK_MALFORMED_CONTRACT,
            _R.BENCHMARK_SOURCE_REQUIREMENTS_INVALID,
        }


def test_pickle_and_copy_round_trips_preserve_the_digest():
    """A round trip must not become a way to build an object that skipped checks."""

    identity = b.identity()
    for clone in (
        copy.copy(identity),
        copy.deepcopy(identity),
        pickle.loads(pickle.dumps(identity)),
    ):
        assert clone == identity
        assert clone.canonical_digest() == identity.canonical_digest()
        assert clone.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED
        assert clone.trusted_resolution_performed is False


def test_object_setattr_forgery_moves_the_digest():
    """Bypassing ``__post_init__`` cannot produce a self-consistent forgery.

    ``object.__setattr__`` defeats ``frozen=True`` — nothing in Python stops it.
    What the contract guarantees is that the *digest follows the bytes*: a
    tampered identity no longer matches the digest anyone recorded for it.
    """

    identity = b.identity()
    before = identity.canonical_digest()
    object.__setattr__(identity, "publisher_id", "publisher-someone-else")
    assert identity.canonical_digest() != before


# --------------------------------------------------------------------------- #
# Honest status — none of it is settable
# --------------------------------------------------------------------------- #
def test_structural_status_has_exactly_one_member():
    assert [m.value for m in BenchmarkStructuralStatus] == ["STRUCTURAL_UNVERIFIED"]


def test_the_status_properties_are_not_fields_and_cannot_be_set():
    identity = b.identity()
    names = {f.name for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)}
    for prop in ("structural_status", "trusted_resolution_performed",
                 "unresolved_reason"):
        assert prop not in names
        with pytest.raises(AttributeError):
            setattr(identity, prop, "anything")


def test_unresolved_reason_is_permanent_across_every_lifecycle_state():
    for state in BenchmarkLifecycleState:
        identity = b.identity(lifecycle_state=state)
        assert identity.unresolved_reason is _R.BENCHMARK_RESOLUTION_NOT_PERFORMED
        assert identity.trusted_resolution_performed is False


def test_structural_refusals_always_contain_resolution_not_performed():
    """There is no input for which BR-1 reports "nothing is wrong"."""

    for identity in (b.identity(), b.minimal_identity()):
        refusals = identity.structural_refusals_at(b.INSIDE)
        assert _R.BENCHMARK_RESOLUTION_NOT_PERFORMED in refusals
        assert refusals != ()


def test_structural_refusals_are_in_declaration_order():
    identity = b.identity(lifecycle_state=BenchmarkLifecycleState.REVOKED)
    refusals = identity.structural_refusals_at(b.EFFECTIVE_TO)
    order = list(BenchmarkRefusalReason)
    assert list(refusals) == sorted(refusals, key=order.index)
    assert _R.BENCHMARK_EXPIRED in refusals
    assert _R.BENCHMARK_REVOKED in refusals
    assert _R.BENCHMARK_RESOLUTION_NOT_PERFORMED in refusals


def test_a_revoked_definition_is_representable_and_refused():
    """§16.2 stage 5's "state admissible" is vacuous unless one state is not."""

    identity = b.identity(lifecycle_state=BenchmarkLifecycleState.REVOKED)
    assert identity.lifecycle_refusal is _R.BENCHMARK_REVOKED
    assert b.identity().lifecycle_refusal is None


def test_a_revoked_state_carries_no_revocation_record():
    """It is a declaration, never the signed, entitled record §17.10-11 requires."""

    names = {f.name for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)}
    for banned in ("revoker", "revoked_at", "revocation_ref", "revocation_digest",
                   "revocation_signature"):
        assert banned not in names


# --------------------------------------------------------------------------- #
# Effective period shape (ADR §15 row 15)
# --------------------------------------------------------------------------- #
def test_a_bounded_period_without_an_end_is_refused():
    with pytest.raises(BenchmarkContractError) as excinfo:
        BenchmarkEffectivePeriod(
            effective_from=b.EFFECTIVE_FROM,
            end_declaration=TemporalBoundDeclaration.BOUNDED,
            effective_to=None,
        )
    assert excinfo.value.reason is _R.BENCHMARK_EFFECTIVE_PERIOD_INVALID


def test_an_open_ended_period_carrying_an_end_is_refused():
    with pytest.raises(BenchmarkContractError) as excinfo:
        BenchmarkEffectivePeriod(
            effective_from=b.EFFECTIVE_FROM,
            end_declaration=TemporalBoundDeclaration.OPEN_ENDED,
            effective_to=b.EFFECTIVE_TO,
        )
    assert excinfo.value.reason is _R.BENCHMARK_EFFECTIVE_PERIOD_INVALID


def test_an_equal_or_reversed_period_is_refused():
    for start, end in (
        (b.EFFECTIVE_FROM, b.EFFECTIVE_FROM),
        (b.EFFECTIVE_TO, b.EFFECTIVE_FROM),
    ):
        with pytest.raises(BenchmarkContractError) as excinfo:
            BenchmarkEffectivePeriod.bounded(start, end)
        assert excinfo.value.reason is _R.BENCHMARK_EFFECTIVE_PERIOD_INVALID
