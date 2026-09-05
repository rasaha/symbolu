"""Inputs for the adversarial suite, including deliberately hostile ones.

The honest fakes build real ``RiskAuthorityMachineResult`` / ``GovernanceVetoResult``
objects and let the REAL ``RiskAuthorityCompositionEngine`` compose them, so the tests
exercise the ratified composition rather than a stand-in for it. The hostile ones are
shaped to defeat a naive projection: a bare string where an enum belongs, a decision that
claims to be executable while denying, an object that raises when inspected.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_risk_authority_runtime.contracts import (
    EffectiveConstraints,
    FinalDisposition,
    GovernanceRestrictions,
    GovernanceVetoResult,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
    VetoDisposition,
)

from ugence_agent_runtime_governance.interfaces import CompositionInputs

ENVELOPE_ID = "rae_000042"


def proposal(
    *,
    instance_id: str = "i1",
    task_id: str = "t1",
    correlation_id: Optional[str] = "corr-1",
) -> TransitionProposal:
    return TransitionProposal.build(
        workflow_id="wf",
        instance_id=instance_id,
        task_id=task_id,
        provider_id="p",
        operation="op",
        arguments={"a": 1},
        idempotency_key=f"{instance_id}:{task_id}",
        correlation_id=correlation_id,
    )


class _Scope:
    """Minimal stand-in for the RA scope the restriction algebra reads."""

    purposes = ("p",)
    tools_allow = frozenset({"tool-a"})
    tools_deny = frozenset()
    data_allow = frozenset({"d"})
    data_deny = frozenset()
    destinations = frozenset({"dest"})
    jurisdictions = frozenset({"eu"})
    max_autonomy_level = 2
    max_amount_minor_units = 10_000
    required_approvals = frozenset()


def ra_result(
    disposition: RiskAuthorityDisposition = RiskAuthorityDisposition.ALLOW,
    *,
    envelope_id: str = ENVELOPE_ID,
    expires_in_s: float = 3600.0,
) -> RiskAuthorityMachineResult:
    return RiskAuthorityMachineResult(
        disposition=disposition,
        reason_codes=("RA_ALLOW",) if disposition is RiskAuthorityDisposition.ALLOW else ("RA_DENY",),
        envelope_id=envelope_id,
        action_digest="digest",
        scope=_Scope(),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_s),
        source_version="ra-test",
    )


def veto(
    source: str,
    disposition: VetoDisposition = VetoDisposition.NO_VETO,
    *,
    restrictions: GovernanceRestrictions = GovernanceRestrictions(),
) -> GovernanceVetoResult:
    return GovernanceVetoResult(
        source=source,
        disposition=disposition,
        reason_codes=(f"{source.upper()}_{disposition.value}",),
        restrictions=restrictions,
        source_version=f"{source}-test",
    )


def inputs(
    *,
    ra: Optional[RiskAuthorityMachineResult] = None,
    da: VetoDisposition = VetoDisposition.NO_VETO,
    ag: VetoDisposition = VetoDisposition.NO_VETO,
    da_restrictions: GovernanceRestrictions = GovernanceRestrictions(),
    envelope: Any = None,
    tier: Any = None,
) -> CompositionInputs:
    return CompositionInputs(
        risk_authority=ra if ra is not None else ra_result(),
        decision_authority=veto("decision_authority", da, restrictions=da_restrictions),
        actiongate=veto("actiongate", ag),
        action=None,
        envelope=envelope,
        tier=tier,
    )


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #
class StaticSource:
    """Returns fixed inputs for every proposal."""

    def __init__(self, value: Any) -> None:
        self.value = value
        self.calls = 0

    def inputs_for(self, proposal: TransitionProposal) -> Any:
        self.calls += 1
        return self.value


class RaisingSource:
    """A source that cannot reach its dependencies."""

    def __init__(self, exc: BaseException | None = None) -> None:
        self.exc = exc or RuntimeError("envelope store unreachable")

    def inputs_for(self, proposal: TransitionProposal) -> Any:
        raise self.exc


# --------------------------------------------------------------------------- #
# hostile decisions — shaped to defeat a naive projection
# --------------------------------------------------------------------------- #
@dataclass
class SpoofedDecision:
    """A decision-shaped object with arbitrary, attacker-chosen fields."""

    final_disposition: Any
    executable: Any = True
    reason_codes: tuple = ("SPOOFED",)
    effective_constraints: Any = None
    risk_authority_result: Any = None

    def to_dict(self) -> dict:
        return {"spoofed": True}


class ExplodingDecision:
    """Every attribute access raises. An uninspectable decision is not permission."""

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f"attribute {name} exploded")


class ExplodingEngine:
    """A composition engine that fails."""

    def compose(self, **kwargs: Any) -> Any:
        raise RuntimeError("composition unavailable")


class StaticEngine:
    """Returns a fixed decision, bypassing real composition — used only to feed the
    projection objects the real engine could never produce."""

    def __init__(self, decision: Any) -> None:
        self.decision = decision

    def compose(self, **kwargs: Any) -> Any:
        return self.decision


def constraints(*, required_approvals: frozenset = frozenset(), expires_at=None):
    return EffectiveConstraints(
        purposes=("p",),
        tools_allow=("tool-a",),
        max_autonomy_level=2,
        max_amount_minor_units=10_000,
        required_approvals=required_approvals,
        expires_at=expires_at,
    )
