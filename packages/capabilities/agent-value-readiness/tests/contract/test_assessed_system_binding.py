"""Adversarial tests for the M-3R.3 ``AssessedSystemBinding``.

The binding exists to make one attack mechanically detectable: reusing a
favourable result produced for system version A under system version B, another
configuration, another tenant, another subject, or another policy context.

These tests therefore hammer the digest boundary — every coordinate must move it
— and hammer the honesty boundary: a structurally perfect binding a caller
fabricated must still report that its authenticity was never established.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import datetime, timezone

import pytest

from ugence_agent_value_readiness.api import (
    AssessedSystemBinding,
    ReadinessContractError,
    SystemBindingAuthenticityStatus,
)

CTX_DIGEST = hashlib.sha256(b"context-a").hexdigest()
CTX_DIGEST_B = hashlib.sha256(b"context-b").hexdigest()
CFG_DIGEST = hashlib.sha256(b"configuration-a").hexdigest()
CFG_DIGEST_B = hashlib.sha256(b"configuration-b").hexdigest()
MANIFEST_DIGEST = hashlib.sha256(b"manifest-a").hexdigest()

T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
NAIVE = datetime(2026, 6, 1)


def binding(**kw) -> AssessedSystemBinding:
    base = dict(
        binding_id="bind-1",
        tenant_id="t1",
        subject_id="a1",
        context_id="ctx1",
        context_digest=CTX_DIGEST,
        system_id="sys-1",
        system_version="1.4.2",
        configuration_id="cfg-a",
        configuration_digest=CFG_DIGEST,
    )
    base.update(kw)
    return AssessedSystemBinding(**base)


# --------------------------------------------------------------------------- #
# Required identity
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "field",
    [
        "binding_id",
        "tenant_id",
        "subject_id",
        "context_id",
        "system_id",
        "system_version",
        "configuration_id",
    ],
)
@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_no_identity_coordinate_may_be_blank(field, blank):
    with pytest.raises(ReadinessContractError):
        binding(**{field: blank})


@pytest.mark.parametrize(
    "field",
    ["binding_id", "tenant_id", "system_id", "system_version", "configuration_id"],
)
@pytest.mark.parametrize("substitute", [None, 7, b"x", ["x"], {"x": 1}])
def test_non_string_identity_coordinates_are_rejected(field, substitute):
    with pytest.raises(ReadinessContractError):
        binding(**{field: substitute})


@pytest.mark.parametrize("field", ["context_digest", "configuration_digest"])
@pytest.mark.parametrize(
    "bad", ["", "not-a-digest", CTX_DIGEST.upper(), CTX_DIGEST[:-1], CTX_DIGEST + "a", None, 7]
)
def test_a_required_digest_must_be_lowercase_sha256_hex(field, bad):
    with pytest.raises(ReadinessContractError):
        binding(**{field: bad})


def test_identity_is_whitespace_normalized():
    assert binding(system_id="  sys-1  ").system_id == "sys-1"
    assert binding(system_id="  sys-1  ") == binding(system_id="sys-1")
    assert (
        binding(system_id="  sys-1  ").canonical_digest()
        == binding(system_id="sys-1").canonical_digest()
    )


# --------------------------------------------------------------------------- #
# Deferred references: opaque, co-required, never minted here
# --------------------------------------------------------------------------- #
def test_a_manifest_reference_and_its_digest_are_co_required():
    with pytest.raises(ReadinessContractError):
        binding(system_manifest_ref="manifest-1")
    with pytest.raises(ReadinessContractError):
        binding(system_manifest_digest=MANIFEST_DIGEST)

    both = binding(system_manifest_ref="manifest-1", system_manifest_digest=MANIFEST_DIGEST)
    assert both.system_manifest_ref == "manifest-1"

    neither = binding()
    assert neither.system_manifest_ref == "" and neither.system_manifest_digest == ""


def test_the_deferred_references_are_opaque_tokens_with_no_invented_semantics():
    """No ``SystemManifest`` type and no environment enum is minted here."""

    b = binding(
        canonical_subject_context_ref="risk-subject-context-1:abc",
        deployment_environment_ref="staging-eu",
    )
    assert b.canonical_subject_context_ref == "risk-subject-context-1:abc"
    assert b.deployment_environment_ref == "staging-eu"
    # They are plain strings — the binding neither resolves nor validates them.
    assert isinstance(b.canonical_subject_context_ref, str)
    assert isinstance(b.deployment_environment_ref, str)


# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field", ["effective_from", "effective_to"])
def test_a_naive_timestamp_is_rejected(field):
    with pytest.raises(ReadinessContractError):
        binding(**{field: NAIVE})


def test_the_effective_period_is_half_open():
    b = binding(effective_from=T_FROM, effective_to=T_TO)
    assert b.is_effective_at(T_FROM) is True
    assert b.is_effective_at(T_MID) is True
    # Closed on the left, OPEN on the right.
    assert b.is_effective_at(T_TO) is False


def test_an_inverted_or_empty_effective_period_is_rejected():
    with pytest.raises(ReadinessContractError):
        binding(effective_from=T_TO, effective_to=T_FROM)
    with pytest.raises(ReadinessContractError):
        binding(effective_from=T_FROM, effective_to=T_FROM)


def test_an_absent_bound_is_open_on_that_side():
    assert binding().is_effective_at(T_MID) is True
    assert binding(effective_from=T_FROM).is_effective_at(T_TO) is True
    assert binding(effective_to=T_TO).is_effective_at(T_FROM) is True


def test_is_effective_at_requires_an_explicit_timezone_aware_instant():
    with pytest.raises(ReadinessContractError):
        binding().is_effective_at(NAIVE)


# --------------------------------------------------------------------------- #
# Digest: the complete identity participates
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kw",
    [
        {"binding_id": "bind-2"},
        {"tenant_id": "t2"},
        {"subject_id": "a2"},
        {"context_id": "ctx2"},
        {"context_digest": CTX_DIGEST_B},
        {"system_id": "sys-2"},
        {"system_version": "1.4.3"},
        {"configuration_id": "cfg-b"},
        {"configuration_digest": CFG_DIGEST_B},
        {"canonical_subject_context_ref": "other"},
        {"system_manifest_ref": "m", "system_manifest_digest": MANIFEST_DIGEST},
        {"deployment_environment_ref": "prod-us"},
        {"effective_from": T_FROM},
        {"effective_to": T_TO},
    ],
)
def test_every_coordinate_moves_the_canonical_digest(kw):
    assert binding().canonical_digest() != binding(**kw).canonical_digest()


def test_two_system_versions_can_never_share_a_binding_digest():
    a = binding(system_version="1.4.2")
    b = binding(system_version="1.4.3")
    assert a.canonical_digest() != b.canonical_digest()


def test_two_configurations_of_one_system_can_never_share_a_binding_digest():
    a = binding(configuration_id="cfg-a", configuration_digest=CFG_DIGEST)
    b = binding(configuration_id="cfg-b", configuration_digest=CFG_DIGEST_B)
    assert a.system_id == b.system_id
    assert a.canonical_digest() != b.canonical_digest()
    assert a.system_configuration_identity != b.system_configuration_identity


def test_equal_bindings_produce_equal_digests():
    assert binding() == binding()
    assert binding().canonical_digest() == binding().canonical_digest()


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "field, value",
    [
        ("system_version", "9.9.9"),
        ("tenant_id", "t2"),
        ("configuration_digest", CFG_DIGEST_B),
        ("effective_to", T_TO),
    ],
)
def test_the_binding_is_frozen(field, value):
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(binding(), field, value)


def test_the_binding_holds_no_caller_owned_collection_to_mutate():
    """Every field is a scalar, so there is no aliasing surface at all."""

    for field in dataclasses.fields(AssessedSystemBinding):
        value = getattr(binding(), field.name)
        assert value is None or isinstance(value, (str, datetime)), field.name


# --------------------------------------------------------------------------- #
# Honesty: construction proves nothing
# --------------------------------------------------------------------------- #
def test_authenticity_is_permanently_structural_and_is_not_a_field():
    b = binding()
    assert b.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    assert b.authenticity_verified is False

    field_names = {f.name for f in dataclasses.fields(AssessedSystemBinding)}
    assert "authenticity_status" not in field_names
    assert "authenticity_verified" not in field_names

    with pytest.raises(TypeError):
        AssessedSystemBinding(
            binding_id="b",
            tenant_id="t1",
            subject_id="a1",
            context_id="ctx1",
            context_digest=CTX_DIGEST,
            system_id="s",
            system_version="1",
            configuration_id="c",
            configuration_digest=CFG_DIGEST,
            authenticity_status="AUTHORITY_VERIFIED",
        )


def test_the_authenticity_enum_admits_no_verified_value():
    assert [m.value for m in SystemBindingAuthenticityStatus] == ["STRUCTURAL_UNVERIFIED"]
    with pytest.raises(ValueError):
        SystemBindingAuthenticityStatus("AUTHORITY_VERIFIED")


def test_a_property_cannot_be_overridden_on_an_instance():
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        setattr(binding(), "authenticity_verified", True)


def test_a_fully_self_consistent_fabricated_binding_is_still_only_structural():
    """The exact boundary, stated as a test.

    A caller who computes every digest correctly produces a binding that passes
    every check here. That is the intended behaviour: this contract detects
    inconsistency, not fabrication. Proving the described system was really
    deployed requires a ratified verifier that does not exist.
    """

    fabricated = binding(
        system_id="a-system-that-was-never-deployed",
        configuration_digest=hashlib.sha256(b"invented bytes").hexdigest(),
    )
    assert fabricated.canonical_digest()
    assert fabricated.authenticity_verified is False
    assert (
        fabricated.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    )
