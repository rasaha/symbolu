"""Shared immutable-versioning helpers for capabilities and rubrics."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.base import DomainModel


class VersionRef(DomainModel):
    """A pinned reference to a specific version of an identified artifact."""

    id: str
    version: int


def next_version(current: int) -> int:
    return current + 1


def is_monotonic(previous: int, candidate: int) -> bool:
    """True if ``candidate`` is a valid successor version (strictly greater)."""
    return candidate == previous + 1


@dataclass(frozen=True)
class VersionWindow:
    """The known version span for an artifact id."""

    first: int
    latest: int
