"""Risk-tiered governance (milestone §8).

Two classes: GOVERNED (full control-plane path) and LOW_RISK (documented fast
path). The consequence class is controlled by the TOOL PROFILE / policy, NEVER
self-asserted by the model/runtime: a CER that claims LOW_RISK for a governed
tool profile is rejected.

The fast path is *documented, not overbuilt*: LOW_RISK read-only tool profiles may
skip the full authorize+operational round-trip. kubernetes.scale is GOVERNED and
always takes the full path.
"""
from __future__ import annotations

# Authoritative tool-profile -> risk tier. Enterprise/policy controlled.
TOOL_PROFILE_RISK = {
    "kubernetes.scale": "GOVERNED",
    "kubernetes.rollout": "GOVERNED",
    "kubernetes.delete": "GOVERNED",
    # examples of low-risk read-only profiles (documented; not exercised by the
    # scale experiment). Present to show the contract, not to broaden scope.
    "kubernetes.get": "LOW_RISK",
    "kubernetes.list": "LOW_RISK",
    "kubernetes.logs": "LOW_RISK",
}


class RiskTierViolation(ValueError):
    """A CER self-asserted a lower risk tier than its tool profile permits."""


def authoritative_tier(actuation_interface: str) -> str:
    """The tier for a tool profile. Unknown profile -> GOVERNED (fail-safe)."""
    return TOOL_PROFILE_RISK.get(actuation_interface, "GOVERNED")


def enforce_tier(cer: dict) -> str:
    """Return the authoritative tier; raise if the CER claims a weaker one.

    The model may not self-assert LOW_RISK. If the CER's declared risk_tier is
    weaker than the tool-profile tier, fail closed.
    """
    interface = cer["identity"]["actuation_interface"]
    auth = authoritative_tier(interface)
    claimed = cer.get("risk_tier", auth)
    if auth == "GOVERNED" and claimed != "GOVERNED":
        raise RiskTierViolation(
            f"{interface} is GOVERNED by tool profile; CER claimed {claimed!r} "
            "(risk tier cannot be self-asserted by the runtime/model)")
    return auth
