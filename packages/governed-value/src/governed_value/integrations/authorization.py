"""The chokepoint seam.

Governed value is measured *per authorized action* — so the count of authorized
actions must come from the same control plane that authorizes them. This module
defines a port for that count and a neutral reference ledger, without importing
the authority kernel: a production deployment adapts a signed
``RiskAuthorizationEnvelope`` (ugence-risk-authority) onto :class:`AuthorizedActionPort`
through the contract, exactly as ``risk_authority`` consumes ActionGate/TAP/PWC
through *its* ports. This keeps ``governed_value`` a stdlib-only leaf.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.action import AuthorizedActionRef

__all__ = ["AuthorizedActionPort", "ReferenceAuthorizationLedger"]


@runtime_checkable
class AuthorizedActionPort(Protocol):
    """Resolves how many actions the control plane authorized for an envelope.

    Implementations count *authorized* actions only — the point of measuring at
    the chokepoint is that denied/aborted actions never reach it.
    """

    def authorized_count(self, tenant_id: str, envelope_id: str) -> int:
        ...


class ReferenceAuthorizationLedger:
    """An in-memory reference ledger for conformance and examples.

    Not a production binding — a real deployment resolves counts from the
    authority kernel's revocation-aware envelope/ActionGate records.
    """

    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}

    def record(self, ref: AuthorizedActionRef) -> None:
        key = (ref.tenant_id, ref.envelope_id)
        self._counts[key] = self._counts.get(key, 0) + ref.authorized_count

    def authorized_count(self, tenant_id: str, envelope_id: str) -> int:
        return self._counts.get((tenant_id, envelope_id), 0)
