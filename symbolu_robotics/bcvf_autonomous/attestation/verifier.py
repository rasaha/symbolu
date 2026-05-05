"""``SensorAttestationVerifier`` — the gate that runs the
seven §4 verification checks per attestation.

Designed to compose with the existing per-predictor exclusion
path. The verifier emits a typed :class:`AttestationResult`
per call; the integrator unions ``not result.passed`` into the
``is_excluded`` mask the trust computer already consumes —
attestation-driven exclusion stacks with deadline-driven +
state-machine-driven exclusion via the same surface.

See ``SENSOR_ATTESTATION_DESIGN.md`` §4 + §5 for the design.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import (
    Callable,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from .errors import AttestationError, UnknownPredictorError
from .interface import (
    AttestationResult,
    SensorAttestation,
    SensorAttestationPolicy,
    canonical_signing_payload,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SensorAttestationVerifier:
    """Per-predictor attestation gate.

    Args:
        policies: mapping from predictor_name → policy. The
            verifier iterates this dict at construction to
            validate each policy's predictor_name matches its
            key.
        key_resolver: callable mapping ``key_id`` → key bytes.
            The integrator wires this to their HSM / TPM /
            secure-enclave; the framework explicitly does not
            hold key material.
        clock: callable returning a unix-time float. Defaults
            to :func:`time.time`. Tests inject a fake clock for
            determinism.

    Usage:

        verifier = SensorAttestationVerifier(
            policies={"M1": policy_m1, "M2": policy_m2, ...},
            key_resolver=my_hsm.get_key,
        )
        result = verifier.verify(
            attestation, expected_data_digest=digest,
        )
        if not result.passed:
            log.warning("attestation failed: %s", result.failure_reason)
            mask[predictor_index] = True   # exclude from consensus
    """

    def __init__(
        self,
        policies: Mapping[str, SensorAttestationPolicy],
        key_resolver: Callable[[str], bytes],
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(policies, Mapping):
            raise AttestationError(
                f"policies must be a Mapping; got "
                f"{type(policies).__name__}"
            )
        if not callable(key_resolver):
            raise AttestationError(
                "key_resolver must be a callable (key_id) -> bytes"
            )
        # Defensive copy so an external mutation doesn't change
        # the verifier's policy view mid-flight.
        self._policies: Dict[str, SensorAttestationPolicy] = {}
        for name, policy in policies.items():
            if not isinstance(policy, SensorAttestationPolicy):
                raise AttestationError(
                    f"policies[{name!r}] must be a SensorAttestationPolicy; "
                    f"got {type(policy).__name__}"
                )
            if policy.predictor_name != name:
                raise AttestationError(
                    f"policy mapping key {name!r} must match "
                    f"policy.predictor_name {policy.predictor_name!r}"
                )
            self._policies[name] = policy
        self._key_resolver = key_resolver
        self._clock = clock
        # Replay cache: per-predictor OrderedDict mapping nonce
        # → wall-clock when first seen. Bounded by the policy's
        # replay_window_seconds — entries older than the window
        # are evicted on access. OrderedDict preserves insertion
        # order so eviction walks oldest-first.
        self._replay_cache: Dict[str, "OrderedDict[str, float]"] = {
            name: OrderedDict() for name in self._policies
        }

    # ----- public properties ----- #

    @property
    def policies(self) -> Mapping[str, SensorAttestationPolicy]:
        return dict(self._policies)

    @property
    def n_replay_cache_entries(self) -> int:
        """Total count of nonce entries across all per-predictor
        caches. Useful for monitoring cache growth in tests +
        in production."""
        return sum(len(c) for c in self._replay_cache.values())

    # ----- single verify ----- #

    def verify(
        self,
        attestation: SensorAttestation,
        *,
        expected_data_digest: str,
    ) -> AttestationResult:
        """Run the seven §4 checks. Returns a typed
        :class:`AttestationResult` with ``passed=True`` only if
        every check passes; otherwise ``passed=False`` +
        ``failure_reason`` names the first failed check."""
        if not isinstance(attestation, SensorAttestation):
            raise AttestationError(
                f"attestation must be a SensorAttestation; got "
                f"{type(attestation).__name__}"
            )
        if not isinstance(expected_data_digest, str):
            raise AttestationError(
                f"expected_data_digest must be a str; got "
                f"{type(expected_data_digest).__name__}"
            )
        verified_at = _utc_now_iso()
        # Check 1: policy lookup. Unknown predictor surfaces as
        # an exception (configuration bug, not a security
        # incident).
        policy = self._policies.get(attestation.predictor_name)
        if policy is None:
            raise UnknownPredictorError(
                f"no policy for predictor {attestation.predictor_name!r}; "
                "verifier was constructed without this predictor in its "
                "policy map"
            )
        # Check 2: policy-disabled short-circuit.
        if not policy.enabled:
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=True,
                failure_reason=None,
                policy_enabled=False,
                verified_at=verified_at,
            )
        # Check 3: firmware allowlist (skip if empty = accept any).
        if (
            policy.accepted_firmware_versions
            and attestation.firmware_version
                not in policy.accepted_firmware_versions
        ):
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=False,
                failure_reason="firmware_version_not_in_allowlist",
                policy_enabled=True,
                verified_at=verified_at,
            )
        # Check 4: freshness.
        try:
            issued_at_ts = datetime.fromisoformat(
                attestation.issued_at
            ).timestamp()
        except ValueError:
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=False,
                failure_reason="issued_at_not_iso_8601",
                policy_enabled=True,
                verified_at=verified_at,
            )
        now = self._clock()
        age_s = now - issued_at_ts
        if age_s > policy.freshness_window_seconds:
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=False,
                failure_reason="attestation_expired",
                policy_enabled=True,
                verified_at=verified_at,
            )
        if age_s < -policy.freshness_window_seconds:
            # Future-dated by more than the freshness window —
            # likely a clock-skew attack or a misconfigured
            # signer. Reject loud rather than silently accept.
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=False,
                failure_reason="attestation_future_dated",
                policy_enabled=True,
                verified_at=verified_at,
            )
        # Check 5: replay. Evict expired entries from this
        # predictor's cache first, then check the nonce.
        cache = self._replay_cache[attestation.predictor_name]
        cutoff = now - policy.replay_window_seconds
        while cache and next(iter(cache.values())) < cutoff:
            cache.popitem(last=False)
        if attestation.nonce in cache:
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=False,
                failure_reason="nonce_replayed",
                policy_enabled=True,
                verified_at=verified_at,
            )
        # Check 6: data binding.
        if attestation.data_digest != expected_data_digest:
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=False,
                failure_reason="data_digest_mismatch",
                policy_enabled=True,
                verified_at=verified_at,
            )
        # Check 7: HMAC signature. Use compare_digest for
        # constant-time comparison (timing-attack safe).
        try:
            key = self._key_resolver(policy.key_id)
        except Exception as exc:
            raise AttestationError(
                f"key_resolver raised resolving key_id "
                f"{policy.key_id!r}: {exc}"
            ) from exc
        if not isinstance(key, (bytes, bytearray)):
            raise AttestationError(
                f"key_resolver returned non-bytes for key_id "
                f"{policy.key_id!r}; got {type(key).__name__}"
            )
        if not key:
            raise AttestationError(
                f"key_resolver returned empty key for key_id "
                f"{policy.key_id!r}"
            )
        payload = canonical_signing_payload(
            predictor_name=attestation.predictor_name,
            firmware_version=attestation.firmware_version,
            nonce=attestation.nonce,
            issued_at=attestation.issued_at,
            data_digest=attestation.data_digest,
        )
        expected_signature = hmac.new(
            bytes(key), payload, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, attestation.signature):
            return AttestationResult(
                predictor_name=attestation.predictor_name,
                passed=False,
                failure_reason="signature_mismatch",
                policy_enabled=True,
                verified_at=verified_at,
            )
        # All checks passed — record the nonce in the replay
        # cache before returning.
        cache[attestation.nonce] = now
        return AttestationResult(
            predictor_name=attestation.predictor_name,
            passed=True,
            failure_reason=None,
            policy_enabled=True,
            verified_at=verified_at,
        )

    # ----- batch verify ----- #

    def verify_batch(
        self,
        attestations: Sequence[SensorAttestation],
        *,
        expected_data_digests: Sequence[str],
    ) -> Tuple[AttestationResult, ...]:
        """Convenience: verify a sequence of attestations
        against a parallel sequence of expected digests. The
        sequences must have the same length; otherwise raises
        :class:`AttestationError` (a count mismatch is a caller
        bug, not a security incident).
        """
        if len(attestations) != len(expected_data_digests):
            raise AttestationError(
                f"attestations length {len(attestations)} does not match "
                f"expected_data_digests length {len(expected_data_digests)}"
            )
        return tuple(
            self.verify(att, expected_data_digest=digest)
            for att, digest in zip(attestations, expected_data_digests)
        )
