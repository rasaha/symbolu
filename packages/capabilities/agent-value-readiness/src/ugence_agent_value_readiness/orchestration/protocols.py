"""The three injected trust boundaries GV-3R-c orchestrates against.

Each protocol is a **seam for dependency injection**, not an implementation:
this package ships no resolver that resolves, no verifier that verifies, and no
permissive default. What it ships is the deny-by-default counterpart of each
seam (see :mod:`.deny`) and one concrete adapter around the **public** trusted
resolution service of the shared Ugence Policy Authority (see :mod:`.authority`).

Custom implementations are composition-root trust decisions
--------------------------------------------------------------
Supplying a resolver or a verifier is exactly the act of saying *"this is the
boundary I trust"*. That decision belongs to the composition root where the
application is wired — never to this package, and never to the caller of a
single assessment. A lax implementation is still constrained: the orchestrator
independently rechecks every coordinate a verifier returns against what it
asked for, so a permissive verifier can still not get a mismatched policy, gate,
condition, tenant, subject, context, target or instant admitted. It can only
weaken the claim about the input it was actually asked about.

The readiness package resolves policy through the shared authority's **public**
resolution service and reproduces none of its signature, approval, revocation or
registry logic; the resolver protocol therefore returns the authority's own
``PolicyResolution`` rather than a parallel readiness-owned resolution type.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ugence_policy_authority.api import PolicyResolution
from ugence_uvi_policy_contracts.api import PolicyReference

from .contracts import (
    ConditionSetVerification,
    ConditionVerificationRequest,
    GateResultVerification,
    GateVerificationRequest,
)

__all__ = ["ReadinessPolicyResolver", "GateResultVerifier", "ConditionSetVerifier"]


@runtime_checkable
class ReadinessPolicyResolver(Protocol):
    """Resolves one exact readiness ``PolicyReference`` through a trust boundary.

    Implementations must be deterministic for a given ``(reference,
    expected_tenant_id, as_of)`` and must never read the system clock: ``as_of``
    is the only instant, and it is supplied by the caller.
    """

    def resolve_readiness_policy(
        self,
        *,
        reference: PolicyReference,
        expected_tenant_id: str,
        as_of: datetime,
    ) -> PolicyResolution:
        """Return the authority's resolution of ``reference`` at ``as_of``.

        Returning an ``UNRESOLVED`` :class:`PolicyResolution` is the correct way
        to refuse. Raising is also handled — it is recorded as a fail-closed gap
        and never as an acceptance — but a typed refusal carries more meaning.
        """
        ...


@runtime_checkable
class GateResultVerifier(Protocol):
    """Verifies one supplied ``GateResult`` against its complete binding.

    The verifier is responsible for the claimed ``GateStatus`` **and** for the
    supporting evidence, benchmark resolution and threshold evaluation behind
    it. The readiness orchestrator performs none of those itself and never
    substitutes caller metadata for a missing attestation.
    """

    def verify_gate_result(self, request: GateVerificationRequest) -> GateResultVerification:
        """Attest (or refuse) the claimed status of one gate result."""
        ...


@runtime_checkable
class ConditionSetVerifier(Protocol):
    """Verifies one supplied ``ConditionSet`` against its complete binding.

    The merged ``ConditionSet`` contract carries no tenant, subject or context
    field, so the verifier's attestation is the **only** place that binding can
    be established. A condition whose tenant/subject/context binding the
    verifier does not attest provides no coverage.
    """

    def verify_condition(self, request: ConditionVerificationRequest) -> ConditionSetVerification:
        """Attest (or refuse) one compensating control for one exact concern."""
        ...
