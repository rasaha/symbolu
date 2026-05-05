"""Behavioural tests for the sensor-attestation framework.

The framework is the §9-row-#8 industry-features-roadmap pick
+ the LAST roadmap-token entry to be removed from
``_ROADMAP_TOKENS``. These tests pin the load-bearing
contracts:

* :class:`SensorAttestation` validates every field at
  construction (non-empty + non-whitespace + 64-hex-char
  digests).
* :class:`SensorAttestationPolicy` validates positive windows
  + non-empty firmware names + non-empty predictor name.
* :class:`SensorAttestationVerifier` runs the seven §4 checks
  in order, emitting typed results with named failure reasons.
* The seven failure reasons (firmware allowlist, freshness,
  future-dating, replay, data-digest mismatch, signature
  mismatch, plus the policy-disabled short-circuit) each have
  a regression test.
* HMAC compare uses ``hmac.compare_digest`` (constant-time);
  pinned by behaviour test rather than implementation
  inspection.
* Replay-cache eviction respects the policy's
  ``replay_window_seconds`` (entries older than the window
  evict on next access).
* Composition with the existing per-predictor exclusion path:
  a verifier output ``not result.passed`` unioned into the
  ``is_excluded`` mask the trust computer consumes.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.attestation import (
    AttestationError,
    AttestationResult,
    AttestationVerificationError,
    SensorAttestation,
    SensorAttestationPolicy,
    SensorAttestationVerifier,
    UnknownPredictorError,
    canonical_signing_payload,
    compute_data_digest,
    sign_attestation,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_TEST_KEY = b"\x00" * 32  # deterministic key for test fixtures


def _key_resolver(key_id: str) -> bytes:
    if key_id == "test_key":
        return _TEST_KEY
    return b""


def _make_attestation(
    predictor_name: str = "M1",
    firmware_version: str = "v1.2",
    nonce: str = None,
    issued_at: str = None,
    trajectory: np.ndarray = None,
) -> tuple[SensorAttestation, str]:
    """Build a valid SensorAttestation + return (attestation,
    expected_data_digest) for use with verifier.verify."""
    if nonce is None:
        nonce = secrets.token_hex(16)
    if issued_at is None:
        issued_at = datetime.now(timezone.utc).isoformat()
    if trajectory is None:
        trajectory = np.zeros((2, 5, 3))
    data_digest = compute_data_digest(trajectory)
    sig = sign_attestation(
        predictor_name=predictor_name,
        firmware_version=firmware_version,
        nonce=nonce,
        issued_at=issued_at,
        data_digest=data_digest,
        key=_TEST_KEY,
    )
    return (
        SensorAttestation(
            predictor_name=predictor_name,
            firmware_version=firmware_version,
            signature=sig,
            nonce=nonce,
            issued_at=issued_at,
            data_digest=data_digest,
        ),
        data_digest,
    )


def _make_verifier(
    policies: dict = None,
    clock=None,
) -> SensorAttestationVerifier:
    if policies is None:
        policies = {
            "M1": SensorAttestationPolicy(
                predictor_name="M1",
                accepted_firmware_versions=("v1.2", "v1.3"),
                key_id="test_key",
            ),
        }
    kwargs = {"policies": policies, "key_resolver": _key_resolver}
    if clock is not None:
        kwargs["clock"] = clock
    return SensorAttestationVerifier(**kwargs)


# --------------------------------------------------------------------------- #
# SensorAttestation construction + validation
# --------------------------------------------------------------------------- #


def test_attestation_construction_with_valid_fields_succeeds():
    att, digest = _make_attestation()
    assert att.predictor_name == "M1"
    assert att.firmware_version == "v1.2"
    assert len(att.signature) == 64
    assert len(att.data_digest) == 64


def test_attestation_rejects_empty_predictor_name():
    with pytest.raises(AttestationError, match="predictor_name"):
        SensorAttestation(
            predictor_name="",
            firmware_version="v1.2",
            signature="0" * 64,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_attestation_rejects_whitespace_only_firmware_version():
    with pytest.raises(AttestationError, match="firmware_version"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="   ",
            signature="0" * 64,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_attestation_rejects_short_signature():
    with pytest.raises(AttestationError, match="64 hex characters"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="abc123",  # not 64 hex
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_attestation_rejects_non_hex_signature():
    with pytest.raises(AttestationError, match="hex"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="z" * 64,  # 64 chars but not hex
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_attestation_rejects_non_iso_8601_issued_at():
    with pytest.raises(AttestationError, match="ISO 8601"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="0" * 64,
            nonce="n",
            issued_at="yesterday",
            data_digest="0" * 64,
        )


def test_attestation_rejects_short_data_digest():
    with pytest.raises(AttestationError, match="64 hex characters"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="0" * 64,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="abc",  # not 64 hex
        )


def test_attestation_to_dict_round_trips():
    att, _ = _make_attestation()
    d = att.to_dict()
    att2 = SensorAttestation.from_dict(d)
    assert att2.signature == att.signature
    assert att2.data_digest == att.data_digest


def test_attestation_from_dict_rejects_missing_fields():
    att, _ = _make_attestation()
    payload = att.to_dict()
    del payload["signature"]
    with pytest.raises(AttestationError, match="missing"):
        SensorAttestation.from_dict(payload)


# --------------------------------------------------------------------------- #
# SensorAttestationPolicy construction + validation
# --------------------------------------------------------------------------- #


def test_policy_construction_with_defaults():
    policy = SensorAttestationPolicy(predictor_name="M1")
    assert policy.predictor_name == "M1"
    assert policy.enabled is True
    assert policy.freshness_window_seconds == 300.0
    assert policy.replay_window_seconds == 600.0


def test_policy_rejects_empty_predictor_name():
    with pytest.raises(AttestationError, match="predictor_name"):
        SensorAttestationPolicy(predictor_name="")


def test_policy_rejects_non_positive_freshness_window():
    with pytest.raises(AttestationError, match="freshness_window_seconds"):
        SensorAttestationPolicy(
            predictor_name="M1", freshness_window_seconds=0
        )


def test_policy_rejects_non_positive_replay_window():
    with pytest.raises(AttestationError, match="replay_window_seconds"):
        SensorAttestationPolicy(
            predictor_name="M1", replay_window_seconds=-1
        )


def test_policy_rejects_non_string_firmware_version_entry():
    with pytest.raises(AttestationError, match="accepted_firmware_versions"):
        SensorAttestationPolicy(
            predictor_name="M1",
            accepted_firmware_versions=("v1.2", ""),
        )


def test_policy_rejects_non_tuple_firmware_versions():
    with pytest.raises(AttestationError, match="must be a tuple"):
        SensorAttestationPolicy(
            predictor_name="M1",
            accepted_firmware_versions=["v1.2"],  # type: ignore[arg-type]
        )


def test_policy_to_dict_round_trips():
    policy = SensorAttestationPolicy(
        predictor_name="M1",
        accepted_firmware_versions=("v1.2",),
        freshness_window_seconds=60.0,
    )
    d = policy.to_dict()
    policy2 = SensorAttestationPolicy.from_dict(d)
    assert policy2.predictor_name == "M1"
    assert policy2.accepted_firmware_versions == ("v1.2",)
    assert policy2.freshness_window_seconds == 60.0


# --------------------------------------------------------------------------- #
# Verifier construction
# --------------------------------------------------------------------------- #


def test_verifier_rejects_non_mapping_policies():
    with pytest.raises(AttestationError, match="Mapping"):
        SensorAttestationVerifier(
            policies=[],  # type: ignore[arg-type]
            key_resolver=_key_resolver,
        )


def test_verifier_rejects_non_callable_key_resolver():
    with pytest.raises(AttestationError, match="callable"):
        SensorAttestationVerifier(
            policies={"M1": SensorAttestationPolicy(predictor_name="M1")},
            key_resolver="not callable",  # type: ignore[arg-type]
        )


def test_verifier_rejects_policy_key_mismatch():
    """The mapping key must equal policy.predictor_name —
    catches a copy-paste error in the integrator's config."""
    with pytest.raises(AttestationError, match="must match"):
        SensorAttestationVerifier(
            policies={"M1": SensorAttestationPolicy(predictor_name="M2")},
            key_resolver=_key_resolver,
        )


# --------------------------------------------------------------------------- #
# Happy-path verification
# --------------------------------------------------------------------------- #


def test_verify_happy_path_passes():
    verifier = _make_verifier()
    att, digest = _make_attestation()
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is True
    assert result.failure_reason is None
    assert result.policy_enabled is True


def test_result_records_predictor_name_and_verified_at():
    verifier = _make_verifier()
    att, digest = _make_attestation()
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.predictor_name == "M1"
    assert result.verified_at  # ISO 8601 string


# --------------------------------------------------------------------------- #
# Failure-reason regression pins (one per check)
# --------------------------------------------------------------------------- #


def test_verify_unknown_predictor_raises():
    """Unknown predictor is a configuration bug, not a
    verification failure — surfaces as UnknownPredictorError
    rather than a passed=False result."""
    verifier = _make_verifier()
    att, digest = _make_attestation(predictor_name="UNKNOWN_M5")
    # The above _make_attestation signs M5; verifier has only M1.
    with pytest.raises(UnknownPredictorError, match="UNKNOWN_M5"):
        verifier.verify(att, expected_data_digest=digest)


def test_verify_policy_disabled_short_circuits_to_pass():
    """A disabled policy returns passed=True with
    policy_enabled=False so the audit trail captures the
    bypass."""
    policy = SensorAttestationPolicy(
        predictor_name="M1",
        enabled=False,
        key_id="test_key",
    )
    verifier = _make_verifier(policies={"M1": policy})
    att, digest = _make_attestation()
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is True
    assert result.policy_enabled is False
    assert result.failure_reason is None


def test_verify_firmware_not_in_allowlist_fails():
    policy = SensorAttestationPolicy(
        predictor_name="M1",
        accepted_firmware_versions=("v1.0", "v1.1"),  # not v1.2
        key_id="test_key",
    )
    verifier = _make_verifier(policies={"M1": policy})
    att, digest = _make_attestation(firmware_version="v1.2")
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is False
    assert result.failure_reason == "firmware_version_not_in_allowlist"


def test_verify_empty_firmware_allowlist_accepts_any():
    """Empty allowlist = test mode; accept any firmware
    version. Pinned so a contributor doesn't accidentally
    flip the semantics to reject-all."""
    policy = SensorAttestationPolicy(
        predictor_name="M1",
        accepted_firmware_versions=(),  # empty
        key_id="test_key",
    )
    verifier = _make_verifier(policies={"M1": policy})
    att, digest = _make_attestation(firmware_version="anything")
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is True


def test_verify_expired_attestation_fails():
    # Issued 1000 seconds ago; default freshness window 300s.
    old_iso = (
        datetime.now(timezone.utc).timestamp() - 1000.0
    )
    old_iso_str = datetime.fromtimestamp(
        old_iso, tz=timezone.utc
    ).isoformat()
    verifier = _make_verifier()
    att, digest = _make_attestation(issued_at=old_iso_str)
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is False
    assert result.failure_reason == "attestation_expired"


def test_verify_future_dated_attestation_fails():
    """Future-dated by more than the freshness window — likely
    a clock-skew attack or a misconfigured signer. Reject loud."""
    future_ts = datetime.now(timezone.utc).timestamp() + 1000.0
    future_iso = datetime.fromtimestamp(
        future_ts, tz=timezone.utc
    ).isoformat()
    verifier = _make_verifier()
    att, digest = _make_attestation(issued_at=future_iso)
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is False
    assert result.failure_reason == "attestation_future_dated"


def test_verify_replayed_nonce_fails():
    verifier = _make_verifier()
    att, digest = _make_attestation()
    # First verify passes.
    result1 = verifier.verify(att, expected_data_digest=digest)
    assert result1.passed is True
    # Same nonce — must fail with nonce_replayed.
    result2 = verifier.verify(att, expected_data_digest=digest)
    assert result2.passed is False
    assert result2.failure_reason == "nonce_replayed"


def test_verify_data_digest_mismatch_fails():
    """An attestation signed for one trajectory but presented
    with a different expected_digest fails the data-binding
    check — closes the swap-trajectory attack."""
    verifier = _make_verifier()
    att, _ = _make_attestation()
    bogus_digest = "f" * 64
    result = verifier.verify(att, expected_data_digest=bogus_digest)
    assert result.passed is False
    assert result.failure_reason == "data_digest_mismatch"


def test_verify_forged_signature_fails():
    """An attestation with a syntactically-valid but
    wrong-key signature fails the HMAC check."""
    verifier = _make_verifier()
    # Build attestation with a syntactically-valid hex signature
    # that does NOT match the real HMAC.
    nonce = secrets.token_hex(16)
    issued_at = datetime.now(timezone.utc).isoformat()
    digest = compute_data_digest(np.zeros((2, 5, 3)))
    att = SensorAttestation(
        predictor_name="M1",
        firmware_version="v1.2",
        signature="0" * 64,  # not the real HMAC
        nonce=nonce,
        issued_at=issued_at,
        data_digest=digest,
    )
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is False
    assert result.failure_reason == "signature_mismatch"


def test_verify_wrong_key_fails():
    """A signature signed with a different key fails the HMAC
    check — the HMAC key is the load-bearing secret."""
    other_key = b"\xff" * 32
    nonce = secrets.token_hex(16)
    issued_at = datetime.now(timezone.utc).isoformat()
    digest = compute_data_digest(np.zeros((2, 5, 3)))
    sig_other_key = sign_attestation(
        predictor_name="M1",
        firmware_version="v1.2",
        nonce=nonce,
        issued_at=issued_at,
        data_digest=digest,
        key=other_key,
    )
    att = SensorAttestation(
        predictor_name="M1",
        firmware_version="v1.2",
        signature=sig_other_key,
        nonce=nonce,
        issued_at=issued_at,
        data_digest=digest,
    )
    verifier = _make_verifier()
    result = verifier.verify(att, expected_data_digest=digest)
    assert result.passed is False
    assert result.failure_reason == "signature_mismatch"


# --------------------------------------------------------------------------- #
# Replay-cache eviction
# --------------------------------------------------------------------------- #


def test_replay_cache_evicts_old_entries():
    """Entries older than policy.replay_window_seconds evict
    on next access — the cache is bounded so a long-running
    process doesn't grow indefinitely."""
    clock_t = [1000.0]
    def fake_clock():
        return clock_t[0]

    # 60-second replay window. Audit-fix Finding 1 requires
    # replay_window_seconds >= freshness_window_seconds, so
    # tighten freshness too.
    policy = SensorAttestationPolicy(
        predictor_name="M1",
        accepted_firmware_versions=(),
        freshness_window_seconds=60.0,
        replay_window_seconds=60.0,
        key_id="test_key",
    )
    verifier = _make_verifier(policies={"M1": policy}, clock=fake_clock)

    # Verify at t=1000.
    issued_at1 = datetime.fromtimestamp(
        1000.0, tz=timezone.utc
    ).isoformat()
    att1, digest1 = _make_attestation(issued_at=issued_at1)
    r1 = verifier.verify(att1, expected_data_digest=digest1)
    assert r1.passed is True
    assert verifier.n_replay_cache_entries == 1

    # Advance to t=1100 (40s past the 60s window). Verify a
    # fresh attestation; old nonce should evict.
    clock_t[0] = 1100.0
    issued_at2 = datetime.fromtimestamp(
        1100.0, tz=timezone.utc
    ).isoformat()
    att2, digest2 = _make_attestation(issued_at=issued_at2)
    r2 = verifier.verify(att2, expected_data_digest=digest2)
    assert r2.passed is True
    # Old nonce evicted; new one in.
    assert verifier.n_replay_cache_entries == 1


def test_replay_cache_holds_within_window():
    """Within the replay window, the cache holds entries
    rather than evicting."""
    clock_t = [1000.0]
    def fake_clock():
        return clock_t[0]

    policy = SensorAttestationPolicy(
        predictor_name="M1",
        accepted_firmware_versions=(),
        replay_window_seconds=600.0,
        key_id="test_key",
    )
    verifier = _make_verifier(policies={"M1": policy}, clock=fake_clock)

    for i in range(3):
        clock_t[0] = 1000.0 + i * 10.0
        issued = datetime.fromtimestamp(
            clock_t[0], tz=timezone.utc
        ).isoformat()
        att, digest = _make_attestation(issued_at=issued)
        verifier.verify(att, expected_data_digest=digest)

    assert verifier.n_replay_cache_entries == 3


# --------------------------------------------------------------------------- #
# Batch verification
# --------------------------------------------------------------------------- #


def test_verify_batch_returns_per_attestation_results():
    verifier = _make_verifier(policies={
        "M1": SensorAttestationPolicy(
            predictor_name="M1",
            accepted_firmware_versions=("v1.2",),
            key_id="test_key",
        ),
        "M2": SensorAttestationPolicy(
            predictor_name="M2",
            accepted_firmware_versions=("v1.2",),
            key_id="test_key",
        ),
    })
    att1, d1 = _make_attestation(predictor_name="M1")
    att2, d2 = _make_attestation(predictor_name="M2")
    results = verifier.verify_batch(
        [att1, att2], expected_data_digests=[d1, d2],
    )
    assert len(results) == 2
    assert all(r.passed for r in results)


def test_verify_batch_rejects_count_mismatch():
    verifier = _make_verifier()
    att, d = _make_attestation()
    with pytest.raises(AttestationError, match="length"):
        verifier.verify_batch([att, att], expected_data_digests=[d])


# --------------------------------------------------------------------------- #
# Sender-side helpers
# --------------------------------------------------------------------------- #


def test_compute_data_digest_is_deterministic():
    arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    a = compute_data_digest(arr)
    b = compute_data_digest(arr)
    assert a == b
    assert len(a) == 64


def test_compute_data_digest_differs_for_different_inputs():
    a = compute_data_digest(np.zeros(5))
    b = compute_data_digest(np.ones(5))
    assert a != b


def test_compute_data_digest_invariant_under_dtype_upcast():
    """A float32 trajectory should produce the same digest as
    its float64 upcast — the digest is deliberately invariant
    under the integrator's downstream casting."""
    arr_32 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    arr_64 = arr_32.astype(np.float64)
    assert compute_data_digest(arr_32) == compute_data_digest(arr_64)


def test_canonical_signing_payload_rejects_pipe_in_field():
    """The pipe separator is reserved as the field delimiter;
    a field value containing '|' would create an ambiguous
    byte string an attacker could exploit."""
    with pytest.raises(AttestationError, match="pipe separator"):
        canonical_signing_payload(
            predictor_name="M|1",  # invalid
            firmware_version="v1.2",
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_sign_attestation_rejects_non_bytes_key():
    with pytest.raises(AttestationError, match="key must be bytes"):
        sign_attestation(
            predictor_name="M1",
            firmware_version="v1.2",
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
            key="not bytes",  # type: ignore[arg-type]
        )


def test_sign_attestation_rejects_empty_key():
    with pytest.raises(AttestationError, match="non-empty"):
        sign_attestation(
            predictor_name="M1",
            firmware_version="v1.2",
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
            key=b"",
        )


# --------------------------------------------------------------------------- #
# Composition with the existing exclusion path
# --------------------------------------------------------------------------- #


def test_verifier_output_unions_into_exclusion_mask():
    """Composition test: a list of AttestationResults from
    verify_batch unions into the boolean ``is_excluded`` mask
    the trust computer's set_exclusion accepts. Pinned so a
    future refactor of the result shape doesn't silently
    break the integration path."""
    verifier = _make_verifier(policies={
        "M1": SensorAttestationPolicy(
            predictor_name="M1",
            accepted_firmware_versions=("v1.2",),
            key_id="test_key",
        ),
        "M2": SensorAttestationPolicy(
            predictor_name="M2",
            accepted_firmware_versions=("v1.2",),
            key_id="test_key",
        ),
    })
    # M1 attestation valid; M2 has wrong firmware.
    att1, d1 = _make_attestation(predictor_name="M1", firmware_version="v1.2")
    att2, d2 = _make_attestation(predictor_name="M2", firmware_version="v9.9")
    results = verifier.verify_batch(
        [att1, att2], expected_data_digests=[d1, d2],
    )
    excluded_mask = np.array([not r.passed for r in results], dtype=bool)
    assert excluded_mask.tolist() == [False, True]


# --------------------------------------------------------------------------- #
# AttestationResult serialisation
# --------------------------------------------------------------------------- #


def test_attestation_result_to_dict_includes_all_fields():
    verifier = _make_verifier()
    att, digest = _make_attestation()
    result = verifier.verify(att, expected_data_digest=digest)
    d = result.to_dict()
    assert set(d.keys()) == {
        "predictor_name", "passed", "failure_reason",
        "policy_enabled", "verified_at",
    }


def test_attestation_verification_error_is_attestation_error_subclass():
    """Catching the base class catches the verification subclass."""
    assert issubclass(AttestationVerificationError, AttestationError)
    err = AttestationVerificationError("test")
    assert isinstance(err, AttestationError)
    assert issubclass(UnknownPredictorError, AttestationError)


# --------------------------------------------------------------------------- #
# HMAC discipline
# --------------------------------------------------------------------------- #


def test_verifier_uses_constant_time_compare():
    """The verifier MUST use ``hmac.compare_digest`` (constant-
    time) rather than ``==`` (variable-time) for the signature
    check — timing-attack discipline. Audit-fix Finding 7:
    the previous test only inspected source for the substring
    "hmac.compare_digest", which a refactor moving the call
    into a helper module + still importing both ``hmac`` and
    ``hmac.compare_digest`` could silently bypass. This
    behaviour-based pin patches ``hmac.compare_digest`` and
    asserts it was actually invoked during verify."""
    import hmac as hmac_mod
    from unittest import mock
    verifier = _make_verifier()
    att, digest = _make_attestation()
    real_compare = hmac_mod.compare_digest
    with mock.patch.object(
        hmac_mod, "compare_digest", side_effect=real_compare
    ) as patched:
        verifier.verify(att, expected_data_digest=digest)
        assert patched.called, (
            "verifier must call hmac.compare_digest at runtime; "
            "using `==` for signature comparison is a timing-attack "
            "vector"
        )


# --------------------------------------------------------------------------- #
# Audit-fix regression pins (post-v0.7.x critical-audit pass on §9-row-#8)
# --------------------------------------------------------------------------- #


def test_audit_fix_replay_window_must_be_ge_freshness_window():
    """Audit Finding 1 (HIGH): replay_window_seconds <
    freshness_window_seconds opens a replay window — a
    captured attestation is replayable in the gap between
    cache eviction (replay-window past first-seen) and
    freshness expiry (freshness-window past issued_at). The
    §4 replay check is the only thing protecting consensus
    from captured-and-replayed attestations; misconfiguration
    silently disabled it."""
    with pytest.raises(AttestationError, match="freshness_window"):
        SensorAttestationPolicy(
            predictor_name="M1",
            freshness_window_seconds=300.0,
            replay_window_seconds=60.0,  # < freshness — forbidden
        )


def test_audit_fix_naive_iso_timestamp_rejected():
    """Audit Finding 2 (HIGH): naive ISO 8601 timestamps were
    accepted but ``.timestamp()`` interprets them as host-
    local time — a verifier on UTC+05 sees a UTC-stamped
    attestation as 5h skewed, breaking freshness in a TZ-
    dependent way. Reject naive at construction; require
    timezone-aware ISO 8601."""
    with pytest.raises(AttestationError, match="timezone offset"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="0" * 64,
            nonce="n",
            issued_at="2026-05-05T12:00:00",  # naive — no offset
            data_digest="0" * 64,
        )


def test_audit_fix_aware_iso_timestamp_accepted():
    """Audit Finding 2 (companion): explicit timezone offset
    is accepted in multiple ISO 8601 formats."""
    for tz_suffix in ("+00:00", "-05:00", "+05:00"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="0" * 64,
            nonce="n",
            issued_at=f"2026-05-05T12:00:00{tz_suffix}",
            data_digest="0" * 64,
        )


def test_audit_fix_disabled_policy_records_nonce_in_replay_cache():
    """Audit Finding 3 (HIGH): when policy.enabled=False the
    verifier short-circuits to passed=True. Previously the
    nonce was NOT recorded in the cache, so an attestation
    captured during the disabled-rollout window could be
    replayed once enabled=True flipped on. Now the cache is
    updated even on disabled-policy passes."""
    clock_t = [1000.0]
    def fake_clock():
        return clock_t[0]
    issued_at = datetime.fromtimestamp(
        1000.0, tz=timezone.utc
    ).isoformat()
    policy_disabled = SensorAttestationPolicy(
        predictor_name="M1",
        accepted_firmware_versions=(),
        enabled=False,
        key_id="test_key",
    )
    verifier_disabled = _make_verifier(
        policies={"M1": policy_disabled}, clock=fake_clock,
    )
    att, digest = _make_attestation(issued_at=issued_at)
    # Pass under disabled policy.
    r1 = verifier_disabled.verify(att, expected_data_digest=digest)
    assert r1.passed is True
    assert r1.policy_enabled is False
    # The nonce must now be in the replay cache.
    assert verifier_disabled.n_replay_cache_entries == 1


def test_audit_fix_strict_hex_signature_rejected():
    """Audit Finding 4 (MEDIUM): ``int(s, 16)`` accepts ``+``,
    ``-``, ``_`` (PEP 515 underscores), leading whitespace —
    none of which are canonical hex. The §2 contract says
    "64 hex characters"; enforce that strictly."""
    # Leading +
    with pytest.raises(AttestationError, match="hex"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="+" + "0" * 63,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )
    # PEP 515 underscore digit-separator
    with pytest.raises(AttestationError, match="hex"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="0" * 32 + "_" + "0" * 31,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_audit_fix_strict_hex_data_digest_rejected():
    with pytest.raises(AttestationError, match="hex"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2",
            signature="0" * 64,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 32 + "_" + "0" * 31,
        )


def test_audit_fix_verified_at_uses_injected_clock():
    """Audit Finding 5 (MEDIUM): verified_at used wall-clock
    time, diverging from the freshness-math clock under tests
    that injected a fake clock. Now the same clock value
    drives freshness, replay, and verified_at — single
    time-of-check."""
    clock_t = [2000.0]
    def fake_clock():
        return clock_t[0]
    verifier = _make_verifier(clock=fake_clock)
    issued_at = datetime.fromtimestamp(
        2000.0, tz=timezone.utc
    ).isoformat()
    att, digest = _make_attestation(issued_at=issued_at)
    result = verifier.verify(att, expected_data_digest=digest)
    # verified_at should round-trip back to the fake clock's
    # timestamp.
    parsed = datetime.fromisoformat(result.verified_at)
    assert parsed.timestamp() == 2000.0


def test_audit_fix_control_chars_rejected_in_predictor_name():
    """Audit Finding 6: NUL byte in predictor_name causes
    log truncation in C-string-backed log shippers. Reject
    loud at construction."""
    with pytest.raises(AttestationError, match="control"):
        SensorAttestation(
            predictor_name="M1\x00malicious",
            firmware_version="v1.2",
            signature="0" * 64,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_audit_fix_zero_width_space_rejected_in_firmware_version():
    """Audit Finding 6 (companion): zero-width space (U+200B)
    in firmware_version is bytewise different from the
    visually-identical version a deployment partner thinks
    they put on the allowlist — would cause confusing
    `firmware_version_not_in_allowlist` failures. Reject."""
    with pytest.raises(AttestationError, match="control"):
        SensorAttestation(
            predictor_name="M1",
            firmware_version="v1.2​",
            signature="0" * 64,
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
        )


def test_audit_fix_short_key_rejected_by_signer():
    """Audit Finding 9: an 8-byte HMAC-SHA256 key gives
    ~2^64 brute-force resistance, not the 2^256 a deployment
    partner thinks they have. Reject at sign_attestation
    (sender side)."""
    with pytest.raises(AttestationError, match="32 bytes"):
        sign_attestation(
            predictor_name="M1",
            firmware_version="v1.2",
            nonce="n",
            issued_at="2026-05-05T12:00:00+00:00",
            data_digest="0" * 64,
            key=b"hunter12",  # 8 bytes — too short
        )


def test_audit_fix_short_key_rejected_by_verifier():
    """Audit Finding 9 (companion): defence-in-depth. A
    misconfigured key_resolver returning a short key is
    rejected by the verifier even if the sender-side check
    was bypassed (e.g., a custom subclass)."""
    def short_key_resolver(key_id: str) -> bytes:
        return b"hunter12"  # 8 bytes
    policy = SensorAttestationPolicy(
        predictor_name="M1",
        accepted_firmware_versions=(),
        key_id="weak_key",
    )
    verifier = SensorAttestationVerifier(
        policies={"M1": policy},
        key_resolver=short_key_resolver,
    )
    att, digest = _make_attestation()
    with pytest.raises(AttestationError, match="32 bytes"):
        verifier.verify(att, expected_data_digest=digest)


def test_audit_fix_replay_cache_survives_clock_rewind():
    """Audit Finding 7 (coverage): a clock rewind (NTP step
    back) leaves cache entries timestamped from the future
    that cannot evict until the clock catches up. Behaviour
    is fail-safe (the entries STAY in the cache → replay
    still detected) but not previously pinned."""
    clock_t = [2000.0]
    def fake_clock():
        return clock_t[0]
    verifier = _make_verifier(clock=fake_clock)
    issued_at = datetime.fromtimestamp(
        2000.0, tz=timezone.utc
    ).isoformat()
    att, digest = _make_attestation(issued_at=issued_at)
    r1 = verifier.verify(att, expected_data_digest=digest)
    assert r1.passed is True
    # Rewind the clock by 500s.
    clock_t[0] = 1500.0
    # Same nonce — must still be rejected as replay (cache
    # entry timestamped 2000 doesn't satisfy the eviction
    # predicate cache_value < now - replay_window = 1500-600
    # = 900). The fail-safe direction is correct: extra
    # protection during a clock rewind, not less.
    # We need a fresh issued_at for the freshness check to
    # pass at the new clock.
    new_issued = datetime.fromtimestamp(
        1500.0, tz=timezone.utc
    ).isoformat()
    att_replayed = SensorAttestation(
        predictor_name="M1",
        firmware_version="v1.2",
        signature=att.signature,
        nonce=att.nonce,  # SAME nonce
        issued_at=new_issued,
        data_digest=att.data_digest,
    )
    # The signature won't match the new issued_at, but the
    # replay check fires before signature — order matters.
    r2 = verifier.verify(att_replayed, expected_data_digest=digest)
    assert r2.passed is False
    assert r2.failure_reason == "nonce_replayed"
