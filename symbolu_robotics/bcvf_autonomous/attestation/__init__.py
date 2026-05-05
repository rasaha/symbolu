"""Sensor attestation interface — closes the UN ECE R155
cybersecurity loop the adversarial family opened.

Public surface (provisional, see ``API_STABILITY.md`` §2.2 +
``SENSOR_ATTESTATION_DESIGN.md`` §8):

* :class:`SensorAttestation` — typed per-message attestation
  record (signature + nonce + issued_at + data_digest).
* :class:`SensorAttestationPolicy` — per-predictor verification
  policy (firmware allowlist + freshness/replay windows + key
  ID + enabled flag).
* :class:`AttestationResult` — typed verdict from
  :meth:`SensorAttestationVerifier.verify`.
* :class:`SensorAttestationVerifier` — runs the seven §4
  checks per attestation; emits typed results the integrator
  unions into the existing per-predictor exclusion mask.
* :func:`compute_data_digest` — sender-side helper to bind an
  attestation to its trajectory tensor.
* :func:`canonical_signing_payload` — sender-side helper for
  the HMAC-SHA256 input.
* :func:`sign_attestation` — sender-side reference HMAC
  signer (the verifier's symmetric counterpart).
* :class:`AttestationError` / :class:`UnknownPredictorError` /
  :class:`AttestationVerificationError` — exception hierarchy.

See ``SENSOR_ATTESTATION_DESIGN.md`` for the full design.
"""

from .errors import (
    AttestationError,
    AttestationVerificationError,
    UnknownPredictorError,
)
from .interface import (
    AttestationResult,
    SensorAttestation,
    SensorAttestationPolicy,
    canonical_signing_payload,
    compute_data_digest,
    sign_attestation,
)
from .verifier import SensorAttestationVerifier


__all__ = [
    # Records
    "SensorAttestation",
    "SensorAttestationPolicy",
    "AttestationResult",
    # Verifier
    "SensorAttestationVerifier",
    # Sender-side helpers
    "compute_data_digest",
    "canonical_signing_payload",
    "sign_attestation",
    # Errors
    "AttestationError",
    "UnknownPredictorError",
    "AttestationVerificationError",
]
