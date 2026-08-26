"""The vNext authorization request.

This mirrors the neutral ``ActionGovernanceRequest`` field for field, with one
addition: ``authorization_expired``. The neutral contract has carried that flag
since it was written, the control-plane adapter computes it
(``cer.expires_at < now``), and the framework's own reference provider honours
it — but the pre-vNext ActionGate request mapping dropped it, and ActionGate's
native outcome vocabulary had no way to express expiry.

Carrying it here does not by itself change any live authorization. Nothing on
the frozen public path constructs this type yet: wiring it through
``mapping/request.py`` and adding the native ``EXPIRED`` outcome is a MAJOR
change under the platform's own compatibility rules (a fail-safe change), and is
staged separately. What this type does is make the evaluator complete, so that
step is a wiring change rather than a semantics change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple


@dataclass(frozen=True)
class VNextAuthorizationRequest:
    """A request to authorize a prepared action, with every dimension carried."""

    action_type: str
    parameters: Mapping[str, str] = field(default_factory=dict)
    principal: str = ""
    authority: str = ""
    resource: str = ""
    policy_context: Tuple[str, ...] = ()
    risk_context: Mapping[str, str] = field(default_factory=dict)
    evidence_refs: Tuple[str, ...] = ()
    decision_refs: Tuple[str, ...] = ()
    tenant: str = ""
    correlation_id: str = ""
    idempotency_key: str = ""
    authorization_expired: bool = False

    @property
    def risk_score(self) -> str:
        """The conventional risk key. Empty string when unsupplied.

        ``risk_context`` is a neutral string mapping; ``score`` is the one key
        the evaluator reads. Any other key is carried but not interpreted, so a
        deployment can attach detail without changing the decision.
        """
        return self.risk_context.get("score", "")


__all__ = ["VNextAuthorizationRequest"]
