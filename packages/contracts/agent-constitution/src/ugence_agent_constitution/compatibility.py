"""Version-compatibility rules.

Two independent questions, deliberately not merged:

**Can this build read that shape?** — a *schema* version question. Answered by
:func:`schema_compatibility`. An unrecognized schema version is not rejected as
wrong; it is reported as undecidable, because a build that has never seen a shape
cannot know whether an artifact in that shape is well-formed. Guessing "probably
compatible" is the failure mode this rule exists to prevent.

**Is this artifact a legitimate successor to that one?** — an *artifact* version
question. Answered by :func:`succession_compatibility`. A successor must share
its predecessor's lineage identity, must bump its artifact version strictly
upward, and must actually differ in content. A "successor" that reuses its
predecessor's digest is not a new version of anything.

Semantic versions are compared as ``MAJOR.MINOR.PATCH`` integer triples. Only
release versions are accepted: pre-release and build-metadata suffixes are
refused rather than ordered, because their ordering rules are subtle enough that
a silent wrong answer is likelier than a right one, and this comparison decides
whether a governance artifact supersedes another.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from .errors import MalformedVersionError, UnknownArtifactKind
from .models.common import ArtifactKind
from .version import RETIRED_SCHEMA_VERSIONS, SUPPORTED_SCHEMA_VERSIONS


class SchemaCompatibility(str, Enum):
    """Whether this build can read an artifact declaring a given schema version."""

    #: Known and readable by this build.
    SUPPORTED = "SUPPORTED"
    #: Known to this build and deliberately retired. A hard refusal.
    RETIRED = "RETIRED"
    #: Never seen. Undecidable here — this build must not pretend to understand it.
    UNRECOGNIZED = "UNRECOGNIZED"


class SuccessionCompatibility(str, Enum):
    """Whether one artifact is a well-formed successor to another."""

    #: A legitimate successor: same lineage, strictly newer version, changed content.
    VALID_SUCCESSION = "VALID_SUCCESSION"
    #: The first artifact in a lineage; there is nothing to succeed.
    LINEAGE_ROOT = "LINEAGE_ROOT"
    #: The predecessor names a different lineage.
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    #: The artifact version was not bumped above the predecessor's.
    VERSION_NOT_BUMPED = "VERSION_NOT_BUMPED"
    #: Content is byte-identical to the predecessor; nothing was superseded.
    NO_MATERIAL_CHANGE = "NO_MATERIAL_CHANGE"
    #: A version string could not be ordered. Undecidable, so refused.
    UNORDERABLE_VERSION = "UNORDERABLE_VERSION"


def parse_semantic_version(value: str) -> Tuple[int, int, int]:
    """Parse ``MAJOR.MINOR.PATCH`` into an integer triple.

    Raises :class:`~.errors.MalformedVersionError` for anything else, including
    pre-release and build-metadata suffixes. See the module docstring for why
    those are refused rather than ordered.
    """
    if not isinstance(value, str):
        raise MalformedVersionError(f"not a version string: {value!r}")
    parts = value.split(".")
    if len(parts) != 3:
        raise MalformedVersionError(
            f"expected MAJOR.MINOR.PATCH, got {value!r}"
        )
    triple = []
    for part in parts:
        if not part.isdigit():
            raise MalformedVersionError(
                f"non-numeric or suffixed component {part!r} in {value!r}; "
                "pre-release and build-metadata versions are refused, not ordered"
            )
        triple.append(int(part))
    return (triple[0], triple[1], triple[2])


def is_semantic_version(value: str) -> bool:
    """True when ``value`` parses as a release ``MAJOR.MINOR.PATCH`` version."""
    try:
        parse_semantic_version(value)
    except MalformedVersionError:
        return False
    return True


def compare_artifact_versions(left: str, right: str) -> int:
    """Return ``-1``/``0``/``1`` ordering ``left`` against ``right``."""
    a, b = parse_semantic_version(left), parse_semantic_version(right)
    return (a > b) - (a < b)


def schema_compatibility(kind: ArtifactKind, declared: str) -> SchemaCompatibility:
    """Classify a declared schema version for one artifact kind.

    Raises :class:`~.errors.UnknownArtifactKind` for a kind outside the closed set —
    that is a caller bug, not data this package can be asked to judge.
    """
    try:
        key = ArtifactKind(kind).value
    except ValueError as exc:
        raise UnknownArtifactKind(f"no such artifact kind: {kind!r}") from exc
    if declared in SUPPORTED_SCHEMA_VERSIONS.get(key, ()):
        return SchemaCompatibility.SUPPORTED
    if declared in RETIRED_SCHEMA_VERSIONS.get(key, ()):
        return SchemaCompatibility.RETIRED
    return SchemaCompatibility.UNRECOGNIZED


def succession_compatibility(
    *,
    lineage_id: str,
    artifact_version: str,
    content_digest: str,
    predecessor_lineage_id: Optional[str],
    predecessor_version: Optional[str],
    predecessor_digest: Optional[str],
) -> SuccessionCompatibility:
    """Classify a candidate succession from its pinned predecessor coordinates.

    Takes plain coordinates rather than models so the rule can be applied to an
    artifact this package has not constructed — a payload being validated, or a
    predecessor known only from a stored reference.
    """
    if predecessor_lineage_id is None and predecessor_version is None and predecessor_digest is None:
        return SuccessionCompatibility.LINEAGE_ROOT
    if predecessor_lineage_id != lineage_id:
        return SuccessionCompatibility.LINEAGE_MISMATCH
    if not is_semantic_version(artifact_version) or not is_semantic_version(
        predecessor_version or ""
    ):
        return SuccessionCompatibility.UNORDERABLE_VERSION
    if compare_artifact_versions(artifact_version, predecessor_version or "") <= 0:
        return SuccessionCompatibility.VERSION_NOT_BUMPED
    if content_digest and content_digest == predecessor_digest:
        return SuccessionCompatibility.NO_MATERIAL_CHANGE
    return SuccessionCompatibility.VALID_SUCCESSION


def requires_version_bump(predecessor_digest: str, successor_digest: str) -> bool:
    """True when content changed and therefore the artifact version must be bumped."""
    return bool(successor_digest) and successor_digest != predecessor_digest


__all__ = [
    "SchemaCompatibility",
    "SuccessionCompatibility",
    "parse_semantic_version",
    "is_semantic_version",
    "compare_artifact_versions",
    "schema_compatibility",
    "succession_compatibility",
    "requires_version_bump",
]
