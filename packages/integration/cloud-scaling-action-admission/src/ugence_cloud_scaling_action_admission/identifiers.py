"""Ratified identifiers for Phase 5C admission (ADR 5C, D-2)."""

from __future__ import annotations

from typing import Final

from ugence_cloud_scaling_authorization_contracts import (
    CANONICAL_ACTION_TYPES,
    PURPOSE_CAPACITY_ACTION,
)
from ugence_cloud_scaling_envelope_issuance import (
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_TARGET_SCOPE,
)

__all__ = [
    "ADMISSION_PROFILE",
    "ADMISSION_PROFILE_VERSION",
    "CANONICAL_ACTION_TYPES",
    "PURPOSE_CAPACITY_ACTION",
    "BINDING_KIND_AUTHORIZATION_CANDIDATE",
    "BINDING_KIND_TARGET_SCOPE",
    "REQUIRED_ENVELOPE_BINDINGS",
]

#: How a verdict was reached. Recorded in every authorization's reason codes on denial so an
#: auditor can tell which projection produced it.
ADMISSION_PROFILE: Final[str] = "ugence.cloud-scaling.action-admission"
ADMISSION_PROFILE_VERSION: Final[str] = "v1"

#: The two envelope bindings the gate reconciles the presented artifacts against (D-2).
REQUIRED_ENVELOPE_BINDINGS: Final[tuple[str, ...]] = (
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_TARGET_SCOPE,
)
