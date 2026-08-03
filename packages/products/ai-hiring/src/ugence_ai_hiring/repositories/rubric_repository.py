"""Rubric repository (port + in-memory adapter).

Rubrics evolve through an append-only snapshot history per ``rubric_id``. Each
lifecycle transition appends a new immutable snapshot; the latest snapshot is the
current state. A PUBLISHED snapshot for a version is terminal for that version's
*content* — further content changes require a new version. Stored snapshots are
never mutated in place.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..errors import RecordNotFoundError
from ..rubrics.approval import RubricStatus
from ..rubrics.rubric import Rubric


@runtime_checkable
class RubricRepository(Protocol):
    def append(self, rubric: Rubric) -> Rubric: ...
    def current(self, rubric_id: str) -> Rubric: ...
    def exists(self, rubric_id: str) -> bool: ...
    def history(self, rubric_id: str) -> tuple[Rubric, ...]: ...
    def published(self, rubric_id: str) -> Optional[Rubric]: ...
    def list_published(self) -> tuple[Rubric, ...]: ...


class InMemoryRubricRepository:
    def __init__(self) -> None:
        self._history: dict[str, list[Rubric]] = {}

    def append(self, rubric: Rubric) -> Rubric:
        self._history.setdefault(rubric.rubric_id, []).append(rubric)
        return rubric

    def current(self, rubric_id: str) -> Rubric:
        snaps = self._history.get(rubric_id)
        if not snaps:
            raise RecordNotFoundError(f"rubric '{rubric_id}' not found")
        return snaps[-1]

    def exists(self, rubric_id: str) -> bool:
        return rubric_id in self._history

    def history(self, rubric_id: str) -> tuple[Rubric, ...]:
        return tuple(self._history.get(rubric_id, ()))

    def published(self, rubric_id: str) -> Optional[Rubric]:
        # The latest snapshot whose status is PUBLISHED (highest version wins).
        published = [s for s in self._history.get(rubric_id, ())
                     if s.status is RubricStatus.PUBLISHED]
        if not published:
            return None
        return max(published, key=lambda s: s.version)

    def list_published(self) -> tuple[Rubric, ...]:
        out = []
        for rid in sorted(self._history):
            pub = self.published(rid)
            if pub is not None:
                out.append(pub)
        return tuple(out)
