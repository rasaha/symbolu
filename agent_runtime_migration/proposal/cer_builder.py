"""Native Canonical Execution Request (CER) builder.

Builds a CER for a governed Action using the FROZEN ``cer_v0_3`` contract — it does
NOT reimplement CER identity, canonicalization, or the schema. Runtime provenance is
carried OUTSIDE the CER action identity (the v2 profile excludes it). Incomplete or
invalid CERs are rejected here (fail closed) before they ever reach the control plane.

Supported profiles are exactly the frozen CER profiles:
``kubernetes.scale.v1``, ``kubernetes.rollout.v1``, ``database.mutation.v1``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .. import _paths  # noqa: F401  (import-only bootstrap for the frozen CER)
from ..contracts.action import Action, RiskClass
from ..contracts.errors import ProposalError

from cer_v0_3 import envelope as _cer_env  # frozen  # noqa: E402
from cer_v0_3.profiles.base import CERValidationError  # noqa: E402

SUPPORTED_PROFILES = ("kubernetes.scale.v1", "kubernetes.rollout.v1", "database.mutation.v1")


@dataclass(frozen=True)
class ProposalContext:
    """The non-actuation envelope sections the runtime supplies for a governed action:
    authority, state binding, policy reference, and (non-identity) provenance."""
    authority: Dict[str, Any]
    state_binding: Dict[str, Any]
    policy_ref: Dict[str, Any]
    provenance: Dict[str, Any] = field(default_factory=dict)
    risk_tier: str = "GOVERNED"


def build_cer(action: Action, ctx: ProposalContext) -> Dict[str, Any]:
    """Assemble + validate a CER for a governed action. Fail closed on any problem."""
    if action.risk_class is not RiskClass.GOVERNED_CONSEQUENTIAL:
        raise ProposalError("build_cer requires a GOVERNED_CONSEQUENTIAL action")
    if action.profile not in SUPPORTED_PROFILES:
        raise ProposalError(f"unsupported CER profile {action.profile!r} "
                            f"(supported: {SUPPORTED_PROFILES})")
    actuation = action.arguments.get("actuation")
    if not isinstance(actuation, dict):
        raise ProposalError("governed action must carry actuation dict in arguments['actuation']")

    cer = {
        "cer_version": "0.2",
        "profile": action.profile,
        "risk_tier": ctx.risk_tier,
        "authority": ctx.authority,
        "state_binding": ctx.state_binding,
        "policy_ref": ctx.policy_ref,
        "actuation": actuation,
        "provenance": dict(ctx.provenance),   # excluded from identity by the v2 profile
    }
    # Fail closed: reject incomplete/invalid CERs before submission.
    try:
        _cer_env.validate_cer(cer)
    except CERValidationError as exc:
        raise ProposalError(f"invalid CER (fail closed): {exc}") from exc
    return cer


def cer_identity(cer: Dict[str, Any]) -> str:
    """The exact-action identity (v2 action digest) of a CER, via the frozen contract."""
    return _cer_env.action_digest(cer)
