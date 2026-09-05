"""What a deployment supplies to the hook.

The hook composes and projects; it does not decide. It cannot obtain a Risk Authority
verdict on its own — that needs an envelope, a key ring, a revocation state, an identity
and a canonical action, none of which the Agent Runtime has or should have. So a
deployment supplies a :class:`GovernanceInputSource` that turns a neutral
``TransitionProposal`` into the three per-source results the composition engine consumes,
and the hook does the rest.

Drawing the boundary here keeps two things true at once: the hook re-implements no
composition logic (it calls ``RiskAuthorityCompositionEngine.compose``), and it carries
no credentials (the key ring and envelope live in the source, on the deployment's side).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_risk_authority_runtime.contracts import (
    GovernanceVetoResult,
    RiskAuthorityMachineResult,
)

__all__ = ["CompositionInputs", "GovernanceInputSource"]


@dataclass(frozen=True)
class CompositionInputs:
    """The three per-source results for one proposal, plus what the recheck needs.

    ``envelope`` and ``tier`` are carried through so the last-mile authority recheck can
    re-verify *the same envelope* the CLEAR rested on at the commit point. They are not
    used to decide anything here — the composition engine owns that — and the hook never
    reads a field off the envelope other than to hand it back to Risk Authority's own
    status check.
    """

    risk_authority: RiskAuthorityMachineResult
    decision_authority: GovernanceVetoResult
    actiongate: GovernanceVetoResult
    #: The exact canonical action Risk Authority verified. Passed to ``compose`` so it
    #: can re-check ``CurrentAction ∈ EffectiveScope`` (F1). When absent the engine
    #: composes at the algebra level and performs no action re-check.
    action: Any = None
    #: The signed ``RiskAuthorizationEnvelope`` the verdict rested on, for the recheck.
    envelope: Any = None
    #: The case-derived risk tier for the staleness policy. ``None`` ⇒ the status check
    #: treats it as CRITICAL (fail-closed), which is Risk Authority's own rule, not ours.
    tier: Any = None


@runtime_checkable
class GovernanceInputSource(Protocol):
    """Produces the composition inputs for one proposed transition.

    Implementations own every concrete dependency: the envelope store, the key ring, the
    revocation state, the runtime identity, and the mapping from a neutral proposal to a
    canonical action. They may raise — the hook treats any failure as a missing authority
    input and fails closed, which is not the same as a denial and is recorded differently.
    """

    def inputs_for(self, proposal: TransitionProposal) -> Optional[CompositionInputs]:
        """Return the composition inputs, or ``None`` if this proposal is not
        authority-bound.

        Returning ``None`` is **not** permission. The hook still refuses: a runtime that
        asked the governance boundary about a transition gets an answer, and "this is not
        authority-bound" is a deployment configuration question, not a clearance.
        """
