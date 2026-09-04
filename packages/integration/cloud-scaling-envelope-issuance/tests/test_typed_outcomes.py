"""The outcome vocabulary is closed, partitioned and honest."""

from __future__ import annotations

from datetime import datetime, timezone

from risk_authority.api import VERIFIED, VerifiedArtifactBinding

from ugence_cloud_scaling_envelope_issuance import (
    REFUSING_STATUSES,
    REQUIRED_BINDING_KINDS,
    ArtifactBindingStatus,
    CloudScalingVerificationReport,
)


def test_exactly_one_status_is_a_pass_and_it_is_the_seams_word():
    passes = [s for s in ArtifactBindingStatus if s.value == VERIFIED]
    assert passes == [ArtifactBindingStatus.VERIFIED]
    assert REFUSING_STATUSES == frozenset(ArtifactBindingStatus) - {ArtifactBindingStatus.VERIFIED}
    assert len(REFUSING_STATUSES) >= 6


def test_a_report_is_all_verified_only_when_every_binding_says_so():
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ok = tuple(VerifiedArtifactBinding(k, "a" * 64, VERIFIED, at) for k in REQUIRED_BINDING_KINDS)
    assert CloudScalingVerificationReport(at, ok, VERIFIED, VERIFIED).all_verified
    one_bad = ok[:-1] + (VerifiedArtifactBinding(
        REQUIRED_BINDING_KINDS[-1], "a" * 64, ArtifactBindingStatus.CANDIDATE_NOT_REDERIVED.value, at),)
    assert not CloudScalingVerificationReport(at, one_bad, VERIFIED, VERIFIED).all_verified
    assert not CloudScalingVerificationReport(at, (), None, None).all_verified


def test_the_five_kinds_are_distinct_namespaced_tokens():
    assert len(set(REQUIRED_BINDING_KINDS)) == 5
    assert all(k.startswith("cloud-scaling.") and k == k.strip() for k in REQUIRED_BINDING_KINDS)
