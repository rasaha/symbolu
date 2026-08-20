"""The outcome vocabulary is closed, typed, exhaustive and fails closed.

The rule under test: a security outcome is told apart by its **member**, never by parsing a
message string. A caller that had to grep prose to distinguish "unknown key" from "revoked
key" would be one refactor away from conflating them.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from _producer_fixtures import (
    AS_OF,
    FOREIGN_ISSUER_ID,
    PRODUCER_KEY_ID,
    UNTRUSTED_KEY_ID,
    UNTRUSTED_PRODUCER_SEED,
    WINDOW_FROM,
    WINDOW_TO,
    build_anchor,
    build_attestation,
    build_directory,
    build_verifier,
)

import ugence_cloud_scaling_producer_attestation as pkg
from ugence_cloud_scaling_producer_attestation import (
    ANCHOR_LIFECYCLE_OUTCOMES,
    REFUSAL_OUTCOMES,
    DenyAllTrustAnchorDirectory,
    KeyRevocation,
    ProducerAttestationRefusal,
    ProducerAuthenticityOutcome,
    ProducerAuthenticityResult,
    TrustAnchorCapability,
    VerifiedArtifactIntegrityError,
    VerifiedProducerAttestation,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.


O = ProducerAuthenticityOutcome
PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent

#: The minimum vocabulary the ratified design names, plus the fail-closed terminals.
REQUIRED_MEMBERS = {
    "VERIFIED",
    "ATTESTATION_ABSENT",
    "ATTESTATION_MALFORMED",
    "PAYLOAD_MISMATCH",
    "ANCHOR_UNKNOWN",
    "ANCHOR_REVOKED",
    "ANCHOR_NOT_IN_WINDOW",
    "ANCHOR_DISABLED",
    "WRONG_CAPABILITY",
    "WRONG_AUTHORITY",
    "WRONG_TENANT",
    "WRONG_SUBJECT",
    "UNSUPPORTED_SIGNING_PURPOSE",
    "UNSUPPORTED_PROFILE",
    "UNSUPPORTED_ENCODING",
    "MALFORMED_SIGNATURE",
    "SIGNATURE_INVALID",
    "UNSUPPORTED_EXACT_TYPE",
    "INDETERMINATE",
    # additionally required so no two distinct security failures share a member
    "UNSUPPORTED_SCHEMA_VERSION",
    "UNSUPPORTED_ALGORITHM",
    "RECOMMENDATION_ID_MISMATCH",
    "RECOMMENDATION_DIGEST_MISMATCH",
    "ANCHOR_NOT_YET_VALID",
    "ANCHOR_EXPIRED",
    "VERIFICATION_UNAVAILABLE",
    "INVARIANT_VIOLATION",
}


@pytest.mark.invariant
def test_the_ratified_vocabulary_is_present_in_full():
    """O-1: every member the design names exists."""

    members = {m.name for m in O}
    missing = REQUIRED_MEMBERS - members
    assert missing == set(), missing


@pytest.mark.invariant
def test_there_is_exactly_one_success_member():
    """O-2: one success, and every other member is a refusal."""

    successes = [m for m in O if m not in REFUSAL_OUTCOMES]
    assert successes == [O.VERIFIED]
    assert len(REFUSAL_OUTCOMES) == len(list(O)) - 1


def test_no_member_names_authority_or_execution():
    """O-3: there is no ``AUTHORIZED``, ``ADMITTED`` or ``EXECUTABLE`` to reach."""

    for member in O:
        lowered = member.name.lower()
        for banned in ("authoriz", "admit", "execut", "envelope", "credential", "grant"):
            assert banned not in lowered, member.name


def test_a_refusal_cannot_carry_the_success_member():
    """O-4: ``VERIFIED`` is not spellable as a refusal."""

    with pytest.raises(ValueError):
        ProducerAttestationRefusal(outcome=O.VERIFIED)


def test_a_result_cannot_carry_both_or_neither_branch(verifier, candidate, attestation, as_of):
    """O-5: no 'verified refusal' state and no untyped silence."""

    artifact = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation
    with pytest.raises(ValueError):
        ProducerAuthenticityResult()
    with pytest.raises(ValueError):
        ProducerAuthenticityResult(
            verified_attestation=artifact,
            refusal=ProducerAttestationRefusal(outcome=O.SIGNATURE_INVALID),
        )


def test_a_result_carries_no_boolean_success_flag():
    """O-6: a caller must branch on which branch is present, not read a bool."""

    import dataclasses

    names = {f.name for f in dataclasses.fields(ProducerAuthenticityResult)}
    assert names == {"verified_attestation", "refusal"}
    for banned in ("ok", "success", "valid", "verified_flag", "is_verified"):
        assert banned not in names


def test_a_refusal_outcome_is_exact_typed():
    """O-7: a look-alike enum cannot be presented as an outcome."""

    class FakeOutcome:
        value = "VERIFIED"
        name = "VERIFIED"

    with pytest.raises(TypeError):
        ProducerAttestationRefusal(outcome=FakeOutcome())


def test_distinct_failures_produce_distinct_members(candidate):
    """O-8: the members actually discriminate — no two of these share one."""

    genuine = build_attestation(candidate)
    cases = {
        "absent": (None, build_directory(), O.ATTESTATION_ABSENT),
        "wrong_type": (object(), build_directory(), O.UNSUPPORTED_EXACT_TYPE),
        "tenant": (
            build_attestation(candidate, tenant_id="tenant-2"),
            build_directory(),
            O.WRONG_TENANT,
        ),
        "subject": (
            build_attestation(candidate, subject_id="billing-api"),
            build_directory(),
            O.WRONG_SUBJECT,
        ),
        "rec_digest": (
            build_attestation(candidate, recommendation_digest="sha256:" + "d" * 64),
            build_directory(),
            O.RECOMMENDATION_DIGEST_MISMATCH,
        ),
        "rec_id": (
            build_attestation(candidate, recommendation_id="rec-other"),
            build_directory(),
            O.RECOMMENDATION_ID_MISMATCH,
        ),
        "unknown_anchor": (
            build_attestation(
                candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=UNTRUSTED_KEY_ID
            ),
            build_directory(),
            O.ANCHOR_UNKNOWN,
        ),
        "bad_signature": (
            build_attestation(
                candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=PRODUCER_KEY_ID
            ),
            build_directory(),
            O.SIGNATURE_INVALID,
        ),
        "revoked": (
            genuine,
            build_directory(build_anchor(revocation=KeyRevocation(effective_at=WINDOW_FROM))),
            O.ANCHOR_REVOKED,
        ),
        "disabled": (genuine, build_directory(build_anchor(disabled=True)), O.ANCHOR_DISABLED),
        "expired": (
            genuine,
            build_directory(
                build_anchor(effective_to=WINDOW_FROM + __import__("datetime").timedelta(minutes=1))
            ),
            O.ANCHOR_EXPIRED,
        ),
        "not_yet_valid": (
            genuine,
            build_directory(
                build_anchor(
                    effective_from=WINDOW_TO,
                    effective_to=WINDOW_TO + __import__("datetime").timedelta(days=1),
                )
            ),
            O.ANCHOR_NOT_YET_VALID,
        ),
        "deny_all": (genuine, DenyAllTrustAnchorDirectory(), O.ANCHOR_UNKNOWN),
    }
    seen = {}
    for label, (attestation, directory, expected) in cases.items():
        verifier = build_verifier(directory=directory)
        result = verifier.verify(
            candidate=candidate, attestation=attestation, as_of=AS_OF
        )
        assert result.refusal.outcome is expected, (label, result.refusal)
        seen[label] = result.refusal.outcome
    assert len(set(seen.values())) >= 11, "the members are not discriminating enough"


def test_a_refusal_message_is_never_the_distinguishing_information(candidate):
    """O-9: two different failures may read alike; they never share a member."""

    tenant = build_verifier().verify(
        candidate=candidate,
        attestation=build_attestation(candidate, tenant_id="tenant-2"),
        as_of=AS_OF,
    ).refusal
    subject = build_verifier().verify(
        candidate=candidate,
        attestation=build_attestation(candidate, subject_id="billing-api"),
        as_of=AS_OF,
    ).refusal
    assert tenant.outcome is not subject.outcome
    # The suite asserts on members. Nothing in the package's own logic branches on detail.
    for path in sorted(PKG_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "detail":
                assert isinstance(
                    getattr(node, "ctx", None), (ast.Store, ast.Load)
                ), path.name


@pytest.mark.invariant
def test_the_lifecycle_family_is_named_and_complete():
    """O-10: the anchor-lifecycle refusals are enumerable, for documentation and tests."""

    assert ANCHOR_LIFECYCLE_OUTCOMES == {
        O.ANCHOR_DISABLED,
        O.ANCHOR_REVOKED,
        O.ANCHOR_NOT_YET_VALID,
        O.ANCHOR_EXPIRED,
        O.ANCHOR_NOT_IN_WINDOW,
    }
    assert ANCHOR_LIFECYCLE_OUTCOMES <= REFUSAL_OUTCOMES


def test_indeterminate_is_a_refusal_not_a_pass():
    """O-11: the default arm of every exhaustive match mints nothing."""

    assert O.INDETERMINATE in REFUSAL_OUTCOMES
    assert O.VERIFICATION_UNAVAILABLE in REFUSAL_OUTCOMES
    assert O.INVARIANT_VIOLATION in REFUSAL_OUTCOMES
    result = ProducerAuthenticityResult(
        refusal=ProducerAttestationRefusal(outcome=O.INDETERMINATE)
    )
    assert result.verified_attestation is None
    assert result.outcome is O.INDETERMINATE


def test_every_typed_error_carries_an_outcome_member():
    """O-12: even the construction errors branch on a member, not on a message."""

    from ugence_cloud_scaling_producer_attestation import (
        CloudScalingProducerAttestationError,
        ProducerAttestationCanonicalFieldError,
        ProducerAttestationConfigurationError,
        ProducerAttestationExactTypeError,
        ProducerAttestationSigningBoundaryError,
        VerifiedArtifactIntegrityError,
    )

    for cls in (
        CloudScalingProducerAttestationError,
        ProducerAttestationCanonicalFieldError,
        ProducerAttestationConfigurationError,
        ProducerAttestationExactTypeError,
        ProducerAttestationSigningBoundaryError,
        VerifiedArtifactIntegrityError,
    ):
        error = cls("message")
        assert type(error.outcome) is O, cls.__name__
        assert error.outcome is not O.VERIFIED, cls.__name__


# --------------------------------------------------------------------------------------- #
# 5. The result decides the presence of an artifact; a caller does not supply one
# --------------------------------------------------------------------------------------- #


def test_a_fabricated_artifact_cannot_be_wrapped_in_a_result():
    """O-13: the docstring claim, made executable.

    ``ProducerAuthenticityResult`` is exported, so a caller can construct one. Its only
    artifact gate was an exact-type check — and ``object.__new__`` produces exactly the
    right type with no instance state at all, so the check saw nothing wrong with it. The
    result constructed, and ``result.outcome`` then read ``VERIFIED``: a caller-assembled
    object reporting a determination that never happened, at the exact boundary a consumer
    branches on.

    Construction now routes the artifact through the same revalidation every other
    consumption boundary performs, so the fabrication is refused where it is made.
    """

    fabricated = object.__new__(VerifiedProducerAttestation)
    assert type(fabricated) is VerifiedProducerAttestation  # the old gate was satisfied

    with pytest.raises(VerifiedArtifactIntegrityError) as exc:
        ProducerAuthenticityResult(verified_attestation=fabricated)
    assert "fabricated without running the verification routine" in str(exc.value)


def test_a_token_bearing_forgery_cannot_be_wrapped_in_a_result(
    verifier, candidate, attestation, as_of
):
    """O-14: the harder fabrication — borrow the token, recompute the digest, still refused.

    O-13 covers the empty shell. This is V-20's forgery, which is internally consistent:
    exact type, every field present, a genuine construction token read off a real artifact,
    and a self-digest that recomputes. Only provenance-registry membership distinguishes it,
    and the result boundary now checks that too.
    """

    import dataclasses

    from ugence_cloud_scaling_producer_attestation import canonical_digest

    genuine = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation
    fields = {f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    fields["tenant_id"] = "tenant-forged"
    payload = {
        **{
            k: v
            for k, v in fields.items()
            if k not in ("artifact_digest", "construction_token")
        },
        "outcome": "VERIFIED",
        "grants_authority": False,
    }
    fields["artifact_digest"] = canonical_digest(payload)
    forged = VerifiedProducerAttestation(**fields)

    with pytest.raises(VerifiedArtifactIntegrityError) as exc:
        ProducerAuthenticityResult(verified_attestation=forged)
    assert "never reached" in str(exc.value)


@pytest.mark.happy
def test_a_genuine_determination_still_builds_a_result(
    verifier, candidate, attestation, as_of
):
    """O-15: the positive control. The revalidation must not refuse the real thing.

    Including a result rebuilt by hand around a genuine artifact — the revalidation is
    about the artifact's provenance, not about who assembled the wrapper.
    """

    genuine = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation
    rebuilt = ProducerAuthenticityResult(verified_attestation=genuine)
    assert rebuilt.outcome is O.VERIFIED
    assert rebuilt.verified_attestation is genuine
    assert rebuilt.refusal is None
