"""The refusal vocabulary is complete, namespaced and entirely refusals.

ADR §16.3 ratifies "a stable typed refusal reason"; §22.11 requires reason-code
namespaces "scoped per capability, stable across versions, never reused for a
different meaning"; DD-1 delegates the exact vocabulary to this milestone.
"""

from __future__ import annotations

import pytest
from ugence_benchmark_registry.api import (
    BENCHMARK_REFUSAL_REASONS,
    BR1_BENCHMARK_REFUSAL_REASONS,
    BenchmarkCanonicalizationError,
    BenchmarkContractError,
    BenchmarkLifecycleError,
    BenchmarkRefusalReason,
)

_R = BenchmarkRefusalReason

#: The BR-1 vocabulary, written out in declaration order independently of the
#: package's own frozenset, so a rename, a removal or a reordering fails here.
BR1_CODES = [
    "BENCHMARK_DEFINITION_MISSING",
    "BENCHMARK_MALFORMED_CONTRACT",
    "BENCHMARK_CANONICALIZATION_FAILED",
    "BENCHMARK_IDENTITY_COORDINATE_MISSING",
    "BENCHMARK_COORDINATE_NOT_EXACT",
    "BENCHMARK_APPLICABILITY_INCONSISTENT",
    "BENCHMARK_MEASUREMENT_SEMANTICS_INCOMPLETE",
    "BENCHMARK_SOURCE_REQUIREMENTS_INVALID",
    "BENCHMARK_APPROVAL_REFERENCE_INVALID",
    "BENCHMARK_ROLE_SEPARATION_VIOLATED",
    "BENCHMARK_EFFECTIVE_PERIOD_INVALID",
    "BENCHMARK_NOT_YET_EFFECTIVE",
    "BENCHMARK_EXPIRED",
    "BENCHMARK_INVALID_LIFECYCLE_TRANSITION",
    "BENCHMARK_REVOKED",
    "BENCHMARK_SUPERSESSION_DECLARATION_INVALID",
    "BENCHMARK_RESOLUTION_NOT_PERFORMED",
]

#: BR-1 codes that no BR-1 input can currently produce, and why.
#:
#: ``BENCHMARK_SUPERSESSION_DECLARATION_INVALID`` guards
#: :class:`BenchmarkSupersessionDeclaration` against a status other than
#: ``UNDETERMINED``. It cannot fire today because
#: :class:`BenchmarkSupersessionStatus` has exactly one member and the field is
#: exact-type-checked, so there is no other value to supply — a **defence-in-depth**
#: gate, not a load-bearing one, and counted as such in the mutation ledger.
#:
#: It stays: the day DD-4 ratifies a structured successor and a second member
#: exists, the guard becomes load-bearing, and a check added after the vocabulary
#: widens is a check added too late. ``test_the_supersession_guard_is_unreachable_
#: for_exactly_one_reason`` pins the structure that makes it unreachable, so this
#: claim fails loudly if it ever loosens.
STRUCTURALLY_UNREACHABLE_AT_BR1 = frozenset(
    {BenchmarkRefusalReason.BENCHMARK_SUPERSESSION_DECLARATION_INVALID}
)

#: Vocabulary ADR §30/§32 assigns to BR-2. None of it may appear at BR-1: a code
#: no code path can raise is a promise about behaviour that does not exist.
BR2_CODES_MUST_BE_ABSENT = [
    "BENCHMARK_REGISTRY_UNAVAILABLE",
    "BENCHMARK_NOT_FOUND",
    "BENCHMARK_LOOKUP_FAILED",
    "BENCHMARK_ADMISSION_DENIED",
    "BENCHMARK_COORDINATE_OCCUPIED",
    "BENCHMARK_REGISTRATION_CONFLICT",
    "BENCHMARK_APPROVAL_VERIFICATION_FAILED",
    "BENCHMARK_PUBLISHER_UNAUTHORIZED",
    "BENCHMARK_SIGNATURE_INVALID",
    "BENCHMARK_KEY_REVOKED",
    "BENCHMARK_TRUST_ANCHOR_MISSING",
    "BENCHMARK_REVOCATION_UNVERIFIED",
    "BENCHMARK_SUPERSEDED",
    "BENCHMARK_SUCCESSOR_UNRESOLVED",
    "BENCHMARK_CROSS_TENANT_DENIED",
    "BENCHMARK_STORAGE_FAILURE",
    "BENCHMARK_LIFECYCLE_STATE_INADMISSIBLE",
]


def test_the_vocabulary_is_exactly_the_seventeen_br1_codes_in_order():
    assert [m.value for m in BenchmarkRefusalReason] == BR1_CODES
    assert len(BR1_CODES) == 17


def test_member_names_equal_member_values():
    for member in BenchmarkRefusalReason:
        assert member.name == member.value


def test_every_member_is_namespaced():
    for member in BenchmarkRefusalReason:
        assert member.value.startswith("BENCHMARK_"), member
        assert member.value == member.value.upper(), member


def test_values_are_unique():
    values = [m.value for m in BenchmarkRefusalReason]
    assert len(set(values)) == len(values)


def test_the_constant_sets_agree_with_the_enum():
    assert BENCHMARK_REFUSAL_REASONS == frozenset(BenchmarkRefusalReason)
    assert BR1_BENCHMARK_REFUSAL_REASONS == BENCHMARK_REFUSAL_REASONS


def test_the_constants_are_immutable():
    for constant in (BENCHMARK_REFUSAL_REASONS, BR1_BENCHMARK_REFUSAL_REASONS):
        assert isinstance(constant, frozenset)
        with pytest.raises(AttributeError):
            constant.add(_R.BENCHMARK_EXPIRED)


def test_there_is_no_success_member():
    """Every member is a refusal; "nothing refused" has no positive spelling.

    Compared on whole underscore-separated words, so ``…_INVALID`` is not read as
    containing ``VALID``: the point is that no member *names a success*, and
    ``INVALID`` names the opposite of one.
    """

    positive = {"OK", "SUCCESS", "VALID", "ADMITTED", "RESOLVED", "APPROVED",
                "TRUSTED", "PASS", "PASSED", "ACCEPTED", "REGISTERED"}
    for member in BenchmarkRefusalReason:
        words = set(member.value.split("_"))
        assert not (words & positive), member


def test_resolution_not_performed_is_a_refusal_not_a_pass():
    assert _R.BENCHMARK_RESOLUTION_NOT_PERFORMED in BENCHMARK_REFUSAL_REASONS


@pytest.mark.parametrize("code", BR2_CODES_MUST_BE_ABSENT)
def test_no_br2_runtime_code_is_minted(code):
    assert code not in {m.value for m in BenchmarkRefusalReason}


def test_no_trusted_evidence_code_is_reused():
    """Two capabilities, two namespaces (ADR §22.11)."""

    for member in BenchmarkRefusalReason:
        assert "EVIDENCE" not in member.value, member
        assert "TRUSTED_EVIDENCE" not in member.value, member


def test_no_assertion_support_vocabulary_is_reused():
    """ADR §6.1 — the tap-provider's scoring vocabulary is a different question."""

    forbidden = {"SUPPORTED", "UNSUPPORTED", "CONSTRAINED", "INDETERMINATE",
                 "UNKNOWN"}
    assert not ({m.value for m in BenchmarkRefusalReason} & forbidden)


def test_declaration_order_is_the_deterministic_reason_order():
    order = list(BenchmarkRefusalReason)
    assert order[0] is _R.BENCHMARK_DEFINITION_MISSING
    assert order[-1] is _R.BENCHMARK_RESOLUTION_NOT_PERFORMED
    assert sorted(order, key=order.index) == order


# --------------------------------------------------------------------------- #
# Error types carry the codes
# --------------------------------------------------------------------------- #
def test_the_error_hierarchy_is_value_error_based():
    assert issubclass(BenchmarkContractError, ValueError)
    assert issubclass(BenchmarkCanonicalizationError, BenchmarkContractError)
    assert issubclass(BenchmarkLifecycleError, BenchmarkContractError)


def test_the_specialised_errors_carry_their_ratified_codes():
    assert (
        BenchmarkCanonicalizationError.reason
        is _R.BENCHMARK_CANONICALIZATION_FAILED
    )
    assert (
        BenchmarkLifecycleError.reason
        is _R.BENCHMARK_INVALID_LIFECYCLE_TRANSITION
    )


def test_the_base_error_defaults_to_no_code():
    assert BenchmarkContractError.reason is None


def test_a_raised_error_is_catchable_as_a_value_error():
    import _builders as b

    with pytest.raises(ValueError):
        b.coordinate(benchmark_version="latest")


# --------------------------------------------------------------------------- #
# Reachability — every BR-1 code is produced by a real code path
# --------------------------------------------------------------------------- #
def test_every_conditional_code_has_a_demonstrated_producer():
    """The codes BR-1 raises or returns, each shown to be reachable.

    ``BENCHMARK_DEFINITION_MISSING`` is the one member with no producer *inside*
    this package, and deliberately so: it is the code a **consumer** reports when
    no definition was supplied at all, which is a condition only the consumer can
    observe. It is listed here rather than silently exempted.
    """

    import _builders as b
    from ugence_benchmark_registry.api import (
        BenchmarkApplicabilityCoordinate,
        BenchmarkApprovalReference,
        BenchmarkEffectivePeriod,
        BenchmarkLifecycleState,
        BenchmarkScope,
        canonical_bytes,
        require_valid_lifecycle_transition,
    )

    produced = set()

    def record(fn):
        try:
            fn()
        except BenchmarkContractError as error:
            if error.reason is not None:
                produced.add(error.reason)

    record(lambda: b.coordinate(benchmark_id=" padded"))
    record(lambda: canonical_bytes("not a contract"))
    record(lambda: b.coordinate(benchmark_id=""))
    record(lambda: b.coordinate(benchmark_version="latest"))
    record(lambda: BenchmarkApplicabilityCoordinate.applicable(""))
    record(lambda: b.measurement(unit=""))
    record(lambda: b.source_requirements(provenance_requirement_refs=()))
    record(
        lambda: b.identity(
            approval=b.approval(approved_content_digest=b.OTHER_CONTENT_DIGEST)
        )
    )
    record(
        lambda: b.identity(publisher_id="authority-benchmark-governance-board")
    )
    record(lambda: BenchmarkEffectivePeriod.bounded(b.EFFECTIVE_TO, b.EFFECTIVE_FROM))
    record(
        lambda: require_valid_lifecycle_transition(
            BenchmarkLifecycleState.AUTHORED, BenchmarkLifecycleState.REVOKED
        )
    )
    # Returned rather than raised.
    identity = b.identity(lifecycle_state=BenchmarkLifecycleState.REVOKED)
    produced.add(identity.lifecycle_refusal)
    produced.add(identity.unresolved_reason)
    produced.add(identity.temporal_refusal_at(b.BEFORE))
    produced.add(identity.temporal_refusal_at(b.EFFECTIVE_TO))

    expected = (
        set(BenchmarkRefusalReason)
        - {_R.BENCHMARK_DEFINITION_MISSING}
        - STRUCTURALLY_UNREACHABLE_AT_BR1
    )
    assert expected - produced == set(), sorted(
        m.value for m in (expected - produced)
    )
    # Sanity: the scope/tenant path also produces the applicability code.
    record(lambda: BenchmarkScope.for_tenant(""))
    record(
        lambda: BenchmarkApprovalReference(
            approval_ref="ap", approval_authority_ref="auth",
            approved_content_digest="short",
        )
    )


def test_the_supersession_guard_is_unreachable_for_exactly_one_reason():
    """Pin the structure that makes the supersession guard defence-in-depth.

    The guard is unreachable **only** because the status vocabulary has one
    member and the field is exact-type-checked. If either fact changes, this test
    fails and the guard must be re-classified as load-bearing and given a
    behavioural test.
    """

    from ugence_benchmark_registry.api import (
        BenchmarkSupersessionDeclaration,
        BenchmarkSupersessionStatus,
    )

    assert len(list(BenchmarkSupersessionStatus)) == 1

    # And a non-member is refused earlier, by the exact-type check.
    with pytest.raises(BenchmarkContractError) as excinfo:
        BenchmarkSupersessionDeclaration(status="UNDETERMINED")
    assert excinfo.value.reason is _R.BENCHMARK_MALFORMED_CONTRACT
