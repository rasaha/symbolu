"""Exceptions raised by the sensor-attestation framework.

Three layers:

* :class:`AttestationError` — base class. A buyer's
  attestation-handling script can ``except AttestationError``
  to catch every attestation-specific failure without
  catching unrelated ``ValueError`` slips.
* :class:`UnknownPredictorError` — subclass raised when a
  caller submits an attestation for a predictor name that
  has no corresponding policy in the verifier. Distinct from
  a verification failure because the integrator likely has a
  configuration bug, not a security incident.
* :class:`AttestationVerificationError` — subclass raised by
  callers who want to escalate a verify-failed result to an
  exception (the framework's :meth:`verify` returns a typed
  result, not an exception, so the caller decides whether to
  escalate).
"""

from __future__ import annotations


class AttestationError(Exception):
    """Base class for sensor-attestation errors.

    Raised on:

    * Malformed :class:`SensorAttestation` / :class:`SensorAttestationPolicy`
      construction (missing fields, non-ISO-8601 timestamps,
      negative window seconds).
    * Verifier construction with malformed policy mapping.
    * Key resolver returning non-bytes / empty key.
    """


class UnknownPredictorError(AttestationError):
    """Raised when an attestation references a predictor name
    not present in the verifier's policy map. The integrator
    most likely has a configuration bug — they're verifying
    against the wrong calibration set, or the sensor stack
    started publishing a predictor the policy doesn't cover.
    Surfaces loud rather than silently treating an
    unconfigured predictor as a verification failure."""


class AttestationVerificationError(AttestationError):
    """Raised by callers who choose to escalate an
    :class:`AttestationResult` ``passed=False`` to an exception.

    The framework's :meth:`verify` method itself does NOT
    raise this — it returns a typed result with the
    ``failure_reason`` named. The caller decides whether to
    escalate, mirroring the discipline established by
    :class:`BudgetViolationError` in the real-time-budget
    framework.
    """
