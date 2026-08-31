"""The one composition helper: wire a resolver with the family guarded-registered.

A deployment that configured everything else correctly and forgot to register the
agent-constitution adapter would get a fail-closed refusal on every request, with
the authority reporting that no adapter claims the artifact. That is the right
failure, and it is also an avoidable one — so this helper takes the adapter
registration out of a composition root's hands and puts it in the same call that
builds the resolver.

Registration here goes through the family package's own
``register_agent_constitution_policy_family`` /
``assert_agent_constitution_family_registration``, so **every composition path
runs the `ACC-S1-Q3` registration-time family-collision guard** over the
assembled registry: a registry in which this family does not answer exactly once
fails to compose, before any request is served.

It is a **convenience only**, and it grants nothing. Trust anchors, the registry,
and above all the approval verifier remain the composition root's to choose; this
helper supplies none of them and no default for any of them. In particular there
is no default approval verifier here: an unconfigured deployment must fail to
construct, never quietly issue or resolve against nobody's approval.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from ugence_agent_constitution_policy import (
    AGENT_CONSTITUTION_ADAPTER_ID,
    assert_agent_constitution_family_registration,
    register_agent_constitution_policy_family,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    ApprovalVerifier,
    PolicyCoordinate,
)

from .resolution import PolicyAuthorityConstitutionResolver

__all__ = ["build_constitution_resolver", "with_agent_constitution_adapter"]


def with_agent_constitution_adapter(
    adapters: Optional[AdapterRegistry] = None,
) -> AdapterRegistry:
    """Return a registry carrying this family's adapter, collision-guarded.

    Idempotent on the adapter id — a registry already carrying it is returned
    unchanged — but never guard-skipping: whichever branch runs, the assembled
    registry has passed the `ACC-S1-Q3` assertion before it is returned.
    """

    if adapters is None:
        return register_agent_constitution_policy_family(AdapterRegistry())
    if not isinstance(adapters, AdapterRegistry):
        raise TypeError("adapters must be an AdapterRegistry or None")
    if any(
        existing.adapter_id == AGENT_CONSTITUTION_ADAPTER_ID
        for existing in adapters.adapters
    ):
        assert_agent_constitution_family_registration(adapters)
        return adapters
    return register_agent_constitution_policy_family(adapters)


def build_constitution_resolver(
    *,
    reference_map: Mapping[Tuple[str, str], PolicyCoordinate],
    registry: Any,
    signature_verifier: Any,
    approval_verifier: ApprovalVerifier,
    adapters: Optional[AdapterRegistry] = None,
) -> PolicyAuthorityConstitutionResolver:
    """Build a resolver whose adapter registry certainly carries this family,
    asserted collision-free by the ruled guard."""

    return PolicyAuthorityConstitutionResolver(
        reference_map=reference_map,
        registry=registry,
        signature_verifier=signature_verifier,
        adapters=with_agent_constitution_adapter(adapters),
        approval_verifier=approval_verifier,
    )
