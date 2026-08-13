"""The chokepoint reference.

Governed value is normalized *per authorized action* — per action the control
plane actually approved. This value object is a neutral, by-value reference to
that chokepoint: it carries the authorization artifact's identifiers and the
count of authorized actions in the accounting window, but imports nothing from
the authority kernel. A production integration maps a signed
``RiskAuthorizationEnvelope`` (ugence-risk-authority) onto this shape through the
:mod:`governed_value.integrations.authorization` seam — measurement happens at
exactly the point where authorization already happens.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["AuthorizedActionRef"]


@dataclass(frozen=True)
class AuthorizedActionRef:
    tenant_id: str
    envelope_id: str
    action_digest: str
    authorized_count: int

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not isinstance(self.authorized_count, int) or isinstance(
            self.authorized_count, bool
        ):
            raise ValueError("authorized_count must be an int")
        # A non-positive count is not raised here — it is a fail-closed *scoring*
        # signal (nothing to normalize over), handled by the scorer's guards.
