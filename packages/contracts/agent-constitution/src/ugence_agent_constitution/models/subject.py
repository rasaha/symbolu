"""The conformance subject — what *would* be assessed, not an assessment.

A subject names a thing (an implementation, a developer artifact, a deployment
candidate), pins the constitution version it claims to be governed by, and
declares which capability registry entries it says it uses.

AC-0 ships **no conformance evaluation**. There is no verdict field, no findings
collection, and no method that returns one, because a partially-implemented
assessment surface is the kind of thing that gets read as an assessment. The
class-level :data:`ConformanceSubject.conformance_evaluated` is permanently
``False`` and exists to say so in code rather than only in prose.
"""

from __future__ import annotations

from typing import ClassVar, Optional, Tuple

from ..version import CONFORMANCE_SUBJECT_V1
from .common import (
    CapabilityRegistryEntryRef,
    ConstitutionRef,
    ContentRef,
    FrozenArtifact,
    SubjectKind,
)


class ConformanceSubject(FrozenArtifact):
    """A declared subject of a future conformance assessment. Not an assessment."""

    DIGEST_EXCLUDED_FIELDS: ClassVar[frozenset] = frozenset({"content_digest"})

    schema_version: str = CONFORMANCE_SUBJECT_V1
    subject_id: str
    subject_kind: SubjectKind
    #: The constitution version this subject claims to be governed by.
    constitution_ref: ConstitutionRef
    #: The implementation contract this subject was built against, if any.
    contract_ref: Optional[ContentRef] = None
    #: What the subject *says* it uses. Unverified: nothing here resolves a registry.
    declared_capability_entries: Tuple[CapabilityRegistryEntryRef, ...] = ()
    description: str = ""
    content_digest: str = ""

    #: Permanently ``False``. AC-0 evaluates no subject and emits no finding.
    conformance_evaluated: ClassVar[bool] = False

    def with_content_digest(self) -> "ConformanceSubject":
        """Return this subject with ``content_digest`` set to its recomputed value."""
        from ..fingerprint import compute_content_digest

        return self.model_copy(update={"content_digest": compute_content_digest(self)})

    @property
    def declared_entry_tokens(self) -> Tuple[str, ...]:
        """Declared capability tokens, sorted for deterministic comparison."""
        return tuple(sorted(e.token for e in self.declared_capability_entries))


__all__ = ["ConformanceSubject"]
