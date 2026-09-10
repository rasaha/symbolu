"""Pure selectors over a sequence of drafts, and the read-only port.

Nothing here reads a clock, opens a file or decides anything: a caller hands in
records and gets a subset or an ordering back.
"""

from __future__ import annotations

from typing import Dict, Optional, Protocol, Sequence, Tuple, runtime_checkable

from .draft import WorkflowDraft
from .errors import ContractViolation

__all__ = ["WorkflowDraftPort", "superseded_by", "heads", "lineage", "select_for_tenant"]


def superseded_by(drafts: Sequence[WorkflowDraft]) -> Dict[str, str]:
    """``predecessor id -> successor id`` for every recorded supersession."""

    out: Dict[str, str] = {}
    for draft in drafts:
        if draft.supersedes:
            out[draft.supersedes] = draft.draft_id
    return out


def heads(drafts: Sequence[WorkflowDraft]) -> Tuple[WorkflowDraft, ...]:
    """The drafts nothing supersedes: the current revision of every lineage, in the
    order they were recorded."""

    taken = superseded_by(drafts)
    return tuple(d for d in drafts if d.draft_id not in taken)


def lineage(drafts: Sequence[WorkflowDraft], draft_id: str) -> Tuple[WorkflowDraft, ...]:
    """Oldest first: the draft named and every predecessor it revises."""

    by_id = {d.draft_id: d for d in drafts}
    if draft_id not in by_id:
        return ()
    chain = []
    seen = set()
    current: Optional[WorkflowDraft] = by_id[draft_id]
    while current is not None and current.draft_id not in seen:
        chain.append(current)
        seen.add(current.draft_id)
        current = by_id.get(current.supersedes) if current.supersedes else None
    return tuple(reversed(chain))


def select_for_tenant(drafts: Sequence[WorkflowDraft], *, tenant_id: str,
                      include_superseded: bool = False) -> Tuple[WorkflowDraft, ...]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation("tenant_id must be a non-empty string")
    mine = tuple(d for d in drafts if d.tenant_id == tenant_id)
    return mine if include_superseded else heads(mine)


@runtime_checkable
class WorkflowDraftPort(Protocol):
    """The read seam a composition root types against. Reads only; the one write is
    the durable store's own ``save``."""

    tenant_id: str

    def get_draft(self, draft_id: str) -> Optional[WorkflowDraft]: ...

    def drafts_for_tenant(self, *, tenant_id: str,
                          include_superseded: bool = False) -> Tuple[WorkflowDraft, ...]: ...

    def lineage_of(self, draft_id: str) -> Tuple[WorkflowDraft, ...]: ...
