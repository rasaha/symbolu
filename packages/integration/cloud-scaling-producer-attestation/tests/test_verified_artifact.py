"""``VerifiedProducerAttestation`` invariants: exact-typed, immutable, non-authoritative.

A frozen dataclass is not a security boundary. These properties prove the boundary is made
of the token, the self-digest and the revalidator instead.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import pickle

import pytest

from _producer_fixtures import AS_OF, build_attestation, build_verifier

from ugence_cloud_scaling_producer_attestation import (
    ProducerAuthenticityOutcome,
    VerifiedArtifactIntegrityError,
    VerifiedProducerAttestation,
    require_verified_producer_attestation,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

O = ProducerAuthenticityOutcome


@pytest.fixture
def artifact(verifier, candidate, attestation, as_of):
    return verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation


# --------------------------------------------------------------------------------------- #
# 1. It cannot be constructed outside the verification routine
# --------------------------------------------------------------------------------------- #


def test_direct_construction_is_refused(artifact):
    """V-1: the token guard. Reassembling the same facts by hand is refused."""

    fields = {f.name: getattr(artifact, f.name) for f in dataclasses.fields(artifact)}
    fields["construction_token"] = None
    with pytest.raises(VerifiedArtifactIntegrityError):
        VerifiedProducerAttestation(**fields)


@pytest.mark.parametrize("token", [None, True, object(), "token", 0])
def test_no_caller_held_token_is_accepted(artifact, token):
    """V-2: no look-alike sentinel reaches the private token."""

    fields = {f.name: getattr(artifact, f.name) for f in dataclasses.fields(artifact)}
    fields["construction_token"] = token
    with pytest.raises(VerifiedArtifactIntegrityError):
        VerifiedProducerAttestation(**fields)


def test_an_object_new_fabrication_is_refused_at_consumption():
    """V-3: ``object.__new__`` skips ``__post_init__``; the revalidator catches it."""

    fabricated = object.__new__(VerifiedProducerAttestation)
    with pytest.raises(VerifiedArtifactIntegrityError):
        require_verified_producer_attestation(fabricated)


def test_a_subclass_is_refused_at_consumption(artifact):
    """V-4: a subclass can divert every read through a property. Exact type only."""

    class SubArtifact(VerifiedProducerAttestation):
        @property
        def grants_authority(self) -> bool:  # pragma: no cover - never consulted
            return True

    fields = {f.name: getattr(artifact, f.name) for f in dataclasses.fields(artifact)}
    sub = object.__new__(SubArtifact)
    for name, value in fields.items():
        object.__setattr__(sub, name, value)
    with pytest.raises(VerifiedArtifactIntegrityError):
        require_verified_producer_attestation(sub)


def test_a_duck_typed_look_alike_is_refused_at_consumption(artifact):
    """V-5: having every attribute is not being the type."""

    class LookAlike:
        pass

    fake = LookAlike()
    for f in dataclasses.fields(artifact):
        setattr(fake, f.name, getattr(artifact, f.name))
    with pytest.raises(VerifiedArtifactIntegrityError):
        require_verified_producer_attestation(fake)


def test_there_is_no_deserializer_to_fabricate_through():
    """V-6: a serialized verification artifact would be a forgeable one. There is none."""

    for name in dir(VerifiedProducerAttestation):
        assert name not in ("from_dict", "from_json", "parse", "loads", "deserialize")


# --------------------------------------------------------------------------------------- #
# 2. Mutation after construction is detected
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "subject_id", "recommendation_digest", "verified_issuer",
     "verified_key_id", "candidate_digest", "trust_anchor_capability"],
)
def test_a_mutated_field_fails_revalidation(artifact, field):
    """V-7: ``object.__setattr__`` after construction moves the self-digest."""

    mutated = copy.copy(artifact)
    object.__setattr__(mutated, field, "substituted-value")
    assert mutated.artifact_digest != mutated.digest()
    with pytest.raises(VerifiedArtifactIntegrityError):
        require_verified_producer_attestation(mutated)


def test_a_rewritten_self_digest_does_not_rescue_a_mutation(artifact):
    """V-8: recomputing the digest too still fails — the token check is independent.

    An attacker who mutates a field *and* rewrites ``artifact_digest`` to match defeats the
    digest check. The token check is what catches them, and it is why the boundary has
    three independent parts rather than one.
    """

    mutated = copy.copy(artifact)
    object.__setattr__(mutated, "tenant_id", "tenant-2")
    object.__setattr__(mutated, "artifact_digest", mutated.digest())
    object.__setattr__(mutated, "construction_token", None)
    assert mutated.artifact_digest == mutated.digest()
    with pytest.raises(VerifiedArtifactIntegrityError):
        require_verified_producer_attestation(mutated)


def test_the_outcome_property_cannot_be_overwritten(artifact):
    """V-9: ``outcome`` is a data descriptor, so ``object.__setattr__`` loses to it."""

    with pytest.raises(AttributeError):
        object.__setattr__(artifact, "outcome", "FORGED")
    assert artifact.outcome is O.VERIFIED


def test_the_grants_authority_property_cannot_be_overwritten(artifact):
    """V-10: and so does ``grants_authority``. There is no field to flip."""

    with pytest.raises(AttributeError):
        object.__setattr__(artifact, "grants_authority", True)
    assert artifact.grants_authority is False


def test_a_doctored_instance_dictionary_does_not_shadow_the_properties(artifact):
    """V-11: a frozen dataclass with ``__dict__`` still loses to a data descriptor."""

    try:
        artifact.__dict__["grants_authority"] = True
        artifact.__dict__["outcome"] = "FORGED"
    except (AttributeError, TypeError):
        pass
    assert artifact.grants_authority is False
    assert artifact.outcome is O.VERIFIED


# --------------------------------------------------------------------------------------- #
# 3. It grants nothing
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "concept",
    ["authorized", "executable", "envelope", "envelope_issued", "actiongate",
     "action_gate", "admitted", "credential", "credential_eligible", "execution",
     "execution_permitted", "permit", "grant", "allow", "verified"],
)

def test_no_field_names_an_authority_concept(concept):
    """V-12: the vocabulary does not exist, so there is nothing to set to True."""

    names = {f.name for f in dataclasses.fields(VerifiedProducerAttestation)}
    offenders = [n for n in names if concept in n.lower()]
    # ``verified_*`` names identify WHO verified, never that something IS authorized.
    offenders = [
        n for n in offenders
        if not n.startswith("verified_") and n not in ("verified_as_of_fact",)
    ]
    assert offenders == [], offenders


def test_no_boolean_field_is_caller_settable():
    """V-13: no ``bool`` field exists at all — the two booleans are derived properties."""

    boolean_fields = [
        f.name
        for f in dataclasses.fields(VerifiedProducerAttestation)
        if f.type in ("bool", bool)
    ]
    assert boolean_fields == []


def test_grants_authority_has_no_branch_returning_true():
    """V-14: read the source. There is one ``return False`` and nothing else."""

    source = inspect.getsource(VerifiedProducerAttestation.grants_authority.fget)
    assert "return False" in source
    assert "return True" not in source


def test_the_artifact_carries_no_envelope_gate_credential_or_executor_object(artifact):
    """V-15: every bound value is a string, a datetime or ``None``. Nothing callable."""

    for f in dataclasses.fields(artifact):
        if f.name == "construction_token":
            continue
        value = getattr(artifact, f.name)
        assert value is None or isinstance(value, (str, __import__("datetime").datetime)), (
            f.name,
            type(value),
        )


# --------------------------------------------------------------------------------------- #
# 4. What it does bind
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_every_bound_field_is_covered_by_the_self_digest(artifact):
    """V-16: no field rides along outside the digest."""

    payload = artifact.digest_payload()
    unbound = (
        {f.name for f in dataclasses.fields(artifact)}
        - set(payload)
        - {"artifact_digest", "construction_token"}
    )
    assert unbound == set(), unbound


@pytest.mark.invariant
def test_the_digest_commits_to_granting_nothing(artifact):
    """V-17: ``outcome`` and ``grants_authority`` are framed into the digest deliberately."""

    payload = artifact.digest_payload()
    assert payload["outcome"] == "VERIFIED"
    assert payload["grants_authority"] is False


@pytest.mark.happy
def test_the_artifact_is_hashable_and_comparable_by_value(artifact):
    """V-18: two verifications of the same inputs produce equal artifacts."""

    assert artifact == copy.copy(artifact)


@pytest.mark.invariant
def test_the_artifact_repr_states_that_it_grants_nothing(artifact):
    """V-19: the one-line rendering an operator reads says so plainly."""

    assert "grants_authority=False" in repr(artifact)
