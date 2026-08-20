"""The verified artifact is a boundary, not a shape. Every fabrication route is closed here.

A frozen dataclass stops accidental mutation and stops nothing deliberate. These tests walk
each deliberate route and require a refusal: direct construction, ``object.__new__``
fabrication, a borrowed construction token, post-construction mutation, a subclass, a
duck-typed look-alike, and a cross-process copy.
"""

from __future__ import annotations

import copy
import pickle

import pytest

from _policy_fixtures import T_MID, issued, verifier_for
from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityResult,
    VerifiedPolicyArtifactIntegrityError,
    VerifiedPolicyAuthenticity,
    require_verified_policy_authenticity,
)


def _genuine():
    authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy


@pytest.mark.adversarial
def test_direct_construction_is_refused():
    genuine = _genuine()
    fields = {
        name: getattr(genuine, name)
        for name in genuine.digest_payload()
        if name not in ("outcome", "grants_authority", "historical")
    }
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        VerifiedPolicyAuthenticity(**fields, artifact_digest=genuine.artifact_digest)


@pytest.mark.adversarial
def test_an_object_new_fabrication_is_refused_at_the_consumption_boundary():
    fabricated = object.__new__(VerifiedPolicyAuthenticity)
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(fabricated)


@pytest.mark.adversarial
def test_a_borrowed_construction_token_does_not_mint_a_second_determination():
    """Possession of a genuine artifact is not authority to mint another one."""

    genuine = _genuine()
    token = genuine.construction_token  # readable off any genuine artifact
    fields = {
        name: getattr(genuine, name)
        for name in genuine.digest_payload()
        if name not in ("outcome", "grants_authority", "historical")
    }
    fields["record_id"] = "a-determination-this-process-never-reached"
    forged = VerifiedPolicyAuthenticity(
        **fields,
        artifact_digest=_recompute(fields),
        construction_token=token,
    )
    # It constructs — the token and the self-digest both check out — and it is still refused,
    # because the provenance registry never recorded this determination.
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(forged)


def _recompute(fields: dict) -> str:
    from ugence_cloud_scaling_policy_authenticity import (
        POLICY_AUTHENTICITY_DIGEST_DOMAIN,
        framed_digest,
    )

    payload = dict(fields)
    payload.update({"outcome": "VERIFIED", "grants_authority": False, "historical": False})
    return framed_digest(domain=POLICY_AUTHENTICITY_DIGEST_DOMAIN, body=payload)


@pytest.mark.adversarial
def test_mutation_after_construction_is_caught_by_the_self_digest():
    genuine = _genuine()
    object.__setattr__(genuine, "policy_tenant_id", "some-other-tenant")
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(genuine)


@pytest.mark.adversarial
def test_a_subclass_is_refused_not_adapted():
    class Sneaky(VerifiedPolicyAuthenticity):
        @property
        def grants_authority(self) -> bool:  # the whole point of subclassing
            return True

    genuine = _genuine()
    fabricated = object.__new__(Sneaky)
    for name, value in vars(genuine).items():
        object.__setattr__(fabricated, name, value)
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(fabricated)


@pytest.mark.adversarial
def test_a_duck_typed_look_alike_is_refused():
    class LookAlike:
        grants_authority = True

        def __getattr__(self, name):
            return "whatever you asked for"

    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(LookAlike())


@pytest.mark.happy
def test_a_faithful_in_process_copy_still_revalidates():
    genuine = _genuine()
    assert require_verified_policy_authenticity(copy.copy(genuine)) is not None


@pytest.mark.adversarial
def test_an_artifact_that_crossed_a_process_boundary_is_refused():
    """``deepcopy`` and ``pickle`` rebuild the token sentinel, so the copy is not this
    process's determination. Failing here is the correct direction: re-verify, do not ship."""

    genuine = _genuine()
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(copy.deepcopy(genuine))
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(pickle.loads(pickle.dumps(genuine)))


@pytest.mark.adversarial
def test_a_result_cannot_be_assembled_around_a_fabricated_artifact():
    fabricated = object.__new__(VerifiedPolicyAuthenticity)
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        PolicyAuthenticityResult(verified_policy=fabricated)


@pytest.mark.adversarial
def test_a_result_must_carry_exactly_one_branch():
    from ugence_cloud_scaling_policy_authenticity import (
        PolicyAuthenticityOutcome,
        PolicyAuthenticityRefusal,
    )

    with pytest.raises(ValueError):
        PolicyAuthenticityResult()
    with pytest.raises(ValueError):
        PolicyAuthenticityRefusal(outcome=PolicyAuthenticityOutcome.VERIFIED)


@pytest.mark.invariant
def test_there_is_no_deserializer_on_the_public_surface():
    import ugence_cloud_scaling_policy_authenticity as pkg

    for forbidden in ("from_dict", "from_json", "loads", "deserialize", "parse"):
        assert not hasattr(VerifiedPolicyAuthenticity, forbidden)
        assert forbidden not in pkg.__all__
