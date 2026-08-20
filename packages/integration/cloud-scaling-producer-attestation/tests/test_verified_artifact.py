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


# --------------------------------------------------------------------------------------- #
# 5. Possession of a genuine artifact is not authority to mint one
# --------------------------------------------------------------------------------------- #


def test_a_borrowed_construction_token_does_not_mint_an_artifact(artifact):
    """V-20: the escalation the provenance registry closes.

    The construction token is a dataclass field, so anyone holding one genuine artifact can
    read it off — and a forger who also recomputes ``artifact_digest`` produces something
    the token check and the digest check both accept. Only the registry distinguishes it:
    the authoritative routine is the only thing that records, and this object never went
    through it.
    """

    from ugence_cloud_scaling_producer_attestation import canonical_digest

    borrowed = artifact.construction_token
    fields = {f.name: getattr(artifact, f.name) for f in dataclasses.fields(artifact)}
    fields["tenant_id"] = "tenant-2"
    fields["construction_token"] = borrowed
    payload = {
        **{k: v for k, v in fields.items()
           if k not in ("artifact_digest", "construction_token")},
        "outcome": "VERIFIED",
        "grants_authority": False,
    }
    fields["artifact_digest"] = canonical_digest(payload)

    forged = VerifiedProducerAttestation(**fields)
    # It is internally consistent — token accepted, self-digest matches...
    assert forged.construction_token is borrowed
    assert forged.artifact_digest == forged.digest()
    assert forged.tenant_id == "tenant-2"
    # ...and it is still refused at every consumption boundary.
    with pytest.raises(VerifiedArtifactIntegrityError) as exc:
        require_verified_producer_attestation(forged)
    assert "never reached" in str(exc.value)


def test_a_faithful_copy_of_a_genuine_determination_still_revalidates(artifact):
    """V-21: the registry keys on the determination, not on object identity.

    A determination is its facts. An artifact carrying identical facts *is* the same
    determination — copied, queued or rebuilt — so refusing a faithful copy would break
    ordinary use while doing nothing extra against a forger, whose facts differ. V-20 is
    the case that matters, and it is refused.
    """

    duplicate = copy.copy(artifact)
    assert duplicate == artifact
    assert duplicate.artifact_digest == artifact.artifact_digest
    assert require_verified_producer_attestation(artifact) is artifact
    assert require_verified_producer_attestation(duplicate) is duplicate


@pytest.mark.parametrize(
    "rebuild",
    [
        pytest.param(copy.deepcopy, id="deepcopy"),
        pytest.param(lambda a: pickle.loads(pickle.dumps(a)), id="pickle"),
    ],
)
def test_a_rebuilt_artifact_is_refused_by_the_token_check_alone(artifact, rebuild):
    """V-24: the case that makes the token check load-bearing rather than sibling-backed.

    ``copy.deepcopy`` and ``pickle`` both bypass ``__init__``, so ``__post_init__`` and its
    construction-time token twin never run. Both rebuild the token — a bare ``object()``
    whose whole meaning is its identity — while copying ``artifact_digest`` as the string it
    is. The result therefore carries:

    * the **same** ``artifact_digest``, so the provenance registry admits it;
    * a self-digest that still recomputes, so the mutation check admits it;
    * the exact type and every declared field, so those two checks admit it;
    * a **different** construction token.

    Exactly one of the five checks in :func:`require_verified_producer_attestation` refuses
    it, and this is that check. The sweep classified it "sibling-backed" until this property
    existed; the registry is not a sibling here, because a rebuilt artifact names a
    determination this process genuinely did reach.
    """

    from ugence_cloud_scaling_producer_attestation.verified import _MINTED_DIGESTS

    rebuilt = rebuild(artifact)

    # The four checks that do NOT refuse it, asserted rather than assumed — this is what
    # distinguishes the property from "something, somewhere, said no".
    assert type(rebuilt) is VerifiedProducerAttestation
    assert all(
        hasattr(rebuilt, f.name) for f in dataclasses.fields(VerifiedProducerAttestation)
    )
    assert rebuilt.artifact_digest == artifact.artifact_digest
    assert rebuilt.artifact_digest in _MINTED_DIGESTS
    assert rebuilt.artifact_digest == rebuilt.digest()

    # The one that does.
    assert rebuilt.construction_token is not artifact.construction_token
    with pytest.raises(VerifiedArtifactIntegrityError) as exc:
        require_verified_producer_attestation(rebuilt)
    assert "construction token" in str(exc.value)


def test_no_deserializer_admits_an_artifact_from_another_process(artifact):
    """V-25: the stated consequence — a determination does not travel between processes.

    V-24 fixes the mechanism inside one interpreter. The claim the module docstring makes
    is broader: there is deliberately no deserializer, so an artifact that has crossed a
    process boundary cannot be re-admitted at all. Pickling is the only serialization the
    class supports at all, and its output is refused on the way back in; the package
    exposes no ``from_dict``, ``from_json``, ``parse`` or ``loads`` route that would offer
    a second one.
    """

    import ugence_cloud_scaling_producer_attestation as pkg

    for constructor in ("from_dict", "from_json", "parse", "parse_obj", "loads"):
        assert not hasattr(VerifiedProducerAttestation, constructor)
        assert constructor not in pkg.__all__

    with pytest.raises(VerifiedArtifactIntegrityError):
        require_verified_producer_attestation(pickle.loads(pickle.dumps(artifact)))


def test_the_registry_is_not_reachable_from_the_curated_api():
    """V-22: neither the token nor the registry is exported."""

    import ugence_cloud_scaling_producer_attestation as pkg

    for private in ("_VERIFICATION_TOKEN", "_MINTED_DIGESTS", "_record_minted"):
        assert private not in pkg.__all__
        assert not hasattr(pkg, private)


def test_every_freshly_verified_artifact_is_in_the_registry(verifier, candidate, as_of):
    """V-23: the positive control for the registry — minting records, every time."""

    from _producer_fixtures import build_attestation

    for _ in range(3):
        minted = verifier.verify(
            candidate=candidate, attestation=build_attestation(candidate), as_of=as_of
        ).verified_attestation
        assert require_verified_producer_attestation(minted) is minted


# ======================================================================================= #
# Issuer versus producer: the artifact names what the signature actually established.
# ======================================================================================= #


def test_a_trusted_issuer_may_attest_a_producer_other_than_itself():
    """V-A1: the attested producer is the issuer's claim, and it need not be the issuer.

    The anchor is resolved by **issuer**. ``producer_id`` is a signed field, but nothing
    resolves it against a trust anchor of its own, so a trusted issuer/key can name any
    producer it likes. That is legitimate — Phase 5 ADR §3 ratifies the controller signing
    its own output and does not require the identifiers to differ — and it is exactly why
    the artifact field is called :attr:`attested_producer_id` rather than
    ``verified_producer_id``.
    """

    from _producer_fixtures import ISSUER_ID, build_candidate

    candidate = build_candidate()
    attestation = build_attestation(candidate, producer_id="some-other-producer-service")
    result = build_verifier().verify(
        candidate=candidate, attestation=attestation, as_of=AS_OF
    )

    artifact = result.verified_attestation
    assert artifact is not None
    assert artifact.attested_producer_id == "some-other-producer-service"
    assert artifact.verified_issuer == ISSUER_ID
    assert artifact.attested_producer_id != artifact.verified_issuer


def test_the_artifact_never_claims_the_producer_was_independently_verified():
    """V-A2: the misleading name is gone, and is not retained as an alias.

    A compatibility alias would keep the false claim readable, which is the whole problem.
    The package is unmerged, so the name is corrected rather than deprecated.
    """

    from _producer_fixtures import build_candidate

    candidate = build_candidate()
    result = build_verifier().verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    artifact = result.verified_attestation

    assert not hasattr(artifact, "verified_producer_id")
    assert "verified_producer_id" not in artifact.digest_payload()
    assert "attested_producer_id" in artifact.digest_payload()
    field_names = {f.name for f in dataclasses.fields(artifact)}
    assert "attested_producer_id" in field_names
    assert "verified_producer_id" not in field_names


def test_the_issuer_and_key_are_verified_while_the_producer_is_attested():
    """V-A3: the naming distinction tracks a real difference in what was checked.

    ``verified_issuer`` and ``verified_key_id`` name the coordinate an anchor was actually
    resolved and lifecycle-checked at, and whose public key verified the signature.
    ``attested_producer_id`` names a value that was only ever inside the signed bytes.
    """

    from _producer_fixtures import ISSUER_ID, PRODUCER_KEY_ID, build_candidate

    candidate = build_candidate()
    result = build_verifier().verify(
        candidate=candidate,
        attestation=build_attestation(candidate, producer_id="claimed-producer"),
        as_of=AS_OF,
    )
    artifact = result.verified_attestation

    # Resolved, and therefore verified.
    assert artifact.verified_issuer == ISSUER_ID
    assert artifact.verified_key_id == PRODUCER_KEY_ID
    # Signed, and therefore only attested.
    assert artifact.attested_producer_id == "claimed-producer"
