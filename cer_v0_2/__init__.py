"""CER V0.2 — multi-runtime, multi-profile conformance (envelope + domain profiles).

Profiles: kubernetes.scale.v1 (identity-equivalent to frozen V0.1 scale),
kubernetes.rollout.v1 (new). Reuses the frozen ActionGate v2 identity profile and
ACP core unchanged. Second real runtime: OpenAI Agents SDK.
"""
from __future__ import annotations

from .envelope import (  # noqa: F401
    CER_VERSION, IDENTITY_PROFILE, action_digest, to_cloud_candidate,
    to_cloud_world, to_envelope, validate_cer,
)
from .profiles.base import CERValidationError  # noqa: F401

__all__ = ["CER_VERSION", "IDENTITY_PROFILE", "action_digest", "to_envelope",
           "to_cloud_world", "to_cloud_candidate", "validate_cer", "CERValidationError"]
