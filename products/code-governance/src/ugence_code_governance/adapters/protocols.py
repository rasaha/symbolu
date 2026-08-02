"""Narrow adapter protocol.

Every read-only adapter exposes exactly one operation: ``collect_snapshot``. An
adapter returns **data only** (an :class:`AdapterResult`). It never invokes Action
Clearance, never mutates a workflow, never authorizes anything, and never executes.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import AdapterCapability, AdapterRequest, AdapterResult


@runtime_checkable
class ReadOnlyAdapter(Protocol):
    """A read-only enterprise signal adapter."""

    def capability(self) -> AdapterCapability:
        """Describe the adapter's signal-producing capability."""
        ...

    def collect_snapshot(self, request: AdapterRequest) -> AdapterResult:
        """Collect a read-only snapshot of source facts for the governed change."""
        ...


__all__ = ["ReadOnlyAdapter"]
