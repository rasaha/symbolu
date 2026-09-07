"""SCR-1: the wrapper binds an unmodified result, and the engine role means the
signer is the engine the result names.

A result altered after construction, a self-digest that disagrees with the
result's own fields, and a signer speaking for an identity the result does not
name are refused at wrap time, before any byte is signed.
"""

from __future__ import annotations

import dataclasses

import pytest

import ugence_reasoning_method_result_attestation as ra
from _fixtures import (
    ENGINE,
    ENGINE_ID,
    OTHER_ENGINE_ID,
    SIGNED_AT,
    anchor_of,
    assessment,
    engine_signer,
    result,
    signed,
    verifier,
    verify,
)

R = ra.ComparisonResultRefusalReason


def test_a_signer_whose_identity_is_not_the_results_engine_cannot_sign_it_as_the_engine():
    impostor = engine_signer(signer_identity=OTHER_ENGINE_ID)
    with pytest.raises(ra.ComparisonResultAttestationSigningBoundaryError, match="engine_identity"):
        ra.sign_comparison_result(result(), signer=impostor, signed_at=SIGNED_AT)
    # And the wrapper itself refuses the same mismatch when built by hand.
    sr = signed()
    with pytest.raises(ra.ComparisonResultAttestationContractError, match="engine_identity"):
        dataclasses.replace(sr, signer_identity=OTHER_ENGINE_ID)


def test_a_result_naming_another_engine_is_signed_only_by_that_engine():
    foreign = result(assessment(engine=OTHER_ENGINE_ID), engine=OTHER_ENGINE_ID)
    other = engine_signer(signer_identity=OTHER_ENGINE_ID)
    sr = ra.sign_comparison_result(foreign, signer=other, signed_at=SIGNED_AT)
    assert sr.signer_identity == OTHER_ENGINE_ID
    # The verifier's caller expects the comparison engine: the wrapper names another.
    r = verify(verifier(anchor_of(other)), sr, res=foreign)
    assert r.refusal_reason is R.WRONG_ENGINE_IDENTITY
    # With the caller expecting that engine, it verifies under that engine's anchor.
    r = verify(verifier(anchor_of(other)), sr, res=foreign, engine=OTHER_ENGINE_ID)
    assert r.outcome is ra.ComparisonResultVerificationOutcome.VERIFIED


def test_a_wrapped_result_altered_in_place_after_signing_refuses():
    """A frozen dataclass forced open with object.__setattr__ on the wrapped result:
    the identity field moves, so the projection no longer matches the caller's — and
    because ``result_digest`` covers it, the self-digest no longer describes it either."""

    sr = signed()
    object.__setattr__(sr.result, "request_id", "cmp.tampered")
    r = verify(verifier(anchor_of(engine_signer())), sr)
    assert r.refusal_reason is R.RESULT_MISMATCH
    # ``produced_at`` is outside the governance digest, so moving it alone is the
    # pure projection mismatch: the wrapper still projects, to a different result.
    sr = signed()
    object.__setattr__(sr.result, "produced_at", sr.result.produced_at.replace(hour=13))
    r = verify(verifier(anchor_of(engine_signer())), sr)
    assert r.refusal_reason is R.RESULT_MISMATCH and "not the comparison result the caller holds" in r.detail


def test_a_wrapped_result_whose_self_digest_was_altered_is_refused_at_every_read():
    sr = signed()
    object.__setattr__(sr.result, "result_digest", "0" * 64)
    with pytest.raises(ra.ComparisonResultAttestationContractError, match="recomputed"):
        sr.result_digest
    with pytest.raises(ra.ComparisonResultAttestationContractError, match="recomputed"):
        sr.signing_payload()
    # The verifier refuses the same object as not the caller's result.
    r = verify(verifier(anchor_of(engine_signer())), sr)
    assert r.refusal_reason is R.RESULT_MISMATCH
    assert "no longer projects" in r.detail


def test_a_wrapped_result_whose_assessments_were_swapped_after_signing_refuses():
    """The assessments are bound through ``result_digest``: swapping them makes the
    stored self-digest disagree with the recomputed one."""

    sr = signed()
    object.__setattr__(sr.result, "assessments", (assessment(assessment_id="a.swapped"),))
    with pytest.raises(ra.ComparisonResultAttestationContractError, match="recomputed"):
        sr.result_digest


def test_the_callers_result_with_different_assessments_is_a_different_result():
    sr = signed()
    other = result(assessment(assessment_id="a.other"))
    assert other.result_digest != sr.result_digest
    r = verify(verifier(anchor_of(engine_signer())), sr, res=other)
    assert r.refusal_reason is R.RESULT_MISMATCH
    assert r.result_digest == other.result_digest  # the caller's own, always


def test_the_result_is_held_by_exact_type_never_a_look_alike():
    from ugence_reasoning_method_governance.api import ReadinessComparisonResult

    class Sub(ReadinessComparisonResult):
        pass

    res = result()
    sub = Sub(**{f.name: getattr(res, f.name) for f in dataclasses.fields(res)})
    with pytest.raises(ra.ComparisonResultAttestationContractError, match="exactly ReadinessComparisonResult"):
        ra.sign_comparison_result(sub, signer=engine_signer(), signed_at=SIGNED_AT)
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        verify(verifier(anchor_of(engine_signer())), signed(), res=sub)


def test_the_role_is_inside_the_signed_bytes_and_inside_the_coordinate():
    sr = signed()
    payload = sr.signing_payload()
    assert payload["signer_role"] == "COMPARISON_ENGINE"
    assert payload["signer_identity"] == payload["result"]["engine_identity"] == ENGINE_ID
    assert "signer_role" in ra.COMPARISON_RESULT_SIGNED_FIELDS
    coordinate = ra.comparison_result_signer_coordinate(
        role=ENGINE, signer_identity=ENGINE_ID, signer_key_id="engine-key-1"
    )
    assert coordinate.capability is ra.TrustAnchorCapability.COMPARISON_RESULT_ATTESTATION
    assert coordinate.authority_id == ENGINE_ID
