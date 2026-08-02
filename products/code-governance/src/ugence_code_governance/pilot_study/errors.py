"""Typed, fail-closed errors for the shadow-pilot validation study (MVP 1F)."""
from __future__ import annotations

from ..errors import CodeGovernanceError


class PilotStudyError(CodeGovernanceError):
    """Base for pilot-study failures."""


class StudyManifestError(PilotStudyError):
    """A pilot study manifest was rejected (fail closed)."""


class StudyAmendmentError(PilotStudyError):
    """An amendment attempted to rewrite prior results or was malformed."""


class AnnotationError(PilotStudyError):
    """A reviewer annotation was rejected (cross-tenant, unknown eval, etc.)."""


class EvidencePackError(PilotStudyError):
    """An evidence pack could not be built or verified."""


class PilotSafetyBlocked(PilotStudyError):
    """A security or integrity failure blocks pilot continuation/analysis."""


__all__ = [
    "PilotStudyError", "StudyManifestError", "StudyAmendmentError", "AnnotationError",
    "EvidencePackError", "PilotSafetyBlocked",
]
