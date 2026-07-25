"""Abstract ports the kernel exposes to consuming domains and applications.

A *port* is a provider-neutral seam: the kernel depends only on these Protocols,
never on a concrete adapter, vendor SDK, or domain package. Domains and
applications supply the adapters (an external business-system client, a policy
store, an evidence source, a control plane, an external execution system,
persistence, a clock, an identity provider, …) and inject them at composition time.

This module re-exports the Protocols already defined by the kernel contract
packages so consumers have a single, stable import surface for the extension
points.
"""

from __future__ import annotations

from ..actions.control_plane import ActionControlPlanePort
from ..execution.external_system import ExternalExecutionPort
from .linked_record import (
    BLOCKED_METADATA_KEY,
    FINALIZED_STATUS,
    LinkedRecordPort,
    LinkedRecordSnapshot,
)

__all__ = [
    "ActionControlPlanePort",
    "ExternalExecutionPort",
    "LinkedRecordPort",
    "LinkedRecordSnapshot",
    "FINALIZED_STATUS",
    "BLOCKED_METADATA_KEY",
]
