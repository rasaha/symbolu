"""Contracts (ports) for integrating existing governance components.

``risk_authority`` integrates ActionGate, TAP and PWC through these ports and
never imports their application-specific policy logic directly (user brief §1).
"""

from __future__ import annotations

from .actiongate import ActionGatePort, ReferenceActionGate, RuntimeIdentity
from .pwc import InMemoryWorkflowIRSource, WorkflowIRSource
from .tap import EvidenceAdmissionPort, ReferenceEvidenceAdmission

__all__ = [
    "ActionGatePort",
    "ReferenceActionGate",
    "RuntimeIdentity",
    "EvidenceAdmissionPort",
    "ReferenceEvidenceAdmission",
    "WorkflowIRSource",
    "InMemoryWorkflowIRSource",
]
