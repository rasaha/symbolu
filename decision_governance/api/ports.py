"""Public API — the provider-neutral seams.

Domains implement these ports to plug their records and external systems into the
governance chain without the kernel ever depending on a concrete provider:

* ``LinkedRecordPort``       — resolve a domain record into a neutral snapshot;
* ``ActionControlPlanePort`` — authorize a prepared action under runtime controls;
* ``ExternalExecutionPort``  — dispatch to, and observe, an external system.

Deterministic offline reference adapters are included for tests/development.
"""

from __future__ import annotations

from ..ports import (
    BLOCKED_METADATA_KEY,
    FINALIZED_STATUS,
    LinkedRecordPort,
    LinkedRecordSnapshot,
)
from ..actions import ActionControlPlanePort, OfflineDeterministicControlPlane
from ..execution import (
    ExternalDispatchResponse,
    ExternalExecutionPort,
    ExternalStatusResponse,
    OfflineDeterministicExecutionAdapter,
)

__all__ = [
    # linked-record seam
    "LinkedRecordPort",
    "LinkedRecordSnapshot",
    "FINALIZED_STATUS",
    "BLOCKED_METADATA_KEY",
    # control-plane seam
    "ActionControlPlanePort",
    "OfflineDeterministicControlPlane",
    # external-execution seam
    "ExternalExecutionPort",
    "ExternalDispatchResponse",
    "ExternalStatusResponse",
    "OfflineDeterministicExecutionAdapter",
]
