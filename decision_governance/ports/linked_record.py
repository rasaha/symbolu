"""Linked-record port — the kernel's neutral view of a record it links to.

A decision case links to *other* governance records (e.g. an assessment produced
upstream). The kernel must not depend on any domain's concrete record type, so it
sees only a :class:`LinkedRecordSnapshot`: the governance-relevant projection —
identity, tenant, version, a neutral status, subject reference, and opaque
metadata. The domain resolves its own records behind :class:`LinkedRecordPort`; the
kernel never interprets record *content*.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from pydantic import Field

from ..base import DomainModel
from ..common import utc_now

#: Neutral status a domain adapter reports for a record that is final/complete and
#: therefore linkable. Domains map their own terminal status onto this value.
FINALIZED_STATUS = "FINALIZED"
#: Metadata key a domain adapter sets to "true" when a record has a blocking
#: condition that must prevent decision readiness.
BLOCKED_METADATA_KEY = "blocked"


class LinkedRecordSnapshot(DomainModel):
    """The governance-relevant projection of a linked record.

    Deliberately free of domain content: the kernel reads identity, tenant,
    version, a neutral ``status``, the ``subject_ref``, and opaque ``metadata`` —
    never evidence, scores, or any domain-specific payload.
    """

    record_type: str
    record_id: str
    version: int
    tenant_id: str
    status: str
    content_hash: str = ""
    subject_ref: str = ""
    policy_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def is_finalized(self) -> bool:
        return self.status == FINALIZED_STATUS

    @property
    def is_blocked(self) -> bool:
        return self.metadata.get(BLOCKED_METADATA_KEY) == "true"


@runtime_checkable
class LinkedRecordPort(Protocol):
    """Resolves a domain record into its neutral governance snapshot.

    Implementations return a snapshot, or ``None`` when the record does not exist
    (the kernel then fails closed). Implementations never leak domain content.
    """

    def get_record(
        self,
        *,
        tenant_id: str,
        record_type: str,
        record_id: str,
        version: Optional[int] = None,
    ) -> Optional[LinkedRecordSnapshot]:
        ...
