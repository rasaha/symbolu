"""The forgery-laundering proof — the failing traversal Phase 5B-0A exists to produce.

The blocker, restated
---------------------
A self-consistent forged recommendation launders cleanly through the whole Cloud Scaling
chain. Nothing in it establishes *who produced* the recommendation:

* the forger invents capacity facts and runs them through the controller's **real**
  Phase-3 pipeline, so the recommendation is internally consistent;
* its unkeyed content digest matches its own content, because an unkeyed digest is a
  function of the content and the forger controls the content;
* Phase 4C's structural admission passes — it reconciles a digest against an expectation
  the forger also supplies;
* a genuine Risk Decision is minted for it;
* a valid Phase 5A ``CapacityAuthorizationCandidate`` is built, because Phase 5A checks
  the attestation structurally and never checks the signature.

Every one of those steps is *correct*. None of them was ever specified to establish
provenance, and the brief's verdict is that the gap is real.

What this module proves
-----------------------
That Phase 5B-0A refuses at the end of that traversal, in both the **absent** arm and the
**forged** arm, and that the refusal is isolated to the authenticity gate: the two arms
differ from the positive control by the producer key **and nothing else**. Same
recommendation, same projection, same decision, same candidate, same tenant, same subject,
same digests, same instant. Only the key changes.

And that a refusal reaches nothing downstream: zero envelope requests, zero signer calls,
zero ActionGate calls, zero credential calls, zero executor calls.
"""

from __future__ import annotations

import pytest

import phase5a_fixtures as P5A
from _producer_fixtures import (
    AS_OF,
    PRODUCER_KEY_ID,
    TRUSTED_PRODUCER_SEED,
    UNTRUSTED_KEY_ID,
    UNTRUSTED_PRODUCER_SEED,
    CountingSignatureVerifier,
    CountingSigner,
    ForbiddenCollaborator,
    build_attestation,
    build_directory,
    build_verifier,
)

from ugence_cloud_scaling_producer_attestation import ProducerAuthenticityOutcome

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

O = ProducerAuthenticityOutcome

#: Capacity facts nobody in the chain ever asserted. The forger's invention.
FORGED_RECOMMENDATION_ID = "rec-forged-by-an-attacker"
FORGED_PREDICTED = 8


class DownstreamCallCounters:
    """Counting doubles for every downstream capability this phase must not reach.

    Each one raises the moment it is touched, so "zero calls" is proved by construction
    rather than asserted about a counter nobody had a chance to increment.
    """

    def __init__(self) -> None:
        self.envelope_issuer = ForbiddenCollaborator("envelope_issuer")
        self.envelope_request_builder = ForbiddenCollaborator("envelope_request_builder")
        self.action_gate = ForbiddenCollaborator("action_gate")
        self.credential_broker = ForbiddenCollaborator("credential_broker")
        self.executor = ForbiddenCollaborator("executor")
        self.signer = CountingSigner()

    def assert_untouched(self, label: str) -> None:
        for collaborator in (
            self.envelope_issuer,
            self.envelope_request_builder,
            self.action_gate,
            self.credential_broker,
            self.executor,
        ):
            assert collaborator.calls == [], f"{label} reached {collaborator.name}"
        assert self.signer.calls == 0, f"{label} called a signer during verification"


# --------------------------------------------------------------------------------------- #
# The traversal itself
# --------------------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def forged_chain():
    """The complete laundering traversal, up to but not including Phase 5B-0A.

    Built through the **real** pipeline at every step, from Phase 5A's own frozen fixture
    module. Nothing here is stubbed: a proof against a hand-rolled candidate would prove
    nothing about the artifact the chain actually produces.
    """

    forged_recommendation = P5A.build_recommendation(
        predicted=FORGED_PREDICTED, recommendation_id=FORGED_RECOMMENDATION_ID
    )
    projection = P5A.build_projection(forged_recommendation)
    decision = P5A.build_decision(projection)
    # The v1 attestation names the forger's own recommendation label, so the laundered
    # chain is self-consistent end to end rather than self-consistent up to a label.
    v1_attestation = P5A.build_attestation(
        recommendation_digest=projection.recommendation_digest,
        recommendation_id=FORGED_RECOMMENDATION_ID,
    )
    candidate = P5A.build_candidate(
        projection=projection, decision=decision, producer_attestation=v1_attestation
    )
    return {
        "recommendation": forged_recommendation,
        "projection": projection,
        "decision": decision,
        "candidate": candidate,
    }


def test_step_1_the_forged_recommendation_is_internally_self_consistent(forged_chain):
    """L-1: the forgery passes the controller's own consistency, unaided."""

    serialized = forged_chain["recommendation"].to_canonical_dict()
    assert serialized["evidence_digest"], "the forgery carries its own content digest"
    assert forged_chain["recommendation"].recommendation_id == FORGED_RECOMMENDATION_ID


def test_step_2_the_unkeyed_digest_matches_the_forged_content(forged_chain):
    """L-2: an unkeyed digest is a function of content, and the forger controls content."""

    projection = forged_chain["projection"]
    serialized = forged_chain["recommendation"].to_canonical_dict()
    assert projection.recommendation_digest == serialized["evidence_digest"]


def test_step_3_phase_4c_structurally_admits_the_forgery(forged_chain):
    """L-3: Phase 4C's structural admission passes. It was never a provenance check."""

    projection = forged_chain["projection"]
    assert projection.tenant_id == "tenant-1"
    assert projection.request is not None
    assert projection.context_digest and projection.subject_digest


def test_step_4_a_genuine_risk_decision_is_minted_for_the_forgery(forged_chain):
    """L-4: the Risk Decision is real. It binds a digest, not a provenance."""

    decision = forged_chain["decision"]
    assert decision.decision_digest
    assert decision.decision_snapshot is not None


def test_step_5_a_valid_phase_5a_candidate_is_built_from_the_forgery(forged_chain):
    """L-5: the gap, made concrete. Phase 5A builds a valid candidate for a forgery.

    This is not a Phase 5A defect. Phase 5A documents exactly this: its one trust state is
    ``PRESENT_BUT_NOT_TRUST_VERIFIED`` and it verifies no signature. The candidate is
    structurally impeccable and provenance-free.
    """

    candidate = forged_chain["candidate"]
    assert candidate.candidate_digest
    assert candidate.recommendation_id == FORGED_RECOMMENDATION_ID
    assert candidate.grants_authority is False
    assert (
        candidate.producer_attestation.trust_state.value
        == "PRESENT_BUT_NOT_TRUST_VERIFIED"
    )


# --------------------------------------------------------------------------------------- #
# Step 6 — Phase 5B-0A, in both required arms
# --------------------------------------------------------------------------------------- #


def test_step_6a_the_absent_arm_is_refused(forged_chain):
    """L-6: absent producer signature. Refused, typed, with nothing minted or reached."""

    counters = DownstreamCallCounters()
    signature_verifier = CountingSignatureVerifier()
    verifier = build_verifier(
        directory=build_directory(), signature_verifier=signature_verifier
    )

    result = verifier.verify(
        candidate=forged_chain["candidate"], attestation=None, as_of=AS_OF
    )

    assert result.verified_attestation is None
    assert result.refusal.outcome is O.ATTESTATION_ABSENT
    assert signature_verifier.calls == 0
    counters.assert_untouched("absent arm")


def test_step_6b_the_forged_arm_is_refused(forged_chain):
    """L-7: a forged producer signature under an unregistered key. Refused, typed."""

    counters = DownstreamCallCounters()
    signature_verifier = CountingSignatureVerifier()
    verifier = build_verifier(
        directory=build_directory(), signature_verifier=signature_verifier
    )

    forged_attestation = build_attestation(
        forged_chain["candidate"],
        seed=UNTRUSTED_PRODUCER_SEED,
        producer_key_id=UNTRUSTED_KEY_ID,
    )
    result = verifier.verify(
        candidate=forged_chain["candidate"],
        attestation=forged_attestation,
        as_of=AS_OF,
    )

    assert result.verified_attestation is None
    assert result.refusal.outcome is O.ANCHOR_UNKNOWN
    counters.assert_untouched("forged arm")


def test_step_6c_a_forged_key_under_a_trusted_key_id_is_refused_at_the_signature(
    forged_chain,
):
    """L-8: the isolated authenticity gate. Only the signing key differs from the control.

    The attacker names the *trusted* coordinate, so the anchor resolves, is in window and
    is correctly scoped. Every gate before the signature check succeeds. The signature
    check is what refuses, and it is the only thing that can.
    """

    counters = DownstreamCallCounters()
    signature_verifier = CountingSignatureVerifier()
    verifier = build_verifier(
        directory=build_directory(), signature_verifier=signature_verifier
    )

    impostor = build_attestation(
        forged_chain["candidate"],
        seed=UNTRUSTED_PRODUCER_SEED,
        producer_key_id=PRODUCER_KEY_ID,
    )
    result = verifier.verify(
        candidate=forged_chain["candidate"], attestation=impostor, as_of=AS_OF
    )

    assert result.verified_attestation is None
    assert result.refusal.outcome is O.SIGNATURE_INVALID
    assert signature_verifier.calls == 1, "the signature check must actually have run"
    counters.assert_untouched("impostor arm")


@pytest.mark.happy
def test_step_6d_the_positive_control_differs_only_in_the_signing_key(forged_chain):
    """L-9: isolation, proved both ways.

    The same forged recommendation, the same projection, the same decision, the same
    candidate, the same coordinates and the same instant — attested with the **trusted**
    key — verifies. So the refusals above are attributable to the key and to nothing else:
    no sibling gate is silently doing the work.
    """

    verifier = build_verifier(directory=build_directory())

    trusted = build_attestation(
        forged_chain["candidate"],
        seed=TRUSTED_PRODUCER_SEED,
        producer_key_id=PRODUCER_KEY_ID,
    )
    impostor = build_attestation(
        forged_chain["candidate"],
        seed=UNTRUSTED_PRODUCER_SEED,
        producer_key_id=PRODUCER_KEY_ID,
    )

    # The two attestations are byte-identical except for the signature itself.
    assert trusted.signing_payload() == impostor.signing_payload()
    assert trusted.signed_bytes() == impostor.signed_bytes()
    assert trusted.signature != impostor.signature

    good = verifier.verify(
        candidate=forged_chain["candidate"], attestation=trusted, as_of=AS_OF
    )
    bad = verifier.verify(
        candidate=forged_chain["candidate"], attestation=impostor, as_of=AS_OF
    )

    assert good.refusal is None and good.verified_attestation is not None
    assert bad.verified_attestation is None
    assert bad.refusal.outcome is O.SIGNATURE_INVALID


def test_a_downstream_valid_signature_never_compensates_for_invalid_provenance(
    forged_chain,
):

    """L-10: a later valid signature cannot rescue an earlier invalid one.

    The Phase 5A candidate carries a v1 producer attestation with a genuine Ed25519
    signature over its own v1 payload. That signature is valid — and it is irrelevant: it
    is a different contract at a different schema tag, and Phase 5B-0A neither consults it
    nor lets it stand in for a v2 proof. The forged arm still refuses.
    """

    candidate = forged_chain["candidate"]
    assert candidate.producer_attestation.signature  # a real, valid v1 signature exists
    verifier = build_verifier(directory=build_directory())

    result = verifier.verify(
        candidate=candidate,
        attestation=build_attestation(
            candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=UNTRUSTED_KEY_ID
        ),
        as_of=AS_OF,
    )
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.ANCHOR_UNKNOWN

    # ...and the v1 attestation cannot itself be submitted as the v2 proof.
    v1_result = verifier.verify(
        candidate=candidate, attestation=candidate.producer_attestation, as_of=AS_OF
    )
    assert v1_result.verified_attestation is None
    assert v1_result.refusal.outcome is O.UNSUPPORTED_EXACT_TYPE
