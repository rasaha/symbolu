"""Exceptions raised by the calibration framework.

Three layers:

* :class:`CalibrationSetError` — base class. A buyer's
  configuration-management script can ``except CalibrationSetError``
  to catch every calibration-specific failure without catching
  unrelated ``ValueError`` slips.
* :class:`CalibrationVersionError` — subclass raised when a
  bundle's ``kernel_version`` doesn't match the running
  ``bcvf_autonomous.__version__``. A calibration tuned against
  an older kernel may no longer be fit-for-purpose; the load
  surfaces the drift loud unless the caller explicitly opts
  out via ``allow_version_drift=True``.
* :class:`CalibrationDigestError` — subclass raised when a
  bundle's recorded ``digest`` does not match the SHA-256 of
  its canonical serialisation. Tamper / corruption detection.

The base class is the one a downstream caller catches; the
subclasses are the ones the test suite asserts on.
"""

from __future__ import annotations


class CalibrationSetError(Exception):
    """Base class for calibration-bundle errors.

    Raised on:

    * Missing required fields at bundle load time.
    * Whitespace-only / empty ``calibration_id`` /
      ``kernel_version``.
    * Non-ISO-8601 ``created_at``.
    * Embedded config dict that fails its source-dataclass
      validator (e.g. malformed BCVFConfig field).
    """


class CalibrationVersionError(CalibrationSetError):
    """Raised when a bundle's ``kernel_version`` doesn't match
    the running ``bcvf_autonomous.__version__``. The caller can
    override with ``allow_version_drift=True`` when they've
    verified the kernel changes don't affect their tuning."""


class CalibrationDigestError(CalibrationSetError):
    """Raised when a bundle's recorded ``digest`` does not match
    the SHA-256 of its canonical serialisation. Indicates either
    tampering, corruption, or a hand-edit to the JSON. The
    framework refuses to load the bundle in either case — a
    silently-loaded tampered bundle is the failure mode the
    digest discipline exists to prevent."""
