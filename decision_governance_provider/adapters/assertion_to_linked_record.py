"""Adapter: AssertionProvider → kernel LinkedRecordPort.

The adapter owns the translation; the kernel stays unaware of providers. It
implements the frozen ``LinkedRecordPort`` Protocol by delegating to an
:class:`AssertionProvider` and mapping its neutral :class:`AssertionResult` onto a
``LinkedRecordSnapshot``.
"""

from __future__ import annotations

from typing import Optional

from decision_governance.api.ports import (
    BLOCKED_METADATA_KEY,
    FINALIZED_STATUS,
    LinkedRecordSnapshot,
)

from ..contracts import AssertionProvider


class AssertionProviderLinkedRecordAdapter:
    """Implements ``LinkedRecordPort`` over an :class:`AssertionProvider`."""

    def __init__(self, provider: AssertionProvider) -> None:
        self._provider = provider

    def get_record(
        self,
        *,
        tenant_id: str,
        record_type: str,
        record_id: str,
        version: Optional[int] = None,
    ) -> Optional[LinkedRecordSnapshot]:
        result = self._provider.resolve_assertion(
            tenant_id=tenant_id, record_type=record_type, record_id=record_id,
            version=version)
        if not result.found:
            return None
        metadata = dict(result.metadata)
        if result.blocked:
            metadata[BLOCKED_METADATA_KEY] = "true"
        return LinkedRecordSnapshot(
            record_type=result.record_type or record_type,
            record_id=result.record_id or record_id,
            version=result.version,
            tenant_id=result.tenant_id or tenant_id,
            status=FINALIZED_STATUS if result.finalized else "PENDING",
            subject_ref=result.subject_ref,
            metadata=metadata)
