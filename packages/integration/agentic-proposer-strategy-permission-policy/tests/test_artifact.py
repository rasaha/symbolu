"""Construction rules for the strategy-permission artifact.

Every rule here is fail-closed: a refused construction produces no artifact, so a
malformed policy never reaches the authority to be issued.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from _strategy_permission_fixtures import (
    ADAPTER,
    DEFAULT_PERMITTED,
    STRATEGY_POLICY_REF,
    T_FROM,
    T_TO,
    TENANT,
    make_permission_policy,
)
from ugence_agentic_proposer import ReasoningStrategy
from ugence_agentic_proposer_strategy_permission_policy import (
    ADMITTED_STRATEGY_TOKENS,
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    STRATEGY_PERMISSION_POLICY_FAMILY,
    STRATEGY_VOCABULARY_VERSION,
    StrategyPermissionDuplicateError,
    StrategyPermissionFieldError,
    StrategyPermissionOrderingError,
    StrategyPermissionPolicy,
    StrategyPermissionPolicyError,
    StrategyPermissionPolicyMetadata,
)

SINGLE = ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value
MULTI = ReasoningStrategy.MULTI_CANDIDATE_UNREVISED.value
REVISED = ReasoningStrategy.REVISED_ADVISORY.value


def _draft(**kwargs) -> StrategyPermissionPolicy:
    fields = dict(
        metadata=StrategyPermissionPolicyMetadata(
            policy_id="p-1",
            version="1.0.0",
            content_digest=PLACEHOLDER_CONTENT_DIGEST,
            scope=POLICY_SCOPE_TENANT,
            lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
            tenant_id=TENANT,
        ),
        strategy_policy_ref=STRATEGY_POLICY_REF,
        permitted_strategies=DEFAULT_PERMITTED,
    )
    fields.update(kwargs)
    return StrategyPermissionPolicy(**fields)


# --------------------------------------------------------------------------- #
# The permitted set
# --------------------------------------------------------------------------- #


def test_a_well_formed_policy_constructs():
    policy = _draft()
    assert policy.permitted_strategies == DEFAULT_PERMITTED
    assert policy.vocabulary_version == STRATEGY_VOCABULARY_VERSION


def test_an_empty_permitted_set_is_refused_at_construction():
    """`S2B-PF-B=A`: a policy that permits nothing is not issuable.

    A policy permitting nothing would resolve and let the reader conclude nothing,
    which is worse than having no policy because it looks like coverage. The state
    remains representable at the resolver-response boundary, which is where the
    ratified replay reports it; it is simply not something this family issues.
    """

    with pytest.raises(StrategyPermissionFieldError):
        _draft(permitted_strategies=())


def test_a_duplicate_member_is_refused():
    with pytest.raises(StrategyPermissionDuplicateError):
        _draft(permitted_strategies=(SINGLE, SINGLE))


def test_an_unsorted_permitted_set_is_refused_and_never_reordered():
    """Rejected if unsorted — the artifact a reader sees is the one its author wrote."""

    unsorted = (SINGLE, MULTI)
    assert list(unsorted) != sorted(unsorted)
    with pytest.raises(StrategyPermissionOrderingError):
        _draft(permitted_strategies=unsorted)


def test_a_token_outside_the_vocabulary_is_refused():
    with pytest.raises(StrategyPermissionFieldError):
        _draft(permitted_strategies=("STAGED_DECOMPOSITION",))


def test_a_permitted_set_must_be_a_tuple_not_a_list():
    with pytest.raises(StrategyPermissionFieldError):
        _draft(permitted_strategies=[SINGLE])


def test_an_enum_member_is_not_stored_in_place_of_its_string_value():
    """The artifact stays plain stdlib: the projection depends on no enum coercion."""

    with pytest.raises(StrategyPermissionFieldError):
        _draft(permitted_strategies=(ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED,))


def test_all_three_ratified_spellings_are_admissible_together():
    policy = _draft(permitted_strategies=tuple(sorted((SINGLE, MULTI, REVISED))))
    assert set(policy.permitted_strategies) == ADMITTED_STRATEGY_TOKENS


@pytest.mark.parametrize("member", list(ReasoningStrategy))
def test_membership_is_exact_codepoint_equality(member):
    policy = _draft(permitted_strategies=(member.value,))
    assert policy.permits(member) is True
    assert policy.permits(member.value) is True
    assert policy.permits(member.value.lower()) is False
    assert policy.permits(f" {member.value} ") is False


def test_permits_refuses_a_value_that_is_neither_a_member_nor_a_str():
    with pytest.raises(StrategyPermissionFieldError):
        _draft().permits(object())


# --------------------------------------------------------------------------- #
# The signed reference and the vocabulary version
# --------------------------------------------------------------------------- #


def test_the_reference_must_satisfy_the_c5a_identifier_grammar():
    with pytest.raises(StrategyPermissionFieldError):
        _draft(strategy_policy_ref="has a space")
    with pytest.raises(StrategyPermissionFieldError):
        _draft(strategy_policy_ref="-leading-hyphen")
    with pytest.raises(StrategyPermissionFieldError):
        _draft(strategy_policy_ref="")


def test_the_reference_admits_the_slash_the_identifier_grammar_allows():
    assert _draft(strategy_policy_ref="a/b:c.d-e").strategy_policy_ref == "a/b:c.d-e"


def test_the_vocabulary_version_is_the_one_fixed_value():
    assert STRATEGY_VOCABULARY_VERSION == "ugence.agentic-proposer.reasoning-strategy/v1"
    with pytest.raises(StrategyPermissionFieldError):
        _draft(vocabulary_version="ugence.agentic-proposer.reasoning-strategy/v2")
    with pytest.raises(StrategyPermissionFieldError):
        _draft(vocabulary_version="")


# --------------------------------------------------------------------------- #
# The metadata envelope
# --------------------------------------------------------------------------- #


def _metadata(**overrides) -> StrategyPermissionPolicyMetadata:
    fields = dict(
        policy_id="p-1",
        version="1.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=TENANT,
    )
    fields.update(overrides)
    return StrategyPermissionPolicyMetadata(**fields)


@pytest.mark.parametrize("bad", ["has space", "-leading", "", "a/b"])
def test_policy_id_must_satisfy_the_c5b_token_grammar(bad):
    """C5b bars ``/``: the id is stamped onto the advisory as a ``Token``."""

    with pytest.raises(StrategyPermissionFieldError):
        _metadata(policy_id=bad)


@pytest.mark.parametrize("bad", ["has space", "-leading", "", "1/2"])
def test_version_must_satisfy_the_c5b_token_grammar(bad):
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(version=bad)


def test_the_version_is_a_string_never_a_number():
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(version=1)


def test_an_over_long_identifier_is_refused():
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(policy_id="a" * 201)


@pytest.mark.parametrize("bad", ["", "A" * 64, "0" * 63, "z" * 64, 42])
def test_the_content_digest_must_be_lowercase_sha256_hex(bad):
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(content_digest=bad)


def test_an_unknown_scope_is_refused():
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(scope="REGIONAL")


def test_an_unknown_lifecycle_label_is_refused():
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(lifecycle_state="ACTIVE")


def test_scope_and_tenant_are_one_fact():
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(scope=POLICY_SCOPE_GLOBAL, tenant_id=TENANT)
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(scope=POLICY_SCOPE_TENANT, tenant_id="")
    assert _metadata(scope=POLICY_SCOPE_GLOBAL, tenant_id="").tenant_id == ""


def test_a_naive_datetime_is_never_assumed_to_be_utc():
    with pytest.raises(StrategyPermissionFieldError):
        _metadata(effective_from=datetime(2026, 1, 1))


def test_an_empty_effective_interval_is_refused():
    with pytest.raises(StrategyPermissionOrderingError):
        _metadata(effective_from=T_TO, effective_to=T_FROM)
    with pytest.raises(StrategyPermissionOrderingError):
        _metadata(effective_from=T_FROM, effective_to=T_FROM)


def test_an_unbounded_interval_is_admissible():
    assert _metadata(effective_from=None, effective_to=None).effective_from is None


def test_the_policy_family_is_fixed_and_not_an_authored_field():
    metadata = _metadata()
    assert metadata.policy_family == STRATEGY_PERMISSION_POLICY_FAMILY
    with pytest.raises(TypeError):
        StrategyPermissionPolicyMetadata(
            policy_id="p-1",
            version="1.0.0",
            content_digest=PLACEHOLDER_CONTENT_DIGEST,
            scope=POLICY_SCOPE_GLOBAL,
            lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
            policy_family="something.else",
        )


def test_the_metadata_must_be_exactly_this_family_s_envelope():
    class Extended(StrategyPermissionPolicyMetadata):
        pass

    sneaky = Extended(
        policy_id="p-1",
        version="1.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_GLOBAL,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
    )
    with pytest.raises(StrategyPermissionFieldError):
        _draft(metadata=sneaky)


def test_every_construction_error_descends_from_one_root():
    for error in (
        StrategyPermissionFieldError,
        StrategyPermissionOrderingError,
        StrategyPermissionDuplicateError,
    ):
        assert issubclass(error, StrategyPermissionPolicyError)


# --------------------------------------------------------------------------- #
# The artifact is frozen and its digest binds its body
# --------------------------------------------------------------------------- #


def test_the_artifact_is_frozen():
    policy = make_permission_policy()
    with pytest.raises(Exception):
        policy.permitted_strategies = (SINGLE,)


def test_the_declared_digest_binds_the_body():
    descriptor = ADAPTER.describe(make_permission_policy())
    assert descriptor.body_digest() == descriptor.declared_content_digest


@pytest.mark.parametrize(
    "overrides",
    [
        dict(permitted=(SINGLE,)),
        dict(strategy_policy_ref="ugence.agentic-proposer/other-role/v1"),
        dict(version="1.0.1"),
        dict(effective_to=datetime(2027, 2, 1, tzinfo=timezone.utc)),
    ],
    ids=["permitted-set", "reference", "version", "effective-window"],
)
def test_every_body_field_moves_the_digest(overrides):
    """`[V]` Conditional on the projection: each field is transitively signed."""

    base = ADAPTER.describe(make_permission_policy()).body_digest()
    other = ADAPTER.describe(make_permission_policy(**overrides)).body_digest()
    assert base != other
