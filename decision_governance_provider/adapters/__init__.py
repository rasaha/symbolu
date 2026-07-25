"""Provider→kernel-port adapters. The adapter owns translation; the kernel is unaware."""
from __future__ import annotations

from .assertion_to_linked_record import AssertionProviderLinkedRecordAdapter
from .authorization_to_control_plane import AuthorizationProviderControlPlaneAdapter
from .execution_to_external_system import ExecutionProviderExternalSystemAdapter

__all__ = [
    "AssertionProviderLinkedRecordAdapter",
    "AuthorizationProviderControlPlaneAdapter",
    "ExecutionProviderExternalSystemAdapter",
]
