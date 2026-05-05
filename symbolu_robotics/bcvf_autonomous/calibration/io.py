"""JSON I/O helpers for :class:`CalibrationSet`.

Mirrors the strict-validation discipline of
``analysis/io.py``, ``safety_case/sbom/``, and ``replay/``:
corrupt or tampered artifacts fail loudly at load time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

from .._version import __version__ as _autonomy_version
from .bundle import CalibrationSet
from .errors import CalibrationSetError, CalibrationVersionError


def save_calibration_set(
    calibration: CalibrationSet,
    path: Union[str, Path],
) -> None:
    """Write a :class:`CalibrationSet` to disk as canonical JSON
    (sorted keys, 2-space indent, trailing newline) so the
    output is diff-friendly and snapshot-stable.

    The on-disk JSON is human-readable; the `digest` field
    in the file is the same as `bundle.digest`. A field engineer
    opening the file can recompute `sha256` over the rest of
    the bundle (sorted-keys / no-whitespace canonical form) and
    verify integrity by hand.
    """
    path = Path(path)
    text = json.dumps(
        calibration.to_dict(), indent=2, sort_keys=True
    ) + "\n"
    path.write_text(text, encoding="utf-8")


def load_calibration_set(
    path: Union[str, Path],
    *,
    allow_version_drift: bool = False,
    verify_digest: bool = True,
) -> CalibrationSet:
    """Load a :class:`CalibrationSet` from disk.

    Strict validation:

    * Missing path raises :class:`CalibrationSetError`.
    * Invalid JSON raises :class:`CalibrationSetError`.
    * Missing required fields raise :class:`CalibrationSetError`.
    * Bad digest raises :class:`CalibrationDigestError`
      (subclass) — unless ``verify_digest=False`` for
      diagnostic-only loads.
    * Kernel version mismatch raises
      :class:`CalibrationVersionError` (subclass) — unless
      ``allow_version_drift=True`` for the explicit "I've
      verified the kernel changes don't affect my tuning" path.
    """
    path = Path(path)
    if not path.exists():
        raise CalibrationSetError(
            f"calibration bundle not found at {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CalibrationSetError(
            f"calibration bundle at {path} is not valid JSON: {exc}"
        ) from exc
    bundle = CalibrationSet.from_dict(payload, verify_digest=verify_digest)
    if not allow_version_drift and bundle.kernel_version != _autonomy_version:
        raise CalibrationVersionError(
            f"calibration kernel_version {bundle.kernel_version!r} "
            f"does not match running bcvf_autonomous version "
            f"{_autonomy_version!r}. Pass allow_version_drift=True if "
            "you've verified the kernel changes between record-time "
            "and load-time don't affect your tuning."
        )
    return bundle


def render_calibration_set_text(calibration: CalibrationSet) -> str:
    """Same canonical serialisation as :func:`save_calibration_set`
    but returns the string instead of writing. Used by tests +
    by callers wiring the bundle into other artifact pipelines."""
    return json.dumps(calibration.to_dict(), indent=2, sort_keys=True) + "\n"
