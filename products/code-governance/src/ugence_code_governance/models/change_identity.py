"""Exact change identity — the product-owned immutable binding of *what would land*.

``GovernedChangeIdentity`` is **not an authorization**. It is the exact,
content-addressed identity of a proposed source-control change. The approved
source SHA alone is insufficient (the base can advance; GitHub can create a
merge/squash/rebase artifact), so the governed operation binds the full tuple.

The *fingerprint* is derived only from the governed artifact fields, so:

* the same normalized identity always yields the same fingerprint (idempotent
  re-delivery of the same webhook does not create a new identity);
* changing the head SHA, base SHA, merge method, repository, or tenant yields a
  different fingerprint;
* delivery metadata (delivery id, capture time, installation/org) never changes
  the fingerprint — it is provenance, not artifact identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..fingerprints import domain_hash
from .enums import MergeMethod

_DOMAIN = "governed_change_identity.v1"


@dataclass(frozen=True)
class GovernedChangeIdentity:
    """Immutable identity of a governed change. Never an authorization."""

    tenant_id: str
    repository_owner: str
    repository_name: str
    pull_request_number: int
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    captured_at: datetime
    event_source: str
    event_delivery_id: str
    target_branch: str = ""
    merge_method: Optional[MergeMethod] = None
    installation_id: Optional[str] = None
    organization_id: Optional[str] = None

    def __post_init__(self) -> None:
        # Default the target branch to the base ref when the event does not
        # override it (direct/squash merges target the base branch).
        if not self.target_branch:
            object.__setattr__(self, "target_branch", self.base_ref)

    @property
    def repository(self) -> str:
        """Canonical ``owner/name`` repository identity."""
        return f"{self.repository_owner}/{self.repository_name}"

    @property
    def governed_fields(self) -> dict:
        """The fields that define the exact artifact (drive the fingerprint)."""
        return {
            "tenant_id": self.tenant_id,
            "repository": self.repository,
            "pull_request_number": self.pull_request_number,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "target_branch": self.target_branch,
            "merge_method": self.merge_method.value if self.merge_method else None,
        }

    @property
    def fingerprint(self) -> str:
        """Deterministic, domain-separated fingerprint over the governed fields."""
        return domain_hash(_DOMAIN, self.governed_fields)

    def with_merge_method(self, method: MergeMethod) -> "GovernedChangeIdentity":
        """Return a copy that selects a merge method (a new artifact identity)."""
        return dataclass_replace(self, merge_method=method)


def dataclass_replace(identity: GovernedChangeIdentity, **changes) -> GovernedChangeIdentity:
    """Local ``dataclasses.replace`` wrapper (kept explicit for readability)."""
    from dataclasses import replace

    return replace(identity, **changes)


__all__ = ["GovernedChangeIdentity"]
