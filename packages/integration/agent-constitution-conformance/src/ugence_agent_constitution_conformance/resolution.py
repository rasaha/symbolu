"""The concrete constitution resolver, backed by the shared Policy Authority (§5.2).

On the ratified `S2B-PF-D`/`S2B-PF-E` pattern, restated once for this family.

How a role reference becomes a coordinate
-----------------------------------------
Through an **injected, immutable, defensively copied mapping** keyed by
``(tenant_id, role_contract_ref)`` to a complete ``PolicyCoordinate``. The
reachable set is deployment trust configuration; the reference **selects among
pre-registered coordinates and can mint none**. An unknown key fails closed: no
fallback, no prefix match, no newest-version rule. Because a stored coordinate
carries its content digest, a new bound requires a new configured entry rather
than a silent re-point — a floating reference is unrepresentable. This mapping is
also where the `ACC-S1-Q4` rule is enforceable today: keyed by role, a deployment
cannot *represent* two active constitutions for one role at one ``as_of``; the
signed ``governed_role_refs`` membership post-check then binds the one selected
constitution to the role on the signed side. Population of the mapping remains
ungoverned — a disclosed, carried gap.

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
* **No clock.** ``as_of`` is the caller's, passed through verbatim, so the
  constitution consulted is the one in force at the instant the caller asserts.
* **No historical answers.** Historical resolution stays at deny-always: an
  answer about the past is never accepted here.
* **No approval shortcut.** An approval verifier is always supplied, so an
  approval withdrawn after issuance invalidates resolution. Without one, the
  issuance signature would prove only that approval held at issuance time.
* **No degraded answer.** A constitution is returned only when the authority
  answered with a resolution; every other outcome raises.
* **No ``verified`` boolean.** A boolean a resolver sets is the resolver
  asserting its own trustworthiness. The evidence is structural instead: a
  returned artifact exists at all only on a successful resolution.
* **No lifecycle authority and no disposition.** Nothing here writes any agent
  or role state, and nothing maps a failure to an operational outcome.

The four post-checks (§5.2), each with its own error class
----------------------------------------------------------
1. the returned artifact's **exact runtime type**;
2. the requested role reference is a member of the signed
   ``governed_role_refs`` — the signed-side role binding (`ACC-S1-Q4`);
3. every closed-bound element is a member of its source enum — re-checked from
   the resolved artifact, because a forged body should fail here even if it
   somehow survived the digest;
4. where the caller presents a constitution reference (the `OD-C1=B` amendment
   round's consumer, optional until that round lands), **exact equality** with
   the signed ``agent_constitution_ref``: a caller-supplied value never becomes
   authoritative, it must match a value the issuing authority signed.

What a returned constitution does not prove
-------------------------------------------
That its bounds are wise, correct or lawful; that any presented role facts
conform (that is the verifier's separate question); that the issuing authority
is the one a reader expects, rather than the one the configured trust anchors
name; or that this resolver is honest.
"""

from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Tuple

from ugence_agent_constitution_policy import (
    ADMITTED_CANDIDATE_DISPOSITION_TOKENS,
    ADMITTED_REVIEW_ACTION_TOKENS,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    AgentConstitutionPolicy,
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
    ConstitutionArtifactTypeError,
    ConstitutionFactsError,
    ConstitutionReferenceBindingError,
    ConstitutionRoleBindingError,
    ConstitutionTenantScopeError,
    ConstitutionUnresolvedError,
    ConstitutionVocabularyError,
    UnknownConstitutionReferenceError,
)

__all__ = ["PolicyAuthorityConstitutionResolver"]

#: The historical-resolution posture, stated once as a constant so that relaxing
#: it is a visible edit rather than an omitted keyword.
HISTORICAL_RESOLUTION = HistoricalResolutionRule.DENY_ALWAYS


class PolicyAuthorityConstitutionResolver:
    """Resolves the constitution governing one role through the shared authority,
    or raises. Returns the exact resolved ``AgentConstitutionPolicy`` artifact —
    no response envelope is ratified for this boundary, and none is invented."""

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
            f"PolicyAuthorityConstitutionResolver is immutable; cannot set {name!r}"
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"PolicyAuthorityConstitutionResolver is immutable; cannot delete {name!r}"
        )

    @property
    def reference_map(self) -> Mapping[Tuple[str, str], PolicyCoordinate]:
        """A read-only view of the configured mapping.

        Mutating the mapping passed in, or the view returned here, cannot change
        what this resolver can reach.
        """

        return self._reference_map

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def resolve(
        self,
        *,
        tenant_id: str,
        role_contract_ref: str,
        as_of: datetime,
        presented_constitution_ref: str = "",
    ) -> AgentConstitutionPolicy:
        """The one resolution entry point. Returns the artifact, or raises.

        ``presented_constitution_ref`` is optional until the `OD-C1=B` amendment
        round gives the role surface a reference field; when non-empty it must
        equal the signed ``agent_constitution_ref`` exactly.
        """

        if type(tenant_id) is not str:
            raise ConstitutionFactsError("tenant_id must be exactly a str")
        if type(role_contract_ref) is not str or not role_contract_ref.strip():
            raise ConstitutionFactsError(
                "role_contract_ref must be a non-empty str"
            )
        if type(presented_constitution_ref) is not str:
            raise ConstitutionFactsError(
                "presented_constitution_ref must be exactly a str"
            )
        if not isinstance(as_of, datetime) or as_of.tzinfo is None or (
            as_of.tzinfo.utcoffset(as_of) is None
        ):
            raise ConstitutionFactsError(
                "as_of must be a timezone-aware datetime; a naive datetime is "
                "never assumed to be UTC"
            )

        # -- role reference -> coordinate ---------------------------------
        coordinate = self._reference_map.get((tenant_id, role_contract_ref))
        if coordinate is None:
            raise UnknownConstitutionReferenceError(
                "no constitution coordinate is configured for this tenant and "
                "role reference; the mapping fails closed and mints nothing"
            )

        expected_reference_tenant_id = self._expected_tenant(coordinate, tenant_id)

        resolution = resolve_policy(
            reference=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            as_of=as_of,
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
            raise ConstitutionUnresolvedError(
                "the policy authority did not return a policy version; the "
                "machine-readable cause is carried on the reason attribute",
                reason=resolution.reason,
            )

        policy = resolution.policy
        # Post-check 1: exact runtime type.
        if type(policy) is not AgentConstitutionPolicy:
            raise ConstitutionArtifactTypeError(
                "the artifact returned under this coordinate is not exactly an "
                "AgentConstitutionPolicy"
            )

        # Post-check 2: the signed-side role binding (`ACC-S1-Q4`).
        if role_contract_ref not in policy.governed_role_refs:
            raise ConstitutionRoleBindingError(
                "the resolved constitution's signed role list does not contain "
                "the requested role reference"
            )

        # Post-check 3: every closed-bound element re-checked against its source
        # enum, from the resolved artifact itself.
        self._check_bound_vocabulary(policy)

        # Post-check 4: the signed reference binding, where one is presented.
        if (
            presented_constitution_ref
            and policy.agent_constitution_ref != presented_constitution_ref
        ):
            raise ConstitutionReferenceBindingError(
                "the reference this constitution is signed as named by is not "
                "the reference presented with this request"
            )

        return policy

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _expected_tenant(coordinate: PolicyCoordinate, tenant_id: str) -> str:
        """The tenant identity to hand the authority, derived from the request."""

        if coordinate.scope == POLICY_SCOPE_GLOBAL:
            if coordinate.tenant_id != GLOBAL_TENANT:
                raise ConstitutionTenantScopeError(
                    "a global-scope coordinate must carry the canonical empty "
                    "tenant component"
                )
            return GLOBAL_TENANT
        if coordinate.scope == POLICY_SCOPE_TENANT:
            if not coordinate.tenant_id or coordinate.tenant_id != tenant_id:
                raise ConstitutionTenantScopeError(
                    "the configured coordinate names a different tenant than "
                    "this request"
                )
            return tenant_id
        raise ConstitutionTenantScopeError(
            "the configured coordinate carries a scope this family does not admit"
        )

    @staticmethod
    def _check_bound_vocabulary(policy: AgentConstitutionPolicy) -> None:
        """Every closed-bound element is a member of its source enum.

        A lawful artifact cannot violate this — the family refuses to construct
        one — so a hit here means the body under this coordinate is forged, and
        the refusal must not depend on the family's own constructor having run.
        """

        for values, admitted in (
            (
                policy.permitted_candidate_dispositions_bound,
                ADMITTED_CANDIDATE_DISPOSITION_TOKENS,
            ),
            (policy.permitted_review_actions_bound, ADMITTED_REVIEW_ACTION_TOKENS),
        ):
            for token in values:
                if token not in admitted:
                    raise ConstitutionVocabularyError(
                        "the constitution carries a bound token that is not a "
                        "member of the vocabulary this boundary admits"
                    )


def _copy_reference_map(
    reference_map: Mapping[Tuple[str, str], PolicyCoordinate],
) -> Mapping[Tuple[str, str], PolicyCoordinate]:
    """Validate, copy, and expose read-only.

    Every key is exactly a ``(tenant_id, role_contract_ref)`` pair of strings
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
                "every reference_map key must be a (tenant_id, role_contract_ref) "
                "pair of strings"
            )
        if type(coordinate) is not PolicyCoordinate:
            raise TypeError(
                "every reference_map value must be exactly a PolicyCoordinate; a "
                "partial identity cannot name one exact policy version"
            )
        collected[key] = coordinate
    return MappingProxyType(collected)
