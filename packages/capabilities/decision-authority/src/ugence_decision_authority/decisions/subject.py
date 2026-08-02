"""Value objects for the DecisionCase aggregate: subjects and versioned references.

A case never embeds another record; it *references* it by id **and explicit
version**. Keeping references versioned is what lets the aggregate link evidence,
assessments, recommendations, and decisions without collapsing them into one
object — the four-record separation is preserved by construction.
"""

from __future__ import annotations

from pydantic import model_validator

from ..base import DomainModel
from ..errors import DomainValidationError


class SubjectRef(DomainModel):
    """A reference to the subject of a case (e.g. a person or entity)."""

    subject_id: str
    subject_type: str = "subject"

    @model_validator(mode="after")
    def _validate(self) -> "SubjectRef":
        if not self.subject_id.strip():
            raise DomainValidationError("subject_id is required")
        return self


class VersionedRef(DomainModel):
    """An immutable reference to a specific *version* of another record.

    ``kind`` is a free label (``assessment``, ``policy``, ``recommendation``,
    ``decision``) used only for readability and audit; it is never interpreted.
    """

    ref_id: str
    version: int
    kind: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "VersionedRef":
        if not self.ref_id.strip():
            raise DomainValidationError("ref_id is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self
