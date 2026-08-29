"""The one composition helper: wire a resolver with the family adapter registered.

A deployment that configured everything else correctly and forgot to register the
strategy-permission adapter would get a fail-closed refusal on every request, with
the authority reporting that no adapter claims the artifact. That is the right
failure, and it is also an avoidable one — so this helper takes the adapter
registration out of a composition root's hands and puts it in the same call that
builds the resolver.

It is a **convenience only**, and it grants nothing. Trust anchors, the registry,
and above all the approval verifier remain the composition root's to choose; this
helper supplies none of them and no default for any of them. In particular there
is no default approval verifier here: an unconfigured deployment must fail to
construct, never quietly issue or resolve against nobody's approval.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from ugence_agentic_proposer_strategy_permission_policy import (
    StrategyPermissionPolicyFamilyAdapter,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    ApprovalVerifier,
    PolicyCoordinate,
)

from .resolver import PolicyAuthorityStrategyPolicyResolver

__all__ = ["build_strategy_policy_resolver", "with_strategy_permission_adapter"]


def with_strategy_permission_adapter(
    adapters: Optional[AdapterRegistry] = None,
) -> AdapterRegistry:
    """Return a registry carrying this family's adapter alongside whatever it had.

    Idempotent: a registry that already carries the adapter is returned unchanged,
    because the authority refuses a registry holding two adapters with one id.
    """

    if adapters is None:
        return AdapterRegistry((StrategyPermissionPolicyFamilyAdapter(),))
    if not isinstance(adapters, AdapterRegistry):
        raise TypeError("adapters must be an AdapterRegistry or None")
    adapter = StrategyPermissionPolicyFamilyAdapter()
    if any(existing.adapter_id == adapter.adapter_id for existing in adapters.adapters):
        return adapters
    return adapters.with_adapter(adapter)


def build_strategy_policy_resolver(
    *,
    reference_map: Mapping[Tuple[str, str], PolicyCoordinate],
    registry: Any,
    signature_verifier: Any,
    approval_verifier: ApprovalVerifier,
    adapters: Optional[AdapterRegistry] = None,
) -> PolicyAuthorityStrategyPolicyResolver:
    """Build a resolver whose adapter registry certainly carries this family."""

    return PolicyAuthorityStrategyPolicyResolver(
        reference_map=reference_map,
        registry=registry,
        signature_verifier=signature_verifier,
        adapters=with_strategy_permission_adapter(adapters),
        approval_verifier=approval_verifier,
    )
