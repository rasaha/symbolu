"""Stdlib-only validation helpers shared by the orchestration shapes.

They mirror the package's existing contract discipline — sequences coerced to
real tuples (scalar substitutes rejected), digests as lowercase sha-256 hex,
timestamps timezone-aware, canonical serialization as sorted-key JSON + sha-256
— and surface every rejection as :class:`ReadinessAssessmentError` so a caller
of the orchestration boundary sees one error type.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

from ..contracts.errors import ReadinessContractError
from .errors import ReadinessAssessmentError

__all__ = [
    "as_assessment_error",
    "require_str",
    "require_bool",
    "require_nonempty_str",
    "require_digest_token",
    "digest_payload",
    "iso_or_none",
]

_HEX = frozenset("0123456789abcdef")


def as_assessment_error(fn, *args, **kwargs):
    """Run a shared contract helper, re-typing its rejection for this boundary."""

    try:
        return fn(*args, **kwargs)
    except ReadinessAssessmentError:
        raise
    except ReadinessContractError as exc:
        raise ReadinessAssessmentError(str(exc)) from exc


def require_str(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise ReadinessAssessmentError(f"{name} must be a string")


def require_bool(value: object, name: str) -> None:
    if not isinstance(value, bool):
        raise ReadinessAssessmentError(f"{name} must be a bool")


def require_nonempty_str(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ReadinessAssessmentError(f"{name} must be a non-empty string")


def require_digest_token(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise ReadinessAssessmentError(f"{name} must be a lowercase 64-char sha-256 hex digest")


def digest_payload(payload: dict) -> str:
    """Deterministic sha-256 over a sorted-key, separator-fixed JSON payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def iso_or_none(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None
