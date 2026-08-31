"""The dedicated capability, and the cross-domain reuse it refuses.

An independent closure audit of this PR proved a concrete authority defect. Because the
repository deliberately keeps **one** trust-anchor store, and because this package
resolved its anchors under TEV's ``EVIDENCE_PRODUCTION``, a key provisioned purely to
sign Trusted Evidence — a telemetry agent, holding no Cloud Scaling grant of any kind —
successfully signed and verified a capacity-recommendation producer attestation. The
coordinate could not tell the two signing domains apart, so the entitlement was shared.

This module is the regression. It reproduces the audit's attack against the **real**
public verification boundary, requires a typed refusal, and then proves the positive
control differs in nothing but the capability on the anchor.

Domain separation inside the signed bytes is not what fixes this, and this module does
not pretend otherwise. The schema tag and the signing purpose stop a *signature* from
being replayed across domains; they say nothing about which *keys* a domain trusts. Only
the coordinate carries that, and the capability is the part of the coordinate that names
the role.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from ugence_trusted_evidence_authority import TrustAnchorCapability, KeyRevocation

from _producer_fixtures import (
    AS_OF,
    ISSUER_ID,
    PRODUCER_ID,
    PRODUCER_KEY_ID,
    TRUSTED_PRODUCER_SEED,
    build_anchor,
    build_attestation,
    build_candidate,
    build_directory,
    build_verifier,
)

from ugence_cloud_scaling_producer_attestation import (
    PRODUCER_ATTESTATION_CAPABILITY,
    ProducerAuthenticityOutcome as O,
    producer_anchor_coordinate,
)

#: Property category: this module's default is declared in ``tests/conftest.py``.

CS = TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION
EV = TrustAnchorCapability.EVIDENCE_PRODUCTION
RI = TrustAnchorCapability.RECEIPT_ISSUANCE


def _verify(anchor, *, as_of=AS_OF):
    """Run the real public boundary against one anchor, with everything else identical."""

    candidate = build_candidate()
    attestation = build_attestation(candidate)
    return build_verifier(directory=build_directory(anchor)).verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    )


# --------------------------------------------------------------------------------------- #
# 1. The audit's attack, reproduced and refused
# --------------------------------------------------------------------------------------- #


def test_a_pure_evidence_production_key_cannot_verify_a_cloud_scaling_recommendation():
    """C-1: the reported cross-domain escalation, reproduced end to end.

    The key is real, the signature is real and valid over the real canonical payload, and
    the private half is the one the anchor's public half belongs to. The **only** thing
    the anchor does not carry is the Cloud Scaling capability. Before remediation this
    verified; it must now refuse.
    """

    result = _verify(build_anchor(capability=EV))

    assert result.verified_attestation is None, (
        "an evidence-production key attested a capacity recommendation; the "
        "cross-domain privilege reuse has returned"
    )
    assert result.refusal.outcome is O.ANCHOR_UNKNOWN


def test_a_receipt_issuance_key_cannot_verify_a_cloud_scaling_recommendation():
    """C-2: the other TEV role is refused for the same structural reason."""

    result = _verify(build_anchor(capability=RI))
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.ANCHOR_UNKNOWN


def test_the_positive_control_differs_only_in_the_capability():
    """C-3: same issuer, same key id, same seed, same payload — and it verifies.

    This is what makes C-1 attributable. The two runs differ in exactly one field of one
    record, so the refusal above cannot be some sibling gate quietly doing the work.
    """

    refused = _verify(build_anchor(capability=EV))
    verified = _verify(build_anchor(capability=CS))

    assert refused.verified_attestation is None
    assert verified.verified_attestation is not None
    assert verified.verified_attestation.trust_anchor_capability == CS.value


@pytest.mark.parametrize("capability", [EV, RI])
def test_the_two_evidence_capabilities_are_never_substitutable(capability):
    """C-4: neither TEV role can stand in for the Cloud Scaling one, in either direction."""

    assert PRODUCER_ATTESTATION_CAPABILITY is not capability
    assert _verify(build_anchor(capability=capability)).verified_attestation is None


def test_registering_both_records_keeps_each_grant_explicit():
    """C-5: one key may hold both grants, but each is a separate, configured record.

    Nothing derives one grant from the other: the evidence anchor alone still refuses,
    and it is the *added* Cloud Scaling record that admits — which is exactly what
    "explicit and independently configured" has to mean to be worth anything.
    """

    evidence_only = build_directory(build_anchor(capability=EV))
    both = build_directory(
        build_anchor(capability=EV), build_anchor(capability=CS)
    )
    candidate = build_candidate()
    attestation = build_attestation(candidate)

    refused = build_verifier(directory=evidence_only).verify(
        candidate=candidate, attestation=attestation, as_of=AS_OF
    )
    admitted = build_verifier(directory=both).verify(
        candidate=candidate, attestation=attestation, as_of=AS_OF
    )
    assert refused.verified_attestation is None
    assert admitted.verified_attestation is not None


# --------------------------------------------------------------------------------------- #
# 2. The capability is inside the coordinate, which is what makes it load-bearing
# --------------------------------------------------------------------------------------- #


def test_changing_only_the_capability_moves_the_trust_anchor_coordinate_digest():
    """C-6: the coordinate is the entitlement, so the digest must separate the domains."""

    from ugence_cloud_scaling_producer_attestation import anchor_coordinate_digest
    from ugence_trusted_evidence_authority import TrustAnchorCoordinate

    digests = {
        capability: anchor_coordinate_digest(
            TrustAnchorCoordinate(
                authority_id=ISSUER_ID, key_id=PRODUCER_KEY_ID, capability=capability
            )
        )
        for capability in TrustAnchorCapability
    }
    assert len(set(digests.values())) == 3
    assert digests[CS] == anchor_coordinate_digest(
        producer_anchor_coordinate(issuer=ISSUER_ID, producer_key_id=PRODUCER_KEY_ID)
    )


def test_the_capability_is_not_a_caller_supplied_lookup_parameter():
    """C-7: a caller cannot ask for verification under another domain's capability."""

    import inspect

    parameters = set(inspect.signature(producer_anchor_coordinate).parameters)
    assert parameters == {"issuer", "producer_key_id"}
    assert producer_anchor_coordinate(
        issuer=ISSUER_ID, producer_key_id=PRODUCER_KEY_ID
    ).capability is CS


# --------------------------------------------------------------------------------------- #
# 3. Holding the dedicated capability is still not a licence
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "anchor_kwargs, expected",
    [
        ({"revocation": KeyRevocation(effective_at=AS_OF - timedelta(days=1),
                                      reason_ref="compromised")}, O.ANCHOR_REVOKED),
        ({"disabled": True}, O.ANCHOR_DISABLED),
        ({"effective_from": AS_OF - timedelta(days=10),
          "effective_to": AS_OF - timedelta(days=1)}, O.ANCHOR_EXPIRED),
        ({"effective_from": AS_OF + timedelta(days=1),
          "effective_to": AS_OF + timedelta(days=10)}, O.ANCHOR_NOT_YET_VALID),
    ],
)
def test_a_lifecycle_failure_still_refuses_under_the_dedicated_capability(
    anchor_kwargs, expected
):
    """C-8: the new capability replaces no other gate. Every lifecycle refusal still fires."""

    result = _verify(build_anchor(capability=CS, **anchor_kwargs))
    assert result.verified_attestation is None
    assert result.refusal.outcome is expected


def test_an_untrusted_key_under_the_dedicated_capability_still_fails_the_signature():
    """C-9: the capability admits a coordinate; it never substitutes for the signature."""

    from _producer_fixtures import UNTRUSTED_PRODUCER_SEED

    candidate = build_candidate()
    impostor = build_attestation(candidate, seed=UNTRUSTED_PRODUCER_SEED)
    result = build_verifier(
        directory=build_directory(build_anchor(seed=TRUSTED_PRODUCER_SEED, capability=CS))
    ).verify(candidate=candidate, attestation=impostor, as_of=AS_OF)
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.SIGNATURE_INVALID


# --------------------------------------------------------------------------------------- #
# 4. The lent capability grants nothing back inside TEV
# --------------------------------------------------------------------------------------- #


def test_the_dedicated_capability_cannot_produce_tev_evidence_or_issue_a_receipt():
    """C-10: the loan is one-way. TEV's own paths refuse the lent member.

    Asserted here as well as in TEV's suite, because this is the package that benefits
    from the loan and therefore the package that must not quietly widen it.
    """

    import ugence_trusted_evidence_authority as tev

    assert CS is not tev.TrustAnchorCapability.EVIDENCE_PRODUCTION
    assert CS is not tev.TrustAnchorCapability.RECEIPT_ISSUANCE

    # Structural: TEV resolves evidence only under EVIDENCE_PRODUCTION and receipts only
    # under RECEIPT_ISSUANCE, so an anchor filed under the lent member is at neither
    # coordinate. The behavioural proof lives in TEV's own suite, which owns those paths.
    import ast
    import pathlib

    tev_root = pathlib.Path(tev.__file__).resolve().parent
    for module, allowed in (
        ("verification.py", {"EVIDENCE_PRODUCTION"}),
        ("signing.py", {"RECEIPT_ISSUANCE"}),
        ("reverification.py", {"RECEIPT_ISSUANCE"}),
    ):
        tree = ast.parse((tev_root / "authority" / module).read_text(encoding="utf-8"))
        named = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "TrustAnchorCapability"
        }
        assert named <= allowed, (module, named)
