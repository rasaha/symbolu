"""Deterministic mock AssertionProvider — validates the framework, not a domain."""
from __future__ import annotations

from typing import Optional

from ..contracts import AssertionResult, BaseProvider
from ..metadata import ProviderCapabilities, ProviderKind, ProviderMetadata


class MockAssertionProvider(BaseProvider):
    """Always resolves a finalized assertion (configurable to block / not-find)."""

    def __init__(self, *, name: str = "mock-assertion", found: bool = True,
                 finalized: bool = True, blocked: bool = False,
                 subject_ref: str = "subject") -> None:
        super().__init__(
            ProviderMetadata(name=name, version="0.1.0", kind=ProviderKind.ASSERTION,
                             kernel_port_version="1.0.0", description="deterministic mock",
                             vendor="framework-tests"),
            ProviderCapabilities(kind=ProviderKind.ASSERTION,
                                 features=frozenset({"resolve"}), deterministic=True))
        self._found, self._finalized, self._blocked = found, finalized, blocked
        self._subject_ref = subject_ref

    def resolve_assertion(self, *, tenant_id: str, record_type: str, record_id: str,
                          version: Optional[int] = None) -> AssertionResult:
        if not self._found:
            return AssertionResult(found=False)
        return AssertionResult(
            found=True, record_type=record_type, record_id=record_id,
            version=version or 1, tenant_id=tenant_id, finalized=self._finalized,
            blocked=self._blocked, subject_ref=self._subject_ref)
