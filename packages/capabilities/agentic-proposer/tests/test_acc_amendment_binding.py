"""The `OD-C1=B` amendment's behavioural surface (`ACC-AM-1`..`ACC-AM-5`).

The structural half — field sets, classifications, cardinalities, required-ness,
the G2 mirror — is carried by the existing pinned guards, which this change set
updated in place. This module proves the **behaviour** the round ratified: the
role bears the reference; the pair is stamped from the injected resolution and
never accepted from a caller; the signed-reference equality is checked before
any stamped value is used; the pair is identity-participating; and every refusal
stays inside H2's existing five classes.
"""

from __future__ import annotations

import pytest
import pydantic
import s1_specification_mirror as spec
import ugence_agentic_proposer as ap
from test_s2b_strategy_permission import _builder_kwargs, _world


@pytest.fixture(scope="module")
def world():
    return _world()


# --------------------------------------------------------------------------- #
# `ACC-AM-1` — the role bears the reference, required and C5a
# --------------------------------------------------------------------------- #


def test_the_role_requires_a_constitution_reference(world):
    fields = {name: getattr(world["role"], name)
              for name in type(world["role"]).model_fields}
    assert fields.pop("constitution_ref") == spec.CONSTITUTION_REF
    with pytest.raises(pydantic.ValidationError):
        type(world["role"])(**fields)


def test_the_role_reference_is_an_identifier_not_a_token(world):
    """C5a admits ``/``; a C5b-typed field would refuse the reference shape the
    constitution family actually mints."""

    assert "/" in spec.CONSTITUTION_REF
    role = type(world["role"])(
        **{**{name: getattr(world["role"], name)
              for name in type(world["role"]).model_fields},
           "constitution_ref": "ugence.agent-constitution/other/v2"})
    assert role.constitution_ref == "ugence.agent-constitution/other/v2"


# --------------------------------------------------------------------------- #
# `ACC-AM-2` — stamped from the injected resolution, never from a caller
# --------------------------------------------------------------------------- #


def test_the_pair_is_stamped_from_the_injected_resolution(world):
    advisory = ap.build_proposer_advisory(**_builder_kwargs(
        world, constitution_resolution=spec.StubConstitutionResolution()))
    assert advisory.constitution_policy_id == spec.CONSTITUTION_POLICY_ID
    assert advisory.constitution_policy_version == spec.CONSTITUTION_POLICY_VERSION


def test_a_diverted_identity_is_what_gets_stamped_proving_the_source(world):
    """Vary the resolution and the stamp moves with it: the value provably comes
    from the injected resolution, not from any fixture default."""

    advisory = ap.build_proposer_advisory(**_builder_kwargs(
        world, constitution_resolution=spec.StubConstitutionResolution(
            policy_id="agent-constitution-other", policy_version="2.0.0")))
    assert advisory.constitution_policy_id == "agent-constitution-other"
    assert advisory.constitution_policy_version == "2.0.0"


def test_a_mismatched_signed_reference_refuses_construction(world):
    """The ratified consumer: the resolution's signed ``agent_constitution_ref``
    must equal the role's ``constitution_ref`` exactly, before any value is used."""

    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(**_builder_kwargs(
            world, constitution_resolution=spec.StubConstitutionResolution(
                signed_ref="ugence.agent-constitution/tenant-1/other/v1")))


def test_a_resolution_missing_the_read_shape_refuses_inside_h2(world):
    """`S2B-PF-G=B`'s boundary discipline: an alien object is refused as
    ``CrossContractViolationError`` here, never escaping as ``AttributeError``."""

    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(**_builder_kwargs(
            world, constitution_resolution=object()))


def test_a_non_string_identity_in_the_resolution_is_refused(world):
    class _Alien(spec.StubConstitutionResolution):
        def __init__(self):
            super().__init__()
            self.metadata.policy_id = 7

    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(**_builder_kwargs(
            world, constitution_resolution=_Alien()))


def test_the_refusal_happens_before_the_evaluation_sequence(world):
    """`S2B-S1-Q12=A`'s order, extended on its own rationale: a mis-bound
    constitution never reaches the injected domain evaluator."""

    log = []
    provider = spec.StubDomainEvaluationProvider(log=log)
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(**_builder_kwargs(
            world, provider=provider,
            constitution_resolution=spec.StubConstitutionResolution(
                signed_ref="ugence.agent-constitution/tenant-1/other/v1")))
    assert "provider" not in log, (
        "the domain evaluator was reached before the constitution binding refused")


# --------------------------------------------------------------------------- #
# Identity participation — the pair is inside P_unsigned
# --------------------------------------------------------------------------- #


def test_the_stamped_pair_moves_the_advisory_identity(world):
    baseline = ap.build_proposer_advisory(**_builder_kwargs(
        world, constitution_resolution=spec.StubConstitutionResolution()))
    role_fields = {name: getattr(world["role"], name)
                   for name in type(world["role"]).model_fields}
    other_role = type(world["role"])(
        **{**role_fields,
           "constitution_ref": "ugence.agent-constitution/tenant-1/next/v2"})
    varied = ap.build_proposer_advisory(**_builder_kwargs(
        world, role=other_role,
        constitution_resolution=spec.StubConstitutionResolution(
            signed_ref="ugence.agent-constitution/tenant-1/next/v2",
            policy_version="2.0.0")))
    assert varied.constitution_policy_version != (
        baseline.constitution_policy_version)
    assert varied.advisory_digest != baseline.advisory_digest


def test_the_stamped_pair_survives_identity_replay(world):
    advisory = ap.build_proposer_advisory(**_builder_kwargs(
        world, constitution_resolution=spec.StubConstitutionResolution()))
    assert ap.verify_advisory_identity(advisory=advisory) is True

    tampered = advisory.model_copy(
        update={"constitution_policy_version": "99.0.0"})
    assert ap.verify_advisory_identity(advisory=tampered) is False


def test_advisory_version_stays_at_one(world):
    """`ACC-AM-3`: the field addition moves digests, not the version literal."""

    advisory = ap.build_proposer_advisory(**_builder_kwargs(
        world, constitution_resolution=spec.StubConstitutionResolution()))
    assert advisory.advisory_version == "1"


# --------------------------------------------------------------------------- #
# The revision path carries the same binding
# --------------------------------------------------------------------------- #


def test_a_revision_stamps_from_its_own_injected_resolution(world):
    revision = ap.build_advisory_revision(
        parent=world["advisory"], candidate_set=world["candidate_set"],
        identity=world["identity"], role=world["role"], mandate=world["mandate"],
        context=world["context"], observations=[world["observation"]],
        claim_summaries=[], observation_refs=[], uncertainties=[],
        created_at=world["advisory"].created_at,
        expires_at=world["advisory"].expires_at,
        provider=world["provider"], expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref="role-approver",
        strategy_policy_resolver=world["resolver"],
        declared_strategy=ap.ReasoningStrategy.REVISED_ADVISORY,
        constitution_resolution=spec.StubConstitutionResolution(
            policy_version="1.1.0"))
    assert revision.constitution_policy_version == "1.1.0"
    assert ap.verify_advisory_identity(advisory=revision) is True
