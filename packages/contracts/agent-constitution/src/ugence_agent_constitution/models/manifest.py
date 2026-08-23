"""The agent role manifest — the drafting artifact.

A manifest is where a role is worked out. It is explicitly **not** a
constitution: it is not ratified, it is not authority-bearing, and nothing may
treat it as binding. That distinction is the reason the two are separate types
rather than one type with a ``ratified`` flag, which is exactly the sort of field
that gets set to ``True`` by a caller in a hurry.

"Mutable draft" and "frozen model" are reconciled by copy-on-write: the instance
is immutable, and :meth:`AgentRoleManifest.revise` returns a *new* manifest with
``draft_revision`` incremented. Editing is therefore always a new value with a
new digest, and no already-digested draft can change under a reader's feet.
"""

from __future__ import annotations

from typing import Any, ClassVar, Tuple

from ..version import AGENT_ROLE_MANIFEST_V1
from .capability import CapabilityRequirement
from .common import FrozenArtifact

class AgentRoleManifest(FrozenArtifact):
    """A mutable-by-revision drafting artifact for an agent role. Carries no authority."""

    DIGEST_EXCLUDED_FIELDS: ClassVar[frozenset] = frozenset({"draft_digest"})

    schema_version: str = AGENT_ROLE_MANIFEST_V1
    manifest_id: str
    draft_revision: int = 0
    role_name: str
    role_summary: str
    author_id: str
    capability_requirements: Tuple[CapabilityRequirement, ...] = ()
    prohibited_actions: Tuple[str, ...] = ()
    notes: str = ""
    #: Digest of this draft revision's content. Excluded from its own scope.
    draft_digest: str = ""

    #: Permanently ``False``. A manifest is never authority-bearing, at any
    #: revision, under any issuer, in any build of this package.
    carries_authority: ClassVar[bool] = False
    #: Permanently ``False``. Ratification produces an :class:`AgentConstitution`;
    #: it never converts a manifest into one in place.
    is_ratified: ClassVar[bool] = False

    def revise(self, **changes: Any) -> "AgentRoleManifest":
        """Return the next draft revision with ``changes`` applied.

        The revision counter is advanced automatically and the stale
        ``draft_digest`` is cleared, so a revised draft never carries the previous
        revision's digest. Callers re-stamp it via :meth:`with_draft_digest`.
        """
        if "draft_revision" in changes:
            raise ValueError(
                "draft_revision is advanced by revise(); it is not a caller-set field"
            )
        payload = self.model_dump(mode="python")
        payload.update(changes)
        payload["draft_revision"] = self.draft_revision + 1
        payload["draft_digest"] = ""
        return type(self).model_validate(payload)

    def with_draft_digest(self) -> "AgentRoleManifest":
        """Return this draft with ``draft_digest`` set to its recomputed digest."""
        from ..fingerprint import compute_content_digest

        return self.model_copy(update={"draft_digest": compute_content_digest(self)})

    @property
    def requirement_ids(self) -> Tuple[str, ...]:
        """Declared requirement identifiers, in declaration order (duplicates kept)."""
        return tuple(r.requirement_id for r in self.capability_requirements)

__all__ = ["AgentRoleManifest"]
