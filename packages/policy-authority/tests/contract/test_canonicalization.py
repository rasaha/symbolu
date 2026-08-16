"""Canonicalization, digest binding, Unicode posture and datetime rules (ADR §12)."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import replace
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
from ugence_policy_authority.api import (
    CANONICALIZATION_VERSION,
    POLICY_BODY_DIGEST_DOMAIN,
    PolicyCanonicalizationError,
    PolicyDigestMismatchError,
    UviPolicyFamilyAdapter,
    canonical_bytes,
    framed_body_bytes,
    framed_body_digest,
    sha256_hex,
)
from ugence_policy_authority.core.canonical import require_nfc, require_tzaware, to_canonical_obj
from ugence_governance_contracts.api import BenchmarkReference
from ugence_uvi_policy_contracts.api import (
    DomainPolicy,
    GateCategory,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    PolicyScope,
    ReadinessTarget,
    RequirementClass,
)

ADAPTER = UviPolicyFamilyAdapter()


def digest_of(policy) -> str:
    return ADAPTER.describe(policy).body_digest()


# --------------------------------------------------------------------------- #
# The digest is a single-pass fixed relation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_digest_is_a_single_pass_fixed_relation(family):
    policy = make_policy(family)
    assert digest_of(policy) == policy.metadata.content_digest


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_the_declaration_does_not_participate_in_its_own_digest(family):
    policy = make_policy(family)
    tampered = replace(policy, metadata=replace(policy.metadata, content_digest=ARBITRARY_DIGEST))
    assert digest_of(tampered) == digest_of(policy)


def test_no_sentinel_or_placeholder_value_participates():
    """Two drafts with different placeholders digest identically."""

    policy = make_policy(PolicyFamily.DOMAIN)
    a = replace(policy, metadata=replace(policy.metadata, content_digest="0" * 64))
    b = replace(policy, metadata=replace(policy.metadata, content_digest="f" * 64))
    assert digest_of(a) == digest_of(b) == digest_of(policy)
    # And the removed key is genuinely absent, not blanked.
    projection = ADAPTER.describe(policy).canonical_projection
    assert "content_digest" not in projection["metadata"]


def test_only_the_declared_path_is_removed_nested_digests_stay_bound():
    """A nested ``content_digest`` elsewhere in the artifact remains bound."""

    def build(benchmark_digest: str):
        ref = BenchmarkReference(
            benchmark_id="bench-1", version="1", content_digest=benchmark_digest
        )
        return make_policy(
            PolicyFamily.DOMAIN, overrides={"domain_benchmark_refs": (ref,)}
        )

    a = build("a" * 64)
    b = build("b" * 64)
    assert digest_of(a) != digest_of(b), "a nested content_digest must remain bound"

    projection = ADAPTER.describe(a).canonical_projection
    assert projection["domain_benchmark_refs"][0]["content_digest"] == "a" * 64
    assert "content_digest" not in projection["metadata"]


# --------------------------------------------------------------------------- #
# Framing: version, domain, adapter identity, policy type
# --------------------------------------------------------------------------- #
def test_the_frame_binds_version_domain_adapter_and_policy_type():
    raw = framed_body_bytes(adapter_id="a", policy_type="T", projection={"x": 1}).decode()
    for required in (CANONICALIZATION_VERSION, POLICY_BODY_DIGEST_DOMAIN, '"adapter":"a"', '"policy_type":"T"'):
        assert required in raw, required


def test_two_families_with_identical_shapes_do_not_collide():
    a = make_policy(PolicyFamily.GEOGRAPHY)
    b = make_policy(PolicyFamily.DOMAIN)
    assert digest_of(a) != digest_of(b)


def test_a_different_adapter_id_changes_the_digest():
    projection = ADAPTER.describe(make_policy()).canonical_projection
    one = framed_body_digest(adapter_id="a", policy_type="T", projection=projection)
    two = framed_body_digest(adapter_id="b", policy_type="T", projection=projection)
    assert one != two


# --------------------------------------------------------------------------- #
# Determinism and normalization
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_equal_normalized_policies_produce_equal_bytes_and_digest(family):
    a, b = make_policy(family), make_policy(family)
    assert a == b
    assert digest_of(a) == digest_of(b)


def test_digest_is_deterministic_across_repeated_computation():
    policy = make_policy(PolicyFamily.READINESS)
    assert len({digest_of(policy) for _ in range(25)}) == 1


def test_meaningful_content_change_changes_the_digest():
    a = make_policy(PolicyFamily.DOMAIN)
    b = make_policy(PolicyFamily.DOMAIN, overrides={"governed_outcome_unit": "closed_case"})
    assert a.metadata.content_digest != b.metadata.content_digest


def test_list_and_tuple_inputs_normalize_identically():
    gate = PolicyGate(
        gate_id="g1",
        category=GateCategory.QUALITY,
        requirement_class=RequirementClass.CONDITIONAL,
        applicability=[ReadinessTarget.PILOT],
    )
    as_list = make_policy(PolicyFamily.READINESS, overrides={"gates": [gate]})
    as_tuple = make_policy(PolicyFamily.READINESS, overrides={"gates": (gate,)})
    assert isinstance(as_list.gates, tuple)
    assert digest_of(as_list) == digest_of(as_tuple)


def test_mutating_a_caller_owned_list_after_construction_changes_nothing():
    gates = [
        PolicyGate(
            gate_id="g1",
            category=GateCategory.QUALITY,
            requirement_class=RequirementClass.ADVISORY,
            applicability=(ReadinessTarget.PILOT,),
        )
    ]
    policy = make_policy(PolicyFamily.READINESS, overrides={"gates": gates})
    before = digest_of(policy)
    gates.clear()
    gates.append("not even a gate")
    assert digest_of(policy) == before


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
def test_every_metadata_identity_field_is_bound(field, value):
    policy = make_policy(PolicyFamily.DOMAIN)
    changed = replace(policy, metadata=replace(policy.metadata, **{field: value}))
    assert digest_of(changed) != digest_of(policy)


def test_scope_and_tenant_changes_alter_the_digest():
    glob = make_policy(PolicyFamily.DOMAIN)
    a = make_policy(PolicyFamily.DOMAIN, scope=PolicyScope.TENANT, tenant_id="t-1")
    b = make_policy(PolicyFamily.DOMAIN, scope=PolicyScope.TENANT, tenant_id="t-2")
    assert len({p.metadata.content_digest for p in (glob, a, b)}) == 3


# --------------------------------------------------------------------------- #
# Datetimes
# --------------------------------------------------------------------------- #
def test_equal_instants_in_different_timezones_digest_identically():
    tz = timezone(timedelta(hours=5, minutes=30))
    utc = make_policy(PolicyFamily.DOMAIN, effective_from=T_FROM)
    other = make_policy(PolicyFamily.DOMAIN, effective_from=T_FROM.astimezone(tz))
    assert T_FROM.astimezone(tz) == T_FROM
    assert utc.metadata.content_digest == other.metadata.content_digest


def test_a_naive_datetime_is_rejected_by_the_canonicalization_helper_directly():
    """Not merely discouraged at the service layer — refused at the helper."""

    naive = datetime(2026, 6, 1)
    with pytest.raises(PolicyCanonicalizationError, match="naive datetime"):
        to_canonical_obj(naive)
    with pytest.raises(PolicyCanonicalizationError, match="naive datetime"):
        canonical_bytes({"when": naive})
    with pytest.raises(PolicyCanonicalizationError, match="naive datetime"):
        require_tzaware(naive)
    with pytest.raises(PolicyCanonicalizationError):
        framed_body_digest(adapter_id="a", policy_type="T", projection={"when": naive})


def test_a_naive_datetime_nested_deep_inside_a_structure_is_rejected():
    naive = datetime(2026, 6, 1)
    with pytest.raises(PolicyCanonicalizationError, match=r"\$\.a\[1\]\.b"):
        canonical_bytes({"a": [1, {"b": naive}]})


# --------------------------------------------------------------------------- #
# Unicode posture (a): NFC required, NFD rejected — recursively
# --------------------------------------------------------------------------- #
NFC = "café"
NFD = unicodedata.normalize("NFD", NFC)


def test_the_two_spellings_really_are_different_strings():
    assert NFC != NFD
    assert unicodedata.normalize("NFC", NFD) == NFC


def test_nfc_is_accepted_and_nfd_is_rejected():
    assert require_nfc(NFC) == NFC
    assert canonical_bytes({"j": NFC})
    with pytest.raises(PolicyCanonicalizationError, match="NFC"):
        require_nfc(NFD)
    with pytest.raises(PolicyCanonicalizationError, match="NFC"):
        canonical_bytes({"j": NFD})


@pytest.mark.parametrize(
    "payload,marker",
    [
        ({"j": NFD}, "$.j"),
        ({"a": [NFD]}, "$.a[0]"),
        ({"a": {"b": {"c": NFD}}}, "$.a.b.c"),
        ({"a": [{"b": [NFD]}]}, "$.a[0].b[0]"),
        ({NFD: "v"}, "$."),
    ],
)
def test_nfd_is_rejected_recursively_including_mapping_keys(payload, marker):
    with pytest.raises(PolicyCanonicalizationError) as exc:
        canonical_bytes(payload)
    assert "NFC" in str(exc.value)
    assert marker in str(exc.value)


def test_an_nfd_policy_field_is_rejected_rather_than_silently_folded():
    policy = make_policy(PolicyFamily.DOMAIN, overrides={"governed_outcome_unit": NFC})
    nfd_policy = replace(policy, governed_outcome_unit=NFD)
    with pytest.raises(PolicyCanonicalizationError, match="NFC"):
        digest_of(nfd_policy)
    # The two spellings therefore never collapse onto one digest.
    assert digest_of(policy)


# --------------------------------------------------------------------------- #
# Type rejection
# --------------------------------------------------------------------------- #
def test_float_is_rejected():
    with pytest.raises(PolicyCanonicalizationError, match="float"):
        canonical_bytes({"x": 1.5})


def test_an_unsupported_type_is_rejected():
    with pytest.raises(PolicyCanonicalizationError, match="not canonicalizable"):
        canonical_bytes({"x": object()})


def test_a_non_string_mapping_key_is_rejected():
    with pytest.raises(PolicyCanonicalizationError, match="mapping keys must be strings"):
        canonical_bytes({1: "x"})


# --------------------------------------------------------------------------- #
# Signature independence and declared-digest enforcement
# --------------------------------------------------------------------------- #
def test_a_policy_artifact_has_no_signature_field():
    import dataclasses

    for family in ALL_FAMILIES:
        policy = make_policy(family)
        names = {f.name for f in dataclasses.fields(policy)} | {
            f.name for f in dataclasses.fields(policy.metadata)
        }
        assert not {n for n in names if "signature" in n or "signed" in n}


def test_the_issuance_signature_does_not_change_the_body_digest():
    policy = make_policy(PolicyFamily.DOMAIN)
    before = digest_of(policy)
    record = make_authority().issue(policy)
    assert record.signature
    assert digest_of(record.policy) == before


def test_an_arbitrary_well_formed_digest_is_refused_before_anything_happens():
    policy = make_policy(PolicyFamily.DOMAIN)
    forged = replace(policy, metadata=replace(policy.metadata, content_digest=ARBITRARY_DIGEST))
    assert len(ARBITRARY_DIGEST) == 64
    authority = make_authority()
    with pytest.raises(PolicyDigestMismatchError):
        authority.issue(forged)
    assert authority.approval.calls == []


def test_body_mutation_after_reference_creation_is_detected():
    original = make_policy(PolicyFamily.DOMAIN)
    reference = original.reference
    mutated = replace(original, governed_outcome_unit="something else entirely")
    assert mutated.metadata.content_digest == reference.content_digest
    assert digest_of(mutated) != reference.content_digest
    with pytest.raises(PolicyDigestMismatchError):
        make_authority().issue(mutated)


# --------------------------------------------------------------------------- #
# Independent verification
# --------------------------------------------------------------------------- #
def test_a_third_party_can_recompute_the_digest_from_public_functions_only():
    policy = make_policy(PolicyFamily.INTENDED_OUTCOME)
    descriptor = UviPolicyFamilyAdapter().describe(policy)

    expected = hashlib.sha256(
        json.dumps(
            {
                "adapter": descriptor.adapter_id,
                "body": descriptor.canonical_projection,
                "canonicalization": CANONICALIZATION_VERSION,
                "domain": POLICY_BODY_DIGEST_DOMAIN,
                "policy_type": descriptor.policy_type,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    assert descriptor.body_digest() == expected == policy.metadata.content_digest
    assert sha256_hex(
        framed_body_bytes(
            adapter_id=descriptor.adapter_id,
            policy_type=descriptor.policy_type,
            projection=descriptor.canonical_projection,
        )
    ) == expected


def test_the_digest_output_shape_matches_the_contract_digest_format():
    digest = digest_of(make_policy(PolicyFamily.VALUATION))
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    PolicyArtifactMetadata(
        policy_id="p", policy_family=PolicyFamily.VALUATION, version="1", content_digest=digest
    )
