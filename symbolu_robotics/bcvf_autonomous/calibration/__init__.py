"""Calibration parameter management + drift detection.

Public surface (provisional, see ``API_STABILITY.md`` §2.2 +
``CALIBRATION_DESIGN.md`` §8):

* :class:`CalibrationSet` — versioned, hash-identified,
  kernel-version-validated bundle of per-deployment tuning
  knobs.
* :func:`build_calibration_set` — factory wrapping in-memory
  config objects into a bundle.
* :func:`save_calibration_set` / :func:`load_calibration_set` —
  canonical-JSON round-trip with strict validation.
* :class:`CalibrationDriftDetector` — fires when live fleet
  aggregates leave the calibration's expected ranges.
* :class:`CalibrationDriftAlert` — typed verdict for one
  range violation.
* :class:`CalibrationSetError` /
  :class:`CalibrationVersionError` /
  :class:`CalibrationDigestError` — exception hierarchy.

See ``CALIBRATION_DESIGN.md`` for the full design.
"""

from .bundle import CalibrationSet, build_calibration_set
from .drift import CalibrationDriftAlert, CalibrationDriftDetector
from .errors import (
    CalibrationDigestError,
    CalibrationSetError,
    CalibrationVersionError,
)
from .io import (
    load_calibration_set,
    render_calibration_set_text,
    save_calibration_set,
)


__all__ = [
    # Bundle
    "CalibrationSet",
    "build_calibration_set",
    # Drift detector
    "CalibrationDriftDetector",
    "CalibrationDriftAlert",
    # I/O
    "load_calibration_set",
    "render_calibration_set_text",
    "save_calibration_set",
    # Errors
    "CalibrationSetError",
    "CalibrationVersionError",
    "CalibrationDigestError",
]
