"""Typed records for the sensor-attestation interface.

Three frozen dataclasses:

* :class:`SensorAttestation` — one per-message attestation a
  predictor (or its upstream sensor stack) attaches to its
  trajectory output. Validated at construction.
* :class:`SensorAttestationPolicy` — per-predictor verification
  policy the integrator distributes alongside their
  :class:`CalibrationSet`. Validated at construction.
* :class:`AttestationResult` — typed verdict from
  :meth:`SensorAttestationVerifier.verify`.

Plus stdlib-only helpers (:func:`compute_data_digest`,
:func:`canonical_signing_payload`) the integrator uses to
construct + sign attestations on the sender side.

See ``SENSOR_ATTESTATION_DESIGN.md`` for the full design.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .errors import AttestationError


# --------------------------------------------------------------------------- #
# Data-digest helper
# --------------------------------------------------------------------------- #


def compute_data_digest(trajectory: np.ndarray) -> str:
    """Compute a deterministic SHA-256 hex digest over a
    trajectory tensor. Binds the attestation to the data — an
    attacker can't swap the trajectory for a different one and
    keep the same attestation valid.

    The digest is computed over the trajectory's bytes after
    casting to ``np.float64`` + a C-contiguous layout — this
    makes the digest invariant under view / stride / dtype-
    upcast changes the integrator might apply downstream.
    """
    arr = np.ascontiguousarray(np.asarray(trajectory, dtype=np.float64))
    return hashlib.sha256(arr.tobytes()).hexdigest()


def canonical_signing_payload(
    *,
    predictor_name: str,
    firmware_version: str,
    nonce: str,
    issued_at: str,
    data_digest: str,
) -> bytes:
    """Build the canonical byte string the HMAC-SHA256 signs.

    Format: ``predictor_name|firmware_version|nonce|issued_at|data_digest``.
    The pipe separator + the field order are the load-bearing
    properties; an attacker who controls one field can't shift
    bytes between fields. Pinned by tests.
    """
    parts = [
        str(predictor_name),
        str(firmware_version),
        str(nonce),
        str(issued_at),
        str(data_digest),
    ]
    for part in parts:
        if "|" in part:
            raise AttestationError(
                f"attestation field {part!r} contains pipe separator '|'; "
                "the canonical signing format reserves '|' as the field "
                "delimiter. Reject loud rather than allow ambiguous bytes."
            )
    return "|".join(parts).encode("utf-8")


def sign_attestation(
    *,
    predictor_name: str,
    firmware_version: str,
    nonce: str,
    issued_at: str,
    data_digest: str,
    key: bytes,
) -> str:
    """Compute the HMAC-SHA256 hex digest a sender attaches to
    a :class:`SensorAttestation`'s ``signature`` field.

    This is the *sender-side* helper. The verifier uses
    :func:`hmac.compare_digest` (constant-time) against this
    output. Symmetric — same key signs + verifies.
    """
    if not isinstance(key, (bytes, bytearray)):
        raise AttestationError(
            f"key must be bytes; got {type(key).__name__}"
        )
    if not key:
        raise AttestationError("key must be non-empty")
    payload = canonical_signing_payload(
        predictor_name=predictor_name,
        firmware_version=firmware_version,
        nonce=nonce,
        issued_at=issued_at,
        data_digest=data_digest,
    )
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- #
# SensorAttestation — the per-message record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SensorAttestation:
    """One per-message attestation.

    See ``SENSOR_ATTESTATION_DESIGN.md`` §2 for the per-field
    rationale + the canonical signing payload format.
    """

    predictor_name: str
    firmware_version: str
    signature: str        # HMAC-SHA256 hex digest
    nonce: str
    issued_at: str        # ISO 8601
    data_digest: str      # SHA-256 hex over trajectory payload
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.predictor_name or not self.predictor_name.strip():
            raise AttestationError(
                "predictor_name must be a non-empty, non-whitespace string"
            )
        if not self.firmware_version or not self.firmware_version.strip():
            raise AttestationError(
                "firmware_version must be a non-empty, non-whitespace string"
            )
        if not self.signature or not self.signature.strip():
            raise AttestationError(
                "signature must be a non-empty, non-whitespace string"
            )
        # SHA-256 hex digest = 64 hex chars; HMAC-SHA256 hex = 64 hex chars.
        if len(self.signature) != 64:
            raise AttestationError(
                f"signature must be 64 hex characters (HMAC-SHA256); "
                f"got {len(self.signature)} characters"
            )
        try:
            int(self.signature, 16)
        except ValueError as exc:
            raise AttestationError(
                f"signature must be valid hex: {exc}"
            ) from exc
        if not self.nonce or not self.nonce.strip():
            raise AttestationError(
                "nonce must be a non-empty, non-whitespace string"
            )
        if not self.issued_at or not self.issued_at.strip():
            raise AttestationError(
                "issued_at must be a non-empty, non-whitespace ISO 8601 string"
            )
        try:
            datetime.fromisoformat(self.issued_at)
        except ValueError as exc:
            raise AttestationError(
                f"issued_at {self.issued_at!r} is not a valid ISO 8601 "
                f"timestamp: {exc}"
            ) from exc
        if not self.data_digest or len(self.data_digest) != 64:
            raise AttestationError(
                f"data_digest must be 64 hex characters (SHA-256); "
                f"got {len(self.data_digest)} characters"
            )
        try:
            int(self.data_digest, 16)
        except ValueError as exc:
            raise AttestationError(
                f"data_digest must be valid hex: {exc}"
            ) from exc
        if not isinstance(self.metadata, dict):
            raise AttestationError(
                f"metadata must be a dict; got "
                f"{type(self.metadata).__name__}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predictor_name": self.predictor_name,
            "firmware_version": self.firmware_version,
            "signature": self.signature,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "data_digest": self.data_digest,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SensorAttestation":
        if not isinstance(payload, dict):
            raise AttestationError(
                f"payload must be a dict; got {type(payload).__name__}"
            )
        required = {
            "predictor_name", "firmware_version", "signature",
            "nonce", "issued_at", "data_digest",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise AttestationError(
                f"attestation payload missing required fields: {missing}"
            )
        return cls(
            predictor_name=str(payload["predictor_name"]),
            firmware_version=str(payload["firmware_version"]),
            signature=str(payload["signature"]),
            nonce=str(payload["nonce"]),
            issued_at=str(payload["issued_at"]),
            data_digest=str(payload["data_digest"]),
            metadata=dict(payload.get("metadata", {})),
        )


# --------------------------------------------------------------------------- #
# SensorAttestationPolicy — per-predictor verification policy
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SensorAttestationPolicy:
    """Per-predictor verification policy the integrator
    distributes alongside the deployment's
    :class:`CalibrationSet`. See
    ``SENSOR_ATTESTATION_DESIGN.md`` §3 for the per-field
    rationale.
    """

    predictor_name: str
    accepted_firmware_versions: Tuple[str, ...] = ()
    freshness_window_seconds: float = 300.0
    replay_window_seconds: float = 600.0
    key_id: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.predictor_name or not self.predictor_name.strip():
            raise AttestationError(
                "predictor_name must be a non-empty, non-whitespace string"
            )
        if not isinstance(self.accepted_firmware_versions, tuple):
            raise AttestationError(
                f"accepted_firmware_versions must be a tuple; got "
                f"{type(self.accepted_firmware_versions).__name__}"
            )
        for v in self.accepted_firmware_versions:
            if not isinstance(v, str) or not v.strip():
                raise AttestationError(
                    f"accepted_firmware_versions entries must be non-empty "
                    f"non-whitespace strings; got {v!r}"
                )
        if self.freshness_window_seconds <= 0:
            raise AttestationError(
                f"freshness_window_seconds must be positive; got "
                f"{self.freshness_window_seconds}"
            )
        if self.replay_window_seconds <= 0:
            raise AttestationError(
                f"replay_window_seconds must be positive; got "
                f"{self.replay_window_seconds}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predictor_name": self.predictor_name,
            "accepted_firmware_versions": list(self.accepted_firmware_versions),
            "freshness_window_seconds": float(self.freshness_window_seconds),
            "replay_window_seconds": float(self.replay_window_seconds),
            "key_id": self.key_id,
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SensorAttestationPolicy":
        if not isinstance(payload, dict):
            raise AttestationError(
                f"policy payload must be a dict; got "
                f"{type(payload).__name__}"
            )
        return cls(
            predictor_name=str(payload["predictor_name"]),
            accepted_firmware_versions=tuple(
                str(v) for v in payload.get("accepted_firmware_versions", ())
            ),
            freshness_window_seconds=float(
                payload.get("freshness_window_seconds", 300.0)
            ),
            replay_window_seconds=float(
                payload.get("replay_window_seconds", 600.0)
            ),
            key_id=str(payload.get("key_id", "")),
            enabled=bool(payload.get("enabled", True)),
        )


# --------------------------------------------------------------------------- #
# AttestationResult — typed verdict from verify()
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AttestationResult:
    """The verdict of one :meth:`SensorAttestationVerifier.verify`
    call. ``failure_reason`` is ``None`` on pass; on fail, it
    names the first check that failed (so an audit trail
    captures *why* a predictor was excluded).
    """

    predictor_name: str
    passed: bool
    failure_reason: Optional[str]
    policy_enabled: bool
    verified_at: str   # ISO 8601

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predictor_name": self.predictor_name,
            "passed": bool(self.passed),
            "failure_reason": self.failure_reason,
            "policy_enabled": bool(self.policy_enabled),
            "verified_at": self.verified_at,
        }
