"""The concrete ``StrategyPolicyResolver``, backed by the shared Policy Authority.

This is the runtime half of Reasoning Strategy Permission: it turns the Agentic
Proposer's opaque ``strategy_policy_ref`` into one exact policy version, resolves
that version through the authority, and answers with the ratified
``StrategyPolicyResponse`` — or raises.

How a reference becomes a coordinate
------------------------------------
Through an **injected, immutable, defensively copied mapping** keyed by
``(tenant_id, strategy_policy_ref)`` to a complete ``PolicyCoordinate``. The
reachable set is deployment trust configuration; the reference **selects among
pre-registered coordinates and can mint none**. An unknown key fails closed: no
fallback, no prefix match, no newest-version rule. Because a stored coordinate
carries its content digest, a new permitted set requires a new configured entry
rather than a silent re-point — a floating reference is unrepresentable.

That alone would leave the reference-to-policy binding as unsigned deployment
state, so it is not alone: the resolved artifact carries its own
``strategy_policy_ref``, inside the digest the authority signed, and this
resolver requires **exact equality** with the request's reference. The caller's
value never becomes authoritative; it must match a value the issuing authority
signed. Configuration locates the policy; the authority states which reference it
answers to.

Tenant handling, and why it is not vacuous
------------------------------------------
``expected_reference_tenant_id`` is derived from the **request**, never read off
the coordinate. The authority compares ``coordinate.tenant_id`` against it, so
passing the coordinate's own value would make that comparison vacuous for every
coordinate. This resolver passes the request's tenant for a ``TENANT``-scope
coordinate and the canonical global tenant component for a ``GLOBAL`` one — in
both branches a value the coordinate did not supply. It also pre-checks scope and
tenant agreement itself and fails closed on disagreement, so the two checks are
redundant rather than co-dependent.

``expected_reference_tenant_id`` checks the reference's declared tenant identity,
never caller entitlement. **This resolver performs no caller authorization and
claims none.**

What it never does
------------------
* **``case_ref`` selects nothing.** It is correlation and audit context. It is
  not in the mapping key, not in any coordinate, and the authority accepts no
  such parameter. Letting it select would be per-invocation authorization, which
  is not ratified — permission is role-level.
* **No clock.** ``as_of`` is the caller's, passed through verbatim, so the policy
  consulted is the one in force at the instant the advisory asserts.
* **No historical answers.** Historical resolution stays at deny-always: an
  answer about the past is never accepted here.
* **No approval shortcut.** An approval verifier is always supplied, so an
  approval withdrawn after issuance invalidates resolution. Without one, the
  issuance signature would prove only that approval held at issuance time.
* **No degraded answer.** A response is produced only when the authority
  answered with a resolution; every other outcome raises.
* **No ``verified`` boolean.** A boolean a resolver sets is the resolver
  asserting its own trustworthiness. The evidence is structural instead: a
  response exists at all only on a successful resolution.

What a response does not prove
------------------------------
That the policy is wise, correct, lawful or commercially sound; that the issuing
authority is the one a reader expects, rather than the one the configured trust
anchors name; that any producer executed any declared procedure; that private
reasoning matched a declaration; or that this resolver is honest. The reference
echo is a request/response **correlation** check: a resolver that wishes to
mislead echoes back what it was handed while resolving something else, and
nothing in this boundary can detect that.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping, Tuple

from ugence_agentic_proposer import (
    ReasoningStrategy,
    StrategyPolicyRequest,
    StrategyPolicyResponse,
)
from ugence_agentic_proposer_strategy_permission_policy import (
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    StrategyPermissionPolicy,
)
from ugence_policy_authority.api import (
    GLOBAL_TENANT,
    AdapterRegistry,
    ApprovalVerifier,
    HistoricalResolutionRule,
    PolicyCoordinate,
    PolicyResolutionStatus,
    resolve_policy,
)

from .errors import (
    StrategyPolicyArtifactError,
    StrategyPolicyReferenceBindingError,
    StrategyPolicyTenantScopeError,
    StrategyPolicyUnresolvedError,
    StrategyPolicyVocabularyError,
    UnknownStrategyPolicyReferenceError,
)

__all__ = ["PolicyAuthorityStrategyPolicyResolver"]

#: The historical-resolution posture, stated once as a constant so that relaxing
#: it is a visible edit rather than an omitted keyword.
HISTORICAL_RESOLUTION = HistoricalResolutionRule.DENY_ALWAYS


class PolicyAuthorityStrategyPolicyResolver:
    """Resolves a strategy policy through the shared authority, or raises.

    Satisfies the Agentic Proposer's ``StrategyPolicyResolver`` protocol
    structurally; it deliberately does not inherit from it, because the protocol
    is the proposer's and a runtime subclass relation would add nothing.
    """

    __slots__ = (
        "_reference_map",
        "_registry",
        "_signature_verifier",
        "_adapters",
        "_approval_verifier",
    )

    def __init__(
        self,
        *,
        reference_map: Mapping[Tuple[str, str], PolicyCoordinate],
        registry: Any,
        signature_verifier: Any,
        adapters: AdapterRegistry,
        approval_verifier: ApprovalVerifier,
    ) -> None:
        if not isinstance(adapters, AdapterRegistry):
            raise TypeError("adapters must be an AdapterRegistry")
        if approval_verifier is None or not hasattr(approval_verifier, "verify_approval"):
            # Required, never optional: without it an approval withdrawn after
            # issuance would still resolve, because the issuance signature proves
            # only that the approval was bound at issuance time.
            raise TypeError(
                "approval_verifier is required and must implement verify_approval"
            )
        for name, dependency in (
            ("registry", registry),
            ("signature_verifier", signature_verifier),
        ):
            if dependency is None:
                raise TypeError(f"{name} is required")

        object.__setattr__(self, "_reference_map", _copy_reference_map(reference_map))
        object.__setattr__(self, "_registry", registry)
        object.__setattr__(self, "_signature_verifier", signature_verifier)
        object.__setattr__(self, "_adapters", adapters)
        object.__setattr__(self, "_approval_verifier", approval_verifier)

    def __setattr__(self, name: str, value: object) -> None:
        # The configured trust state is not rebindable after construction:
        # replacing the reference map wholesale would be exactly the coordinate
        # injection the defensive copy and the read-only view exist to prevent.
        raise AttributeError(
            f"PolicyAuthorityStrategyPolicyResolver is immutable; cannot set {name!r}"
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"PolicyAuthorityStrategyPolicyResolver is immutable; cannot delete {name!r}"
        )

    @property
    def reference_map(self) -> Mapping[Tuple[str, str], PolicyCoordinate]:
        """A read-only view of the configured mapping.

        Mutating the mapping passed in, or the view returned here, cannot change
        what this resolver can reach.
        """

        return self._reference_map

    # ------------------------------------------------------------------
    # The protocol
    # ------------------------------------------------------------------
    def resolve(self, *, request: StrategyPolicyRequest) -> StrategyPolicyResponse:
        if type(request) is not StrategyPolicyRequest:
            raise TypeError("resolve(request) must be a StrategyPolicyRequest")

        # -- reference -> coordinate --------------------------------------
        # case_ref is deliberately absent from this key. It is correlation and
        # audit context; letting it select would be per-invocation authorization.
        coordinate = self._reference_map.get(
            (request.tenant_id, request.strategy_policy_ref)
        )
        if coordinate is None:
            raise UnknownStrategyPolicyReferenceError(
                "no policy coordinate is configured for this tenant and reference; "
                "the mapping fails closed and mints nothing"
            )

        expected_reference_tenant_id = self._expected_tenant(coordinate, request)

        resolution = resolve_policy(
            reference=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            as_of=request.as_of,
            registry=self._registry,
            signature_verifier=self._signature_verifier,
            adapters=self._adapters,
            approval_verifier=self._approval_verifier,
            historical_resolution=HISTORICAL_RESOLUTION,
        )

        # -- the only accepted outcome ------------------------------------
        # Every other status raises, which covers the authority's whole reason
        # enumeration by construction rather than by enumerating it here.
        if resolution.status is not PolicyResolutionStatus.RESOLVED:
            raise StrategyPolicyUnresolvedError(
                "the policy authority did not return a policy version; the "
                "machine-readable cause is carried on the reason attribute",
                reason=resolution.reason,
            )

        policy = resolution.policy
        if type(policy) is not StrategyPermissionPolicy:
            raise StrategyPolicyArtifactError(
                "the artifact returned under this coordinate is not exactly a "
                "StrategyPermissionPolicy"
            )

        # -- the signed reference binding ---------------------------------
        if policy.strategy_policy_ref != request.strategy_policy_ref:
            raise StrategyPolicyReferenceBindingError(
                "the reference this policy is signed as answering to is not the "
                "reference this request carried"
            )

        permitted = self._permitted(policy)

        return StrategyPolicyResponse(
            strategy_policy_id=policy.metadata.policy_id,
            strategy_policy_version=policy.metadata.version,
            permitted_strategies=permitted,
            # The request's own value, echoed verbatim - and, by the check above,
            # equal to a value the issuing authority signed.
            strategy_policy_ref=request.strategy_policy_ref,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _expected_tenant(
        coordinate: PolicyCoordinate, request: StrategyPolicyRequest
    ) -> str:
        """The tenant identity to hand the authority, derived from the request."""

        if coordinate.scope == POLICY_SCOPE_GLOBAL:
            if coordinate.tenant_id != GLOBAL_TENANT:
                raise StrategyPolicyTenantScopeError(
                    "a global-scope coordinate must carry the canonical empty tenant "
                    "component"
                )
            return GLOBAL_TENANT
        if coordinate.scope == POLICY_SCOPE_TENANT:
            if not coordinate.tenant_id or coordinate.tenant_id != request.tenant_id:
                raise StrategyPolicyTenantScopeError(
                    "the configured coordinate names a different tenant than this "
                    "request"
                )
            return request.tenant_id
        raise StrategyPolicyTenantScopeError(
            "the configured coordinate carries a scope this family does not admit"
        )

    @staticmethod
    def _permitted(policy: StrategyPermissionPolicy) -> Tuple[ReasoningStrategy, ...]:
        """Map the artifact's tokens onto enum members, order preserved."""

        try:
            return tuple(ReasoningStrategy(value) for value in policy.permitted_strategies)
        except ValueError as exc:
            raise StrategyPolicyVocabularyError(
                "the policy carries a strategy token that is not a member of the "
                "vocabulary this boundary admits"
            ) from exc


def _copy_reference_map(
    reference_map: Mapping[Tuple[str, str], PolicyCoordinate],
) -> Mapping[Tuple[str, str], PolicyCoordinate]:
    """Validate, copy, and expose read-only.

    Every key is exactly a ``(tenant_id, strategy_policy_ref)`` pair of strings
    and every value exactly a ``PolicyCoordinate``. A malformed entry is refused
    at construction rather than at the first request that happens to reach it.
    """

    if not isinstance(reference_map, Mapping):
        raise TypeError("reference_map must be a mapping")
    collected = {}
    for key, coordinate in reference_map.items():
        if (
            type(key) is not tuple
            or len(key) != 2
            or type(key[0]) is not str
            or type(key[1]) is not str
        ):
            raise TypeError(
                "every reference_map key must be a (tenant_id, strategy_policy_ref) "
                "pair of strings"
            )
        if type(coordinate) is not PolicyCoordinate:
            raise TypeError(
                "every reference_map value must be exactly a PolicyCoordinate; a "
                "partial identity cannot name one exact policy version"
            )
        collected[key] = coordinate
    return MappingProxyType(collected)
