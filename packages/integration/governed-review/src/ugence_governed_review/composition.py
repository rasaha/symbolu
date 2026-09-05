"""Composition helpers. A root wires these; nothing here runs on its own.

The eligibility port is answered by the authority directory's own adapter, so who may
decide is a reported role grant, never a name a caller typed. The ledger is the
approval workflow's SQLite store (D-22 Posture B, single-node durable). Neither
package imports the other; this module is where the two seams meet.
"""

from __future__ import annotations

from typing import Optional

from ugence_approval_workflow import SqliteApprovalWorkflowStore
from ugence_authority_directory import (
    AuthorityDirectoryPort,
    DirectoryApproverEligibility,
    SqliteAuthorityDirectory,
)

__all__ = ["build_review_ledger", "open_directory"]


def open_directory(path: str, *, production_mode: bool = False) -> SqliteAuthorityDirectory:
    """The durable authority directory a review ledger reports eligibility from."""

    return SqliteAuthorityDirectory(path, production_mode=production_mode)


def build_review_ledger(path: str, directory: AuthorityDirectoryPort, *,
                        production_mode: bool = False,
                        scope_prefix: Optional[str] = None) -> SqliteApprovalWorkflowStore:
    """The approval ledger the source binds to, with directory-backed eligibility.

    ``scope_prefix`` follows the directory adapter's convention
    (``<prefix>/<subject_kind>/<subject_digest>``); a root that scopes role grants
    differently supplies its own eligibility adapter instead.
    """

    kwargs = {} if scope_prefix is None else {"scope_prefix": scope_prefix}
    eligibility = DirectoryApproverEligibility(directory, **kwargs)
    return SqliteApprovalWorkflowStore(path, eligibility, production_mode=production_mode)
