"""
Healthcare enforcement + adversarial validation harness.

The DECISION layer (agentic/healthcare) answers "may this class of access happen,
under which authority, with which minimum-necessary constraints". This ENFORCEMENT
layer proves those constraints are actually applied between authorization and a
simulated HIS/EMR retrieval — and cannot be ignored, widened, replayed, or
bypassed.

Nothing here connects to a real hospital. Records are synthetic.

Pieces:
  * artifact.py — signed AuthorizationArtifact, ExecutionRequest, PHI-safe
    ExecutionReceipt, and mismatch codes.
  * emr.py — SyntheticEMR (multi-tenant/patient/encounter synthetic records).
  * enforcement.py — AuthorizationIssuer (allow-only), EnforcementAdapter
    (deterministic checks + TOCTOU + projection/redaction + replay/session
    state), HarnessMetrics, EnforcementHarness.
"""

from agentic.healthcare.enforcement.artifact import (
    AuthorizationArtifact,
    ExecutionRequest,
    ExecutionReceipt,
    ExecutionResult,
    ExecutionStatus,
    MismatchCode,
    sign_payload,
)
from agentic.healthcare.enforcement.emr import (
    SyntheticEMR,
    build_synthetic_emr,
    SYNTHETIC_CREDENTIAL_SENTINEL,
)
from agentic.healthcare.enforcement.enforcement import (
    AuthorizationIssuer,
    EnforcementAdapter,
    EnforcementState,
    EnforcementConfig,
    HarnessMetrics,
    EnforcementHarness,
    FixedClock,
)

__all__ = [
    "AuthorizationArtifact",
    "ExecutionRequest",
    "ExecutionReceipt",
    "ExecutionResult",
    "ExecutionStatus",
    "MismatchCode",
    "sign_payload",
    "SyntheticEMR",
    "build_synthetic_emr",
    "SYNTHETIC_CREDENTIAL_SENTINEL",
    "AuthorizationIssuer",
    "EnforcementAdapter",
    "EnforcementState",
    "EnforcementConfig",
    "HarnessMetrics",
    "EnforcementHarness",
    "FixedClock",
]
