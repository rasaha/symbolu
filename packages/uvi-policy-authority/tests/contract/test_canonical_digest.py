"""Proofs about the canonical body digest (GV-2C-b §6)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from _authority_fixtures import (
    ALL_FAMILIES,
    ARBITRARY_DIGEST,
    T_FROM,
    T_TO,
    make_authority,
    make_policy,
)
from ugence_uvi_policy_authority.api import (
    POLICY_BODY_DIGEST_DOMAIN,
    PolicyAuthorityError,
    PolicyDigestMismatchError,
    canonical_policy_body_bytes,
    canonical_policy_body_digest,
)
from ugence_uvi_policy_contracts.api import (
    DomainPolicy,
    GovernedThreshold,
    ComparisonOperator,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyLifecycleState,
    PolicyScope,
    ReadinessPolicy,
    GateCategory,
    PolicyGate,
    ReadinessTarget,
    RequirementClass,
)


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_digest_is_a_single_pass_fixed_relation(family):
    """content_digest == body digest, computable in one pass, no iteration.

    The self-referential field is *removed* from the payload, so digesting a
    draft that carries a placeholder yields exactly the digest the final
    artifact declares. Setting the field cannot change the result.
    """

    policy = make_policy(family)
    assert canonical_policy_body_digest(policy) == policy.metadata.content_digest


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_content_digest_does_not_participate_in_its_own_digest(family):
    """Rewriting content_digest alone never changes the body digest."""

    policy = make_policy(family)
    from dataclasses import replace

    tampered = replace(
        policy, metadata=replace(policy.metadata, content_digest=ARBITRARY_DIGEST)
    )
    assert canonical_policy_body_digest(tampered) == canonical_policy_body_digest(policy)


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_equal_normalized_policies_produce_equal_bytes_and_digest(family):
    a = make_policy(family)
    b = make_policy(family)
    assert a == b
    assert canonical_policy_body_bytes(a) == canonical_policy_body_bytes(b)
    assert canonical_policy_body_digest(a) == canonical_policy_body_digest(b)


def test_digest_is_deterministic_across_repeated_computation():
    policy = make_policy(PolicyFamily.READINESS)
    digests = {canonical_policy_body_digest(policy) for _ in range(25)}
    assert len(digests) == 1


def test_meaningful_content_change_changes_the_digest():
    a = make_policy(PolicyFamily.DOMAIN)
    b = make_policy(PolicyFamily.DOMAIN, overrides={"governed_outcome_unit": "closed_case"})
    assert a.metadata.content_digest != b.metadata.content_digest


def test_list_and_tuple_inputs_normalize_identically():
    """A caller-owned list and the tuple it normalizes to are indistinguishable."""

    gate = PolicyGate(
        gate_id="g1",
        category=GateCategory.QUALITY,
        requirement_class=RequirementClass.CONDITIONAL,
        applicability=[ReadinessTarget.PILOT],  # list in
    )
    as_list = make_policy(PolicyFamily.READINESS, overrides={"gates": [gate]})
    as_tuple = make_policy(PolicyFamily.READINESS, overrides={"gates": (gate,)})

    assert isinstance(as_list.gates, tuple)
    assert canonical_policy_body_bytes(as_list) == canonical_policy_body_bytes(as_tuple)
    assert as_list.metadata.content_digest == as_tuple.metadata.content_digest


def test_mutating_the_caller_owned_list_after_construction_changes_nothing():
    gates = [
        PolicyGate(
            gate_id="g1",
            category=GateCategory.QUALITY,
            requirement_class=RequirementClass.ADVISORY,
            applicability=(ReadinessTarget.PILOT,),
        )
    ]
    policy = make_policy(PolicyFamily.READINESS, overrides={"gates": gates})
    before = canonical_policy_body_digest(policy)
    gates.clear()
    gates.append("not even a gate")
    assert canonical_policy_body_digest(policy) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("policy_id", "other-policy"),
        ("version", "2.0.0"),
        ("lifecycle_state", PolicyLifecycleState.DRAFT),
        ("effective_from", T_FROM + timedelta(days=1)),
        ("effective_to", T_TO + timedelta(days=1)),
        ("issuer_ref", "issuer-x"),
        ("approval_ref", "approval-x"),
        ("supersedes_ref", "prior-version"),
        ("created_at", T_FROM),
    ],
)
def test_metadata_identity_changes_alter_the_bound_representation(field, value):
    """Every metadata identity field is inside the bound representation."""

    from dataclasses import replace

    policy = make_policy(PolicyFamily.DOMAIN)
    changed = replace(policy, metadata=replace(policy.metadata, **{field: value}))
    assert canonical_policy_body_digest(changed) != canonical_policy_body_digest(policy)


def test_scope_and_tenant_changes_alter_the_digest():
    glob = make_policy(PolicyFamily.DOMAIN)
    tenant = make_policy(PolicyFamily.DOMAIN, scope=PolicyScope.TENANT, tenant_id="t-1")
    other = make_policy(PolicyFamily.DOMAIN, scope=PolicyScope.TENANT, tenant_id="t-2")
    assert len({d.metadata.content_digest for d in (glob, tenant, other)}) == 3


def test_two_families_with_identical_shapes_do_not_collide():
    """The exact runtime dataclass name is bound into the digest."""

    a = make_policy(PolicyFamily.GEOGRAPHY)
    b = make_policy(PolicyFamily.DOMAIN)
    assert canonical_policy_body_bytes(a) != canonical_policy_body_bytes(b)
    assert POLICY_BODY_DIGEST_DOMAIN.encode() in canonical_policy_body_bytes(a)


def test_equal_instants_in_different_timezones_digest_identically():
    """Timestamps normalize to UTC before rendering, so representation is not identity."""

    tz = timezone(timedelta(hours=5, minutes=30))
    utc_policy = make_policy(PolicyFamily.DOMAIN, effective_from=T_FROM)
    tz_policy = make_policy(PolicyFamily.DOMAIN, effective_from=T_FROM.astimezone(tz))
    assert T_FROM.astimezone(tz) == T_FROM
    assert utc_policy.metadata.content_digest == tz_policy.metadata.content_digest


def test_signature_bytes_can_never_enter_the_body_digest():
    """A policy artifact has no signature field, so the digest cannot be circular."""

    import dataclasses

    for family in ALL_FAMILIES:
        policy = make_policy(family)
        names = {f.name for f in dataclasses.fields(policy)} | {
            f.name for f in dataclasses.fields(policy.metadata)
        }
        assert not {n for n in names if "signature" in n or "signed" in n}


def test_issuance_signature_does_not_change_the_body_digest():
    policy = make_policy(PolicyFamily.DOMAIN)
    before = canonical_policy_body_digest(policy)
    record = make_authority().issue(policy)
    assert record.signature
    assert canonical_policy_body_digest(record.policy) == before


def test_arbitrary_well_formed_digest_is_not_accepted_as_proof():
    """A syntactically perfect 64-hex string binds nothing and is rejected."""

    from dataclasses import replace

    policy = make_policy(PolicyFamily.DOMAIN)
    forged = replace(policy, metadata=replace(policy.metadata, content_digest=ARBITRARY_DIGEST))
    assert len(ARBITRARY_DIGEST) == 64 and all(c in "0123456789abcdef" for c in ARBITRARY_DIGEST)

    with pytest.raises(PolicyDigestMismatchError):
        make_authority().issue(forged)


def test_policy_body_mutation_after_reference_creation_is_detected():
    """A reference minted from one body cannot be re-used for a different body."""

    from dataclasses import replace

    original = make_policy(PolicyFamily.DOMAIN)
    reference = original.reference

    mutated = replace(original, governed_outcome_unit="something else entirely")
    assert mutated.metadata.content_digest == reference.content_digest
    assert canonical_policy_body_digest(mutated) != reference.content_digest

    with pytest.raises(PolicyDigestMismatchError):
        make_authority().issue(mutated)


def test_non_dataclass_and_shapeless_inputs_are_refused():
    with pytest.raises(PolicyAuthorityError):
        canonical_policy_body_digest("not a policy")
    with pytest.raises(PolicyAuthorityError):
        canonical_policy_body_digest(DomainPolicy)


def test_float_is_not_canonicalizable():
    from ugence_uvi_policy_authority.canonical import to_canonical_obj

    with pytest.raises(PolicyAuthorityError):
        to_canonical_obj({"x": 1.5})


def test_digest_output_shape_matches_the_contract_digest_format():
    digest = canonical_policy_body_digest(make_policy(PolicyFamily.VALUATION))
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    # Directly usable as a PolicyReference content digest.
    PolicyArtifactMetadata(
        policy_id="p", policy_family=PolicyFamily.VALUATION, version="1", content_digest=digest
    )


def test_threshold_change_inside_a_nested_collection_changes_the_digest():
    base = make_policy(PolicyFamily.READINESS)
    gate = PolicyGate(
        gate_id="safety-1",
        category=GateCategory.SAFETY,
        requirement_class=RequirementClass.MANDATORY,
        applicability=(ReadinessTarget.PILOT, ReadinessTarget.PRODUCTION),
        threshold=GovernedThreshold(
            threshold_id="t1",
            governed_unit="ratio",
            comparator=ComparisonOperator.GTE,
            literal_value="0.50",  # relaxed from 0.99
        ),
    )
    relaxed = make_policy(PolicyFamily.READINESS, overrides={"gates": (gate,)})
    assert relaxed.metadata.content_digest != base.metadata.content_digest


def test_digest_matches_an_independent_recomputation_of_the_documented_rule():
    """Recompute the documented definition by hand and compare."""

    import json

    from ugence_uvi_policy_authority.canonical import to_canonical_obj

    policy = make_policy(PolicyFamily.INTENDED_OUTCOME)
    body = to_canonical_obj(policy)
    body["metadata"] = {k: v for k, v in body["metadata"].items() if k != "content_digest"}
    expected = hashlib.sha256(
        json.dumps(
            {
                "domain": POLICY_BODY_DIGEST_DOMAIN,
                "policy_type": type(policy).__name__,
                "body": body,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert canonical_policy_body_digest(policy) == expected
